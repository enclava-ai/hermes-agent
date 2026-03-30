# Phase 3: Platforms and Skills - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can configure platform connections (13+ adapters), test them inline from the dashboard, and enable or disable individual skills — all through new tabs in the existing tabbed settings UI. This phase adds "Platforms" and "Skills" tabs to the shell established in Phase 2.

</domain>

<decisions>
## Implementation Decisions

### New Tabs in Existing Shell
- **D-01:** Add two new tabs to the existing tabbed settings shell: "Platforms" and "Skills". They follow the same HTMX `hx-get` pattern as LLM/General/Status tabs from Phase 2. New routes: `/settings/platforms`, `/settings/skills`.
- **D-02:** Tabs are added to `index.html`'s tab bar. Each loads its content via the Phase 2 established pattern (`hx-get`, `hx-target="#tab-content"`).

### Platform Configuration
- **D-03:** Platform forms use a data-driven schema — a Python dict per platform defines its fields (name, type, env_var, required, help_text). One Jinja2 template iterates the schema to render platform-specific forms. No 13 separate templates.
- **D-04:** The schema dict maps to `gateway.config.Platform` enum values and references `OPTIONAL_ENV_VARS` / `_EXTRA_ENV_KEYS` from `hermes_cli/config.py` for env var names.
- **D-05:** Platform cards are displayed as a card grid. Each card shows: platform name, configured/not-configured badge, and an expand/collapse to reveal the form fields. Configured platforms are visually highlighted.
- **D-06:** Platform secrets (tokens, API keys) use the same `redact_secret()` / `save_env_value()` pattern from Phase 1/2. Display redacted, write new values to `.env`.
- **D-07:** On managed-mode installs, platform forms are read-only with the standard managed-mode banner (same pattern as Phase 2 D-05).

### Test Connection
- **D-08:** Each platform card has a "Test Connection" button. Clicking it sends an HTMX POST to `/settings/platforms/{platform}/test`. The backend performs a lightweight connectivity check (e.g., Telegram `getMe`, Discord gateway check, Slack `auth.test`) and returns inline success/error in the card — same flash pattern as Phase 2.
- **D-09:** Test connection is backend-proxied (PLAT-02 requirement) — the browser never makes direct API calls to external services. The handler imports the relevant adapter module and calls a minimal check method.
- **D-10:** Test connection works on the currently-entered form values (not necessarily saved values). The form data is submitted along with the test request so the user can test before committing.

### Platform Save
- **D-11:** Each platform has its own save button. POST to `/settings/platforms/{platform}/save`. Saves both `.env` values (secrets) and `config.yaml` entries (non-secret settings like chat IDs, modes). Uses `app["config_lock"]` for concurrent write safety.

### Skills Management
- **D-12:** Skills tab displays all installed skills as a card grid grouped by category. Each card shows: skill name, description (from SKILL.md frontmatter), category, and an enable/disable toggle switch.
- **D-13:** Skills data comes from `tools/skills_tool.py:skills_list()` or direct filesystem scan of `skills/` and `~/.hermes/skills/` directories, reading SKILL.md frontmatter.
- **D-14:** Enable/disable toggle sends HTMX POST to `/settings/skills/{skill_name}/toggle`. Backend uses logic from `tools/skill_manager_tool.py:skill_manage()` to update the config.
- **D-15:** Skill-specific configuration (SKIL-03) — if a skill has configurable settings in its SKILL.md frontmatter, show them as an expandable form below the toggle. This is optional and only renders when settings exist.

### Claude's Discretion
- Platform card expand/collapse animation (CSS transition or instant)
- Card grid column count (responsive, 1-3 columns based on viewport)
- Whether to show unconfigurable platforms (LOCAL, API_SERVER, WEBHOOK) or filter them out
- Skills category ordering (alphabetical vs custom)
- Empty state for skills when none are installed
- Test connection timeout and error message formatting

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Dashboard Foundation (Phase 1+2 code)
- `gateway/dashboard/__init__.py` — Subapp factory, existing route registration. New platform/skill routes added here.
- `gateway/dashboard/settings.py` — Existing LLM/General/Status handlers. New platform/skill handlers go here or in new modules.
- `gateway/dashboard/auth.py` — `redact_secret()` for browser-safe secret display.
- `gateway/dashboard/templates/index.html` — Tab shell to extend with Platforms/Skills tabs.
- `gateway/dashboard/templates/settings/_flash.html` — Reusable flash message partial.
- `gateway/dashboard/static/style.css` — Existing tab and form styles.

### Platform System
- `gateway/config.py` — `Platform` enum (all 14 platform values), `PlatformConfig` dataclass.
- `gateway/platforms/base.py` — `BasePlatformAdapter` ABC with `is_connected`, `has_fatal_error`, `fatal_error_message` properties.
- `gateway/platforms/*.py` — Individual adapter implementations. Each has different config needs.
- `hermes_cli/config.py` — `OPTIONAL_ENV_VARS` dict (platform env vars with descriptions), `_EXTRA_ENV_KEYS` frozenset, `save_env_value()`, `get_env_value()`.

### Skills System
- `tools/skills_tool.py` — `skills_list()` function for listing installed skills.
- `tools/skill_manager_tool.py` — `skill_manage()` for enable/disable operations.
- `agent/skill_utils.py` — Skill file parsing utilities (SKILL.md frontmatter reading).
- `skills/` — Bundled skills directory structure (category/skill-name/SKILL.md).

### Config System
- `hermes_cli/config.py` — `load_config()`, `save_config()`, `is_managed()`, `save_env_value()`, `get_env_value()`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gateway/dashboard/settings.py` — `_render_llm()` helper pattern for shared GET/POST rendering. New platform/skill handlers should follow this pattern.
- `gateway/dashboard/templates/settings/_flash.html` — Reusable flash message partial for save/test feedback.
- `gateway/dashboard/auth.py:redact_secret()` — Browser-safe secret redaction.
- `app["config_lock"]` — asyncio.Lock for concurrent config writes (already wired).
- `app["gateway_runner"]` — GatewayRunner reference for adapter status (already used in status tab).
- `hermes_cli/config.py:OPTIONAL_ENV_VARS` — Contains platform env var definitions with descriptions (can drive form field help text).
- `hermes_cli/config.py:_EXTRA_ENV_KEYS` — Additional env vars (DISCORD_HOME_CHANNEL, TELEGRAM_HOME_CHANNEL, etc.) that platforms need.
- `toolsets.get_all_toolsets()` — Already imported in Phase 2's general handler.

### Established Patterns
- HTMX tab loading via `hx-get` to `/settings/*` endpoints (Phase 2).
- Per-section HTMX `hx-post` save with inline flash feedback (Phase 2).
- Deferred imports inside function bodies to avoid import-time failures (Phase 1/2).
- `aiohttp_jinja2.render_template()` for template rendering (synchronous, not awaited).
- Managed-mode guard pattern: check `is_managed()`, disable forms, show banner (Phase 2).

### Integration Points
- `gateway/dashboard/__init__.py:create_dashboard_app()` — Register new routes.
- `gateway/dashboard/templates/index.html` — Add "Platforms" and "Skills" tab links to tab bar.
- `gateway/dashboard/settings.py` or new `platforms.py`/`skills.py` — Handler functions.
- `gateway/dashboard/templates/settings/` — New template partials (_platforms.html, _skills.html, _platform_card.html).

</code_context>

<specifics>
## Specific Ideas

- The platform schema dict approach means adding a new platform adapter in the future only requires adding an entry to the schema — no new template needed.
- Test connection should be lightweight — just enough to verify credentials are valid (e.g., Telegram `getMe`, not a full message send).
- Phase 2 already shows platform connection status in the Status tab (read-only). Phase 3 adds the configuration forms that write those settings.
- Skills are file-system-based. The enable/disable toggle likely updates a config.yaml key (disabled_skills list or similar) rather than modifying SKILL.md files.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-platforms-and-skills*
*Context gathered: 2026-03-30*
