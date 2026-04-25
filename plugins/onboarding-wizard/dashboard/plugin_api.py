"""Onboarding wizard plugin — backend routes.

Mounted by upstream's web_server at /api/plugins/onboarding-wizard/.

Owns three concerns only:
  1. Wizard draft state (persisted to ~/.hermes/.wizard_draft.json)
  2. Platform connection-test handlers (lightweight HTTP probes)
  3. Atomic apply of LLM + platform configuration on completion

Everything else (config reads, env reads, redaction, provider registry) is
delegated to upstream's hermes_cli helpers so this plugin survives upstream
internals churn as long as those public-ish helpers stay stable.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Plugin lives at <repo>/plugins/onboarding-wizard/dashboard/plugin_api.py.
# Make sure repo root is on sys.path so we can import hermes_cli/gateway.
_PLUGIN_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PLUGIN_DIR.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Local module (sibling) — keep its import path stable inside the plugin.
sys.path.insert(0, str(_PLUGIN_DIR))
from platform_schema import PLATFORM_SCHEMA  # noqa: E402

from gateway.config import Platform  # noqa: E402
from hermes_cli.auth import PROVIDER_REGISTRY  # noqa: E402
from hermes_cli.config import (  # noqa: E402
    get_env_value,
    is_managed,
    load_config,
    redact_key,
    save_config,
    save_env_value,
)
from hermes_constants import get_hermes_home  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Draft persistence
# ---------------------------------------------------------------------------

_DEFAULT_DRAFT: Dict[str, Any] = {
    "current_step": 1,
    "completed_steps": [],
    "llm": {},
    "platform": {},
    "platform_env": {},
}


def _draft_path() -> Path:
    return Path(get_hermes_home()) / ".wizard_draft.json"


def _load_draft() -> Dict[str, Any]:
    try:
        return json.loads(_draft_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_DRAFT, completed_steps=[])


def _save_draft(draft: Dict[str, Any]) -> None:
    try:
        _draft_path().write_text(json.dumps(draft, indent=2), encoding="utf-8")
    except OSError as e:
        logger.debug("wizard: could not persist draft: %s", e)


def _clear_draft() -> None:
    _draft_path().unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Bootstrap context (LLM step)
# ---------------------------------------------------------------------------


def _build_llm_context(draft: Dict[str, Any]) -> Dict[str, Any]:
    """LLM step initial state — populates from draft, then current config."""
    config = load_config()
    llm_draft = draft.get("llm", {})

    model_cfg = config.get("model", "")
    if isinstance(model_cfg, dict):
        cfg_provider = model_cfg.get("provider", "")
        cfg_model_name = model_cfg.get("default", "")
    else:
        cfg_provider, _, cfg_model_name = str(model_cfg).partition("/")

    provider = llm_draft.get("provider") or cfg_provider
    model_name = llm_draft.get("model_name") or cfg_model_name

    providers = []
    for pid, pconfig in PROVIDER_REGISTRY.items():
        env_var = pconfig.api_key_env_vars[0] if pconfig.api_key_env_vars else ""
        providers.append({
            "name": pid,
            "display_name": pconfig.name,
            "auth_type": pconfig.auth_type,
            "env_var": env_var,
        })

    api_key_env_var = llm_draft.get("api_key_env_var", "")
    if not api_key_env_var:
        registry_entry = PROVIDER_REGISTRY.get(provider)
        if registry_entry and registry_entry.api_key_env_vars:
            api_key_env_var = registry_entry.api_key_env_vars[0]

    api_key_display = ""
    if llm_draft.get("api_key") and "***" not in llm_draft["api_key"]:
        api_key_display = redact_key(llm_draft["api_key"])
    elif api_key_env_var:
        raw_key = get_env_value(api_key_env_var)
        if raw_key:
            api_key_display = redact_key(raw_key)

    agent_cfg = config.get("agent", {})
    return {
        "provider": provider,
        "model_name": model_name,
        "api_key_display": api_key_display,
        "api_key_env_var": api_key_env_var,
        "providers": providers,
        "temperature": llm_draft.get("temperature") or agent_cfg.get("temperature", ""),
        "max_tokens": llm_draft.get("max_tokens") or agent_cfg.get("max_tokens", ""),
    }


def _build_platforms_context(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Platform card grid initial state."""
    platform_draft = draft.get("platform", {})
    platforms = []
    for platform_enum, schema in PLATFORM_SCHEMA.items():
        if not schema.get("configurable", True):
            continue
        fields = []
        configured = False
        for field_def in schema["fields"]:
            raw_value = get_env_value(field_def["name"]) or ""
            display_value = redact_key(raw_value) if (
                field_def["type"] == "password" and raw_value
            ) else raw_value
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
    return {
        "platforms": platforms,
        "selected_platform": platform_draft.get("selected"),
        "platform_test_passed": platform_draft.get("test_passed", False),
    }


# ---------------------------------------------------------------------------
# Platform connection-test handlers (lightweight httpx probes)
# ---------------------------------------------------------------------------


async def _test_telegram(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    token = form.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False, "Bot token is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        data = resp.json()
        if data.get("ok"):
            return True, f"Connected as @{data['result'].get('username', 'unknown')}"
        return False, data.get("description", "Invalid token")


async def _test_discord(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    token = form.get("DISCORD_BOT_TOKEN", "")
    if not token:
        return False, "Bot token is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bot {token}"},
        )
        if resp.status_code == 200:
            return True, f"Connected as {resp.json().get('username', 'unknown')}"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_slack(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    token = form.get("SLACK_BOT_TOKEN", "")
    if not token:
        return False, "Bot token is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        if data.get("ok"):
            return True, f"Connected as {data.get('bot_id', 'unknown')} in {data.get('team', 'unknown')}"
        return False, data.get("error", "Auth failed")


async def _test_mattermost(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    url = form.get("MATTERMOST_URL", "").rstrip("/")
    token = form.get("MATTERMOST_TOKEN", "")
    if not url or not token:
        return False, "URL and token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{url}/api/v4/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return True, f"Connected as {resp.json().get('username', 'unknown')}"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_matrix(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    homeserver = form.get("MATRIX_HOMESERVER", "").rstrip("/")
    token = form.get("MATRIX_ACCESS_TOKEN", "")
    if not homeserver or not token:
        return False, "Homeserver URL and access token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{homeserver}/_matrix/client/v3/account/whoami",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return True, f"Connected as {resp.json().get('user_id', 'unknown')}"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_signal(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    http_url = form.get("SIGNAL_HTTP_URL", "").rstrip("/")
    if not http_url:
        return False, "Signal HTTP URL is required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{http_url}/api/v1/check")
        if resp.status_code == 200:
            return True, "Signal CLI REST API is reachable"
        return False, f"HTTP {resp.status_code}: not reachable"


async def _test_homeassistant(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    url = form.get("HASS_URL", "").rstrip("/")
    token = form.get("HASS_TOKEN", "")
    if not url or not token:
        return False, "URL and token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{url}/api/",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return True, "Home Assistant API is reachable"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"


async def _test_email(form: Dict[str, str]) -> tuple[bool, str]:
    import imaplib
    import ssl
    host = form.get("EMAIL_IMAP_HOST", "")
    address = form.get("EMAIL_ADDRESS", "")
    password = form.get("EMAIL_PASSWORD", "")
    if not host or not address or not password:
        return False, "Email address, password, and IMAP host are required"
    port = int(form.get("EMAIL_IMAP_PORT", "") or "993")
    try:
        ctx = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(host, port, ssl_context=ctx, timeout=10)
        imap.login(address, password)
        imap.logout()
        return True, f"IMAP login successful as {address}"
    except Exception as e:
        return False, f"IMAP connection failed: {e}"


async def _test_sms(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    sid = form.get("TWILIO_ACCOUNT_SID", "")
    auth_token = form.get("TWILIO_AUTH_TOKEN", "")
    if not sid or not auth_token:
        return False, "Account SID and auth token are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
            auth=(sid, auth_token),
        )
        if resp.status_code == 200:
            return True, f"Connected to Twilio account {resp.json().get('friendly_name', sid[:8])}"
        return False, f"HTTP {resp.status_code}: authentication failed"


async def _test_dingtalk(form: Dict[str, str]) -> tuple[bool, str]:
    import httpx
    client_id = form.get("DINGTALK_CLIENT_ID", "")
    client_secret = form.get("DINGTALK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return False, "Client ID and secret are required"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken",
            json={"appKey": client_id, "appSecret": client_secret},
        )
        data = resp.json()
        if data.get("accessToken"):
            return True, "DingTalk credentials are valid"
        return False, data.get("message", "Auth failed")


_TEST_HANDLERS: Dict[str, Callable[[Dict[str, str]], Awaitable[tuple[bool, str]]]] = {
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
# Pydantic request schemas
# ---------------------------------------------------------------------------


class LlmStepInput(BaseModel):
    provider: str
    model_name: str = ""
    api_key: str = ""
    api_key_env_var: str = ""
    temperature: str = ""
    max_tokens: str = ""


class TestRequest(BaseModel):
    platform: str
    form_data: Dict[str, str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/state")
async def get_state() -> Dict[str, Any]:
    """Return wizard draft state plus the rendering context for all steps.

    Single round-trip on page load — frontend stays mostly static after.
    """
    draft = _load_draft()
    return {
        "draft": draft,
        "managed": is_managed(),
        "llm": _build_llm_context(draft),
        "platforms": _build_platforms_context(draft),
    }


@router.post("/llm")
async def submit_llm(payload: LlmStepInput) -> Dict[str, Any]:
    """Save Step 1 (LLM provider). Validates that creds are available."""
    has_real_key = bool(payload.api_key and "***" not in payload.api_key)
    if not has_real_key and payload.api_key_env_var:
        has_real_key = bool(get_env_value(payload.api_key_env_var))
    if not payload.provider or not has_real_key:
        raise HTTPException(
            status_code=422,
            detail="Provider and API key are required.",
        )

    draft = _load_draft()
    draft["llm"] = payload.model_dump()
    completed = draft.get("completed_steps", [])
    if 1 not in completed:
        completed.append(1)
    draft["completed_steps"] = completed
    draft["current_step"] = 2
    _save_draft(draft)
    return {"ok": True, "draft": draft}


@router.post("/test")
async def test_platform(payload: TestRequest) -> Dict[str, Any]:
    """Test platform connection. Falls back to saved env values for empty
    password fields so the user doesn't have to re-enter secrets."""
    handler = _TEST_HANDLERS.get(payload.platform)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Test not supported for {payload.platform}")

    form_data = dict(payload.form_data)
    try:
        platform_enum = Platform(payload.platform)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown platform {payload.platform}")
    schema = PLATFORM_SCHEMA.get(platform_enum, {})
    for field_def in schema.get("fields", []):
        if field_def["type"] == "password" and not form_data.get(field_def["name"]):
            saved = get_env_value(field_def["name"])
            if saved:
                form_data[field_def["name"]] = saved

    try:
        ok, message = await handler(form_data)
    except Exception as e:  # noqa: BLE001 — surface the error to the UI
        logger.debug("wizard test failed for %s: %s", payload.platform, e)
        return {"ok": False, "message": f"Connection failed: {e}"}

    draft = _load_draft()
    if ok:
        draft["platform"] = {"selected": payload.platform, "test_passed": True}
        draft["platform_env"] = {k: v for k, v in form_data.items() if v}
        completed = draft.get("completed_steps", [])
        if 2 not in completed:
            completed.append(2)
        draft["completed_steps"] = completed
        _save_draft(draft)
    else:
        draft.setdefault("platform", {})["test_passed"] = False
        _save_draft(draft)

    return {"ok": ok, "message": message, "draft": draft}


@router.post("/complete")
async def complete_wizard() -> Dict[str, Any]:
    """Apply the draft atomically: write config + env, clear draft."""
    draft = _load_draft()
    llm = draft.get("llm", {})

    config = load_config()
    if llm.get("provider") and llm.get("model_name"):
        model_cfg = config.get("model", {}) if isinstance(config.get("model", {}), dict) else {}
        model_cfg["provider"] = llm["provider"]
        model_cfg["default"] = llm["model_name"]
        config["model"] = model_cfg
    if llm.get("temperature"):
        try:
            config.setdefault("agent", {})["temperature"] = float(llm["temperature"])
        except ValueError:
            pass
    if llm.get("max_tokens"):
        try:
            config.setdefault("agent", {})["max_tokens"] = int(llm["max_tokens"])
        except ValueError:
            pass
    save_config(config)

    if llm.get("api_key") and "***" not in llm["api_key"] and llm.get("api_key_env_var"):
        save_env_value(llm["api_key_env_var"], llm["api_key"])
    for key, value in draft.get("platform_env", {}).items():
        if value and "***" not in value:
            save_env_value(key, value)

    _clear_draft()
    logger.info("wizard: configuration applied")
    return {"ok": True}


@router.post("/reset")
async def reset_draft() -> Dict[str, Any]:
    _clear_draft()
    return {"ok": True}
