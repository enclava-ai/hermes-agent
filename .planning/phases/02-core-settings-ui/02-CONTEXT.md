# Phase 2: Core Settings UI - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can read and write LLM provider config and general agent settings through the dashboard, with atomic saves, secret redaction, and a live status overview. This phase establishes the config read/write/redact pattern that all subsequent settings sections (Phase 3: platforms, skills) will reuse.

</domain>

<decisions>
## Implementation Decisions

### Settings Page Layout
- **D-01:** Dashboard settings organized as a tabbed single page using HTMX tab switching. Tabs: "LLM", "General", "Status". No multi-page routing — keeps it simple and avoids new URL routes beyond `/dashboard/`.
- **D-02:** Each tab loads its content via HTMX `hx-get` to a backend endpoint (e.g., `/settings/llm`, `/settings/general`, `/settings/status`). Tab content is swapped into a target div without full page reload.

### Config Save UX
- **D-03:** Form submissions use HTMX `hx-post` with partial swap. A flash message (success/error) is shown inline after save — no full page reload.
- **D-04:** Save buttons are per-section (not one global save). Each section posts its own form independently.
- **D-05:** On managed-mode installs (`is_managed()` returns True), save buttons are disabled and a clear banner explains that config is managed by NixOS — satisfying success criterion 5.

### LLM Provider Configuration
- **D-06:** Single dropdown selects the LLM provider. Changing the dropdown reveals provider-specific fields (API key, base URL, model name, temperature, max tokens) via HTMX swap or JS show/hide.
- **D-07:** API key field uses `redact_secret()` for display. Submitting an empty or unchanged API key field does NOT overwrite the stored key. New keys are written to `~/.hermes/.env` via `save_env_value()`.
- **D-08:** Model name is a text input (not a fixed dropdown) since providers support many models. Temperature and max tokens use number inputs with sensible defaults.
- **D-09:** System prompt / persona is a textarea that reads from and writes to `config.yaml` under the `system_prompt` or `soul` key (researcher to confirm exact key path).

### General Settings
- **D-10:** General settings tab exposes toggles/inputs for: memory (on/off), streaming (on/off), compression (on/off + threshold), session reset policy, and display/skin settings.
- **D-11:** Each setting maps directly to a `config.yaml` key. `load_config()` populates form defaults; `save_config()` persists changes. The `app["config_lock"]` asyncio.Lock serializes concurrent writes.

### Status Overview
- **D-12:** Status tab shows: current LLM model name, list of configured platform adapters with connected/disconnected indicator, and gateway uptime.
- **D-13:** Status data is read-only — no forms on this tab. Data comes from `app["gateway_runner"]` reference (platform adapter status) and `load_config()` (current model).
- **D-14:** Status content refreshes via HTMX polling (`hx-trigger="every 30s"`) or manual refresh button — not WebSocket.

### Toolset Configuration
- **D-15:** Toolset availability (GENL-03) is a checklist of enabled/disabled toolsets. Maps to `config.yaml` `toolsets` key. Presented as checkboxes within the General tab.

### Claude's Discretion
- Tab styling and active state indicators — follow Pico CSS patterns
- Flash message styling and auto-dismiss timing
- Exact field ordering within each tab
- Whether temperature/max-tokens use sliders or plain number inputs
- Loading states while HTMX requests are in-flight

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Dashboard Foundation (Phase 1 code)
- `gateway/dashboard/__init__.py` — Subapp factory, route registration, config_lock creation. New settings routes added here.
- `gateway/dashboard/views.py` — Existing view handlers. Settings handlers go here or in a new `settings.py`.
- `gateway/dashboard/auth.py` — `redact_secret()` function for browser-safe secret display.
- `gateway/dashboard/templates/base.html` — Base template with HTMX error handler. Settings pages extend this.
- `gateway/dashboard/templates/index.html` — Current placeholder home page to be replaced with tabbed settings UI.

### Config System
- `hermes_cli/config.py` — `load_config()`, `save_config()`, `is_managed()`, `managed_error()`, `save_env_value()`, `redact_key()`, `get_config_path()`, `get_env_path()`. ALL config reads/writes must go through this module.
- `hermes_constants.py` — `get_hermes_home()` for resolving `~/.hermes/` path.

### Gateway Status
- `gateway/run.py` — `GatewayRunner` class. The `app["gateway_runner"]` reference provides access to platform adapter status for the status overview.
- `gateway/platforms/base.py` — `BasePlatformAdapter` ABC. Check what status/health methods adapters expose.
- `gateway/config.py` — `GatewayConfig`, `Platform` enum. Maps platform names to adapter classes.

### Prior Phase Context
- `.planning/phases/01-foundation-and-auth/01-CONTEXT.md` — Phase 1 decisions (subapp architecture, auth, secrets redaction pattern).

### Codebase Maps
- `.planning/codebase/CONVENTIONS.md` — Naming patterns, code style, error handling conventions.
- `.planning/codebase/STRUCTURE.md` — Directory layout, "where to add new code" guide.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gateway/dashboard/__init__.py:create_dashboard_app()` — Route registration point. New settings endpoints added here.
- `gateway/dashboard/auth.py:redact_secret()` — Browser-safe secret redaction, already tested.
- `gateway/dashboard/templates/base.html` — Base template with HTMX global error handler, Pico CSS, nav bar.
- `hermes_cli/config.py:load_config()` / `save_config()` — Full config read/write with atomic saves.
- `hermes_cli/config.py:save_env_value()` — Writes secrets to `~/.hermes/.env`.
- `hermes_cli/config.py:is_managed()` — Managed-mode detection for read-only banner.
- `app["config_lock"]` — asyncio.Lock already created in `__init__.py` for serializing config writes.
- `app["gateway_runner"]` — GatewayRunner reference already stored, provides platform adapter status.

### Established Patterns
- HTMX for interactivity with Pico CSS for styling — no custom JS frameworks.
- Auth middleware on dashboard subapp only — new routes automatically protected.
- Routes registered relative to mount point (no `/dashboard/` prefix in route definitions).
- `aiohttp_jinja2.template()` decorator for rendering templates.
- Optional dependency guard with `try/except ImportError` at module top.

### Integration Points
- `create_dashboard_app()` — Add new route registrations for settings endpoints.
- `gateway/dashboard/templates/` — Add new Jinja2 templates for settings tabs.
- `hermes_cli/config.py` — Import and use for all config operations (no direct YAML manipulation).

</code_context>

<specifics>
## Specific Ideas

- The tabbed UI on a single page establishes the pattern Phase 3 will follow for platforms and skills tabs.
- API keys must never round-trip through the browser — display redacted, write new values directly to `.env`.
- The `config_lock` was specifically created in Phase 1 anticipating this phase's concurrent save needs.
- `is_managed()` check satisfies success criterion 5 (managed-mode error display) with minimal code.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-core-settings-ui*
*Context gathered: 2026-03-30*
