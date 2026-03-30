# Roadmap: Hermes Web Dashboard

## Overview

Build a self-contained web dashboard integrated into the existing aiohttp gateway on port 8642. Phases proceed in strict dependency order: infrastructure and auth first (everything else depends on the subapp being mounted correctly and requests being authenticated), then the core settings UI (establishes the config read/write/redact pattern all sections share), then platform and skill management (the two most complex list-management sections), and finally the onboarding wizard (which orchestrates all prior phases in a guided first-run sequence).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation and Auth** - Dashboard subapp wired into gateway with working login/logout
- [ ] **Phase 2: Core Settings UI** - LLM config, general settings, and status overview backed by the config API
- [ ] **Phase 3: Platforms and Skills** - Platform connection management (with test-connection) and skill enable/disable
- [ ] **Phase 4: Onboarding Wizard** - Multi-step first-run wizard orchestrating all prior phases

## Phase Details

### Phase 1: Foundation and Auth
**Goal**: A working dashboard subapp is mounted on the existing gateway, reachable at `/dashboard/`, and protected by session-based login
**Depends on**: Nothing (first phase)
**Requirements**: INFR-01, INFR-02, INFR-03, INFR-04, AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05
**Success Criteria** (what must be TRUE):
  1. Navigating to `/dashboard/` returns an HTML login page (not a 404 and not a JSON error)
  2. User can log in with the generated first-run password and is redirected to the dashboard home
  3. User can log out and is returned to the login page; back-button does not restore the session
  4. Unauthenticated requests to `/dashboard/*` are redirected to login; `/v1/chat/completions` and other API routes are unaffected
  5. API keys and secrets in config responses are masked — visible as `***` in the browser, editable via a dedicated field
**Plans**: 3 plans
Plans:
- [x] 01-01-PLAN.md — Package scaffold, vendored HTMX/Pico CSS, Jinja2 templates
- [x] 01-02-PLAN.md — Auth layer (Fernet sessions, argon2, middleware, login/logout/change-password handlers)
- [x] 01-03-PLAN.md — Gateway hook in api_server.py and integration tests
**UI hint**: yes

### Phase 2: Core Settings UI
**Goal**: Users can read and write LLM provider config and general agent settings through the dashboard, with atomic saves, secret redaction, and a live status overview
**Depends on**: Phase 1
**Requirements**: LLM-01, LLM-02, LLM-03, LLM-04, GENL-01, GENL-02, GENL-03
**Success Criteria** (what must be TRUE):
  1. User can select an LLM provider, enter an API key (stored to `.env`, displayed redacted), set model/temperature/max-tokens, and save — config.yaml reflects the change on disk
  2. User can edit the system prompt / persona and save it without restarting the gateway
  3. User can toggle memory, streaming, and compression settings and see them saved
  4. Status overview shows which platforms are connected, the current model, and a health indicator
  5. Attempting to save config on a managed (NixOS/Enclava) install displays a clear error instead of silently failing
**Plans**: TBD
**UI hint**: yes

### Phase 3: Platforms and Skills
**Goal**: Users can configure platform connections, test them inline, and enable or disable individual skills — all through the dashboard
**Depends on**: Phase 2
**Requirements**: PLAT-01, PLAT-02, PLAT-03, PLAT-04, SKIL-01, SKIL-02, SKIL-03
**Success Criteria** (what must be TRUE):
  1. User sees a card for each of the 13+ platform adapters showing current configuration status (configured / not configured)
  2. User can fill in credentials for Telegram, Discord, or Slack and click "Test Connection" — the dashboard shows success or an error message (the call goes through the Python backend, not the browser)
  3. User can save platform credentials and see the platform marked as configured; secrets are displayed redacted
  4. User can browse all installed skills by name and category, and toggle any skill on or off — the change persists to config.yaml
**Plans**: TBD
**UI hint**: yes

### Phase 4: Onboarding Wizard
**Goal**: First-time users are guided through LLM setup and platform connection in a step-by-step wizard that persists progress and validates each step before advancing
**Depends on**: Phase 3
**Requirements**: WIZD-01, WIZD-02, WIZD-03, WIZD-04, WIZD-05
**Success Criteria** (what must be TRUE):
  1. A user with no existing config is shown the wizard on first login; a user with existing config can access the dashboard directly and optionally re-enter the wizard
  2. User can move forward and backward through wizard steps without losing entered values
  3. The LLM step validates that an API key is provided before allowing progression; the platform step validates the connection before allowing progression
  4. Completing the wizard clears the draft file and lands the user on the dashboard home with a confirmation summary
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Auth | 1/3 | In Progress|  |
| 2. Core Settings UI | 0/? | Not started | - |
| 3. Platforms and Skills | 0/? | Not started | - |
| 4. Onboarding Wizard | 0/? | Not started | - |
