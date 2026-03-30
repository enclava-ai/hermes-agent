"""
Hermes web dashboard — self-contained aiohttp subapp.

Mounted at /dashboard/ by APIServerAdapter.connect() before runner.setup().
All dashboard code lives in this package. The only upstream file touched is
gateway/platforms/api_server.py (the add_subapp() hook — one line).

Usage:
    from gateway.dashboard import create_dashboard_app
    app.add_subapp('/dashboard', create_dashboard_app(gateway_runner=runner))
"""
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from aiohttp import web
    import aiohttp_jinja2
    import jinja2
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False
    web = None  # type: ignore[assignment]


def create_dashboard_app(gateway_runner=None) -> "web.Application":
    """
    Factory for the dashboard aiohttp subapp.

    Called from APIServerAdapter.connect() before runner.setup().
    Auth middleware is scoped to this subapp only — main app routes are unaffected.
    """
    if not DASHBOARD_AVAILABLE:
        raise ImportError(
            "Dashboard dependencies not installed. Run: pip install hermes-agent[dashboard]"
        )

    from .auth import (
        auth_middleware,
        ensure_dashboard_credentials,
        handle_login_page,
        handle_login,
        handle_logout,
        handle_change_password_page,
        handle_change_password,
    )

    # Auth middleware scoped to dashboard subapp only (RESEARCH.md Pitfall 2)
    app = web.Application(middlewares=[auth_middleware])
    app["gateway_runner"] = gateway_runner
    # asyncio.Lock for serializing concurrent config writes (STATE.md concern)
    app["config_lock"] = asyncio.Lock()

    # on_startup: generate first-run password if needed, load Fernet key
    app.on_startup.append(ensure_dashboard_credentials)

    # Static files — served at /dashboard/static/; paths in middleware are exempt
    static_dir = Path(__file__).parent / "static"
    app.router.add_static("/static", static_dir, append_version=True)

    # Routes — all WITHOUT /dashboard/ prefix (relative to mount point, Pitfall 5)
    app.router.add_get("/login", handle_login_page)
    app.router.add_post("/login", handle_login)
    app.router.add_post("/logout", handle_logout)
    app.router.add_get("/change-password", handle_change_password_page)
    app.router.add_post("/change-password", handle_change_password)

    # Dashboard home — import inline to keep Phase 1 minimal
    from .views import handle_index
    app.router.add_get("/", handle_index)

    # Settings tab handlers (Phase 2)
    from .settings import (
        handle_llm_tab,
        handle_llm_save,
        handle_soul_save,
        handle_general_tab,
        handle_general_save,
        handle_status_tab,
    )
    app.router.add_get("/settings/llm", handle_llm_tab)
    app.router.add_post("/settings/llm/save", handle_llm_save)
    app.router.add_post("/settings/soul/save", handle_soul_save)
    app.router.add_get("/settings/general", handle_general_tab)
    app.router.add_post("/settings/general/save", handle_general_save)
    app.router.add_get("/settings/status", handle_status_tab)

    # Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(templates_dir)))

    logger.info("Dashboard subapp created; will be mounted at /dashboard/")
    return app
