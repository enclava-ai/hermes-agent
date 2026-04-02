"""Tests for dashboard log streaming — BroadcastLogHandler and helpers."""
import asyncio
import json
import logging

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
