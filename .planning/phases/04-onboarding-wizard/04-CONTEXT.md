# Phase 4: Onboarding Wizard - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

First-time users are guided through LLM setup and platform connection in a multi-step wizard with a progress indicator, back/forward navigation, per-step validation, and draft persistence. The wizard orchestrates the config forms already built in Phases 2 and 3 — it does not re-implement them. Completing the wizard applies config and lands the user on the dashboard home.

</domain>

<decisions>
## Implementation Decisions

### Wizard Entry Point
- **D-01:** Auto-redirect after first login if no LLM provider is configured. Detection: check `load_config()` for presence of a configured `model` key — if missing or default, user is "first-time" and redirected to `/dashboard/wizard` instead of `/dashboard/`.
- **D-02:** The existing first-login flow (change-password) runs first. After password is set, the redirect-to-wizard check happens.
- **D-03:** Existing users with valid config land on the normal dashboard. A "Re-run setup wizard" link in the dashboard nav lets returning users re-enter the wizard voluntarily.
- **D-04:** STATE.md blocker note: dashboard is unreachable if `api_server` platform adapter is not enabled. The wizard entry point should surface this in documentation/setup instructions, but the wizard itself assumes the dashboard is already reachable.

### Step Structure
- **D-05:** Three wizard steps:
  1. **LLM Setup** — Provider selection, API key, model name, temperature/max-tokens (reuses Phase 2 LLM form logic, satisfies WIZD-02)
  2. **Platform Connection** — Select and configure at least one messaging platform with test-connection (reuses Phase 3 platform form logic, satisfies WIZD-03)
  3. **Summary & Done** — Confirmation showing what was configured, with a "Go to Dashboard" action (satisfies WIZD-01 completion)
- **D-06:** Wizard step templates reuse existing Phase 2/3 form partials (`_llm.html`, `_platform_card.html`) as includes, wrapped in the wizard step container. Changes to settings forms automatically propagate to wizard.

### Progress & Navigation UX
- **D-07:** Numbered step bar at the top of the wizard page: "Step 1 of 3 — LLM Setup". Horizontal bar with numbered circles/labels. Active step highlighted, completed steps marked with a checkmark. Minimal custom CSS on top of Pico.
- **D-08:** No skipping — steps must be completed in order. Back navigation is always available and preserves entered values (WIZD-04). Forward requires validation (WIZD-05).
- **D-09:** HTMX with server-side step routing. Each step is an HTMX request to `/dashboard/wizard/step/{n}`. Forward = POST (submits form, validates, advances). Back = GET to previous step (populates from draft). Consistent with the HTMX-first pattern from all prior phases.
- **D-10:** Step 1 (LLM) validates that a provider and API key are provided before allowing progression. Step 2 (Platform) validates that at least one platform connection test succeeds before allowing progression. Step 3 (Summary) has no validation — just a completion action.

### Draft Persistence
- **D-11:** Server-side in-memory dict (`app["wizard_drafts"]`) keyed by session token. For crash resilience, persist to `~/.hermes/.wizard_draft.json`. On wizard completion, draft is applied to `config.yaml`/`.env` using existing `save_config()`/`save_env_value()`, then the draft file is deleted (success criterion 4).
- **D-12:** If the user abandons the wizard mid-flow, the draft persists. On next login, if a draft exists and config still lacks a configured LLM provider, redirect back to the wizard at their last completed step. Provides natural resume without explicit "save draft" UI.
- **D-13:** Config is NOT written incrementally as the user progresses through steps — all config is applied atomically on wizard completion. This prevents half-configured state if the user abandons mid-flow.

### Claude's Discretion
- Wizard page layout and step bar styling — follow Pico CSS defaults, keep it clean
- Welcome copy and step description text
- Whether the summary step shows a "test your setup" action or just a text summary
- Error message wording for validation failures
- Animation/transition between steps (CSS transition or instant swap)
- Whether to show a "skip wizard" escape hatch for users who prefer manual config

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Dashboard Foundation (Phase 1+2+3 code)
- `gateway/dashboard/__init__.py` — Subapp factory, route registration. New wizard routes added here.
- `gateway/dashboard/views.py` — `handle_index()` — the redirect-to-wizard logic hooks into or replaces this handler.
- `gateway/dashboard/auth.py` — `ensure_dashboard_credentials()`, first-run password flow, `redact_secret()`. The wizard runs after password change completes.
- `gateway/dashboard/templates/base.html` — Base template with HTMX error handler. Wizard pages extend this.
- `gateway/dashboard/templates/index.html` — Tab shell. "Re-run wizard" link goes in the nav. Redirect-to-wizard check may modify this handler.

### Settings Forms (reused by wizard)
- `gateway/dashboard/settings.py` — LLM tab handler (`handle_llm_tab`), general settings handler. Wizard step 1 reuses LLM form logic.
- `gateway/dashboard/templates/settings/_llm.html` — LLM form partial to include in wizard step 1.
- `gateway/dashboard/platforms.py` — Platform save/test handlers. Wizard step 2 reuses platform form logic.
- `gateway/dashboard/platform_schema.py` — Data-driven platform schema dict.
- `gateway/dashboard/templates/settings/_platform_card.html` — Platform card partial to include in wizard step 2.
- `gateway/dashboard/templates/settings/_flash.html` — Reusable flash message partial.

### Config System
- `hermes_cli/config.py` — `load_config()`, `save_config()`, `is_managed()`, `save_env_value()`. All config reads/writes.
- `hermes_constants.py` — `get_hermes_home()` for resolving `~/.hermes/` path (draft file location).

### Requirements
- `.planning/REQUIREMENTS.md` — WIZD-01 through WIZD-05 define the acceptance criteria.

### Prior Phase Context
- `.planning/phases/01-foundation-and-auth/01-CONTEXT.md` — Auth flow, first-run password, session cookies.
- `.planning/phases/02-core-settings-ui/02-CONTEXT.md` — Tabbed settings UI, LLM form pattern, config save UX.
- `.planning/phases/03-platforms-and-skills/03-CONTEXT.md` — Platform schema, test connection, skills toggle.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gateway/dashboard/settings.py` — LLM form rendering logic and save handler. Wizard step 1 can call the same rendering function or include the same template partial.
- `gateway/dashboard/platforms.py` — Platform test/save handlers. Wizard step 2 can invoke these for test-connection validation.
- `gateway/dashboard/platform_schema.py` — Platform field definitions. Drives wizard step 2 form generation.
- `gateway/dashboard/templates/settings/_llm.html` — LLM form HTML. Includable in wizard step template.
- `gateway/dashboard/templates/settings/_platform_card.html` — Platform card HTML. Includable in wizard step template.
- `gateway/dashboard/templates/settings/_flash.html` — Flash message partial for inline feedback.
- `gateway/dashboard/auth.py` — Session token extraction, `redact_secret()`.
- `app["config_lock"]` — asyncio.Lock for serializing config writes on wizard completion.
- `app["gateway_runner"]` — GatewayRunner reference for platform adapter status.

### Established Patterns
- HTMX for all interactivity — `hx-get`/`hx-post` with `hx-target`/`hx-swap` (Phases 1-3).
- Per-section form POST with inline flash feedback (Phase 2-3).
- Template partials in `templates/settings/` prefixed with `_` (Phase 2-3).
- Deferred imports inside function bodies (Phase 1-3).
- `aiohttp_jinja2.render_template()` for template rendering (synchronous, not awaited).
- Auth middleware auto-protects all new routes on the dashboard subapp.

### Integration Points
- `gateway/dashboard/__init__.py:create_dashboard_app()` — Register wizard routes (`/wizard`, `/wizard/step/{n}`).
- `gateway/dashboard/views.py:handle_index()` — Add first-time detection logic (check config, redirect to wizard if needed).
- `gateway/dashboard/templates/index.html` — Add "Re-run wizard" link to nav.
- New files: `gateway/dashboard/wizard.py` (handler), `gateway/dashboard/templates/wizard.html` (wizard page), `gateway/dashboard/templates/wizard/` (step partials).

</code_context>

<specifics>
## Specific Ideas

- The wizard orchestrates existing forms, not rebuilds them. This is the key architectural insight — reuse Phase 2/3 partials as includes.
- Draft persistence is lightweight (in-memory + JSON file) because the wizard is a short-lived flow.
- Atomic config application on completion (D-13) prevents half-configured state — this is a deliberate trade-off for safety over incremental feedback.
- The "first-time" detection (D-01) is intentionally simple: check if `model` key exists in config. This avoids adding wizard-specific state flags to config.yaml.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-onboarding-wizard*
*Context gathered: 2026-03-30*
