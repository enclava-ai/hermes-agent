# Feature Research

**Domain:** Web configuration dashboard for a self-hosted AI agent platform (Hermes Agent)
**Researched:** 2026-03-30
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Username/password login with session | Any web UI that controls a server must be gated; no auth = security hole | LOW | Single user; store bcrypt hash in config; session cookie with expiry; aiohttp-session or hand-rolled |
| Logout / session expiry | Standard browser security hygiene | LOW | Clear cookie on logout; idle timeout (e.g. 24h) |
| First-run onboarding wizard | Fresh install has no config; the user must be guided before anything works | MEDIUM | Step-by-step modal/page flow; skip if config already exists; detect "first run" by absence of config.yaml |
| Progress indicator in wizard | Users abandon multi-step flows without knowing how far they are | LOW | "Step 2 of 5" header; back/forward navigation; review before submit |
| Inline validation + connection testing | Users paste API keys and bot tokens; silent failures are maddening | MEDIUM | Test Telegram token via `getMe`; test LLM key with a minimal completion; show success/fail inline before saving |
| LLM provider config (provider + model + API key) | Core agent function depends on this; nothing works without it | LOW-MEDIUM | Dropdown for provider (openai, anthropic, openrouter, auto); text for model name; masked input for API key; stored in `.env` |
| Temperature / system prompt config | Standard LLM tuning users expect to control | LOW | Slider or number input for temperature; textarea for system prompt (persona/SOUL.md content) |
| Platform connection management (Telegram, Discord, Slack, etc.) | The whole point of Hermes is multi-platform; users need to add/test tokens | MEDIUM | One card per platform; enable/disable toggle; token/credential fields; test-connection button; platform-specific fields differ (Telegram: token; Discord: token+channel; Slack: token+scopes) |
| Plugin/skill enable-disable list | Hermes has 30+ skill directories; users need to control which are active | MEDIUM | List of skills with toggle switches; search/filter by name; show description from DESCRIPTION.md if present |
| General settings editor (memory, compression, streaming, session behavior) | Config.yaml has many knobs; direct YAML editing is error-prone | MEDIUM | Form fields for memory_enabled, nudge_interval, compression enabled/threshold, streaming enabled, multi-session mode; map directly to config.yaml keys |
| Config save with feedback | Users need to know their changes persisted | LOW | Save button per section; success/error toast; write to config.yaml atomically |
| Status overview / health panel | Users need to know what is actually running | MEDIUM | Show which platforms are connected/failing; current model in use; gateway process uptime; active sessions count |
| Dashboard accessible from existing port | Users do not want to open another port or process | LOW | Serve under `/dashboard/` path on existing aiohttp port 8642; avoids new infrastructure |
| Responsive on mobile | Admins check status on phone; raspberry pi setup from tablet | LOW | CSS media queries sufficient; no app needed; vanilla HTML with flexbox/grid |

### Differentiators (Competitive Advantage)

Features that set the product apart from "just editing YAML."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live config apply (no restart) | Hermes can reload config at runtime; dashboard that requires restart is worse than a text editor | HIGH | Requires a config-reload signal or in-process config refresh; Hermes already reads config on session start; need to verify whether platform adapters support runtime reload without full gateway restart — this needs investigation |
| Per-platform toolset configuration | Hermes supports per-platform toolset overrides; surfacing this in UI is genuinely useful and unique | MEDIUM-HIGH | Show current toolset per platform; allow override with checkboxes per toolset; complex because toolset list is dynamic |
| Test-connection button per platform | Confirms credentials actually work before committing; reduces failed-setup support burden | MEDIUM | Telegram: call `api.telegram.org/bot{TOKEN}/getMe`; Discord: validate token format + make a REST call; Slack: check token format; run from backend to avoid CORS |
| Onboarding that detects existing partial config | If config.yaml exists but is incomplete, wizard starts at the right step | MEDIUM | Read config.yaml in wizard entry; pre-fill completed fields; skip steps already done |
| Managed-mode detection with clear message | NixOS/Enclava users should not get a confusing save failure — they need to be told to use nix config | LOW | `is_managed()` already exists in `hermes_cli/config.py`; show banner "Config is managed by NixOS — changes here are read-only" |
| Profile selector | Hermes has a profile system; dashboard should let users switch which profile they are editing | MEDIUM | Dropdown at top of nav; each profile has its own config.yaml; requires profile-aware config path resolution |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems or are out of scope.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time log viewer in UI | Admins want to see what the agent is doing | High complexity (SSE/WebSocket streaming, log file tailing, buffering); out of scope for v1; likely to become a rabbit hole | Use `journalctl -u hermes` or tail log files; add a "View logs" button that links to a doc on how to do this |
| Chat interface in dashboard | "It would be convenient to chat from here" | Open WebUI already handles this via port 8642's OpenAI-compatible API; building a second chat interface creates maintenance burden and feature duplication | Document how to connect Open WebUI to the Hermes API endpoint |
| Multi-user / role-based access | "What if two people admin this?" | Hermes is a single-user self-hosted agent; multi-user adds auth complexity, permission models, and UI states disproportionate to the use case | Single username/password for the instance owner is sufficient |
| Visual workflow builder / drag-drop | "Make it like n8n" | Hermes is not a workflow orchestrator; its skill/toolset model does not map to graph-based flows; building this would be a different product | Skills management list + enable/disable toggles serve the actual need |
| OAuth / SSO login | "Integrate with Google/GitHub login" | External auth dependencies add complexity and failure modes; self-hosted users do not want cloud auth dependencies for a local service | Username/password with bcrypt; optionally document putting a reverse proxy (Caddy, nginx) with SSO in front |
| Plugin marketplace / install from UI | "Let me browse and install new skill packs" | Skills are filesystem directories; installing from UI requires git clone or download logic, file permissions, restart coordination; disproportionate complexity for v1 | Document how to clone skill packs manually; enable/disable existing ones from UI |
| In-UI YAML editor (raw) | "Just show me the YAML" | Raw YAML editing is what we are replacing; one bad indent breaks the config; offers no validation | If power users insist, link to the config file path and document `hermes config edit` CLI fallback |
| Audit log of config changes | "Who changed what?" | Single-user instance — the answer is always "you"; complexity without benefit at this scale | Not needed for v1; git-tracking the config directory is a better fit if users want history |

## Feature Dependencies

```
[Username/password login]
    └──required by──> ALL other dashboard features (auth gate)

[First-run onboarding wizard]
    └──requires──> [LLM provider config step]
    └──requires──> [Platform connection step (at least one)]
    └──requires──> [Config save]
    └──enables──> [Status overview] (config now exists)

[Platform connection management]
    └──requires──> [Config save]
    └──enhances──> [Test-connection button] (validates before saving)
    └──informs──> [Per-platform toolset config]

[Plugin/skill management]
    └──requires──> [Config save]
    └──enhances──> [Per-platform toolset config] (toolsets reference skill dirs)

[LLM provider config]
    └──requires──> [Config save]
    └──requires──> [Masked API key input] (security baseline)

[General settings editor]
    └──requires──> [Config save]

[Live config apply]
    └──requires──> [Config save]
    └──requires──> [Gateway process signal/reload mechanism] — NEEDS INVESTIGATION
    └──conflicts──> [NixOS managed mode] (managed mode must be read-only)

[Profile selector]
    └──requires──> [Config save] (must save to correct profile path)
    └──enhances──> [ALL config sections] (scopes them to selected profile)

[Status overview]
    └──enhances──> [Platform connection management] (shows live vs configured state)
    └──requires──> [Gateway process introspection] (needs running platform state)

[Managed-mode banner]
    └──conflicts──> [Config save] (save must be disabled in managed mode)
    └──requires──> [is_managed() detection] (already exists in hermes_cli/config.py)
```

### Dependency Notes

- **Auth gates everything:** No other feature should be reachable without a valid session. Implement auth first, as a middleware wrapper.
- **Config save is foundational:** Every form section depends on being able to write config.yaml (and .env for secrets) atomically. Build this before any section-specific UI.
- **Onboarding requires at least LLM + one platform step:** The wizard cannot "complete" without these two minimum pieces; all other steps can be optional during onboarding.
- **Live config apply conflicts with managed mode:** NixOS/Enclava deployments use declarative config; the dashboard must detect this and make the UI read-only, not attempt writes.
- **Profile selector enhances all config sections:** If profiles are surfaced in v1, every config read/write must be profile-aware. Consider deferring to v1.x to avoid threading this through all sections simultaneously.
- **Test-connection requires backend proxy:** Platform token tests (Telegram, Discord, Slack) must go through the Python backend to avoid browser CORS restrictions. Cannot call external APIs directly from JS.

## MVP Definition

### Launch With (v1)

Minimum viable product — what is needed to replace CLI-based setup for a first-time user.

- [ ] Username/password auth with session — without this nothing is safe to ship
- [ ] First-run onboarding wizard (LLM config + at least one platform) — primary use case
- [ ] LLM provider configuration (provider, model, API key, temperature, system prompt) — agent cannot function without this
- [ ] Platform connection management for Telegram, Discord, Slack (the top three) — these are the most-used adapters
- [ ] Inline connection testing per platform — reduces first-run failure rate significantly
- [ ] Plugin/skill enable-disable list — users need to turn off skills they do not want
- [ ] General settings (memory, streaming, compression toggle) — covers the most-asked config questions
- [ ] Config save (atomic write to config.yaml and .env) — prerequisite for all of the above
- [ ] Status overview (connected platforms, current model) — users need to verify their setup worked
- [ ] Managed-mode detection + read-only banner — prevents confusing failures on NixOS/Enclava

### Add After Validation (v1.x)

Features to add once core dashboard is working and gathering real usage.

- [ ] Live config apply without restart — high value but needs gateway reload mechanism investigation first; confirm feasibility before committing
- [ ] Per-platform toolset configuration — useful but complex; add once simpler sections are stable
- [ ] Profile selector — Hermes profiles exist; surface them once single-profile flow is proven
- [ ] Support for remaining platforms (Matrix, Mattermost, WhatsApp, Signal, Email, etc.) — add after the top-three pattern is established

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Cron job management UI — cron exists via CLI and API; dashboard UI is additive but non-urgent
- [ ] Skill pack installation from UI — requires git/download infra; defer until demand is confirmed
- [ ] Plugin-level configuration (per-skill settings) — many skills have no config; audit which do before building UI

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Auth (login/logout/session) | HIGH | LOW | P1 |
| First-run onboarding wizard | HIGH | MEDIUM | P1 |
| LLM provider config | HIGH | LOW | P1 |
| Config save (atomic write) | HIGH | LOW | P1 |
| Platform connection + test | HIGH | MEDIUM | P1 |
| Plugin/skill enable-disable | HIGH | MEDIUM | P1 |
| Status overview | HIGH | MEDIUM | P1 |
| General settings editor | MEDIUM | MEDIUM | P1 |
| Managed-mode banner | MEDIUM | LOW | P1 |
| Live config apply | HIGH | HIGH | P2 |
| Per-platform toolset config | MEDIUM | HIGH | P2 |
| Profile selector | MEDIUM | MEDIUM | P2 |
| Remaining platform adapters (Matrix etc.) | LOW | MEDIUM | P2 |
| Cron job management UI | LOW | MEDIUM | P3 |
| Skill pack install from UI | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Botpress (hosted) | n8n (self-hosted) | Open WebUI | Our Approach |
|---------|-------------------|-------------------|------------|--------------|
| First-run wizard | Yes — guided workspace setup | No — drops you in the editor | Yes — quick model setup | Step-by-step wizard detecting first-run state |
| Platform/credential config | Integrations tab per bot | Credentials manager (global) | Provider settings page | Per-platform cards with test-connection |
| LLM provider config | Per-bot model selector | Per-node model config | Global model list | Single primary provider + model with optional routing overrides |
| Plugin management | Hub marketplace + toggles | Community nodes install | Function/plugin list | Enable/disable existing skills; no install in v1 |
| Auth | Workspace SSO / invite | Username/password or LDAP | Username/password | Simple username/password; single user |
| Status/health | Dashboard analytics | Execution log | No dedicated health page | Connected platforms + current model summary |
| Config live apply | N/A (cloud always live) | Restart required for some | N/A | Target v1.x; needs gateway reload mechanism |
| Managed/declarative mode | No | No | No | First-class NixOS managed-mode detection with read-only UI |

## Sources

- Botpress Academy: https://botpress.com/academy-course/ui-guide-dashboard
- n8n admin dashboard docs: https://docs.n8n.io/manage-cloud/cloud-admin-dashboard/
- Eleken — Wizard UI Pattern: https://www.eleken.co/blog-posts/wizard-ui-pattern-explained
- LogRocket — Creating a setup wizard: https://blog.logrocket.com/ux-design/creating-setup-wizard-when-you-shouldnt/
- Grafana plugin management: https://grafana.com/docs/grafana/latest/administration/plugin-management/
- Telegram Bot API (webhook docs): https://core.telegram.org/bots/webhooks
- getclaw.sh — Telegram vs Slack vs Discord for AI bots: https://getclaw.sh/blog/telegram-slack-discord-ai-bot-comparison
- Dashy authentication patterns: https://dashy.to/docs/authentication/
- LiteLLM multi-provider gateway: https://docs.litellm.ai/docs/
- LLM parameters guide: https://learnprompting.org/blog/llm-parameters
- Hermes codebase: `hermes_cli/config.py`, `cli-config.yaml.example`, `gateway/platforms/`

---
*Feature research for: Hermes Agent web configuration dashboard*
*Researched: 2026-03-30*
