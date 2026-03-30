"""
Integration tests for dashboard skills management handlers.

Covers skills tab rendering, skill toggle enable/disable,
auth enforcement, and managed-mode guards.
"""

import copy
import sys
import types
from unittest.mock import patch, MagicMock

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

MOCK_SKILLS = [
    {"name": "web-search", "description": "Search the web", "category": "tools"},
    {"name": "code-review", "description": "Review code", "category": "development"},
    {"name": "summarize", "description": "Summarize text", "category": "tools"},
]


def _fake_skills_module():
    """Create a fake tools.skills_tool module to avoid importing the full tools package.

    The real tools/__init__.py pulls in web_tools which requires firecrawl.
    We only need _find_all_skills for dashboard tests.
    """
    mod = types.ModuleType("tools.skills_tool")
    mod._find_all_skills = lambda skip_disabled=False: list(MOCK_SKILLS)
    return mod


@pytest.fixture(autouse=True)
def _mock_skills_tool():
    """Pre-inject a fake tools.skills_tool into sys.modules so the deferred
    import in gateway.dashboard.skills._render_skills() works without firecrawl."""
    fake = _fake_skills_module()
    # Save originals if they exist
    originals = {}
    for key in ("tools", "tools.skills_tool"):
        if key in sys.modules:
            originals[key] = sys.modules[key]
    # Ensure tools package exists as a namespace (may already from other imports)
    if "tools" not in sys.modules:
        tools_pkg = types.ModuleType("tools")
        tools_pkg.__path__ = []
        sys.modules["tools"] = tools_pkg
    sys.modules["tools.skills_tool"] = fake
    yield
    # Restore
    for key, orig in originals.items():
        sys.modules[key] = orig
    if "tools.skills_tool" in sys.modules and "tools.skills_tool" not in originals:
        del sys.modules["tools.skills_tool"]
    if "tools" in sys.modules and "tools" not in originals:
        del sys.modules["tools"]


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

class TestSkillsAuth:
    @pytest.mark.asyncio
    async def test_skills_tab_requires_auth(self):
        """GET /settings/skills without auth cookie returns 302 redirect."""
        app, _ = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/settings/skills", allow_redirects=False)
            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/login" in location

    @pytest.mark.asyncio
    async def test_skill_toggle_requires_auth(self):
        """POST /settings/skills/web-search/toggle without auth returns 302."""
        app, _ = _make_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/settings/skills/web-search/toggle",
                allow_redirects=False,
            )
            assert resp.status == 302


# ---------------------------------------------------------------------------
# Skills tab rendering
# ---------------------------------------------------------------------------

class TestSkillsTab:
    @pytest.mark.asyncio
    async def test_skills_tab_renders(self):
        """GET /settings/skills with auth returns 200, contains skill names."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.skills_config.get_disabled_skills", return_value=set()),
            ):
                resp = await cli.get("/settings/skills")
            assert resp.status == 200
            body = await resp.text()
            assert "web-search" in body
            assert "code-review" in body
            assert "summarize" in body

    @pytest.mark.asyncio
    async def test_skills_tab_shows_categories(self):
        """Skills are grouped by category in the response."""
        app, fernet = _make_app()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.skills_config.get_disabled_skills", return_value=set()),
            ):
                resp = await cli.get("/settings/skills")
            assert resp.status == 200
            body = await resp.text()
            # Both categories from MOCK_SKILLS should appear
            assert "tools" in body.lower()
            assert "development" in body.lower()


# ---------------------------------------------------------------------------
# Skill toggle
# ---------------------------------------------------------------------------

class TestSkillToggle:
    @pytest.mark.asyncio
    async def test_skill_toggle_enables(self):
        """Toggling a disabled skill removes it from the disabled set."""
        app, fernet = _make_app()
        save_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.skills_config.get_disabled_skills", return_value={"web-search"}),
                patch("hermes_cli.skills_config.save_disabled_skills", save_mock),

            ):
                resp = await cli.post("/settings/skills/web-search/toggle")
            assert resp.status == 200
            body = await resp.text()
            assert "enabled" in body.lower()
            # save_disabled_skills should be called with web-search removed
            save_mock.assert_called_once()
            saved_disabled = save_mock.call_args[0][1]
            assert "web-search" not in saved_disabled

    @pytest.mark.asyncio
    async def test_skill_toggle_disables(self):
        """Toggling an enabled skill adds it to the disabled set."""
        app, fernet = _make_app()
        save_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=False),
                patch("hermes_cli.skills_config.get_disabled_skills", return_value=set()),
                patch("hermes_cli.skills_config.save_disabled_skills", save_mock),

            ):
                resp = await cli.post("/settings/skills/web-search/toggle")
            assert resp.status == 200
            body = await resp.text()
            assert "disabled" in body.lower()
            # save_disabled_skills should be called with web-search added
            save_mock.assert_called_once()
            saved_disabled = save_mock.call_args[0][1]
            assert "web-search" in saved_disabled

    @pytest.mark.asyncio
    async def test_skill_toggle_blocked_managed(self):
        """Toggle in managed mode returns 200 with 'managed' message."""
        app, fernet = _make_app()
        save_mock = MagicMock()
        async with TestClient(TestServer(app)) as cli:
            cli.session.cookie_jar.update_cookies(_auth_cookie(fernet))
            with (
                patch("hermes_cli.config.load_config", return_value=copy.deepcopy(MOCK_CONFIG)),
                patch("hermes_cli.config.is_managed", return_value=True),
                patch("hermes_cli.skills_config.get_disabled_skills", return_value=set()),
                patch("hermes_cli.skills_config.save_disabled_skills", save_mock),

            ):
                resp = await cli.post("/settings/skills/web-search/toggle")
            assert resp.status == 200
            body = await resp.text()
            assert "managed" in body.lower() or "NixOS" in body
            save_mock.assert_not_called()
