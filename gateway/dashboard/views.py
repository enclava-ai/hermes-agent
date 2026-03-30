"""Dashboard view handlers (non-auth pages)."""
import logging

logger = logging.getLogger(__name__)

try:
    import aiohttp_jinja2
    from aiohttp import web
except ImportError:
    pass


async def handle_index(request: "web.Request") -> "web.Response":
    """GET / -- dashboard home, with first-time wizard redirect (D-01, D-12).

    Detection: if config has no model key (or empty), user is first-time.
    Also checks for abandoned wizard draft (D-12) -- resumes at last step.
    Password change (D-02) runs before this handler via auth middleware.
    """
    from hermes_cli.config import load_config

    config = load_config()
    model = config.get("model", "")

    if not model:
        # First-time user or abandoned wizard -- redirect to wizard
        raise web.HTTPFound("/dashboard/wizard")

    # Also check for abandoned draft (D-12): if draft exists and config
    # still lacks a fully configured model, redirect back to wizard
    from gateway.dashboard.wizard import _load_draft_from_disk
    draft = _load_draft_from_disk()
    if draft and not model:
        raise web.HTTPFound("/dashboard/wizard")

    return aiohttp_jinja2.render_template("index.html", request, {})
