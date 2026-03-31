"""
Dashboard onboarding wizard -- multi-step first-run setup flow.

Provides a 3-step wizard: LLM Setup, Platform Connection, Summary.
Draft state persists in app["wizard_drafts"] dict (keyed by session token)
and ~/.hermes/.wizard_draft.json on disk. Config is applied atomically
on wizard completion (D-13) -- no incremental writes during steps.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import aiohttp_jinja2
    from aiohttp import web
except ImportError:
    pass


WIZARD_STEPS = [
    {"number": 1, "name": "LLM Setup", "template": "wizard/_step_llm.html"},
    {"number": 2, "name": "Platform Connection", "template": "wizard/_step_platform.html"},
    {"number": 3, "name": "Summary", "template": "wizard/_step_summary.html"},
]

_DEFAULT_DRAFT = {
    "current_step": 1,
    "completed_steps": [],
    "llm": {},
    "platform": {},
    "platform_env": {},
}


# ---------------------------------------------------------------------------
# Draft persistence (D-11, D-12)
# ---------------------------------------------------------------------------

def _draft_file_path() -> Path:
    from hermes_constants import get_hermes_home
    return Path(get_hermes_home()) / ".wizard_draft.json"


def _load_draft_from_disk() -> Optional[dict]:
    """Read wizard draft from disk. Returns None if missing or invalid."""
    path = _draft_file_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Could not load wizard draft from disk: %s", e)
        return None


def _save_draft_to_disk(draft: dict) -> None:
    """Persist wizard draft to disk for crash resilience."""
    try:
        _draft_file_path().write_text(
            json.dumps(draft, indent=2), encoding="utf-8"
        )
    except OSError as e:
        logger.debug("Could not save wizard draft to disk: %s", e)


def _get_draft(request: "web.Request") -> dict:
    """Load draft from app dict (keyed by session cookie), falling back to disk."""
    drafts = request.app.setdefault("wizard_drafts", {})
    session_key = request.cookies.get("hermes_dash_session", "")
    draft = drafts.get(session_key)
    if draft is not None:
        return draft
    draft = _load_draft_from_disk()
    if draft is not None:
        drafts[session_key] = draft
        return draft
    return dict(_DEFAULT_DRAFT, completed_steps=[])


def _save_draft(request: "web.Request", draft: dict) -> None:
    """Store draft in app dict and persist to disk."""
    drafts = request.app.setdefault("wizard_drafts", {})
    session_key = request.cookies.get("hermes_dash_session", "")
    drafts[session_key] = draft
    _save_draft_to_disk(draft)


def _delete_draft(request: "web.Request") -> None:
    """Remove draft from app dict and unlink disk file."""
    drafts = request.app.setdefault("wizard_drafts", {})
    session_key = request.cookies.get("hermes_dash_session", "")
    drafts.pop(session_key, None)
    _draft_file_path().unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Wizard rendering helper
# ---------------------------------------------------------------------------

def _render_wizard_step(
    request: "web.Request",
    step_number: int,
    draft: dict,
    flash: Optional[str] = None,
) -> "web.Response":
    """Render the wizard page at the given step number.

    Builds step-specific context and returns the full wizard.html template.
    HTMX fragments select the parts they need via hx-select.
    """
    step_info = WIZARD_STEPS[step_number - 1]

    context = {
        "steps": WIZARD_STEPS,
        "current_step": step_number,
        "step_template": step_info["template"],
        "completed_steps": draft.get("completed_steps", []),
        "flash": flash,
        "wizard_mode": True,
    }

    if step_number == 1:
        context.update(_build_llm_context(draft))
    elif step_number == 2:
        context.update(_build_platform_context(request, draft))
    elif step_number == 3:
        context.update(_build_summary_context(draft))

    return aiohttp_jinja2.render_template("wizard.html", request, context)


def _build_llm_context(draft: dict) -> dict:
    """Build LLM form context, populating from draft first then config fallback."""
    from hermes_cli.config import load_config, get_env_value
    from hermes_cli.auth import PROVIDER_REGISTRY
    from gateway.dashboard.auth import redact_secret

    config = load_config()
    llm_draft = draft.get("llm", {})

    # Parse model config — supports both dict and string formats
    model_cfg = config.get("model", "")
    if isinstance(model_cfg, dict):
        cfg_provider = model_cfg.get("provider", "")
        cfg_model_name = model_cfg.get("default", "")
    else:
        cfg_provider, _, cfg_model_name = str(model_cfg).partition("/")

    provider = llm_draft.get("provider") or cfg_provider
    model_name = llm_draft.get("model_name") or cfg_model_name

    # Build provider list for dropdown
    providers = []
    for pid, pconfig in PROVIDER_REGISTRY.items():
        env_var = pconfig.api_key_env_vars[0] if pconfig.api_key_env_vars else ""
        providers.append({
            "name": pid,
            "display_name": pconfig.name,
            "auth_type": pconfig.auth_type,
            "env_var": env_var,
        })

    # Resolve API key env var and display value
    api_key_env_var = llm_draft.get("api_key_env_var", "")
    if not api_key_env_var:
        registry_entry = PROVIDER_REGISTRY.get(provider)
        if registry_entry and registry_entry.api_key_env_vars:
            api_key_env_var = registry_entry.api_key_env_vars[0]

    api_key_display = ""
    if llm_draft.get("api_key") and "***" not in llm_draft["api_key"]:
        api_key_display = redact_secret(llm_draft["api_key"])
    elif api_key_env_var:
        raw_key = get_env_value(api_key_env_var)
        if raw_key:
            api_key_display = redact_secret(raw_key)

    # Agent settings
    agent_cfg = config.get("agent", {})
    temperature = llm_draft.get("temperature") or agent_cfg.get("temperature", "")
    max_tokens = llm_draft.get("max_tokens") or agent_cfg.get("max_tokens", "")

    return {
        "provider": provider,
        "model_name": model_name,
        "api_key_display": api_key_display,
        "api_key_env_var": api_key_env_var,
        "providers": providers,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _build_platform_context(request: "web.Request", draft: dict) -> dict:
    """Build platform card grid context for wizard step 2."""
    from hermes_cli.config import get_env_value
    from gateway.dashboard.auth import redact_secret
    from .platform_schema import PLATFORM_SCHEMA

    platform_draft = draft.get("platform", {})

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

    return {
        "platforms": platforms,
        "selected_platform": platform_draft.get("selected"),
        "platform_test_passed": platform_draft.get("test_passed", False),
    }


def _build_summary_context(draft: dict) -> dict:
    """Build summary context from wizard draft."""
    llm = draft.get("llm", {})
    platform = draft.get("platform", {})

    # Resolve display name for selected platform
    platform_name = platform.get("selected", "")
    if platform_name:
        try:
            from .platform_schema import PLATFORM_SCHEMA
            from gateway.config import Platform
            schema = PLATFORM_SCHEMA.get(Platform(platform_name))
            if schema:
                platform_name = schema["display_name"]
        except (ValueError, ImportError):
            pass

    return {
        "llm_provider": llm.get("provider", ""),
        "llm_model": llm.get("model_name", ""),
        "llm_temperature": llm.get("temperature", ""),
        "llm_max_tokens": llm.get("max_tokens", ""),
        "platform_name": platform_name,
        "platform_test_passed": platform.get("test_passed", False),
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_wizard(request: "web.Request") -> "web.Response":
    """GET /wizard -- render the wizard at the current draft step."""
    draft = _get_draft(request)
    current_step = draft.get("current_step", 1)
    return _render_wizard_step(request, current_step, draft)


async def handle_wizard_step(request: "web.Request") -> "web.Response":
    """GET and POST /wizard/step/{n} -- step navigation with validation."""
    n = int(request.match_info["n"])
    n = max(1, min(3, n))

    draft = _get_draft(request)

    # GET = back navigation -- just render the step from draft
    if request.method == "GET":
        draft["current_step"] = n
        _save_draft(request, draft)
        return _render_wizard_step(request, n, draft)

    # POST = forward navigation with validation
    data = await request.post()

    if n == 1:
        # Step 1: validate provider + API key
        provider = data.get("provider", "").strip()
        api_key = data.get("api_key", "").strip()
        api_key_env_var = data.get("api_key_env_var", "").strip()
        model_name = data.get("model_name", "").strip()
        temperature = data.get("temperature", "").strip()
        max_tokens = data.get("max_tokens", "").strip()

        # Check if api_key is just redaction markers -- fall back to saved value
        has_real_key = bool(api_key and "***" not in api_key)
        if not has_real_key and api_key_env_var:
            from hermes_cli.config import get_env_value
            has_real_key = bool(get_env_value(api_key_env_var))

        if not provider or not has_real_key:
            return _render_wizard_step(
                request, 1, draft,
                flash="error:Please provide a provider and API key to continue.",
            )

        # Store in draft
        draft["llm"] = {
            "provider": provider,
            "model_name": model_name,
            "api_key": api_key,
            "api_key_env_var": api_key_env_var,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        completed = draft.get("completed_steps", [])
        if 1 not in completed:
            completed.append(1)
        draft["completed_steps"] = completed
        draft["current_step"] = 2
        _save_draft(request, draft)
        return _render_wizard_step(request, 2, draft)

    elif n == 2:
        # Step 2: validate test passed
        if not draft.get("platform", {}).get("test_passed"):
            return _render_wizard_step(
                request, 2, draft,
                flash="error:Please test at least one platform connection before continuing.",
            )

        completed = draft.get("completed_steps", [])
        if 2 not in completed:
            completed.append(2)
        draft["completed_steps"] = completed
        draft["current_step"] = 3
        _save_draft(request, draft)
        return _render_wizard_step(request, 3, draft)

    else:
        # Step 3: no validation, just render
        return _render_wizard_step(request, 3, draft)


async def handle_wizard_test(request: "web.Request") -> "web.Response":
    """POST /wizard/test/{platform} -- test platform connection in wizard context."""
    from .platforms import _TEST_HANDLERS
    from hermes_cli.config import get_env_value
    from .platform_schema import PLATFORM_SCHEMA

    platform_id = request.match_info["platform"]
    handler = _TEST_HANDLERS.get(platform_id)

    draft = _get_draft(request)

    if not handler:
        return _render_wizard_step(
            request, 2, draft,
            flash=f"error:Test not supported for {platform_id}",
        )

    data = await request.post()
    form_data = {key: val for key, val in data.items()}

    # For password fields: fall back to saved env value if empty
    try:
        from gateway.config import Platform
        platform_enum = Platform(platform_id)
        schema = PLATFORM_SCHEMA.get(platform_enum, {})
        for field_def in schema.get("fields", []):
            if field_def["type"] == "password" and not form_data.get(field_def["name"]):
                saved = get_env_value(field_def["name"])
                if saved:
                    form_data[field_def["name"]] = saved
    except (ValueError, ImportError):
        pass

    try:
        ok, message = await handler(form_data)
        if ok:
            draft["platform"] = {
                "selected": platform_id,
                "test_passed": True,
            }
            # Store all form field values for later config application
            draft["platform_env"] = {
                k: v for k, v in form_data.items() if v
            }
            _save_draft(request, draft)
            flash = f"success:{message}"
        else:
            draft["platform"]["test_passed"] = False
            _save_draft(request, draft)
            flash = f"error:{message}"
    except Exception as e:
        logger.debug("Wizard test connection failed for %s: %s", platform_id, e)
        flash = f"error:Connection failed: {e}"

    return _render_wizard_step(request, 2, draft, flash=flash)


async def handle_wizard_complete(request: "web.Request") -> "web.Response":
    """POST /wizard/complete -- apply config atomically and redirect to dashboard."""
    draft = _get_draft(request)

    # Apply config atomically under config_lock (D-13)
    async with request.app["config_lock"]:
        from hermes_cli.config import load_config, save_config
        config = load_config()

        llm = draft.get("llm", {})
        if llm.get("provider") and llm.get("model_name"):
            model_cfg = config.get("model", {})
            if not isinstance(model_cfg, dict):
                model_cfg = {}
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

    # Save API key to .env (outside lock -- save_env_value has its own atomicity)
    from hermes_cli.config import save_env_value

    if llm.get("api_key") and "***" not in llm["api_key"] and llm.get("api_key_env_var"):
        save_env_value(llm["api_key_env_var"], llm["api_key"])

    # Save platform env vars from draft
    for key, value in draft.get("platform_env", {}).items():
        if value and "***" not in value:
            save_env_value(key, value)

    # Delete draft and redirect
    _delete_draft(request)
    logger.info("Wizard completed — config applied")
    raise web.HTTPFound("/dashboard/")
