"""Tests for agent/tinfoil_adapter.py — all tests mock TinfoilAI."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest


def _make_mock_tinfoil_client(models=None, completion_text="hello"):
    """Build a mock TinfoilAI client that returns plausible responses."""
    client = MagicMock()

    # models.list()
    model_objs = [SimpleNamespace(id=m) for m in (models or ["llama3-3-70b"])]
    client.models.list.return_value = SimpleNamespace(data=model_objs)

    # chat.completions.create() non-streaming
    choice = SimpleNamespace(
        index=0,
        message=SimpleNamespace(content=completion_text, role="assistant", tool_calls=None),
        finish_reason="stop",
    )
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[choice],
        model="llama3-3-70b",
        usage=usage,
    )
    return client


class TestBuildClient:
    def test_returns_tinfoil_ai_instance(self):
        mock_cls = MagicMock()
        with patch("agent.tinfoil_adapter._TinfoilAI", mock_cls):
            from agent.tinfoil_adapter import build_client
            build_client("tf-key-123")
        mock_cls.assert_called_once_with(api_key="tf-key-123")

    def test_raises_import_error_when_sdk_missing(self):
        with patch("agent.tinfoil_adapter._TinfoilAI", None):
            from agent.tinfoil_adapter import build_client
            with pytest.raises(ImportError, match="tinfoil"):
                build_client("tf-key-123")


class TestCreateChatCompletion:
    def test_delegates_to_client(self):
        from agent.tinfoil_adapter import create_chat_completion
        mock_client = _make_mock_tinfoil_client()
        result = create_chat_completion(
            mock_client,
            model="llama3-3-70b",
            messages=[{"role": "user", "content": "hi"}],
        )
        mock_client.chat.completions.create.assert_called_once_with(
            model="llama3-3-70b",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result.choices[0].message.content == "hello"

    def test_passes_through_kwargs(self):
        from agent.tinfoil_adapter import create_chat_completion
        mock_client = _make_mock_tinfoil_client()
        create_chat_completion(
            mock_client,
            model="llama3-3-70b",
            messages=[],
            temperature=0.7,
            max_tokens=512,
        )
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 512


class TestStreamChatCompletion:
    def test_yields_chunks_from_stream(self):
        from agent.tinfoil_adapter import stream_chat_completion
        mock_client = MagicMock()

        chunk1 = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hel"), finish_reason=None)])
        chunk2 = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"), finish_reason="stop")])
        mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])

        chunks = list(stream_chat_completion(
            mock_client,
            model="llama3-3-70b",
            messages=[{"role": "user", "content": "hi"}],
        ))
        assert len(chunks) == 2
        assert chunks[0].choices[0].delta.content == "hel"
        assert chunks[1].choices[0].delta.content == "lo"

    def test_sets_stream_true(self):
        from agent.tinfoil_adapter import stream_chat_completion
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([])
        list(stream_chat_completion(mock_client, model="m", messages=[]))
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs.get("stream") is True


class TestListModels:
    def test_returns_model_ids(self):
        from agent.tinfoil_adapter import list_models
        mock_cls = MagicMock(return_value=_make_mock_tinfoil_client(models=["llama3-3-70b", "mistral-7b"]))
        with patch("agent.tinfoil_adapter._TinfoilAI", mock_cls):
            result = list_models("tf-key-123")
        assert result == ["llama3-3-70b", "mistral-7b"]

    def test_returns_empty_list_on_error(self):
        from agent.tinfoil_adapter import list_models
        mock_cls = MagicMock(side_effect=Exception("network error"))
        with patch("agent.tinfoil_adapter._TinfoilAI", mock_cls):
            result = list_models("tf-key-123")
        assert result == []
