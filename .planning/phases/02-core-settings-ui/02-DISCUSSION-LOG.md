# Phase 2: Core Settings UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 02-core-settings-ui
**Areas discussed:** Settings page layout, Config save UX, Provider selection flow, Status overview content
**Mode:** Auto (all defaults selected automatically)

---

## Settings Page Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Tabbed single page | HTMX tab switching, all settings on one page with tabs for LLM/General/Status | ✓ |
| Separate pages | Each settings section as its own URL route | |
| Accordion sections | All sections on one page with collapsible sections | |

**User's choice:** Tabbed single page (auto-selected: recommended default)
**Notes:** Keeps navigation simple, HTMX tab switching is natural for the existing stack, avoids multi-page routing complexity. Establishes a pattern Phase 3 reuses for platforms/skills.

---

## Config Save UX

| Option | Description | Selected |
|--------|-------------|----------|
| HTMX form submit with flash feedback | Partial swap, inline success/error message, no full reload | ✓ |
| Full page reload on save | Traditional form POST, page refreshes to show saved state | |
| Auto-save on change | Each field saves immediately on blur/change | |

**User's choice:** HTMX form submit with flash feedback (auto-selected: recommended default)
**Notes:** HTMX is already wired up in base.html with error handler. Partial swap avoids jarring full reload. Per-section save buttons keep forms independent.

---

## Provider Selection Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Single dropdown with dynamic fields | One dropdown reveals provider-specific fields via HTMX swap or JS | ✓ |
| Separate forms per provider | Each provider gets its own form/tab | |
| Wizard-style multi-step | Step 1: pick provider, Step 2: configure it | |

**User's choice:** Single dropdown with dynamic fields (auto-selected: recommended default)
**Notes:** Simpler than separate forms, keeps it one screen. hermes_cli/config.py already has provider-aware logic that can inform which fields to show.

---

## Status Overview Content

| Option | Description | Selected |
|--------|-------------|----------|
| Current model + platforms + uptime | Lightweight status: model name, connected platforms list, gateway uptime | ✓ |
| Full metrics dashboard | Token usage, session counts, response times | |
| Minimal health indicator | Just a green/red dot showing gateway is running | |

**User's choice:** Current model + platforms + uptime (auto-selected: recommended default)
**Notes:** GatewayRunner reference is already passed into the subapp. Platform adapters expose connection status. Keeps it lightweight for v1 without requiring metrics infrastructure.

---

## Claude's Discretion

- Tab styling and active state indicators
- Flash message styling and auto-dismiss timing
- Exact field ordering within each tab
- Whether temperature/max-tokens use sliders or plain number inputs
- Loading states while HTMX requests are in-flight

## Deferred Ideas

None — discussion stayed within phase scope
