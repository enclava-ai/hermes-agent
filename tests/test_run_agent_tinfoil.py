"""Tests for Tinfoil mode wiring in AIAgent — fail-closed behavior."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest


def _make_tinfoil_agent():
    """Build an AIAgent configured for tinfoil mode, with mocked adapter."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="ok", role="assistant", tool_calls=None),
            finish_reason="stop",
            index=0,
        )],
        model="llama3-3-70b",
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )
    with patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
        from run_agent import AIAgent
        agent = AIAgent(
            model="llama3-3-70b",
            api_key="tf-key-123",
            base_url="https://inference.tinfoil.sh",
            provider="tinfoil",
            api_mode="tinfoil",
            quiet_mode=True,
        )
    agent._tinfoil_client = mock_client
    return agent, mock_client


class TestTinfoilAgentInit:
    def test_api_mode_is_tinfoil(self):
        agent, _ = _make_tinfoil_agent()
        assert agent.api_mode == "tinfoil"

    def test_openai_client_is_none(self):
        agent, _ = _make_tinfoil_agent()
        # For tinfoil mode, the generic OpenAI client must not be initialized
        assert agent.client is None

    def test_tinfoil_client_is_set(self):
        agent, mock_client = _make_tinfoil_agent()
        assert agent._tinfoil_client is mock_client


class TestTinfoilNonStreamingCall:
    def test_dispatches_to_tinfoil_adapter(self):
        agent, mock_client = _make_tinfoil_agent()
        api_kwargs = {
            "model": "llama3-3-70b",
            "messages": [{"role": "user", "content": "hi"}],
        }
        with patch("agent.tinfoil_adapter.create_chat_completion",
                   return_value=mock_client.chat.completions.create.return_value) as mock_call:
            response = agent._interruptible_api_call(api_kwargs)
        mock_call.assert_called_once_with(mock_client, **api_kwargs)
        assert response.choices[0].message.content == "ok"

    def test_does_not_use_openai_client(self):
        agent, mock_client = _make_tinfoil_agent()
        with patch("agent.tinfoil_adapter.create_chat_completion",
                   return_value=mock_client.chat.completions.create.return_value):
            agent._interruptible_api_call({
                "model": "llama3-3-70b",
                "messages": [],
            })
        # The generic OpenAI client must never be called
        assert agent.client is None


class TestTinfoilStreamingCall:
    def test_streaming_dispatches_to_tinfoil_adapter(self):
        agent, _ = _make_tinfoil_agent()
        chunk1 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="hel", tool_calls=None), finish_reason=None)],
            model="llama3-3-70b",
        )
        chunk2 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="lo", tool_calls=None), finish_reason="stop")],
            model="llama3-3-70b",
        )

        with patch(
            "agent.tinfoil_adapter.stream_chat_completion",
            return_value=iter([chunk1, chunk2]),
        ) as mock_stream:
            response = agent._interruptible_streaming_api_call(
                {"model": "llama3-3-70b", "messages": []}
            )

        mock_stream.assert_called_once()
        assert response.choices[0].message.content == "hello"


class TestTinfoilFailClosed:
    def test_tinfoil_error_does_not_fall_back_to_openrouter(self):
        """An error in tinfoil mode must not silently route to OpenRouter."""
        agent, mock_client = _make_tinfoil_agent()
        with patch("agent.tinfoil_adapter.create_chat_completion",
                   side_effect=Exception("attestation failed")):
            with pytest.raises(Exception, match="attestation failed"):
                agent._interruptible_api_call({
                    "model": "llama3-3-70b",
                    "messages": [],
                })
        # Verify no OpenAI client was created as a fallback
        assert agent.client is None

    def test_provider_fallback_is_disabled_when_tinfoil_active(self):
        agent, _ = _make_tinfoil_agent()
        agent._fallback_chain = [{"provider": "openrouter", "model": "anthropic/claude-sonnet-4"}]
        agent._fallback_index = 0

        assert agent._try_activate_fallback() is False
        assert agent.provider == "tinfoil"
        assert agent.api_mode == "tinfoil"
