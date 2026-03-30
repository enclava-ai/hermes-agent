"""Dashboard view handlers (non-auth pages)."""
import logging

logger = logging.getLogger(__name__)

try:
    import aiohttp_jinja2
    from aiohttp import web
except ImportError:
    pass


@aiohttp_jinja2.template("index.html")
async def handle_index(request: "web.Request") -> dict:
    return {}
