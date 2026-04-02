"""
Dashboard log streaming — real-time SSE log viewer.

Provides:
- BroadcastLogHandler: logging.Handler that fans out records to SSE subscribers
- parse_log_line(): parse plain-text log lines into structured JSON
- tail_log_file(): efficient reverse-seek file tail
- handle_logs_tab(): serves the Logs tab partial template
- handle_logs_stream(): SSE endpoint for log streaming
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional

from agent.redact import RedactingFormatter

logger = logging.getLogger(__name__)

# Regex to parse the standard log format: "2026-04-02 14:03:22,451 INFO gateway.run: message"
_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+"
    r"(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+"
    r"([\w.]+):\s+"
    r"(.*)$"
)

_DEFAULT_MAX_QUEUE = 500


class BroadcastLogHandler(logging.Handler):
    """Logging handler that broadcasts formatted records to SSE subscribers.

    Each subscriber gets its own asyncio.Queue. The handler owns a
    RedactingFormatter instance and applies it to every record before
    enqueueing. Thread-safe via loop.call_soon_threadsafe().
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, max_queue_size: int = _DEFAULT_MAX_QUEUE):
        super().__init__()
        self._loop = loop
        self._max_queue_size = max_queue_size
        self._subscribers: set[asyncio.Queue] = set()
        self._formatter = RedactingFormatter("%(message)s")

    def subscribe(self) -> asyncio.Queue:
        """Create and return a new subscriber queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(queue)

    def emit(self, record: logging.LogRecord) -> None:
        """Format the record and enqueue to all subscribers."""
        if not self._subscribers:
            return
        try:
            # Use RedactingFormatter to mask secrets in the message
            redacted_msg = self._formatter.format(record)
            event = json.dumps({
                "ts": self.format_time(record),
                "level": record.levelname,
                "logger": record.name,
                "msg": redacted_msg,
            })
            self._loop.call_soon_threadsafe(self._broadcast, event)
        except Exception:
            self.handleError(record)

    def _broadcast(self, event: str) -> None:
        """Distribute event to all subscriber queues (runs on event loop thread)."""
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # should not happen after get_nowait, but be safe

    @staticmethod
    def format_time(record: logging.LogRecord) -> str:
        """Format LogRecord timestamp to match the file log format."""
        import time
        ct = time.localtime(record.created)
        t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
        return f"{t},{int(record.msecs):03d}"


def parse_log_line(line: str) -> dict:
    """Parse a plain-text log line into the standard event dict.

    Returns a dict with keys: ts, level, logger, msg (all strings).
    Malformed lines get fallback values.
    """
    line = line.rstrip("\r\n")
    match = _LOG_LINE_RE.match(line)
    if match:
        return {
            "ts": match.group(1),
            "level": match.group(2),
            "logger": match.group(3),
            "msg": match.group(4),
        }
    return {"ts": "", "level": "INFO", "logger": "", "msg": line}


def tail_log_file(path: Path, num_lines: int = 1000) -> list[str]:
    """Read the last num_lines lines from a log file using reverse-seek.

    Returns a list of raw lines (with newlines stripped).
    Returns empty list if file is missing, empty, or unreadable.
    """
    try:
        if not path.exists() or path.stat().st_size == 0:
            return []
    except OSError:
        return []

    try:
        with open(path, "rb") as f:
            f.seek(0, 2)  # seek to end
            end_pos = f.tell()
            if end_pos == 0:
                return []

            lines_found = []
            block_size = 8192
            remaining = end_pos

            while remaining > 0 and len(lines_found) < num_lines + 1:
                read_size = min(block_size, remaining)
                remaining -= read_size
                f.seek(remaining)
                block = f.read(read_size)
                lines_found = block.split(b"\n") + lines_found[1:]  # merge with existing

            # Filter empty lines and decode
            text_lines = []
            for raw in lines_found:
                raw = raw.rstrip(b"\r")
                if raw:
                    try:
                        text_lines.append(raw.decode("utf-8", errors="replace"))
                    except Exception:
                        text_lines.append(raw.decode("latin-1"))

            # Return the last num_lines
            return text_lines[-num_lines:]
    except OSError:
        return []
