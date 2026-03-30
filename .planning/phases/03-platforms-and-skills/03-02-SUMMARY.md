---
phase: 03-platforms-and-skills
plan: "02"
subsystem: ui
tags: [aiohttp, htmx, httpx, platform-config, test-connection]

requires:
  - phase: 03-01
    provides: "PLATFORM_SCHEMA dict, _render_platforms helper, platform card template"
provides:
  - "Test-connection handlers for 10 platforms via httpx"
  - "Save handler persisting platform credentials to .env"
  - "HTMX-wired buttons on platform card template"
affects: [04-wizard]

tech-stack:
  added: [httpx (deferred import for test connections)]
  patterns: [per-platform test function returning tuple[bool, str], dispatch dict pattern for handler routing]

key-files:
  created: []
  modified:
    - gateway/dashboard/platforms.py
    - gateway/dashboard/__init__.py
    - gateway/dashboard/templates/settings/_platform_card.html

key-decisions:
  - "Added email test handler (IMAP login check) since platform_schema marks email as test_supported=True"
  - "Home Assistant env vars use HASS_URL/HASS_TOKEN (matching platform_schema), not HOMEASSISTANT_*"
  - "Password fields with redaction markers (***) are skipped on save to prevent overwriting secrets with display values"

patterns-established:
  - "_TEST_HANDLERS dispatch dict: maps platform ID string to async test function"
  - "Test handlers return (bool, str) tuple; route handler converts to flash message"
  - "Password fallback pattern: empty password fields in test form fall back to saved env value"

requirements-completed: [PLAT-02]

duration: 2min
completed: 2026-03-30
---

# Phase 3 Plan 02: Platform Test Connection and Save Handlers Summary

**Test-connection handlers for 10 platforms via httpx plus credential save-to-.env, wired as HTMX POST buttons**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T12:49:08Z
- **Completed:** 2026-03-30T12:51:01Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- 10 platform test-connection handlers using lightweight httpx API calls (no full SDKs)
- Save handler persists credentials to .env via save_env_value, with redaction-marker guard
- HTMX-wired Test Connection and Save buttons on platform card template

## Task Commits

Each task was committed atomically:

1. **Task 1: Add test-connection handlers for all supported platforms** - `a15daef8` (feat)
2. **Task 2: Wire HTMX attributes on platform card buttons** - `d0b97e8e` (feat)

## Files Created/Modified
- `gateway/dashboard/platforms.py` - Added 10 test handlers, _TEST_HANDLERS dispatch dict, handle_platform_test, handle_platform_save
- `gateway/dashboard/__init__.py` - Registered POST routes for test and save
- `gateway/dashboard/templates/settings/_platform_card.html` - Replaced disabled placeholder buttons with HTMX-wired live buttons

## Decisions Made
- Added email test handler using IMAP login (not httpx) since platform_schema marks email as test_supported=True but the plan omitted it
- Used HASS_URL/HASS_TOKEN field names matching the actual platform_schema (plan had placeholder comments to verify)
- Both buttons use type="button" to prevent native form submission; HTMX handles the POST

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added email platform test handler**
- **Found during:** Task 1 (test-connection handlers)
- **Issue:** Plan listed 9 test handlers but platform_schema has email with test_supported=True
- **Fix:** Added _test_email() using imaplib IMAP4_SSL login check (stdlib, no extra dependency)
- **Files modified:** gateway/dashboard/platforms.py
- **Verification:** _TEST_HANDLERS has 10 entries; import succeeds
- **Committed in:** a15daef8 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Email test handler fills a gap in plan coverage. No scope creep.

## Issues Encountered
None

## Known Stubs
None - all handlers are fully wired with real API calls.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Platform test and save flow complete; ready for Phase 4 wizard integration
- All 10 testable platforms have connection verification
- Save handler respects managed mode and config_lock

---
*Phase: 03-platforms-and-skills*
*Completed: 2026-03-30*
