"""
Tests for the /settings/llm/verify-key endpoint.

Covers:
- Successful model fetch from OpenAI-compatible provider (mocked httpx)
- Anthropic hardcoded model list (no HTTP call)
- Non-api_key provider returns graceful error
- httpx failure returns error partial
- Missing provider returns error
"""

import copy
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from gateway.dashboard import create_dashboard_app
from gateway.dashboard.auth import make_session_token, SESSION_COOKIE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_CONFIG = {
    "model": "deepseek/deepseek-chat",
    "toolsets": ["hermes-cli"],
    "memory": {"memory_enabled": True},
    "compression": {"enabled": True, "threshold": 0.5},
    "display": {"streaming": False, "skin": "default"},
    "agent": {},
}


def _make_app():
    """Build a dashboard test app with injected Fernet key."""
    fernet = Fernet(Fernet.generate_key())
    app = create_dashboard_app()
    app.on_startup.clear()

    async def _inject_fernet(inner_app):
        inner_app["fernet"] = fernet

    app.on_startup.append(_inject_fernet)
    return app, fernet


def _auth_cookie(fernet):
    token = make_session_token(fernet)
    return {SESSION_COOKIE: token}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVerifyKey:
    @pytest.mark.asyncio
    async def test_successful_model_fetch(self):
        """POST with valid api_key provider returns model select options."""
        app, fernet = _make_app()

        # httpx.Response has synchronous json() and raise_for_status()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "model-b"},
                {"id": "model-a"},
                {"id": "model-c"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.get_env_value", return_value="sk-real-key"),
                patch("gateway.dashboard.settings.httpx.AsyncClient") as mock_client_cls,
            ):
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                resp = await cli.post(
                    "/settings/llm/verify-key",
                    data={
                        "provider": "deepseek",
                        "api_key": "",
                        "api_key_env_var": "DEEPSEEK_API_KEY",
                        "model_name": "deepseek-chat",
                    },
                )
            assert resp.status == 200
            body = await resp.text()
            # Should contain a select with sorted model options
            assert "<select" in body
            assert "model-a" in body
            assert "model-b" in body
            assert "model-c" in body
            # Should be sorted (model-a before model-b)
            assert body.index("model-a") < body.index("model-b")

    @pytest.mark.asyncio
    async def test_anthropic_hardcoded_models(self):
        """POST with provider=anthropic returns hardcoded model list, no HTTP call."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.get_env_value", return_value="sk-ant-key"),
                patch("gateway.dashboard.settings.httpx.AsyncClient") as mock_client_cls,
            ):
                resp = await cli.post(
                    "/settings/llm/verify-key",
                    data={
                        "provider": "anthropic",
                        "api_key": "sk-ant-key",
                        "api_key_env_var": "ANTHROPIC_API_KEY",
                        "model_name": "",
                    },
                )
            assert resp.status == 200
            body = await resp.text()
            assert "<select" in body
            assert "claude-opus-4" in body
            assert "claude-sonnet-4" in body
            assert "claude-haiku-3.5" in body  # friendly name or id
            # No HTTP call should have been made
            mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_api_key_provider_error(self):
        """POST with oauth provider returns error message."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            resp = await cli.post(
                "/settings/llm/verify-key",
                data={
                    "provider": "nous",
                    "api_key": "",
                    "api_key_env_var": "",
                    "model_name": "",
                },
            )
            assert resp.status == 200
            body = await resp.text()
            assert "not available" in body.lower() or "error" in body.lower()
            assert "<select" not in body

    @pytest.mark.asyncio
    async def test_httpx_failure_returns_error(self):
        """POST with valid provider but network error returns error partial."""
        import httpx as real_httpx

        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.get_env_value", return_value="sk-bad-key"),
                patch("gateway.dashboard.settings.httpx.AsyncClient") as mock_client_cls,
            ):
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    side_effect=real_httpx.ConnectError("Connection refused")
                )
                mock_client_cls.return_value = mock_client

                resp = await cli.post(
                    "/settings/llm/verify-key",
                    data={
                        "provider": "deepseek",
                        "api_key": "sk-bad-key",
                        "api_key_env_var": "DEEPSEEK_API_KEY",
                        "model_name": "",
                    },
                )
            assert resp.status == 200
            body = await resp.text()
            assert "<select" not in body
            assert "error" in body.lower() or "flash" in body.lower()

    @pytest.mark.asyncio
    async def test_missing_provider_returns_error(self):
        """POST without provider field returns error."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            resp = await cli.post(
                "/settings/llm/verify-key",
                data={
                    "provider": "",
                    "api_key": "",
                    "api_key_env_var": "",
                    "model_name": "",
                },
            )
            assert resp.status == 200
            body = await resp.text()
            assert "<select" not in body

    @pytest.mark.asyncio
    async def test_no_api_key_available_returns_error(self):
        """POST with api_key provider but no key anywhere returns error."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.get_env_value", return_value=None):
                resp = await cli.post(
                    "/settings/llm/verify-key",
                    data={
                        "provider": "deepseek",
                        "api_key": "",
                        "api_key_env_var": "DEEPSEEK_API_KEY",
                        "model_name": "",
                    },
                )
            assert resp.status == 200
            body = await resp.text()
            assert "<select" not in body
            assert "no api key" in body.lower() or "error" in body.lower()

    @pytest.mark.asyncio
    async def test_redacted_key_falls_back_to_env(self):
        """POST with redacted api_key (***) uses env var value instead."""
        app, fernet = _make_app()

        # httpx.Response has synchronous json() and raise_for_status()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "test-model"}]}
        mock_response.raise_for_status = MagicMock()

        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.get_env_value", return_value="sk-env-key") as env_mock,
                patch("gateway.dashboard.settings.httpx.AsyncClient") as mock_client_cls,
            ):
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                resp = await cli.post(
                    "/settings/llm/verify-key",
                    data={
                        "provider": "deepseek",
                        "api_key": "sk-a***z",
                        "api_key_env_var": "DEEPSEEK_API_KEY",
                        "model_name": "",
                    },
                )
            assert resp.status == 200
            body = await resp.text()
            assert "<select" in body
            # Verify the env value was used (get call was fetched with the env key)
            env_mock.assert_called_with("DEEPSEEK_API_KEY")
