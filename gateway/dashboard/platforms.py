"""
Dashboard platform configuration handler — Platforms tab.

Provides handlers for rendering the platform card grid, testing
connections, and saving platform credentials.

Test-connection handlers use lightweight httpx calls against each
platform's public API (not full SDKs). Secrets persist to .env via
save_env_value(); non-secrets also go to .env (they are env vars).

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


# ---------------------------------------------------------------------------
# Shared rendering helper
# ---------------------------------------------------------------------------

def _render_platforms(request: "web.Request", flash: Optional[str] = None) -> "web.Response":
    """Build platform card grid context and render the template.

    Used by GET handler and POST handlers to avoid duplication.
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


# ---------------------------------------------------------------------------
# Per-platform test-connection functions
# ---------------------------------------------------------------------------
# Each returns (success: bool, message: str).
# All use httpx with a 10-second timeout (deferred import).

async def _test_telegram(form_data: dict) -> tuple[bool, str]:
    import httpx
    token = form_data.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False, "Bot token is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        data = resp.json()
        if data.get("ok"):
            return True, f"Connected as @{data['result'].get('username', 'unknown')}"
        return False, data.get("description", "Invalid token")


async def _test_discord(form_data: dict) -> tuple[bool, str]:
    import httpx
    token = form_data.get("DISCORD_BOT_TOKEN", "")
    if not token:
        return False, "Bot token is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get("https://discord.com/api/v10/users/@me",
                                headers={"Authorization": f"Bot {token}"})
        if resp.status_code == 200:
            return True, f"Connected as {resp.json().get('username', 'unknown')}"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_slack(form_data: dict) -> tuple[bool, str]:
    import httpx
    token = form_data.get("SLACK_BOT_TOKEN", "")
    if not token:
        return False, "Bot token is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post("https://slack.com/api/auth.test",
                                 headers={"Authorization": f"Bearer {token}"})
        data = resp.json()
        if data.get("ok"):
            return True, f"Connected as {data.get('bot_id', 'unknown')} in {data.get('team', 'unknown')}"
        return False, data.get("error", "Auth failed")


async def _test_mattermost(form_data: dict) -> tuple[bool, str]:
    import httpx
    url = form_data.get("MATTERMOST_URL", "").rstrip("/")
    token = form_data.get("MATTERMOST_TOKEN", "")
    if not url or not token:
        return False, "URL and token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{url}/api/v4/users/me",
                                headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            return True, f"Connected as {resp.json().get('username', 'unknown')}"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_matrix(form_data: dict) -> tuple[bool, str]:
    import httpx
    homeserver = form_data.get("MATRIX_HOMESERVER", "").rstrip("/")
    token = form_data.get("MATRIX_ACCESS_TOKEN", "")
    if not homeserver or not token:
        return False, "Homeserver URL and access token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{homeserver}/_matrix/client/v3/account/whoami",
                                headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            return True, f"Connected as {resp.json().get('user_id', 'unknown')}"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_signal(form_data: dict) -> tuple[bool, str]:
    import httpx
    http_url = form_data.get("SIGNAL_HTTP_URL", "").rstrip("/")
    if not http_url:
        return False, "Signal HTTP URL is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{http_url}/api/v1/check")
        if resp.status_code == 200:
            return True, "Signal CLI REST API is reachable"
        return False, f"HTTP {resp.status_code}: not reachable"


async def _test_homeassistant(form_data: dict) -> tuple[bool, str]:
    import httpx
    url = form_data.get("HASS_URL", "").rstrip("/")
    token = form_data.get("HASS_TOKEN", "")
    if not url or not token:
        return False, "URL and token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{url}/api/",
                                headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            return True, "Home Assistant API is reachable"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_email(form_data: dict) -> tuple[bool, str]:
    """Test IMAP connectivity for email platform."""
    import httpx  # noqa: F401 — consistency; actual test uses imaplib
    import imaplib
    import ssl
    host = form_data.get("EMAIL_IMAP_HOST", "")
    address = form_data.get("EMAIL_ADDRESS", "")
    password = form_data.get("EMAIL_PASSWORD", "")
    if not host or not address or not password:
        return False, "Email address, password, and IMAP host are required"
    port = int(form_data.get("EMAIL_IMAP_PORT", "") or "993")
    try:
        ctx = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(host, port, ssl_context=ctx, timeout=10)
        imap.login(address, password)
        imap.logout()
        return True, f"IMAP login successful as {address}"
    except Exception as e:
        return False, f"IMAP connection failed: {e}"


async def _test_sms(form_data: dict) -> tuple[bool, str]:
    import httpx
    sid = form_data.get("TWILIO_ACCOUNT_SID", "")
    auth_token = form_data.get("TWILIO_AUTH_TOKEN", "")
    if not sid or not auth_token:
        return False, "Account SID and auth token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
                                auth=(sid, auth_token))
        if resp.status_code == 200:
            return True, f"Connected to Twilio account {resp.json().get('friendly_name', sid[:8])}"
        return False, f"HTTP {resp.status_code}: authentication failed"


async def _test_dingtalk(form_data: dict) -> tuple[bool, str]:
    import httpx
    client_id = form_data.get("DINGTALK_CLIENT_ID", "")
    client_secret = form_data.get("DINGTALK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return False, "Client ID and secret are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post("https://api.dingtalk.com/v1.0/oauth2/accessToken",
                                 json={"appKey": client_id, "appSecret": client_secret})
        data = resp.json()
        if data.get("accessToken"):
            return True, "DingTalk credentials are valid"
        return False, data.get("message", "Auth failed")


_TEST_HANDLERS = {
    "telegram": _test_telegram,
    "discord": _test_discord,
    "slack": _test_slack,
    "mattermost": _test_mattermost,
    "matrix": _test_matrix,
    "signal": _test_signal,
    "homeassistant": _test_homeassistant,
    "email": _test_email,
    "sms": _test_sms,
    "dingtalk": _test_dingtalk,
}


# ---------------------------------------------------------------------------
# Test and save route handlers
# ---------------------------------------------------------------------------

async def handle_platform_test(request: "web.Request") -> "web.Response":
    """POST /settings/platforms/{platform}/test — test connection with form-submitted values (D-10)."""
    platform_id = request.match_info["platform"]
    handler = _TEST_HANDLERS.get(platform_id)
    if not handler:
        return _render_platforms(request, flash=f"error:Test not supported for {platform_id}")

    data = await request.post()
    form_data = {key: val for key, val in data.items()}

    # For password fields: if the submitted value is empty, fall back to saved env value
    # (user didn't change it, so use existing). Prevents requiring re-entry of secrets.
    from hermes_cli.config import get_env_value
    from .platform_schema import PLATFORM_SCHEMA
    from gateway.config import Platform
    platform_enum = Platform(platform_id)
    schema = PLATFORM_SCHEMA.get(platform_enum, {})
    for field_def in schema.get("fields", []):
        if field_def["type"] == "password" and not form_data.get(field_def["name"]):
            saved = get_env_value(field_def["name"])
            if saved:
                form_data[field_def["name"]] = saved

    try:
        ok, message = await handler(form_data)
        flash = f"success:{message}" if ok else f"error:{message}"
    except Exception as e:
        logger.debug("Test connection failed for %s: %s", platform_id, e)
        flash = f"error:Connection failed: {e}"

    return _render_platforms(request, flash=flash)


async def handle_platform_save(request: "web.Request") -> "web.Response":
    """POST /settings/platforms/{platform}/save — persist platform config."""
    from hermes_cli.config import is_managed, save_env_value
    from .platform_schema import PLATFORM_SCHEMA
    from gateway.config import Platform

    platform_id = request.match_info["platform"]

    if is_managed():
        return _render_platforms(request, flash="error:Configuration is managed by NixOS/Enclava.")

    platform_enum = Platform(platform_id)
    schema = PLATFORM_SCHEMA.get(platform_enum)
    if not schema:
        return _render_platforms(request, flash=f"error:Unknown platform: {platform_id}")

    data = await request.post()

    async with request.app["config_lock"]:
        for field_def in schema["fields"]:
            value = data.get(field_def["name"], "").strip()
            if field_def["type"] == "password":
                # Skip if empty or contains redaction markers (Pitfall 3)
                if not value or "***" in value:
                    continue
                save_env_value(field_def["name"], value)
            else:
                # Non-secret values go to .env too (they're env vars)
                if value:
                    save_env_value(field_def["name"], value)
                # If empty and not required, clear the env var
                elif not field_def.get("required"):
                    save_env_value(field_def["name"], "")

    return _render_platforms(request, flash=f"success:{schema['display_name']} settings saved.")
