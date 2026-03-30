# Requirements: Hermes Web Dashboard

**Defined:** 2026-03-30
**Core Value:** Users can fully configure and onboard Hermes Agent through a browser without touching config files or CLI commands.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Authentication

- [x] **AUTH-01**: User can log in with username and password on a login page
- [x] **AUTH-02**: User session is maintained via encrypted cookie (no external session store)
- [x] **AUTH-03**: Dashboard generates a one-time setup password at deploy time that must be changed on first login
- [x] **AUTH-04**: User can change their dashboard password from the settings page
- [x] **AUTH-05**: API keys and secrets are redacted in all UI responses (masked, editable but not readable)

### LLM Configuration

- [x] **LLM-01**: User can select and configure the LLM provider (OpenAI, Anthropic, OpenRouter, local, etc.)
- [x] **LLM-02**: User can set API keys for the selected provider (stored securely, displayed redacted)
- [x] **LLM-03**: User can configure model parameters (model name, temperature, max tokens)
- [x] **LLM-04**: User can edit the system prompt / persona

### Platform Management

- [x] **PLAT-01**: User can configure connection settings for each of the 13+ platform adapters
- [x] **PLAT-02**: User can test a platform connection before saving (backend-proxied API call)
- [x] **PLAT-03**: Each platform has a dedicated form with fields relevant to that adapter (tokens, chat IDs, webhook URLs, etc.)
- [x] **PLAT-04**: User can see which platforms are currently configured and their connection status

### Skills Management

- [x] **SKIL-01**: User can view all installed skills with name, description, and category
- [x] **SKIL-02**: User can enable or disable individual skills
- [x] **SKIL-03**: User can edit skill-specific configuration settings where applicable

### General Settings

- [x] **GENL-01**: User can edit general agent settings (memory, compression, streaming, session reset, etc.)
- [x] **GENL-02**: User can view a status overview (connected platforms, health check, active session count)
- [x] **GENL-03**: User can configure toolset availability (which tools are enabled per platform)

### Onboarding Wizard

- [ ] **WIZD-01**: First-time users see a step-by-step onboarding wizard with progress indicator
- [ ] **WIZD-02**: Wizard includes a step to configure the LLM provider and API key
- [ ] **WIZD-03**: Wizard includes a step to set up at least one messaging platform connection
- [ ] **WIZD-04**: Wizard includes back/forward navigation between steps
- [ ] **WIZD-05**: Wizard validates each step before allowing progression (e.g., test connection)

### Infrastructure

- [x] **INFR-01**: Dashboard is served as an aiohttp subapp from the existing gateway process on port 8642
- [x] **INFR-02**: Frontend uses vanilla HTML/JS/CSS with HTMX for interactivity (no build step)
- [x] **INFR-03**: All dashboard code lives in a self-contained directory (no modifications to existing upstream files)
- [x] **INFR-04**: Dashboard works in all deployment modes (local, Docker, NixOS, Enclava)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Features

- **ADV-01**: Live config apply without gateway restart (requires reload investigation)
- **ADV-02**: Enable/disable individual platform adapters without removing their config
- **ADV-03**: Managed-mode detection with read-only banner for NixOS declarative configs
- **ADV-04**: Wizard draft persistence (resume interrupted setup)
- **ADV-05**: Profile selector (switch between Hermes profiles from dashboard)
- **ADV-06**: Per-platform toolset configuration in the UI

## Out of Scope

| Feature | Reason |
|---------|--------|
| Chat interface | Open WebUI already serves this via the API server |
| Multi-user / user management | Single-user dashboard for instance owner only |
| Real-time log viewer | Too complex for v1; use journalctl or log files |
| Skill installation from UI | Filesystem operations from browser are disproportionately complex |
| Mobile app | Web dashboard is responsive enough for mobile browsers |
| Modifying upstream files | Must remain mergeable with upstream hermes-agent |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Complete |
| AUTH-02 | Phase 1 | Complete |
| AUTH-03 | Phase 1 | Complete |
| AUTH-04 | Phase 1 | Complete |
| AUTH-05 | Phase 1 | Complete |
| LLM-01 | Phase 2 | Complete |
| LLM-02 | Phase 2 | Complete |
| LLM-03 | Phase 2 | Complete |
| LLM-04 | Phase 2 | Complete |
| PLAT-01 | Phase 3 | Complete |
| PLAT-02 | Phase 3 | Complete |
| PLAT-03 | Phase 3 | Complete |
| PLAT-04 | Phase 3 | Complete |
| SKIL-01 | Phase 3 | Complete |
| SKIL-02 | Phase 3 | Complete |
| SKIL-03 | Phase 3 | Complete |
| GENL-01 | Phase 2 | Complete |
| GENL-02 | Phase 2 | Complete |
| GENL-03 | Phase 2 | Complete |
| WIZD-01 | Phase 4 | Pending |
| WIZD-02 | Phase 4 | Pending |
| WIZD-03 | Phase 4 | Pending |
| WIZD-04 | Phase 4 | Pending |
| WIZD-05 | Phase 4 | Pending |
| INFR-01 | Phase 1 | Complete |
| INFR-02 | Phase 1 | Complete |
| INFR-03 | Phase 1 | Complete |
| INFR-04 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation — traceability complete*
