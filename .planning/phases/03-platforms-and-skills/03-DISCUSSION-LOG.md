# Phase 3: Platforms and Skills - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 03-platforms-and-skills
**Areas discussed:** Platform form fields, Test Connection UX, Skills listing and toggle, Platform card layout
**Mode:** Auto (all defaults selected automatically)

---

## Platform Form Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Data-driven schema dict | Python dict per platform defines fields; one template iterates to render forms | ✓ |
| Separate template per platform | 13+ individual HTML templates, one per platform | |
| YAML config-driven | External YAML file defines platform schemas | |

**User's choice:** Data-driven schema dict (auto-selected: recommended default)
**Notes:** Avoids template proliferation. One template + schema dict is maintainable. New platforms only need a schema entry. Maps naturally to `OPTIONAL_ENV_VARS` and `_EXTRA_ENV_KEYS`.

---

## Test Connection UX

| Option | Description | Selected |
|--------|-------------|----------|
| HTMX POST, inline feedback | Backend-proxied test, success/error shown in platform card via flash | ✓ |
| Modal dialog with test results | Pop-up shows detailed test output | |
| Separate test page | Dedicated test route with full output | |

**User's choice:** HTMX POST with inline feedback (auto-selected: recommended default)
**Notes:** Consistent with Phase 2's flash pattern. Backend-proxied per PLAT-02. Tests on form values before save so user can verify before committing.

---

## Skills Listing and Toggle

| Option | Description | Selected |
|--------|-------------|----------|
| Card grid grouped by category | Cards with name/description/toggle, grouped by skill category dirs | ✓ |
| Flat alphabetical list | Simple list with toggle switches, no grouping | |
| Tree view | Category → skill hierarchy with expand/collapse | |

**User's choice:** Card grid grouped by category (auto-selected: recommended default)
**Notes:** Mirrors how skills are organized on disk (`skills/creative/`, `skills/devops/`, etc.). Categories provide natural grouping for 30+ skills.

---

## Platform Card Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Card grid, configured highlighted | All 13+ platforms as cards, configured ones visually distinct | ✓ |
| Two-column: configured vs available | Split view separating configured from unconfigured | |
| Accordion list | Expandable list items per platform | |

**User's choice:** Card grid with configured highlighting (auto-selected: recommended default)
**Notes:** Simple, scannable. Consistent with skills card grid. Status tab already shows platform connection status — this adds the editable config forms.

---

## Claude's Discretion

- Platform card expand/collapse animation
- Card grid column count (responsive)
- Whether to show LOCAL/API_SERVER/WEBHOOK platforms
- Skills category ordering
- Empty states
- Test connection timeout and error formatting

## Deferred Ideas

None — discussion stayed within phase scope
