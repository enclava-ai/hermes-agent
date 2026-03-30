"""
Integration tests for dashboard settings handlers.

Covers LLM, General, Status, and Soul tabs — all HTTP endpoints exercised
with monkeypatched config to avoid touching real ~/.hermes/ files.
"""

import copy
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from gateway.dashboard import create_dashboard_app
from gateway.dashboard.auth import make_session_token, SESSION_COOKIE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_CONFIG = {
    "model": "anthropic/claude-opus-4.6",
    "toolsets": ["hermes-cli", "code"],
    "memory": {"memory_enabled": True},
    "compression": {"enabled": True, "threshold": 0.5},
    "display": {"streaming": False, "skin": "default"},
    "agent": {"max_turns": 90},
}


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


# ---------------------------------------------------------------------------
# LLM tab tests
# ---------------------------------------------------------------------------

class TestLLMTab:
    @pytest.mark.asyncio
    async def test_llm_tab_loads(self):
        """GET /settings/llm shows provider, model name, and redacted API key."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.get_env_value", return_value="sk-test-key-12345"),
                patch("hermes_cli.config.is_managed", return_value=False),
            ):
                resp = await cli.get("/settings/llm")
            assert resp.status == 200
            body = await resp.text()
            assert "anthropic" in body
            assert "claude-opus-4.6" in body
            assert "***" in body

    @pytest.mark.asyncio
    async def test_llm_save_updates_config(self):
        """POST /settings/llm/save persists provider/model to config."""
        app, fernet = _make_app()
        saved = {}
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.save_config", side_effect=lambda c: saved.update(c)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.config.save_env_value"),
                patch("hermes_cli.config.get_env_value", return_value="sk-test-key-12345"),
            ):
                resp = await cli.post(
                    "/settings/llm/save",
                    data={
                        "provider": "deepseek",
                        "model_name": "deepseek-chat",
                        "api_key": "",
                        "api_key_env_var": "DEEPSEEK_API_KEY",
                    },
                )
            assert resp.status == 200
            body = await resp.text()
            assert "saved" in body.lower() or "Saved" in body
            assert saved["model"] == "deepseek/deepseek-chat"

    @pytest.mark.asyncio
    async def test_llm_save_rejects_managed(self):
        """POST /settings/llm/save in managed mode shows warning, does not save."""
        app, fernet = _make_app()
        save_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.save_config", save_mock),
                patch("hermes_cli.config.is_managed", return_value=True),
                patch("hermes_cli.config.get_env_value", return_value="sk-test-key-12345"),
            ):
                resp = await cli.post(
                    "/settings/llm/save",
                    data={"provider": "openai", "model_name": "gpt-4"},
                )
            assert resp.status == 200
            body = await resp.text()
            assert "managed" in body.lower() or "NixOS" in body
            save_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_save_api_key_sentinel(self):
        """POST /settings/llm/save skips redacted sentinel, writes real key."""
        app, fernet = _make_app()
        env_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))

            # Sentinel (redacted) key — should NOT be saved
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.save_config"),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.config.save_env_value", env_mock),
                patch("hermes_cli.config.get_env_value", return_value="sk-test-key-12345"),
            ):
                await cli.post(
                    "/settings/llm/save",
                    data={
                        "provider": "openai",
                        "model_name": "gpt-4",
                        "api_key": "sk-a***yz",
                        "api_key_env_var": "OPENAI_API_KEY",
                    },
                )
            env_mock.assert_not_called()

            # Real new key — SHOULD be saved
            env_mock.reset_mock()
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.save_config"),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.config.save_env_value", env_mock),
                patch("hermes_cli.config.get_env_value", return_value="sk-test-key-12345"),
            ):
                await cli.post(
                    "/settings/llm/save",
                    data={
                        "provider": "openai",
                        "model_name": "gpt-4",
                        "api_key": "sk-real-new-key",
                        "api_key_env_var": "OPENAI_API_KEY",
                    },
                )
            env_mock.assert_called_once_with("OPENAI_API_KEY", "sk-real-new-key")


# ---------------------------------------------------------------------------
# General tab tests
# ---------------------------------------------------------------------------

MOCK_TOOLSETS = {"hermes-cli": {}, "code": {}, "web": {}}


class TestGeneralTab:
    @pytest.mark.asyncio
    async def test_general_tab_loads(self):
        """GET /settings/general shows toolset names and toggle fields."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("toolsets.get_all_toolsets", return_value=MOCK_TOOLSETS),
            ):
                resp = await cli.get("/settings/general")
            assert resp.status == 200
            body = await resp.text()
            assert "hermes-cli" in body
            assert "memory_enabled" in body

    @pytest.mark.asyncio
    async def test_general_save_updates_config(self):
        """POST /settings/general/save persists toggle states and toolsets."""
        app, fernet = _make_app()
        saved = {}
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.save_config", side_effect=lambda c: saved.update(c)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("toolsets.get_all_toolsets", return_value=MOCK_TOOLSETS),
            ):
                resp = await cli.post(
                    "/settings/general/save",
                    data={
                        "memory_enabled": "on",
                        "compression_enabled": "on",
                        "compression_threshold": "0.6",
                        "toolset_hermes-cli": "on",
                        "toolset_code": "on",
                        # streaming NOT sent = checkbox unchecked
                    },
                )
            assert resp.status == 200
            assert saved["memory"]["memory_enabled"] is True
            assert saved["display"]["streaming"] is False
            assert saved["compression"]["enabled"] is True
            assert saved["compression"]["threshold"] == 0.6
            assert sorted(saved["toolsets"]) == ["code", "hermes-cli"]


# ---------------------------------------------------------------------------
# Status tab tests
# ---------------------------------------------------------------------------

class TestStatusTab:
    @pytest.mark.asyncio
    async def test_status_tab_loads(self):
        """GET /settings/status without gateway_runner shows basic info."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)):
                resp = await cli.get("/settings/status")
            assert resp.status == 200
            body = await resp.text()
            # No runner → "Not running" + "No platform adapters"
            assert "Not running" in body or "not running" in body
            assert "No platform adapters" in body or "no platform" in body.lower()

    @pytest.mark.asyncio
    async def test_status_tab_with_runner(self):
        """GET /settings/status with a mock runner shows platform adapter status."""
        from enum import Enum

        class _MockPlatform(Enum):
            TELEGRAM = "telegram"

        mock_platform = _MockPlatform.TELEGRAM
        mock_adapter = SimpleNamespace(
            is_connected=True,
            has_fatal_error=False,
            fatal_error_message=None,
        )
        mock_runner = SimpleNamespace(adapters={mock_platform: mock_adapter})

        app, fernet = _make_app(gateway_runner=mock_runner)
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)):
                resp = await cli.get("/settings/status")
            assert resp.status == 200
            body = await resp.text()
            assert "telegram" in body
            assert "Connected" in body
            assert "Running" in body


# ---------------------------------------------------------------------------
# Soul save test
# ---------------------------------------------------------------------------

class TestSoulSave:
    @pytest.mark.asyncio
    async def test_soul_save(self, tmp_path):
        """POST /settings/soul/save writes SOUL.md content."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.get_env_value", return_value=""),
                patch("hermes_constants.get_hermes_home", return_value=str(tmp_path)),
            ):
                resp = await cli.post(
                    "/settings/soul/save",
                    data={"soul_content": "You are a helpful assistant."},
                )
            assert resp.status == 200
            body = await resp.text()
            assert "saved" in body.lower() or "Saved" in body
            soul_path = tmp_path / "SOUL.md"
            assert soul_path.exists()
            assert "helpful assistant" in soul_path.read_text()


# ---------------------------------------------------------------------------
# Auth enforcement test
# ---------------------------------------------------------------------------

class TestAuthEnforcement:
    @pytest.mark.asyncio
    async def test_unauthenticated_settings_redirects(self):
        """GET /settings/llm without auth cookie returns 302 to login."""
        app, _ = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/settings/llm", allow_redirects=False)
            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/login" in location
