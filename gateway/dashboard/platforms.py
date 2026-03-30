"""
Dashboard platform configuration handler — Platforms tab.

Provides the GET handler for rendering the platform card grid.
Save and test-connection handlers will be added in Plan 02.

All hermes_cli imports are deferred inside function bodies to avoid
import-time failures when the CLI package is unavailable.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import aiohttp_jinja2
    from aiohttp import web
except ImportError:
    pass


def _render_platforms(request: "web.Request", flash: Optional[str] = None) -> "web.Response":
    """Build platform card grid context and render the template.

    Used by GET handler (and future POST handlers) to avoid duplication.
    Returns a synchronous render_template call (do NOT await).
    """
    from hermes_cli.config import is_managed, get_env_value
    from gateway.dashboard.auth import redact_secret
    from .platform_schema import PLATFORM_SCHEMA

    managed = is_managed()
    platforms = []
    for platform_enum, schema in PLATFORM_SCHEMA.items():
        if not schema.get("configurable", True):
            continue
        fields = []
        configured = False
        for field_def in schema["fields"]:
            raw_value = get_env_value(field_def["name"]) or ""
            if field_def["type"] == "password" and raw_value:
                display_value = redact_secret(raw_value)
            else:
                display_value = raw_value
            if raw_value and field_def.get("required"):
                configured = True
            fields.append({**field_def, "value": display_value})
        platforms.append({
            "id": platform_enum.value,
            "display_name": schema["display_name"],
            "fields": fields,
            "configured": configured,
            "test_supported": schema.get("test_supported", False),
        })

    return aiohttp_jinja2.render_template("settings/_platforms.html", request, {
        "platforms": platforms,
        "managed": managed,
        "flash": flash,
    })


async def handle_platforms_tab(request: "web.Request") -> "web.Response":
    """GET /settings/platforms — render the platform configuration tab."""
    return _render_platforms(request)
