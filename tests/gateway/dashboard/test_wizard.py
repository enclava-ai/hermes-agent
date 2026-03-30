"""
Integration tests for the onboarding wizard flow.

Tests cover the full HTTP request/response cycle using aiohttp TestClient:
- Wizard page renders (GET /wizard)
- Step navigation forward and backward
- Step 1 validation (provider + API key required)
- Step 2 validation (test connection required)
- Wizard completion applies config atomically
- Draft persistence and cleanup
- First-time redirect from dashboard index
"""

import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from gateway.dashboard import create_dashboard_app
from gateway.dashboard.auth import make_session_token, SESSION_COOKIE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Return a dict with the auth session cookie for authenticated requests."""
    token = make_session_token(fernet)
    return {SESSION_COOKIE: token}


# Minimal PROVIDER_REGISTRY mock entries
_MOCK_PROVIDER = SimpleNamespace(
    name="OpenAI",
    auth_type="api_key",
    api_key_env_vars=["OPENAI_API_KEY"],
)

_MOCK_PROVIDER_REGISTRY = {
    "openai": _MOCK_PROVIDER,
}

# Minimal PLATFORM_SCHEMA mock (uses real Platform enum)
_MOCK_PLATFORM_SCHEMA = {}  # populated in fixture below


# ---------------------------------------------------------------------------
# Autouse fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_skills_tool():
    """Pre-inject a fake tools.skills_tool into sys.modules to avoid firecrawl
    import chain when gateway.dashboard.skills is imported."""
    fake = types.ModuleType("tools.skills_tool")
    fake._find_all_skills = lambda skip_disabled=False: []
    originals = {}
    for key in ("tools", "tools.skills_tool"):
        if key in sys.modules:
            originals[key] = sys.modules[key]
    if "tools" not in sys.modules:
        tools_pkg = types.ModuleType("tools")
        tools_pkg.__path__ = []
        sys.modules["tools"] = tools_pkg
    sys.modules["tools.skills_tool"] = fake
    yield
    for key in ("tools", "tools.skills_tool"):
        if key in originals:
            sys.modules[key] = originals[key]
        elif key in sys.modules:
            del sys.modules[key]


@pytest.fixture(autouse=True)
def _mock_platform_schema():
    """Provide a minimal PLATFORM_SCHEMA with one configurable platform."""
    from gateway.config import Platform
    schema = {
        Platform.TELEGRAM: {
            "display_name": "Telegram",
            "fields": [
                {
                    "name": "TELEGRAM_BOT_TOKEN",
                    "label": "Bot Token",
                    "type": "password",
                    "required": True,
                    "help": "Telegram bot token from @BotFather",
                    "help_url": "",
                },
            ],
            "test_supported": True,
            "configurable": True,
        },
    }
    with patch("gateway.dashboard.wizard.PLATFORM_SCHEMA", schema, create=True):
        with patch("gateway.dashboard.platform_schema.PLATFORM_SCHEMA", schema):
            yield schema


@pytest.fixture(autouse=True)
def _mock_is_managed():
    """Ensure is_managed() returns False for all tests."""
    with patch("hermes_cli.config.is_managed", return_value=False):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWizardPage:
    @pytest.mark.asyncio
    async def test_wizard_page_returns_html(self):
        """GET /wizard with auth cookie returns 200 with wizard content."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                resp = await cli.get("/wizard")
            assert resp.status == 200
            body = await resp.text()
            assert "Setup" in body
            assert "wizard-step-bar" in body

    @pytest.mark.asyncio
    async def test_wizard_unauthenticated_redirects_to_login(self):
        """GET /wizard without auth cookie returns 302 redirect to /login."""
        app, _ = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/wizard", allow_redirects=False)
            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/login" in location


class TestWizardStepNavigation:
    @pytest.mark.asyncio
    async def test_get_step_1_renders_llm_form(self):
        """GET /wizard/step/1 returns 200 with LLM form content."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                resp = await cli.get("/wizard/step/1")
            assert resp.status == 200
            body = await resp.text()
            assert "LLM" in body
            assert "provider" in body.lower()
            assert "api_key" in body

    @pytest.mark.asyncio
    async def test_post_step_1_valid_advances_to_step_2(self):
        """POST /wizard/step/1 with valid data advances to step 2."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                resp = await cli.post("/wizard/step/1", data={
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "api_key": "sk-test123",
                    "api_key_env_var": "OPENAI_API_KEY",
                })
            assert resp.status == 200
            body = await resp.text()
            assert "Platform" in body

    @pytest.mark.asyncio
    async def test_post_step_1_missing_provider_shows_error(self):
        """POST /wizard/step/1 with empty provider shows error."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                resp = await cli.post("/wizard/step/1", data={
                    "provider": "",
                    "api_key": "sk-test123",
                    "api_key_env_var": "OPENAI_API_KEY",
                })
            assert resp.status == 200
            body = await resp.text()
            assert "Please provide" in body or "error" in body.lower()

    @pytest.mark.asyncio
    async def test_post_step_1_missing_api_key_shows_error(self):
        """POST /wizard/step/1 with provider but no api_key shows error."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                resp = await cli.post("/wizard/step/1", data={
                    "provider": "openai",
                    "api_key": "",
                    "api_key_env_var": "OPENAI_API_KEY",
                })
            assert resp.status == 200
            body = await resp.text()
            assert "Please provide" in body or "error" in body.lower()

    @pytest.mark.asyncio
    async def test_post_step_2_without_test_shows_error(self):
        """POST /wizard/step/2 without test passed shows error."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                resp = await cli.post("/wizard/step/2", data={})
            assert resp.status == 200
            body = await resp.text()
            assert "test" in body.lower()

    @pytest.mark.asyncio
    async def test_back_from_step_2_to_step_1(self):
        """GET /wizard/step/1 after advancing returns step 1 content."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                # First advance to step 2
                await cli.post("/wizard/step/1", data={
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "api_key": "sk-test123",
                    "api_key_env_var": "OPENAI_API_KEY",
                })
                # Back to step 1
                resp = await cli.get("/wizard/step/1")
            assert resp.status == 200
            body = await resp.text()
            assert "LLM" in body

    @pytest.mark.asyncio
    async def test_get_step_1_back_preserves_draft(self):
        """After posting step 1, going back preserves draft values."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY):
                # Post step 1 with data
                await cli.post("/wizard/step/1", data={
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "api_key": "sk-test123",
                    "api_key_env_var": "OPENAI_API_KEY",
                })
                # Go back to step 1
                resp = await cli.get("/wizard/step/1")
            assert resp.status == 200
            body = await resp.text()
            # Draft should populate the form — provider name should appear
            assert "openai" in body.lower() or "OpenAI" in body


class TestWizardPlatformTest:
    @pytest.mark.asyncio
    async def test_wizard_test_success(self):
        """POST /wizard/test/telegram with mocked success shows success message."""
        app, fernet = _make_app()
        mock_handler = AsyncMock(return_value=(True, "Connected successfully"))
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY), \
                 patch("gateway.dashboard.wizard._TEST_HANDLERS",
                       {"telegram": mock_handler}, create=True), \
                 patch("gateway.dashboard.platforms._TEST_HANDLERS",
                       {"telegram": mock_handler}):
                resp = await cli.post("/wizard/test/telegram", data={
                    "TELEGRAM_BOT_TOKEN": "123:abc",
                })
            assert resp.status == 200
            body = await resp.text()
            assert "success" in body.lower() or "Connected" in body

    @pytest.mark.asyncio
    async def test_wizard_test_failure(self):
        """POST /wizard/test/telegram with mocked failure shows error."""
        app, fernet = _make_app()
        mock_handler = AsyncMock(return_value=(False, "Invalid token"))
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY), \
                 patch("gateway.dashboard.wizard._TEST_HANDLERS",
                       {"telegram": mock_handler}, create=True), \
                 patch("gateway.dashboard.platforms._TEST_HANDLERS",
                       {"telegram": mock_handler}):
                resp = await cli.post("/wizard/test/telegram", data={
                    "TELEGRAM_BOT_TOKEN": "invalid",
                })
            assert resp.status == 200
            body = await resp.text()
            assert "error" in body.lower() or "Invalid" in body


class TestWizardCompletion:
    @pytest.mark.asyncio
    async def test_complete_applies_config_and_redirects(self):
        """POST /wizard/complete saves config and redirects to /dashboard/."""
        app, fernet = _make_app()
        mock_handler = AsyncMock(return_value=(True, "OK"))
        mock_save_config = MagicMock()
        mock_save_env = MagicMock()

        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.config.save_config", mock_save_config), \
                 patch("hermes_cli.config.save_env_value", mock_save_env), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY), \
                 patch("gateway.dashboard.platforms._TEST_HANDLERS",
                       {"telegram": mock_handler}), \
                 patch("gateway.dashboard.wizard._save_draft_to_disk"), \
                 patch("gateway.dashboard.wizard._load_draft_from_disk", return_value=None):

                # Step 1: configure LLM
                await cli.post("/wizard/step/1", data={
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "api_key": "sk-test123",
                    "api_key_env_var": "OPENAI_API_KEY",
                })

                # Test platform connection
                await cli.post("/wizard/test/telegram", data={
                    "TELEGRAM_BOT_TOKEN": "123:abc",
                })

                # Step 2: advance past platform
                await cli.post("/wizard/step/2", data={})

                # Complete wizard (patch _delete_draft disk ops)
                with patch("gateway.dashboard.wizard._draft_file_path") as mock_path:
                    mock_path_obj = MagicMock()
                    mock_path.return_value = mock_path_obj
                    resp = await cli.post("/wizard/complete", allow_redirects=False)

            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/" in location

            # Verify config was saved with model key
            assert mock_save_config.called
            saved_config = mock_save_config.call_args[0][0]
            assert saved_config.get("model") == "openai/gpt-4o"

            # Verify API key was saved
            assert mock_save_env.called
            env_calls = [c[0] for c in mock_save_env.call_args_list]
            assert ("OPENAI_API_KEY", "sk-test123") in env_calls

    @pytest.mark.asyncio
    async def test_complete_deletes_draft_file(self):
        """After wizard completion, the draft file is cleaned up."""
        app, fernet = _make_app()
        mock_handler = AsyncMock(return_value=(True, "OK"))

        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}), \
                 patch("hermes_cli.config.get_env_value", return_value=""), \
                 patch("hermes_cli.config.save_config"), \
                 patch("hermes_cli.config.save_env_value"), \
                 patch("hermes_cli.auth.PROVIDER_REGISTRY", _MOCK_PROVIDER_REGISTRY), \
                 patch("gateway.dashboard.platforms._TEST_HANDLERS",
                       {"telegram": mock_handler}), \
                 patch("gateway.dashboard.wizard._save_draft_to_disk"), \
                 patch("gateway.dashboard.wizard._load_draft_from_disk", return_value=None):

                # Run through full wizard
                await cli.post("/wizard/step/1", data={
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "api_key": "sk-test123",
                    "api_key_env_var": "OPENAI_API_KEY",
                })
                await cli.post("/wizard/test/telegram", data={
                    "TELEGRAM_BOT_TOKEN": "123:abc",
                })
                await cli.post("/wizard/step/2", data={})

                with patch("gateway.dashboard.wizard._draft_file_path") as mock_path:
                    mock_path_obj = MagicMock()
                    mock_path.return_value = mock_path_obj
                    await cli.post("/wizard/complete", allow_redirects=False)

            # Draft should be deleted via unlink
            mock_path_obj.unlink.assert_called_once_with(missing_ok=True)


class TestFirstTimeRedirect:
    @pytest.mark.asyncio
    async def test_index_redirects_to_wizard_when_no_model(self):
        """GET / with auth cookie and no model config redirects to /wizard."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value={}):
                resp = await cli.get("/", allow_redirects=False)
            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/wizard" in location

    @pytest.mark.asyncio
    async def test_index_serves_dashboard_when_model_configured(self):
        """GET / with auth cookie and model configured returns 200 dashboard."""
        app, fernet = _make_app()
        config = {"model": "openai/gpt-4o"}
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with patch("hermes_cli.config.load_config", return_value=config), \
                 patch("gateway.dashboard.wizard._load_draft_from_disk", return_value=None):
                resp = await cli.get("/", allow_redirects=False)
            assert resp.status == 200
            body = await resp.text()
            assert "Dashboard" in body
