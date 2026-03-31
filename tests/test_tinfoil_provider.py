"""Tests for Tinfoil provider registration and runtime resolution."""
from __future__ import annotations

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
