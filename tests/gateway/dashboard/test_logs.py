"""Tests for dashboard log streaming — BroadcastLogHandler and helpers."""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import pytest


class TestBroadcastLogHandler:
    @pytest.mark.asyncio
    async def test_subscribe_receives_events(self):
        """Subscriber queue receives formatted log events."""
        from gateway.dashboard.logs import BroadcastLogHandler

        loop = asyncio.get_event_loop()
        handler = BroadcastLogHandler(loop=loop)
        handler.setLevel(logging.DEBUG)
        queue = handler.subscribe()

        logger = logging.getLogger("test.broadcast")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            logger.info("hello world")
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            parsed = json.loads(event)
            assert parsed["level"] == "INFO"
            assert parsed["logger"] == "test.broadcast"
            assert "hello world" in parsed["msg"]
            assert "ts" in parsed
        finally:
            handler.unsubscribe(queue)
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self):
        """After unsubscribe, handler has no subscribers."""
        from gateway.dashboard.logs import BroadcastLogHandler

        loop = asyncio.get_event_loop()
        handler = BroadcastLogHandler(loop=loop)
        queue = handler.subscribe()
        assert len(handler._subscribers) == 1
        handler.unsubscribe(queue)
        assert len(handler._subscribers) == 0

    @pytest.mark.asyncio
    async def test_backpressure_drops_oldest(self):
        """When queue is full, oldest entry is dropped."""
        from gateway.dashboard.logs import BroadcastLogHandler

        loop = asyncio.get_event_loop()
        handler = BroadcastLogHandler(loop=loop, max_queue_size=2)
        handler.setLevel(logging.DEBUG)
        queue = handler.subscribe()

        logger = logging.getLogger("test.backpressure")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            logger.info("msg1")
            logger.info("msg2")
            logger.info("msg3")
            # Allow call_soon_threadsafe callbacks to execute
            await asyncio.sleep(0.05)

            events = []
            while not queue.empty():
                events.append(json.loads(queue.get_nowait()))
            # Queue size is 2, so msg1 should have been dropped
            assert len(events) == 2
            assert "msg2" in events[0]["msg"]
            assert "msg3" in events[1]["msg"]
        finally:
            handler.unsubscribe(queue)
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_redaction_applied(self):
        """Secrets in log messages are redacted."""
        from gateway.dashboard.logs import BroadcastLogHandler

        loop = asyncio.get_event_loop()
        handler = BroadcastLogHandler(loop=loop)
        handler.setLevel(logging.DEBUG)
        queue = handler.subscribe()

        logger = logging.getLogger("test.redact")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            logger.info("key is sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAA")
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            parsed = json.loads(event)
            assert "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAA" not in parsed["msg"]
            assert "***" in parsed["msg"] or "..." in parsed["msg"]
        finally:
            handler.unsubscribe(queue)
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_payload_schema(self):
        """Every event has exactly ts, level, logger, msg — all strings."""
        from gateway.dashboard.logs import BroadcastLogHandler

        loop = asyncio.get_event_loop()
        handler = BroadcastLogHandler(loop=loop)
        handler.setLevel(logging.DEBUG)
        queue = handler.subscribe()

        logger = logging.getLogger("test.schema")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            logger.warning("check schema")
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            parsed = json.loads(event)
            assert set(parsed.keys()) == {"ts", "level", "logger", "msg"}
            for val in parsed.values():
                assert isinstance(val, str)
        finally:
            handler.unsubscribe(queue)
            logger.removeHandler(handler)


class TestParseLogLine:
    def test_valid_info_line(self):
        from gateway.dashboard.logs import parse_log_line

        line = "2026-04-02 14:03:22,451 INFO gateway.run: Platform telegram started"
        result = parse_log_line(line)
        assert result == {
            "ts": "2026-04-02 14:03:22,451",
            "level": "INFO",
            "logger": "gateway.run",
            "msg": "Platform telegram started",
        }

    def test_valid_warning_line(self):
        from gateway.dashboard.logs import parse_log_line

        line = "2026-04-02 14:03:22,451 WARNING gateway.session: bad JSON"
        result = parse_log_line(line)
        assert result["level"] == "WARNING"
        assert result["msg"] == "bad JSON"

    def test_malformed_line_returns_fallback(self):
        from gateway.dashboard.logs import parse_log_line

        line = "some garbled text without structure"
        result = parse_log_line(line)
        assert result == {
            "ts": "",
            "level": "INFO",
            "logger": "",
            "msg": "some garbled text without structure",
        }

    def test_empty_line(self):
        from gateway.dashboard.logs import parse_log_line

        result = parse_log_line("")
        assert result["msg"] == ""
        assert result["ts"] == ""

    def test_crlf_stripped(self):
        from gateway.dashboard.logs import parse_log_line

        line = "2026-04-02 14:03:22,451 ERROR gateway.run: boom\r\n"
        result = parse_log_line(line)
        assert result["level"] == "ERROR"
        assert result["msg"] == "boom"

    def test_schema_four_string_fields(self):
        from gateway.dashboard.logs import parse_log_line

        result = parse_log_line("anything")
        assert set(result.keys()) == {"ts", "level", "logger", "msg"}
        for val in result.values():
            assert isinstance(val, str)


class TestTailLogFile:
    def test_tail_returns_last_n_lines(self):
        from gateway.dashboard.logs import tail_log_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for i in range(100):
                f.write(f"2026-04-02 10:00:{i:02d},000 INFO test: line {i}\n")
            path = Path(f.name)
        try:
            lines = tail_log_file(path, num_lines=10)
            assert len(lines) == 10
            assert "line 90" in lines[0]
            assert "line 99" in lines[9]
        finally:
            os.unlink(path)

    def test_tail_file_smaller_than_requested(self):
        from gateway.dashboard.logs import tail_log_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2026-04-02 10:00:00,000 INFO test: only line\n")
            path = Path(f.name)
        try:
            lines = tail_log_file(path, num_lines=1000)
            assert len(lines) == 1
            assert "only line" in lines[0]
        finally:
            os.unlink(path)

    def test_tail_missing_file_returns_empty(self):
        from gateway.dashboard.logs import tail_log_file

        lines = tail_log_file(Path("/nonexistent/gateway.log"), num_lines=100)
        assert lines == []

    def test_tail_empty_file_returns_empty(self):
        from gateway.dashboard.logs import tail_log_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            path = Path(f.name)
        try:
            lines = tail_log_file(path, num_lines=100)
            assert lines == []
        finally:
            os.unlink(path)


# --- Task 3: SSE Stream Endpoint tests ---

from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from gateway.dashboard import create_dashboard_app
from gateway.dashboard.auth import make_session_token, SESSION_COOKIE


def _make_app(gateway_runner=None):
    """Build a dashboard test app with injected Fernet key."""
    fernet = Fernet(Fernet.generate_key())
    app = create_dashboard_app(gateway_runner=gateway_runner)
    app.on_startup.clear()

    async def _inject_fernet(inner_app):
        inner_app["fernet"] = fernet

    app.on_startup.append(_inject_fernet)
    return app, fernet


def _auth_cookie(fernet):
    token = make_session_token(fernet)
    return {SESSION_COOKIE: token}


class TestLogsTab:
    @pytest.mark.asyncio
    async def test_logs_tab_requires_auth(self):
        """GET /settings/logs without session redirects to login."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/settings/logs", allow_redirects=False)
            assert resp.status in (302, 303)

    @pytest.mark.asyncio
    async def test_logs_tab_renders(self):
        """GET /settings/logs returns 200 with log container."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            resp = await cli.get("/settings/logs")
            assert resp.status == 200
            body = await resp.text()
            assert "log-container" in body


class TestLogsStream:
    @pytest.mark.asyncio
    async def test_stream_requires_auth(self):
        """GET /logs/stream without session redirects to login."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/logs/stream", allow_redirects=False)
            assert resp.status in (302, 303)

    @pytest.mark.asyncio
    async def test_stream_returns_sse_headers(self):
        """GET /logs/stream has correct SSE headers."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            resp = await cli.get("/logs/stream")
            assert resp.headers["Content-Type"] == "text/event-stream"
            assert resp.headers.get("Cache-Control") == "no-cache"
            assert resp.headers.get("X-Accel-Buffering") == "no"
            resp.close()

    @pytest.mark.asyncio
    async def test_stream_sends_history_from_file(self):
        """Stream endpoint sends history lines from the log file."""
        app, fernet = _make_app()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2026-04-02 10:00:00,000 INFO test.mod: history line\n")
            log_path = Path(f.name)

        try:
            async with TestClient(TestServer(app)) as cli:
                cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
                with patch("gateway.dashboard.logs._get_log_path", return_value=log_path):
                    resp = await cli.get("/logs/stream")
                    # Read the first SSE data line
                    first_line = b""
                    async for chunk in resp.content.iter_any():
                        first_line += chunk
                        if b"\n\n" in first_line:
                            break
                    resp.close()

                    # Parse the first data: line
                    text = first_line.decode()
                    for line in text.split("\n"):
                        if line.startswith("data: "):
                            payload = json.loads(line[6:])
                            assert payload["msg"] == "history line"
                            assert payload["level"] == "INFO"
                            break
        finally:
            os.unlink(log_path)

    @pytest.mark.asyncio
    async def test_stream_handles_missing_log_file(self):
        """Stream starts successfully even when log file doesn't exist."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("gateway.dashboard.logs._get_log_path",
                       return_value=Path("/nonexistent/gateway.log")):
                resp = await cli.get("/logs/stream")
                assert resp.status == 200
                resp.close()


class TestHandlerIdempotency:
    @pytest.mark.asyncio
    async def test_no_duplicate_handlers(self):
        """create_dashboard_app() does not add duplicate BroadcastLogHandlers."""
        from gateway.dashboard.logs import BroadcastLogHandler

        root = logging.getLogger()
        # Count before
        before = sum(1 for h in root.handlers if isinstance(h, BroadcastLogHandler))
        _make_app()
        _make_app()
        after = sum(1 for h in root.handlers if isinstance(h, BroadcastLogHandler))
        # Should add at most 1
        assert after - before <= 1
        # Clean up
        for h in list(root.handlers):
            if isinstance(h, BroadcastLogHandler):
                root.removeHandler(h)
