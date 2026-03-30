# Hermes Web Dashboard

## What This Is

A web-based configuration dashboard for Hermes Agent that lets users set up, configure, and manage their Hermes instance through a browser instead of editing YAML files and running CLI commands. Includes a first-run onboarding wizard and an ongoing settings management interface. Built as a self-contained addition to the existing codebase — no modifications to upstream files.

## Core Value

Users can fully configure and onboard Hermes Agent through a browser without touching config files or CLI commands.

## Requirements

### Validated

- ✓ CLI-based configuration via `hermes setup` wizard — existing
- ✓ YAML config management via `hermes_cli/config.py` — existing
- ✓ API server with OpenAI-compatible endpoints on port 8642 — existing
- ✓ Multi-platform gateway (Telegram, Discord, Slack, etc.) — existing
- ✓ Plugin/skills management via CLI — existing
- ✓ Profile system for isolated instances — existing
- ✓ Cron job management via CLI and API — existing

### Active

- [ ] Web dashboard served from the existing gateway process
- [ ] Username/password authentication for dashboard access
- [ ] First-run onboarding wizard (step-by-step initial setup)
- [x] Platform connection configuration (Discord, Telegram, Slack, etc.) — Validated in Phase 3: Platforms and Skills
- [x] LLM provider configuration (model, API keys, system prompt, temperature) — Validated in Phase 2: Core Settings UI
- [x] Plugin/skills enable/disable and configuration — Validated in Phase 3: Platforms and Skills
- [x] General settings editor (persona, memory, toolsets, compression, etc.) — Validated in Phase 2: Core Settings UI
- [x] Live config.yaml read/write without restarting the agent — Validated in Phase 2: Core Settings UI
- [x] Status overview (connected platforms, active sessions, health) — Validated in Phase 2: Core Settings UI

### Out of Scope

- Chat interface — Open WebUI already serves this purpose via the API server
- User management / multi-user — single-user dashboard for the instance owner
- Mobile app — web dashboard is responsive enough for mobile browsers
- Real-time log viewer — too complex for v1, use `journalctl` or log files
- Modifying upstream hermes-agent files — must remain mergeable with upstream

## Context

- Hermes Agent is a Python-based AI agent platform with 13+ messaging platform adapters
- All config lives in `~/.hermes/config.yaml` (YAML) and `~/.hermes/.env` (secrets)
- The existing API server (`gateway/platforms/api_server.py`) uses aiohttp on port 8642
- The gateway process (`gateway/run.py`) orchestrates all platform adapters
- This is a fork that tracks upstream — all dashboard code must be additive (new files only)
- Frontend must be vanilla HTML/JS (no React/Vue/build step) — possibly HTMX for interactivity
- The `hermes_cli/config.py` module already has config read/write logic that can be reused

## Constraints

- **Upstream compatibility**: No modifications to existing files — dashboard is a new self-contained module
- **Tech stack**: Vanilla HTML/JS/CSS frontend, no Node.js build tooling — served as static files
- **Auth**: Simple username/password login (not OAuth, not API key)
- **Deployment**: Must work in all existing deployment modes (local, Docker, NixOS, Enclava)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Serve from existing gateway process | Avoids new port/process; gateway already runs aiohttp | — Pending |
| Vanilla HTML/JS frontend | No build step, minimal deps, easy to maintain | — Pending |
| Self-contained module (new files only) | Fork must stay mergeable with upstream | — Pending |
| Username/password auth | Simple, no external deps, user controls credentials | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 after Phase 3 completion*
