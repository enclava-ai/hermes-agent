"""Tests for Tinfoil provider registration and runtime resolution."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from hermes_cli.auth import PROVIDER_REGISTRY, ProviderConfig


class TestTinfoilRegistry:
    def test_tinfoil_in_registry(self):
        assert "tinfoil" in PROVIDER_REGISTRY

    def test_tinfoil_is_api_key_provider(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert cfg.auth_type == "api_key"

    def test_tinfoil_has_api_key_env_vars(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert "TINFOIL_API_KEY" in cfg.api_key_env_vars
        assert "TINFOIL_TOKEN" in cfg.api_key_env_vars

    def test_tinfoil_has_inference_base_url(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert cfg.inference_base_url == "https://inference.tinfoil.sh"

    def test_tinfoil_config_is_provider_config_instance(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert isinstance(cfg, ProviderConfig)


class TestTinfoilRuntimeResolution:
    def test_resolves_api_mode_tinfoil(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["api_mode"] == "tinfoil"

    def test_resolves_provider_name(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["provider"] == "tinfoil"

    def test_resolves_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["api_key"] == "tf-test-key"

    def test_resolves_api_key_from_fallback_env(self, monkeypatch):
        monkeypatch.delenv("TINFOIL_API_KEY", raising=False)
        monkeypatch.setenv("TINFOIL_TOKEN", "tf-token-fallback")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["api_key"] == "tf-token-fallback"

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("TINFOIL_API_KEY", raising=False)
        monkeypatch.delenv("TINFOIL_TOKEN", raising=False)
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from hermes_cli.auth import AuthError
        with pytest.raises(AuthError):
            resolve_runtime_provider(requested="tinfoil")

    def test_tinfoil_not_in_auto_fallback(self, monkeypatch):
        """Tinfoil should never be selected via 'auto' provider."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="auto")
        assert result.get("provider") != "tinfoil"

    def test_resolves_base_url(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["base_url"] == "https://inference.tinfoil.sh"


class TestTinfoilModelCatalog:
    def test_provider_models_has_tinfoil_key(self):
        from hermes_cli.models import _PROVIDER_MODELS
        assert "tinfoil" in _PROVIDER_MODELS

    def test_setup_default_models_has_tinfoil_fallback(self):
        from hermes_cli.setup import _DEFAULT_PROVIDER_MODELS
        assert "tinfoil" in _DEFAULT_PROVIDER_MODELS
        assert len(_DEFAULT_PROVIDER_MODELS["tinfoil"]) > 0

    def test_tinfoil_model_selection_uses_list_models(self, monkeypatch):
        """Setup must call list_models (not fetch_api_models) for tinfoil."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        called_with = {}

        def _fake_list_models(api_key):
            called_with["api_key"] = api_key
            return ["llama3-3-70b", "mistral-7b-instruct"]

        import hermes_cli.setup as setup_mod
        monkeypatch.setattr(
            "hermes_cli.setup._tinfoil_list_models",
            _fake_list_models,
            raising=False,
        )

        choices = []
        def _fake_prompt_choice(question, options, default=0):
            choices.extend(options)
            return len(options) - 1  # "Keep current"

        def _fake_prompt_fn(q):
            return ""

        from hermes_cli.config import load_config
        cfg = load_config()
        setup_mod._setup_provider_model_selection(
            cfg, "tinfoil", "llama3-3-70b",
            _fake_prompt_choice, _fake_prompt_fn,
        )
        # list_models should have been called, not fetch_api_models
        assert called_with.get("api_key") == "tf-test-key"
        # The model list from list_models should appear in choices
        assert "llama3-3-70b" in choices
