---
phase: 01-foundation-and-auth
plan: "03"
subsystem: auth
tags: [aiohttp, aiohttp-jinja2, fernet, argon2-cffi, dashboard, integration-tests, subapp]

# Dependency graph
requires:
  - phase: 01-foundation-and-auth
    plan: "01"
    provides: gateway/dashboard/ package scaffold, Jinja2 templates, static assets
  - phase: 01-foundation-and-auth
    plan: "02"
    provides: gateway/dashboard/auth.py full auth layer, create_dashboard_app() wired with auth_middleware

provides:
  - gateway/platforms/api_server.py — dashboard hook (add_subapp) in connect() before AppRunner.setup()
  - tests/gateway/dashboard/test_integration.py — 8 integration tests covering full auth flow

affects:
  - Phase 2+ (all config API features depend on working mounted dashboard)
  - Future platform adapter tests (subapp mounting pattern established)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Dashboard hook pattern: try/except ImportError around add_subapp() — gracefully absent when extras not installed
    - Integration test pattern: TestClient(TestServer(subapp)) with on_startup.clear() + inject_fernet for isolated dashboard tests
    - Auth middleware exempt-path pattern: strip one prefix level from request.path to handle both standalone and mounted subapp contexts
    - patch("hermes_cli.config.load_config") for deferred-import mocking in auth handlers

key-files:
  created:
    - tests/gateway/dashboard/test_integration.py
  modified:
    - gateway/platforms/api_server.py (dashboard hook inserted in connect())
    - gateway/dashboard/auth.py (two bugs fixed: render_template await, exempt-path prefix stripping)

key-decisions:
  - "render_template() in aiohttp-jinja2 is synchronous — must NOT be awaited; all 6 call sites in auth.py fixed"
  - "auth_middleware strips one prefix level from request.path to match EXEMPT_PATHS in both standalone (/login) and mounted (/dashboard/login) deployment contexts"
  - "Integration tests use on_startup.clear() + inject_fernet hook to avoid touching disk (no real config.yaml or .env reads)"

patterns-established:
  - "Pattern 1: Dashboard hook placement — AFTER port-conflict detection, BEFORE self._runner = web.AppRunner(self._app)"
  - "Pattern 2: Subapp middleware exempt-path check uses path-suffix stripping for mount-point agnosticism"
  - "Pattern 3: Integration tests bypass ensure_dashboard_credentials by clearing on_startup and injecting test Fernet key"

requirements-completed: [INFR-01, INFR-03, INFR-04, AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05]

# Metrics
duration: 18min
completed: 2026-03-30
---

# Phase 01 Plan 03: Gateway Hook and Integration Tests Summary

**api_server.py dashboard hook mounting /dashboard/ before AppRunner.setup(), with 8 integration tests proving the full auth flow — two bugs discovered and auto-fixed in auth.py during TDD**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-03-30T09:56:00Z
- **Completed:** 2026-03-30T10:14:56Z
- **Tasks:** 2 of 2 (+ 1 checkpoint auto-approved)
- **Files modified:** 3

## Accomplishments

- Inserted the one-line dashboard hook into `APIServerAdapter.connect()` in api_server.py — wrapped in `try/except ImportError` for graceful degradation when dashboard extras aren't installed
- Created 8 integration tests covering: login page HTML, valid/invalid login, authenticated access, unauthenticated redirect to /dashboard/login, logout cookie clearing, API route isolation (auth middleware does not affect /health), and unauthenticated static asset access
- Auto-fixed two bugs in auth.py discovered during TDD: (1) `render_template()` was incorrectly awaited; (2) auth middleware EXEMPT_PATHS check failed in parent-app mounting context — both critical for correct production behavior

## Task Commits

1. **Task 1: Insert dashboard hook into api_server.py connect()** - `c46c0fe6` (feat)
2. **Task 2: Write integration tests + auto-fix two auth.py bugs** - `743f6b90` (feat)

## Files Created/Modified

- `gateway/platforms/api_server.py` — Dashboard hook block added between port-conflict detection and `web.AppRunner()` instantiation
- `tests/gateway/dashboard/test_integration.py` — 8 integration tests for full auth flow using TestClient(TestServer(app))
- `gateway/dashboard/auth.py` — Fixed `render_template()` await (6 call sites) and fixed EXEMPT_PATHS middleware to work in both standalone and subapp-mounted contexts

## Decisions Made

- `render_template()` in aiohttp-jinja2 is synchronous — found this as a bug because tests with `TestClient` only trigger it when actual form errors occur (the `@aiohttp_jinja2.template` decorator path worked fine; the explicit `render_template()` path was never tested until integration tests)
- `auth_middleware` path-stripping: strips one prefix level from `request.path` so `/dashboard/login` → `/login` to match `EXEMPT_PATHS = {"/login", "/logout"}` — this ensures the middleware works identically whether tested standalone or through the parent app

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `render_template()` incorrectly awaited in handle_login and handle_change_password**
- **Found during:** Task 2 (TDD GREEN phase — running integration tests)
- **Issue:** `aiohttp_jinja2.render_template()` is synchronous (confirmed with `inspect.iscoroutinefunction()`). Using `await render_template(...)` raises `TypeError: 'Response' object can't be awaited` in aiohttp 3.13+ when the function is called directly (not via the `@template` decorator). 6 call sites in `auth.py` were affected.
- **Fix:** Removed `await` from all 6 `aiohttp_jinja2.render_template()` calls using `sed`.
- **Files modified:** `gateway/dashboard/auth.py`
- **Verification:** `test_login_invalid_credentials_returns_form` previously returned 500; after fix returns 200 with "Invalid" in body. All 8 integration tests pass.
- **Committed in:** `743f6b90` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed auth_middleware EXEMPT_PATHS check broken in subapp-mounted context**
- **Found during:** Task 2 (TDD GREEN phase — `test_api_routes_unaffected` failing with 302)
- **Issue:** `EXEMPT_PATHS = {"/login", "/logout"}` — middleware used `request.path in EXEMPT_PATHS`. However, aiohttp's `request.path` always contains the full URL path (e.g., `/dashboard/login`), even inside a subapp middleware. So `/dashboard/login not in {"/login", "/logout"}` → auth redirected instead of passing through. The bug was masked in standalone tests (where subapp IS the root, so `request.path == "/login"`).
- **Fix:** Strip one prefix level from `request.path` in `auth_middleware` and check both the full path and stripped path against `EXEMPT_PATHS` and `EXEMPT_PREFIXES`.
- **Files modified:** `gateway/dashboard/auth.py`
- **Verification:** `test_api_routes_unaffected` confirms `/dashboard/login` returns 200 (login page shown, not redirect). All 8 integration tests pass.
- **Committed in:** `743f6b90` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 × Rule 1 — Bugs)
**Impact on plan:** Both fixes were critical for correct production behavior. Bug 1 caused 500 errors on login failures in the real deployment. Bug 2 made the login page unreachable when mounted at /dashboard/ (the real deployment scenario). No scope creep.

## Issues Encountered

- Worktree branch was behind `main` at start — needed `git merge main` to pull in Plans 01 and 02 work before proceeding. Not a real issue; expected in parallel agent execution.

## Known Stubs

- `gateway/dashboard/templates/index.html` — Dashboard home is still a stub with no real data; intentional — configuration UI added in Phase 2
- `gateway/dashboard/views.py:handle_index` — Returns empty dict, no data wired to template; intentional — Phase 2 adds config API and status data

## User Setup Required

None — the dashboard hook in api_server.py is transparent (no-op if dashboard extras not installed). To enable the dashboard:
```bash
pip install hermes-agent[dashboard]
```

Then start the gateway normally. On first startup, the dashboard logs a first-run password:
```
Dashboard: first-run password is: XXXX — change it at /dashboard/
```

## Next Phase Readiness

- Phase 1 complete: dashboard package + auth layer + gateway hook all in place
- `/dashboard/` accessible in the running gateway (requires api_server platform enabled)
- First-run password generated on startup; change-password flow working
- All Phase 1 requirements satisfied: INFR-01, INFR-03, INFR-04, AUTH-01–AUTH-05
- Phase 2 can begin: config API, platform connection forms, LLM settings, status overview

## Self-Check

Files created/modified:
- gateway/platforms/api_server.py: FOUND
- tests/gateway/dashboard/test_integration.py: FOUND
- gateway/dashboard/auth.py: FOUND (modified)
- .planning/phases/01-foundation-and-auth/01-03-SUMMARY.md: FOUND (this file)

Commits:
- c46c0fe6: CHECKED (feat(01-03): insert dashboard subapp hook)
- 743f6b90: CHECKED (feat(01-03): write integration tests + fix two bugs)

## Self-Check: PASSED

---
*Phase: 01-foundation-and-auth*
*Completed: 2026-03-30*
