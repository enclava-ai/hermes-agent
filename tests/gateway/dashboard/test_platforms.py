"""
Integration tests for dashboard platform configuration handlers.

Covers platform tab rendering, platform save, test-connection dispatch,
auth enforcement, managed-mode guards, and redaction sentinel handling.
"""

import copy
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from gateway.dashboard import create_dashboard_app
from gateway.dashboard.auth import make_session_token, SESSION_COOKIE


# ---------------------------------------------------------------------------
# Fixtures — mirrors test_settings.py pattern
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
# Auth enforcement
# ---------------------------------------------------------------------------

class TestPlatformsAuth:
    @pytest.mark.asyncio
    async def test_platforms_tab_requires_auth(self):
        """GET /settings/platforms without auth cookie returns 302 redirect."""
        app, _ = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/settings/platforms", allow_redirects=False)
            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/login" in location

    @pytest.mark.asyncio
    async def test_platform_save_requires_auth(self):
        """POST /settings/platforms/telegram/save without auth returns 302."""
        app, _ = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/settings/platforms/telegram/save",
                data={"TELEGRAM_BOT_TOKEN": "tok123"},
                allow_redirects=False,
            )
            assert resp.status == 302

    @pytest.mark.asyncio
    async def test_platform_test_requires_auth(self):
        """POST /settings/platforms/telegram/test without auth returns 302."""
        app, _ = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/settings/platforms/telegram/test",
                data={"TELEGRAM_BOT_TOKEN": "tok123"},
                allow_redirects=False,
            )
            assert resp.status == 302


# ---------------------------------------------------------------------------
# Platform tab rendering
# ---------------------------------------------------------------------------

class TestPlatformsTab:
    @pytest.mark.asyncio
    async def test_platforms_tab_renders(self):
        """GET /settings/platforms with auth returns 200, contains platform names."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.get_env_value", return_value=""),
                patch("hermes_cli.config.is_managed", return_value=False),
            ):
                resp = await cli.get("/settings/platforms")
            assert resp.status == 200
            body = await resp.text()
            assert "Telegram" in body
            assert "Discord" in body

    @pytest.mark.asyncio
    async def test_platforms_tab_shows_configured_badge(self):
        """Platform with a required env value set shows 'Configured' badge."""
        app, fernet = _make_app()

        def _get_env(name):
            if name == "TELEGRAM_BOT_TOKEN":
                return "real-token-value"
            return ""

        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.get_env_value", side_effect=_get_env),
                patch("hermes_cli.config.is_managed", return_value=False),
            ):
                resp = await cli.get("/settings/platforms")
            assert resp.status == 200
            body = await resp.text()
            assert "Configured" in body


# ---------------------------------------------------------------------------
# Platform save
# ---------------------------------------------------------------------------

class TestPlatformSave:
    @pytest.mark.asyncio
    async def test_platform_save_persists_env(self):
        """POST save calls save_env_value with correct args for each field."""
        app, fernet = _make_app()
        env_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.config.save_env_value", env_mock),
                patch("hermes_cli.config.get_env_value", return_value=""),
            ):
                resp = await cli.post(
                    "/settings/platforms/telegram/save",
                    data={
                        "TELEGRAM_BOT_TOKEN": "new-bot-token-123",
                        "TELEGRAM_ALLOWED_USERS": "12345,67890",
                    },
                )
            assert resp.status == 200
            body = await resp.text()
            assert "saved" in body.lower() or "Saved" in body
            # Password field should be saved
            env_mock.assert_any_call("TELEGRAM_BOT_TOKEN", "new-bot-token-123")
            # Non-secret field should also be saved
            env_mock.assert_any_call("TELEGRAM_ALLOWED_USERS", "12345,67890")

    @pytest.mark.asyncio
    async def test_platform_save_skips_redacted(self):
        """POST with redacted password value does NOT overwrite existing secret."""
        app, fernet = _make_app()
        env_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.config.save_env_value", env_mock),
                patch("hermes_cli.config.get_env_value", return_value="existing-token"),
            ):
                resp = await cli.post(
                    "/settings/platforms/telegram/save",
                    data={
                        "TELEGRAM_BOT_TOKEN": "sk-a***xyz",
                    },
                )
            assert resp.status == 200
            # save_env_value should NOT have been called for the password field
            # because the value contains "***" (redaction marker)
            for call_args in env_mock.call_args_list:
                assert call_args[0][0] != "TELEGRAM_BOT_TOKEN", (
                    "save_env_value should not be called for redacted password field"
                )

    @pytest.mark.asyncio
    async def test_platform_save_blocked_managed(self):
        """POST save in managed mode returns 200 with 'managed' message, no save."""
        app, fernet = _make_app()
        env_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=True),
                patch("hermes_cli.config.save_env_value", env_mock),
                patch("hermes_cli.config.get_env_value", return_value=""),
            ):
                resp = await cli.post(
                    "/settings/platforms/telegram/save",
                    data={"TELEGRAM_BOT_TOKEN": "new-token"},
                )
            assert resp.status == 200
            body = await resp.text()
            assert "managed" in body.lower() or "NixOS" in body
            env_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Test connection dispatch
# ---------------------------------------------------------------------------

class TestPlatformTestConnection:
    @pytest.mark.asyncio
    async def test_platform_test_dispatches(self):
        """POST /settings/platforms/telegram/test dispatches to _test_telegram with mocked httpx."""
        app, fernet = _make_app()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True, "result": {"username": "testbot"}}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.get_env_value", return_value=""),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("httpx.AsyncClient", return_value=mock_client),
            ):
                resp = await cli.post(
                    "/settings/platforms/telegram/test",
                    data={"TELEGRAM_BOT_TOKEN": "test-token-123"},
                )
            assert resp.status == 200
            body = await resp.text()
            # Handler should report success with bot username
            assert "testbot" in body or "success" in body.lower()
