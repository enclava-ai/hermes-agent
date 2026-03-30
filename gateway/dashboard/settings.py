"""
Dashboard settings handlers — LLM configuration and system prompt (SOUL.md).

Provides GET/POST handlers for:
- /settings/llm — provider, API key, model, temperature, max tokens
- /settings/llm/save — persist LLM config to config.yaml and .env
- /settings/soul/save — persist SOUL.md content

All hermes_cli imports are deferred inside function bodies to avoid
import-time failures when the CLI package is unavailable.
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import aiohttp_jinja2
    from aiohttp import web
except ImportError:
    pass


# --- SOUL.md helpers ---

def read_soul_md() -> str:
    """Read ~/.hermes/SOUL.md content, returning empty string if missing."""
    from hermes_constants import get_hermes_home
    soul_path = Path(get_hermes_home()) / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    return ""


def write_soul_md(content: str) -> None:
    """Write content to ~/.hermes/SOUL.md."""
    from hermes_constants import get_hermes_home
    soul_path = Path(get_hermes_home()) / "SOUL.md"
    soul_path.write_text(content, encoding="utf-8")


# --- Internal render helper ---

def _render_llm(request: "web.Request", flash: Optional[str] = None) -> "web.Response":
    """Build LLM tab context and render the template.

    Used by both GET and POST handlers to avoid duplication.
    Returns a synchronous render_template call (do NOT await).
    """
    from hermes_cli.config import load_config, is_managed, get_env_value
    from hermes_cli.auth import PROVIDER_REGISTRY
    from gateway.dashboard.auth import redact_secret

    config = load_config()

    # Parse model string: "provider/model-name"
    model_str = config.get("model", "")
    provider, _, model_name = model_str.partition("/")

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

    # Get current API key (redacted) for the active provider
    api_key_env_var = ""
    api_key_display = ""
    registry_entry = PROVIDER_REGISTRY.get(provider)
    if registry_entry and registry_entry.api_key_env_vars:
        api_key_env_var = registry_entry.api_key_env_vars[0]
        raw_key = get_env_value(api_key_env_var)
        if raw_key:
            api_key_display = redact_secret(raw_key)

    # Read agent settings with safe defaults
    agent_cfg = config.get("agent", {})
    temperature = agent_cfg.get("temperature", "")
    max_tokens = agent_cfg.get("max_tokens", "")

    managed = is_managed()

    context = {
        "provider": provider,
        "model_name": model_name,
        "api_key_display": api_key_display,
        "api_key_env_var": api_key_env_var,
        "providers": providers,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "managed": managed,
        "soul_content": read_soul_md(),
        "flash": flash,
    }

    return aiohttp_jinja2.render_template("settings/_llm.html", request, context)


# --- HTTP handlers ---

async def handle_llm_tab(request: "web.Request") -> "web.Response":
    """GET /settings/llm — render the LLM configuration tab."""
    return _render_llm(request)


async def handle_llm_save(request: "web.Request") -> "web.Response":
    """POST /settings/llm/save — persist LLM settings."""
    from hermes_cli.config import load_config, save_config, is_managed, save_env_value

    if is_managed():
        return _render_llm(
            request,
            flash="error:Configuration is managed by NixOS/Enclava. Changes must be made through your system configuration.",
        )

    data = await request.post()

    async with request.app["config_lock"]:
        config = load_config()

        provider = data.get("provider", "").strip()
        model_name = data.get("model_name", "").strip()

        if provider and model_name:
            config["model"] = f"{provider}/{model_name}"
        elif model_name:
            config["model"] = model_name

        temperature = data.get("temperature", "").strip()
        if temperature:
            try:
                config.setdefault("agent", {})["temperature"] = float(temperature)
            except ValueError:
                logger.debug("Invalid temperature value: %s", temperature)

        max_tokens_str = data.get("max_tokens", "").strip()
        if max_tokens_str:
            try:
                config.setdefault("agent", {})["max_tokens"] = int(max_tokens_str)
            except ValueError:
                logger.debug("Invalid max_tokens value: %s", max_tokens_str)

        save_config(config)

    # Handle API key separately (outside lock — save_env_value has its own atomicity)
    api_key = data.get("api_key", "").strip()
    api_key_env_var = data.get("api_key_env_var", "").strip()
    if api_key and "***" not in api_key and api_key_env_var:
        save_env_value(api_key_env_var, api_key)

    return _render_llm(request, flash="success:LLM settings saved.")


async def handle_soul_save(request: "web.Request") -> "web.Response":
    """POST /settings/soul/save — persist SOUL.md content."""
    from hermes_cli.config import is_managed

    if is_managed():
        return _render_llm(
            request,
            flash="error:Configuration is managed by NixOS/Enclava. Changes must be made through your system configuration.",
        )

    data = await request.post()
    soul_content = data.get("soul_content", "")
    write_soul_md(soul_content)

    return _render_llm(request, flash="success:System prompt saved.")
