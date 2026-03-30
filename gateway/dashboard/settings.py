"""
Dashboard settings handlers — LLM, General, and Status tabs.

Provides GET/POST handlers for:
- /settings/llm — provider, API key, model, temperature, max tokens
- /settings/llm/save — persist LLM config to config.yaml and .env
- /settings/soul/save — persist SOUL.md content
- /settings/general — memory, streaming, compression toggles + toolset checkboxes
- /settings/general/save — persist general settings to config.yaml
- /settings/status — read-only status overview (model, gateway, platforms)

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


# --- General settings handlers ---

async def handle_general_tab(request: "web.Request") -> "web.Response":
    """GET /settings/general — render the General configuration tab."""
    from hermes_cli.config import load_config, is_managed
    from toolsets import get_all_toolsets

    config = load_config()

    memory_enabled = config.get("memory", {}).get("memory_enabled", True)
    streaming = config.get("display", {}).get("streaming", False)
    compression_enabled = config.get("compression", {}).get("enabled", True)
    compression_threshold = config.get("compression", {}).get("threshold", 0.50)
    skin = config.get("display", {}).get("skin", "default")
    current_toolsets = config.get("toolsets", ["hermes-cli"])

    all_toolsets = get_all_toolsets()
    toolset_list = [
        {"name": name, "enabled": name in current_toolsets}
        for name in sorted(all_toolsets)
    ]

    managed = is_managed()

    context = {
        "memory_enabled": memory_enabled,
        "streaming": streaming,
        "compression_enabled": compression_enabled,
        "compression_threshold": compression_threshold,
        "skin": skin,
        "all_toolsets": toolset_list,
        "managed": managed,
        "flash": None,
    }

    return aiohttp_jinja2.render_template("settings/_general.html", request, context)


async def handle_general_save(request: "web.Request") -> "web.Response":
    """POST /settings/general/save — persist general settings."""
    from hermes_cli.config import load_config, save_config, is_managed
    from toolsets import get_all_toolsets

    if is_managed():
        return aiohttp_jinja2.render_template(
            "settings/_general.html",
            request,
            {"flash": "error:Configuration is managed by NixOS/Enclava.", "managed": True,
             "memory_enabled": True, "streaming": False, "compression_enabled": True,
             "compression_threshold": 0.50, "skin": "default", "all_toolsets": []},
        )

    data = await request.post()

    async with request.app["config_lock"]:
        config = load_config()

        config.setdefault("memory", {})["memory_enabled"] = "memory_enabled" in data
        config.setdefault("display", {})["streaming"] = "streaming" in data
        config.setdefault("compression", {})["enabled"] = "compression_enabled" in data

        threshold = data.get("compression_threshold", "").strip()
        if threshold:
            try:
                config.setdefault("compression", {})["threshold"] = float(threshold)
            except ValueError:
                logger.debug("Invalid compression threshold: %s", threshold)

        config.setdefault("display", {})["skin"] = data.get("skin", "default").strip()

        all_toolsets = get_all_toolsets()
        enabled = [name for name in all_toolsets if data.get(f"toolset_{name}")]
        config["toolsets"] = enabled

        save_config(config)

    # Re-render with updated values
    current_toolsets = config.get("toolsets", [])
    toolset_list = [
        {"name": name, "enabled": name in current_toolsets}
        for name in sorted(all_toolsets)
    ]

    context = {
        "memory_enabled": config.get("memory", {}).get("memory_enabled", True),
        "streaming": config.get("display", {}).get("streaming", False),
        "compression_enabled": config.get("compression", {}).get("enabled", True),
        "compression_threshold": config.get("compression", {}).get("threshold", 0.50),
        "skin": config.get("display", {}).get("skin", "default"),
        "all_toolsets": toolset_list,
        "managed": False,
        "flash": "success:General settings saved.",
    }

    return aiohttp_jinja2.render_template("settings/_general.html", request, context)


# --- Status tab handler ---

async def handle_status_tab(request: "web.Request") -> "web.Response":
    """GET /settings/status — read-only status overview with HTMX polling."""
    from hermes_cli.config import load_config

    config = load_config()
    runner = request.app.get("gateway_runner")

    platforms_status = []
    if runner is not None and hasattr(runner, "adapters"):
        for platform, adapter in runner.adapters.items():
            platforms_status.append({
                "name": platform.value,
                "connected": adapter.is_connected,
                "has_error": adapter.has_fatal_error,
                "error": adapter.fatal_error_message,
            })

    context = {
        "model": config.get("model", "not configured"),
        "platforms": platforms_status,
        "gateway_running": runner is not None,
    }

    return aiohttp_jinja2.render_template("settings/_status.html", request, context)
