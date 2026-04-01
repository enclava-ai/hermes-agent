"""Tests for Tinfoil routing in auxiliary_client — fail-closed on vision fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest


class TestTryTinfoil:
    def test_returns_client_and_model_when_key_set(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        mock_client = MagicMock()
        with patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
            from agent.auxiliary_client import _try_tinfoil
            client, model = _try_tinfoil()
        assert client is not None
        assert isinstance(model, str) and model

    def test_returns_none_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("TINFOIL_API_KEY", raising=False)
        monkeypatch.delenv("TINFOIL_TOKEN", raising=False)
        from agent.auxiliary_client import _try_tinfoil
        client, model = _try_tinfoil()
        assert client is None
        assert model is None


class TestResolveForcedProviderTinfoil:
    def test_forced_tinfoil_resolves(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        mock_client = MagicMock()
        with patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
            from agent.auxiliary_client import _resolve_forced_provider
            client, model = _resolve_forced_provider("tinfoil")
        assert client is not None

    def test_forced_main_uses_tinfoil_when_configured(self, monkeypatch):
        """When the main provider is Tinfoil, 'main' auxiliary must use Tinfoil too."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        mock_client = MagicMock()
        # Patch load_config at the source so all imports see the patched version
        mock_cfg = {"model": {"provider": "tinfoil", "default": "llama3-3-70b"}}
        with patch("hermes_cli.config.load_config", return_value=mock_cfg), \
             patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
            from agent.auxiliary_client import _resolve_forced_provider
            client, model = _resolve_forced_provider("main")
        assert client is not None

    def test_vision_fails_when_tinfoil_active(self, monkeypatch):
        """Vision auxiliary must not fall back to OpenRouter when Tinfoil is the main provider."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        mock_cfg = {"model": {"provider": "tinfoil", "default": "llama3-3-70b"}}
        with patch("hermes_cli.config.load_config", return_value=mock_cfg):
            from agent.auxiliary_client import resolve_provider_client
            # Vision task for tinfoil should return None (unsupported), not fall to OpenRouter
            client, model = resolve_provider_client("tinfoil", task="vision")
        assert client is None

    def test_explicit_tinfoil_uses_tinfoil_sdk_not_openai(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        mock_client = MagicMock()
        with patch("agent.tinfoil_adapter.build_client", return_value=mock_client) as mock_build, \
             patch("agent.auxiliary_client.OpenAI") as mock_openai:
            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client("tinfoil", model="llama3-3-70b")

        assert client is mock_client
        assert model == "llama3-3-70b"
        mock_build.assert_called_once_with("tf-test-key")
        mock_openai.assert_not_called()

    def test_auto_mode_never_selects_tinfoil(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        fake_pconfig = SimpleNamespace(
            auth_type="api_key",
            name="Tinfoil",
            inference_base_url="https://inference.tinfoil.sh/v1",
        )
        with patch(
            "hermes_cli.auth.PROVIDER_REGISTRY",
            {"tinfoil": fake_pconfig},
        ), patch(
            "hermes_cli.auth.resolve_api_key_provider_credentials",
            return_value={"api_key": "tf-test-key"},
        ), patch("agent.auxiliary_client.OpenAI") as mock_openai:
            from agent.auxiliary_client import _resolve_api_key_provider

            client, model = _resolve_api_key_provider()

        assert client is None
        assert model is None
        mock_openai.assert_not_called()
