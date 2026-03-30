"""
Integration tests for the dashboard auth flow.

Tests cover the full HTTP request/response cycle using aiohttp TestClient:
- Login page (GET /login) returns HTML
- Valid credentials → 302 redirect + session cookie
- Invalid credentials → 200 re-render with error message
- Authenticated GET / → 200 (not redirect)
- Unauthenticated GET / → 302 to /dashboard/login
- Logout → 302 + cookie cleared
- API routes on parent app unaffected by dashboard auth middleware
- Static assets accessible without auth cookie

No real config reads — all load_config() calls monkeypatched in tests.
"""

from unittest.mock import patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from cryptography.fernet import Fernet

from gateway.dashboard import create_dashboard_app
from gateway.dashboard.auth import (
    hash_password,
    make_session_token,
    SESSION_COOKIE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_config(password="testpass123", username="admin", force_change=False):
    """Return a minimal config dict with dashboard credentials."""
    pw_hash = hash_password(password)
    return {
        "dashboard": {
            "username": username,
            "password_hash": pw_hash,
            "force_change": force_change,
        }
    }


def _make_dashboard_app(test_config=None, force_password_change=False):
    """
    Build a dashboard subapp with auth wired, but:
    - ensure_dashboard_credentials startup hook REPLACED with a synthetic one
      that injects a known Fernet key without reading/writing disk
    Returns (app, fernet).
    """
    fernet = Fernet(Fernet.generate_key())
    app = create_dashboard_app()

    # Replace the on_startup hook with one that injects our test fernet key
    app.on_startup.clear()

    async def _inject_fernet(inner_app):
        inner_app["fernet"] = fernet
        inner_app["force_password_change"] = force_password_change

    app.on_startup.append(_inject_fernet)
    return app, fernet


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoginPage:
    @pytest.mark.asyncio
    async def test_login_page_returns_html(self):
        """GET /login returns 200 with Content-Type text/html and body containing <form."""
        app, _ = _make_dashboard_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/login")
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/html" in content_type
            body = await resp.text()
            assert "<form" in body


class TestLoginFlow:
    @pytest.mark.asyncio
    async def test_login_valid_credentials_redirects(self):
        """POST /login with valid credentials returns 302 to / and sets session cookie."""
        config = _make_test_config(password="testpass123", username="admin")
        app, _ = _make_dashboard_app()
        async with TestClient(TestServer(app)) as cli:
            with patch("hermes_cli.config.load_config", return_value=config):
                resp = await cli.post(
                    "/login",
                    data={"username": "admin", "password": "testpass123"},
                    allow_redirects=False,
                )
            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/" in location
            assert SESSION_COOKIE in resp.cookies

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_form(self):
        """POST /login with wrong password returns 200 re-renders login form with 'Invalid'."""
        config = _make_test_config(password="testpass123", username="admin")
        app, _ = _make_dashboard_app()
        async with TestClient(TestServer(app)) as cli:
            with patch("hermes_cli.config.load_config", return_value=config):
                resp = await cli.post(
                    "/login",
                    data={"username": "admin", "password": "wrongpassword"},
                    allow_redirects=False,
                )
            assert resp.status == 200
            body = await resp.text()
            assert "Invalid" in body


class TestAuthenticatedAccess:
    @pytest.mark.asyncio
    async def test_authenticated_request_succeeds(self):
        """GET / with a valid session cookie returns 200 (not a redirect)."""
        app, fernet = _make_dashboard_app()
        async with TestClient(TestServer(app)) as cli:
            token = make_session_token(fernet)
            cli.session.cookie_jar.update_cookies({SESSION_COOKIE: token})
            resp = await cli.get("/", allow_redirects=False)
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_unauthenticated_request_redirects(self):
        """GET / without cookie returns 302 to /dashboard/login."""
        app, _ = _make_dashboard_app()
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/", allow_redirects=False)
            assert resp.status == 302
            location = resp.headers.get("Location", "")
            assert "/dashboard/login" in location


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self):
        """POST /logout returns 302 and clears hermes_dash_session cookie."""
        app, fernet = _make_dashboard_app()
        async with TestClient(TestServer(app)) as cli:
            # Set a valid session cookie
            token = make_session_token(fernet)
            cli.session.cookie_jar.update_cookies({SESSION_COOKIE: token})
            resp = await cli.post("/logout", allow_redirects=False)
            assert resp.status == 302
            # Cookie should be cleared — del_cookie sets Max-Age=0 or empty value
            cookie_header = resp.headers.get("Set-Cookie", "")
            assert SESSION_COOKIE in cookie_header
            # aiohttp del_cookie uses Max-Age=0
            assert "Max-Age=0" in cookie_header or "max-age=0" in cookie_header.lower() or '=""' in cookie_header or "=;" in cookie_header


class TestAPIIsolation:
    @pytest.mark.asyncio
    async def test_api_routes_unaffected(self):
        """GET /health on the parent app returns 200 JSON, not HTML redirect.

        Creates a minimal parent app with /health and mounts the dashboard as a
        subapp — mirrors the real api_server.py structure. Verifies that the
        auth middleware does NOT bleed onto parent app routes.
        """
        # Build dashboard subapp
        dashboard_app, _ = _make_dashboard_app()

        # Build parent app with /health and mount dashboard
        parent = web.Application()

        async def health_handler(request):
            return web.json_response({"status": "ok"})

        parent.router.add_get("/health", health_handler)
        parent.add_subapp("/dashboard", dashboard_app)

        async with TestClient(TestServer(parent)) as cli:
            # GET /health must return JSON (not an HTML redirect from auth middleware)
            resp = await cli.get("/health", allow_redirects=False)
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"

            # GET /dashboard/login must return HTML (dashboard is mounted)
            resp2 = await cli.get("/dashboard/login", allow_redirects=False)
            assert resp2.status == 200
            body2 = await resp2.text()
            assert "text/html" in resp2.headers.get("Content-Type", "")
            assert "<form" in body2


class TestStaticAssets:
    @pytest.mark.asyncio
    async def test_static_assets_accessible(self):
        """GET /static/vendor/htmx.min.js returns 200 without auth cookie."""
        app, _ = _make_dashboard_app()
        async with TestClient(TestServer(app)) as cli:
            # No session cookie — static files should be exempt from auth middleware
            resp = await cli.get("/static/vendor/htmx.min.js", allow_redirects=False)
            assert resp.status == 200
