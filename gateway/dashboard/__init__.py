"""
Hermes web dashboard — self-contained aiohttp subapp.

Mounted at /dashboard/ by APIServerAdapter.connect() before runner.setup().
All dashboard code lives in this package. The only upstream file touched is
gateway/platforms/api_server.py (the add_subapp() hook).
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


def create_dashboard_app(gateway_runner=None):
    """
    Factory for the dashboard aiohttp subapp.

    Called from APIServerAdapter.connect() before runner.setup().
    Auth middleware and route registration added in Phase 1 Plan 02.
    """
    if not DASHBOARD_AVAILABLE:
        raise ImportError("Dashboard dependencies not installed: pip install hermes-agent[dashboard]")

    app = web.Application()
    app["gateway_runner"] = gateway_runner
    app["config_lock"] = asyncio.Lock()

    # Static files — served at /dashboard/static/; exempt from auth middleware automatically
    static_dir = Path(__file__).parent / "static"
    app.router.add_static("/static", static_dir, append_version=True)

    # Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(templates_dir)))

    logger.info("Dashboard subapp created; will be mounted at /dashboard/")
    return app
