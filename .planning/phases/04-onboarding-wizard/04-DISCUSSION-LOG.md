# Phase 4: Onboarding Wizard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 04-onboarding-wizard
**Areas discussed:** Wizard Entry Point, Step Structure, Progress & Navigation UX, Draft Persistence
**Mode:** --auto (all decisions auto-selected as recommended defaults)

---

## Wizard Entry Point

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-redirect after first login if no LLM configured | Check config on login, redirect to wizard if no provider set | ✓ |
| Manual button on dashboard home | Show a "Start setup" card on empty dashboard | |
| URL parameter trigger | `/dashboard/?wizard=true` | |

**User's choice:** [auto] Auto-redirect after first login if no LLM provider configured (recommended default)
**Notes:** Detection via `load_config()` checking for configured `model` key. Existing users with config go straight to dashboard. "Re-run wizard" link available in nav.

---

## Step Structure

| Option | Description | Selected |
|--------|-------------|----------|
| 3 steps: LLM, Platform, Summary | Maps to WIZD-02, WIZD-03, WIZD-01 completion | ✓ |
| 4 steps: Welcome, LLM, Platform, Summary | Adds a dedicated welcome/intro step | |
| 2 steps: LLM+Platform combined, Summary | Fewer steps but denser forms | |

**User's choice:** [auto] 3 steps: LLM Setup, Platform Connection, Summary & Done (recommended default)
**Notes:** Reuses Phase 2/3 form partials as includes. DRY — settings form changes propagate to wizard automatically.

---

## Progress & Navigation UX

| Option | Description | Selected |
|--------|-------------|----------|
| Numbered step bar (Step 1 of 3) | Horizontal bar with circles/labels, Pico CSS compatible | ✓ |
| Sidebar step list | Vertical list of steps with active indicator | |
| Progress bar only | Simple percentage bar, no step labels | |

**User's choice:** [auto] Numbered step bar at top (recommended default)
**Notes:** No skipping allowed — forward requires validation (WIZD-05). Back always available, preserves values. HTMX server-side step routing at `/wizard/step/{n}`.

---

## Draft Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory dict + JSON file backup | `app["wizard_drafts"]` keyed by session, `~/.hermes/.wizard_draft.json` for crash resilience | ✓ |
| SQLite table | Add wizard_drafts table to state.db | |
| Cookie-based | Store draft in encrypted session cookie | |

**User's choice:** [auto] Server-side in-memory dict with JSON file backup (recommended default)
**Notes:** Config applied atomically on completion (not incrementally). Abandoned drafts persist for resume on next login. Draft file deleted on wizard completion.

---

## Claude's Discretion

- Wizard page layout and step bar styling
- Welcome copy and step descriptions
- Summary step content format
- Error message wording
- Step transitions (CSS or instant)
- "Skip wizard" escape hatch

## Deferred Ideas

None — discussion stayed within phase scope
