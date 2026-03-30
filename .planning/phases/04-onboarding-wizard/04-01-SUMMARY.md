---
phase: 04-onboarding-wizard
plan: 01
subsystem: dashboard-wizard
tags: [wizard, onboarding, multi-step-form, draft-persistence]
dependency_graph:
  requires: [gateway/dashboard/__init__.py, gateway/dashboard/settings.py, gateway/dashboard/platforms.py, gateway/dashboard/platform_schema.py]
  provides: [gateway/dashboard/wizard.py, wizard-templates, wizard-css]
  affects: [gateway/dashboard/__init__.py, gateway/dashboard/static/style.css]
tech_stack:
  added: []
  patterns: [wizard-draft-persistence, atomic-config-application, htmx-select-oob]
key_files:
  created:
    - gateway/dashboard/wizard.py
    - gateway/dashboard/templates/wizard.html
    - gateway/dashboard/templates/wizard/_step_bar.html
    - gateway/dashboard/templates/wizard/_step_llm.html
    - gateway/dashboard/templates/wizard/_step_platform.html
    - gateway/dashboard/templates/wizard/_step_summary.html
  modified:
    - gateway/dashboard/__init__.py
    - gateway/dashboard/static/style.css
decisions:
  - Wizard templates are standalone (not including settings partials) to avoid coupling wizard form actions to settings endpoints
  - Draft persisted both in-memory and on disk for crash resilience
  - Config applied atomically on completion under config_lock
metrics:
  duration: 3m
  completed: "2026-03-30T14:30:28Z"
---

# Phase 04 Plan 01: Wizard Handler and Templates Summary

3-step onboarding wizard with draft persistence, per-step validation, atomic config application, and HTMX-driven step navigation using hx-select-oob for step bar updates.

## What Was Built

### Task 1: Wizard Handler Module (a1e83643)

Created `gateway/dashboard/wizard.py` with:
- **WIZARD_STEPS** constant defining 3 steps (LLM Setup, Platform Connection, Summary)
- **Draft persistence**: in-memory dict keyed by session cookie + JSON file on disk (~/.hermes/.wizard_draft.json)
- **Step rendering**: builds step-specific context (LLM providers, platform cards, summary) from draft with config fallback
- **Route handlers**: handle_wizard (GET /wizard), handle_wizard_step (GET/POST /wizard/step/{n}), handle_wizard_test (POST /wizard/test/{platform}), handle_wizard_complete (POST /wizard/complete)
- **Validation**: Step 1 requires provider + API key; Step 2 requires successful platform test; Step 3 has no validation
- **Atomic completion**: applies all config under config_lock, saves API key and platform env vars to .env, deletes draft

Registered all 5 route patterns in `gateway/dashboard/__init__.py`.

### Task 2: Wizard Templates and CSS (8ad4c67f)

Created 5 template files:
- **wizard.html**: extends base.html with step bar and content containers
- **_step_bar.html**: numbered progress circles with active (indigo) / done (green) states and connectors
- **_step_llm.html**: provider dropdown, model name, API key with dynamic visibility, temperature, max tokens
- **_step_platform.html**: platform card grid with test connection buttons and back/next navigation
- **_step_summary.html**: configuration review with back button and completion action

HTMX strategy: all forms use `hx-select="#wizard-step-content"` + `hx-select-oob="#wizard-step-bar"` so a single full-page response updates both the step content and progress bar.

Appended wizard step bar CSS to style.css (7 classes for steps, numbers, active/done states, connectors).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Safe platform dict access in handle_wizard_test**
- **Found during:** Task 1
- **Issue:** When test fails and draft["platform"] might not exist yet, accessing draft["platform"]["test_passed"] would KeyError
- **Fix:** Use draft.setdefault("platform", {}) pattern before setting test_passed on failure path
- **Files modified:** gateway/dashboard/wizard.py

## Decisions Made

1. **Standalone wizard templates** -- wizard templates render their own forms rather than including settings partials (_llm.html, _platform_card.html). This avoids coupling wizard form actions to settings POST endpoints, which would violate D-13 (no incremental config writes during wizard steps).
2. **Platform display name resolution** -- summary step resolves platform enum value to human-readable display_name from PLATFORM_SCHEMA for better UX.

## Known Stubs

None -- all wizard steps are fully functional with real data sources wired.

## Self-Check: PASSED
