# Project Research Summary

**Project:** Hermes Agent — Web Configuration Dashboard
**Domain:** Lightweight admin dashboard integrated into existing aiohttp gateway
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

Hermes Agent needs a self-hosted web dashboard to replace CLI-based configuration. The recommended approach is a no-build-step, server-rendered UI: HTMX 2.0.8 + Pico CSS on CDN, Jinja2 server-side templates via `aiohttp-jinja2`, and `aiohttp-session` with `EncryptedCookieStorage` for auth — all mounted as an aiohttp subapp on the existing port 8642 gateway process. Only three new Python dependencies are required (`aiohttp-jinja2`, `aiohttp-session`, `argon2-cffi`); everything else is already in `pyproject.toml`. No Node.js, no build pipeline, no separate process.

The recommended feature scope for v1 is: session auth, first-run onboarding wizard, LLM provider config, platform connection management (Telegram, Discord, Slack), per-platform connection testing, skill enable/disable, general settings editor, atomic config save, status overview, and managed-mode detection. Live config apply without restart and per-platform toolset configuration are high-value but require investigation into gateway reload mechanisms and belong in v1.x. Features like real-time log viewers, multi-user auth, and plugin marketplaces are explicitly anti-features for v1 — they create disproportionate complexity for a single-user self-hosted agent.

The critical risk is **route registration timing**: aiohttp freezes its router on `AppRunner.setup()`, so the dashboard subapp must attach before that call. A close second is **secret exposure** — `load_config()` expands env vars inline and the raw result must never reach the browser. Auth middleware must be scoped to the dashboard subapp only to avoid breaking OpenAI-compatible API clients. Both issues require deliberate decisions in phase 1 before any feature work begins.

## Key Findings

### Recommended Stack

The stack is almost entirely determined by what already exists. aiohttp is the gateway runtime, Jinja2 is a core dependency, and PyYAML is already in use. The dashboard is additive: three new libraries handle templates, sessions, and password hashing. HTMX and Pico CSS are loaded from CDN — no npm, no bundler, no minification step. This is the correct call for a settings UI that is not a real-time application.

**Core technologies:**
- **aiohttp 3.13.4** (already in use): HTTP server, subapp routing, static file serving
- **aiohttp-jinja2 1.6**: Jinja2 template rendering via `@aiohttp_jinja2.template` decorator
- **HTMX 2.0.8** (CDN, no install): Partial page swaps for form submission and toggling without writing imperative JS; use 2.0.8 stable — HTMX 4.0 is alpha and must not be used
- **Pico CSS 2.1.1** (CDN, no install): Semantic CSS that styles raw HTML elements; zero class overhead, WCAG 2.1 AAA compliant, 8KB
- **aiohttp-session 2.12.1**: Cookie-based session storage with `EncryptedCookieStorage` (AES-encrypted, no Redis)
- **argon2-cffi 25.1.0**: OWASP-recommended password hashing (argon2id) for the dashboard credential

### Expected Features

The research draws a clear line between what replaces CLI-based setup for a first-time user (v1) and what adds polish after validation (v1.x/v2+).

**Must have (table stakes):**
- Username/password login with session + logout — without this nothing else is safe to ship
- First-run onboarding wizard with step progress — silent abandonment without it
- LLM provider config (provider, model, API key, temperature, system prompt) — agent cannot start without this
- Platform connection management for Telegram, Discord, Slack with inline test-connection — top three adapters
- Plugin/skill enable-disable list — 30+ skills need user control
- General settings (memory, streaming, compression) — most common config questions
- Atomic config save to `config.yaml` and `.env` — prerequisite for all of the above
- Status overview (connected platforms, current model) — users need to verify setup worked
- Managed-mode detection + read-only banner for NixOS/Enclava — prevents confusing silent failures

**Should have (differentiators):**
- Live config apply without restart — high value but requires gateway reload mechanism investigation first
- Per-platform toolset configuration — unique to Hermes but complex; defer until simpler sections are stable
- Profile selector — Hermes profiles exist; surface after single-profile flow is proven
- Remaining platform adapters (Matrix, Mattermost, WhatsApp, Signal, Email)

**Defer (v2+):**
- Cron job management UI
- Skill pack installation from UI (requires git/download infrastructure)
- Per-skill configuration UI (audit which skills have config before building)

**Explicit anti-features:** real-time log viewer, chat interface in dashboard, multi-user/RBAC, OAuth/SSO, plugin marketplace, raw YAML editor, audit log.

### Architecture Approach

The dashboard is a self-contained `web.Application` subapp mounted at `/dashboard/` via `app.add_subapp()` inside `APIServerAdapter.connect()`, before `runner.setup()` is called. The module lives entirely in `gateway/dashboard/` — dropping the folder removes the feature with no residue. Config reads and writes go through `hermes_cli/config.py` exclusively (`load_config()` / `save_config()` / `save_env_value()`) — no direct YAML parsing in dashboard handlers.

**Major components:**
1. `gateway/dashboard/__init__.py` — `create_dashboard_app(gateway_runner=...)` factory; single integration seam
2. `gateway/dashboard/auth.py` — encrypted cookie session middleware; login/logout handlers; rate limiting on login endpoint
3. `gateway/dashboard/config_api.py` — POST/PATCH handlers for config sections; secret redaction layer; managed-mode guard on every write
4. `gateway/dashboard/status_api.py` — read-only snapshot of `GatewayRunner.adapters` for platform status
5. `gateway/dashboard/static/` — flat directory of HTML templates, vanilla JS glue, served via `add_static()`

### Critical Pitfalls

1. **Dashboard subapp registered after `runner.setup()` freezes the router** — all route registration must happen inside `APIServerAdapter.connect()` before the `AppRunner` is created. Adding routes at any later point raises `RuntimeError: Cannot register a resource into frozen router` and the dashboard silently returns 404. This is a foundation decision, not a fix-later issue.

2. **Auth middleware scoped to main app breaks OpenAI-compatible API clients** — middleware on `self._app` applies to `/v1/chat/completions`, `/health`, and all API routes. Clients receive HTML login pages instead of JSON. The auth check must live only in the dashboard subapp's middleware list; `app.add_subapp()` scopes it correctly.

3. **`load_config()` expands env vars inline — never serialize the raw return value to JSON** — API keys appear in browser DevTools. Every config read endpoint must pass results through the redaction layer (`redact_key()` already exists in `hermes_cli/config.py`). Secret writes go to `.env` via `save_env_value()`, never into the JSON roundtrip.

4. **NixOS managed-mode writes silently succeed at the Python level but get overwritten on `nixos-rebuild switch`** — every write endpoint must call `is_managed()` first and return HTTP 403 with an explanation if true. `save_config()` already guards against this at the stderr level, but the web handler must surface it to the browser.

5. **First-run wizard state lost on browser refresh** — wizard accumulates values across steps; storing state only in memory loses it on F5 or gateway restart. Persist partial wizard state to `~/.hermes/wizard_draft.yaml` after each step, clear on completion.

## Implications for Roadmap

### Phase 1: Foundation and Auth
**Rationale:** The dashboard cannot exist without the subapp mount point being correct, and no feature is safe to ship without session auth. Both the router freeze pitfall and the auth middleware leak pitfall must be resolved here before any UI work begins. Architecture decisions made in this phase cannot be undone cheaply.

**Delivers:** Working dashboard subapp attached to the gateway, login/logout flow with encrypted cookie session, auth middleware scoped correctly to `/dashboard/*`, static file serving, base HTML template with HTMX + Pico CSS, global HTMX error handler.

**Addresses features:** Username/password login, logout/session expiry.

**Avoids pitfalls:** Frozen router (Pitfall 1), auth middleware leak to API routes (Pitfall 2), SimpleCookieStorage plaintext session (Pitfall 4).

**Research flag:** Standard patterns — aiohttp subapp + EncryptedCookieStorage is well-documented. Skip `research-phase`.

---

### Phase 2: Config Read/Write API + Core Settings UI
**Rationale:** Config save is the prerequisite for every settings section. Establish the redaction layer, managed-mode guard, and atomic write pattern once here — all subsequent sections inherit it. The status overview comes in this phase because it validates the `GatewayRunner` reference wiring.

**Delivers:** Config GET/POST API endpoints with secret redaction, managed-mode 403 responses, LLM provider config section, general settings editor (memory, streaming, compression), status overview panel showing connected platforms and current model.

**Addresses features:** LLM provider config, general settings editor, config save with feedback, status overview, managed-mode banner.

**Avoids pitfalls:** Secrets exposed to browser (Pitfall 3), NixOS managed-mode not checked (Pitfall 4 / Pitfall 8), config YAML comments destroyed (Pitfall 7 — use `_set_nested` merge pattern not full rewrite).

**Research flag:** Standard patterns — skip `research-phase`.

---

### Phase 3: Platform Connection Management
**Rationale:** Platform management is the most complex settings section (platform-specific fields, test-connection backend proxying, enable/disable toggles). Building it after the config API is established means the write/redact pattern is already proven. Test-connection calls must go through the Python backend to avoid CORS — this is the one non-trivial backend-fetch in v1.

**Delivers:** Per-platform cards (Telegram, Discord, Slack) with credential fields, enable/disable toggle, and test-connection button that proxies the API call server-side.

**Addresses features:** Platform connection management for top-three platforms, inline connection testing.

**Avoids pitfalls:** Test-connection CORS (must not call external APIs from browser JS — do it in `config_api.py`).

**Research flag:** Standard patterns for Telegram (`getMe`) and Slack (token check). Discord REST call may need minor investigation during implementation. Low-risk — skip `research-phase`.

---

### Phase 4: Skill Management
**Rationale:** Skill enable/disable is a read/write list — simpler than platform management. It fits naturally after platforms are proven because it follows the same toggle + save pattern but with no credential fields or external API calls.

**Delivers:** List of skill directories with enable/disable toggles, description from `DESCRIPTION.md` where present, search/filter by name.

**Addresses features:** Plugin/skill enable-disable list.

**Research flag:** Standard patterns — skip `research-phase`.

---

### Phase 5: First-Run Onboarding Wizard
**Rationale:** The wizard orchestrates all prior phases (auth bootstrap, LLM config, platform config) in a guided sequence. It is built last because it depends on every prior section working correctly. The wizard draft persistence pattern (Pitfall 6) must be implemented here.

**Delivers:** Multi-step onboarding flow detecting first-run state, step progress indicator, back/forward navigation, partial config pre-fill if config.yaml exists, wizard draft persistence to `~/.hermes/wizard_draft.yaml`, draft cleanup on completion.

**Addresses features:** First-run onboarding wizard, progress indicator, inline validation, onboarding that detects existing partial config.

**Avoids pitfalls:** Wizard state lost on refresh (Pitfall 6), wizard skippable with no platforms configured (UX pitfall — detect and prompt return to wizard).

**Research flag:** Standard patterns — skip `research-phase`.

---

### Phase 6 (v1.x): Live Config Apply + Advanced Features
**Rationale:** Live config apply requires investigation into whether `_load_gateway_config()` in `run.py` can be triggered for the current session without a full restart. The per-session reload pattern already exists (config is read fresh per new session) but mid-session reload is unverified. Profile selector threads through all config read/write paths simultaneously — defer until single-profile flow is stable.

**Delivers:** "Restart required" vs "active for new sessions" feedback per setting, optional restart signal endpoint, profile dropdown, remaining platform adapters.

**Addresses features:** Live config apply, profile selector, per-platform toolset config, Matrix/Mattermost/WhatsApp/Signal/Email adapters.

**Research flag:** Needs `research-phase` for live config apply — specifically whether `_load_gateway_config()` is safe to call mid-session and which settings are hot-reloadable vs restart-required.

---

### Phase Ordering Rationale

- Auth before features: no feature is safe without session gating; the subapp mount point is a one-way architectural decision.
- Config API before UI sections: the redaction layer, managed-mode guard, and atomic write must exist before any section builds on them.
- Platforms before wizard: the wizard calls the platform config flow; platforms must be stable first.
- Wizard last in v1: it is an orchestration layer over everything below it.
- Live reload deferred: it requires runtime investigation that should not block v1 launch.

### Research Flags

Phases likely needing `research-phase` during planning:
- **Phase 6 (Live Config Apply):** Whether `_load_gateway_config()` is safe to call for a running session, and which config keys are hot-reloadable vs require restart. Codebase analysis of `run.py` session lifecycle is needed.

Phases with standard patterns (skip `research-phase`):
- **Phase 1:** aiohttp subapp + EncryptedCookieStorage is fully documented
- **Phase 2:** Config read/write via existing `hermes_cli/config.py` is straightforward
- **Phase 3:** Platform test-connection is well-scoped; minor Discord REST lookup may surface during implementation
- **Phase 4:** Skill toggle is the simplest section
- **Phase 5:** HTMX wizard + draft file persistence is documented

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI and official docs; existing `pyproject.toml` constraints confirmed compatible |
| Features | HIGH | Derived from codebase (`hermes_cli/config.py`, `gateway/platforms/`), competitor analysis (Botpress, n8n, Open WebUI), and Hermes-specific constraints |
| Architecture | HIGH | Verified against aiohttp 3.13.4 docs, aiohttp source internals (freeze behavior), and direct codebase analysis of `api_server.py` and `run.py` |
| Pitfalls | HIGH | Critical pitfalls verified in codebase (`atomic_yaml_write`, `is_managed()`, `_load_gateway_config()`, `redact_key()`); aiohttp freeze behavior confirmed in GitHub issues |

**Overall confidence:** HIGH

### Gaps to Address

- **Live config apply feasibility:** `run.py` lines ~3736 and ~4941 show per-session config reload; whether this can be triggered mid-session without a restart needs verification during Phase 6 planning. Do not commit to "no restart needed" UX until this is confirmed.
- **`asyncio.Lock` for concurrent config saves:** `atomic_yaml_write` is crash-safe but not concurrency-safe across two simultaneous dashboard requests. An asyncio lock in the dashboard module must be added — simple but easy to forget.
- **Security headers propagation:** The existing `security_headers_middleware` on the main app should propagate to the subapp, but this must be verified with a request to `/dashboard/api/*` after integration. If not propagating, add `Cache-Control: no-store` and `X-Content-Type-Options: nosniff` explicitly to the dashboard subapp.
- **Dashboard inaccessible if `api_server` platform is disabled:** If a user has not enabled the API server platform, there is no port 8642 to serve from. This dependency must be surfaced in the first-run wizard entry point.

## Sources

### Primary (HIGH confidence)
- `hermes_cli/config.py` — `load_config()`, `save_config()`, `is_managed()`, `redact_key()`, `save_env_value()` verified directly
- `gateway/platforms/api_server.py` — route registration, middleware, app lifecycle verified directly
- `gateway/run.py` — `_load_gateway_config()` per-session reload pattern verified at lines ~3736, ~4941
- `utils.py` — `atomic_yaml_write` implementation verified directly
- [aiohttp 3.13.4 Web Advanced docs](https://docs.aiohttp.org/en/stable/web_advanced.html) — subapp routing, middleware scoping, frozen router
- [aiohttp-jinja2 PyPI](https://pypi.org/project/aiohttp-jinja2/) — version 1.6, compatibility confirmed
- [aiohttp-session PyPI](https://pypi.org/project/aiohttp-session/) — version 2.12.1, EncryptedCookieStorage confirmed
- [argon2-cffi PyPI](https://pypi.org/project/argon2-cffi/) — version 25.1.0, argon2id confirmed
- [HTMX 2.0 release announcement](https://htmx.org/posts/2024-06-17-htmx-2-0-0-is-released/) — stable branch confirmed; 4.0 alpha confirmed as pre-release
- [Pico CSS releases](https://github.com/picocss/pico/releases) — version 2.1.1 confirmed
- `pyproject.toml` — existing dependency constraints verified

### Secondary (MEDIUM confidence)
- [aiohttp GitHub issue #3701](https://github.com/aio-libs/aiohttp/issues/3701) — frozen router runtime behavior
- Botpress, n8n, Open WebUI feature analysis — competitor patterns for wizard and platform management UI

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
