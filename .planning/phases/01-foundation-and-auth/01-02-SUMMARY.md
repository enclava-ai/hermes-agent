---
phase: 01-foundation-and-auth
plan: "02"
subsystem: auth
tags: [aiohttp, fernet, argon2-cffi, cryptography, dashboard, auth, brute-force, session]

# Dependency graph
requires:
  - phase: 01-foundation-and-auth
    plan: "01"
    provides: gateway/dashboard/ package scaffold, Jinja2 templates, static assets, stub auth.py
provides:
  - gateway/dashboard/auth.py — full auth layer with Fernet session, argon2id verify, middleware, handlers
  - gateway/dashboard/__init__.py — create_dashboard_app() wired with auth_middleware, all routes, on_startup
  - gateway/dashboard/views.py — dashboard home handler (handle_index)
  - tests/gateway/dashboard/test_auth.py — 11 unit tests for all auth security primitives
affects:
  - 01-03 (mounts dashboard subapp in api_server.py — auth layer now fully functional)
  - Phase 2+ (all config API features depend on working auth boundary)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Fernet session token with ttl= TTL enforcement at crypto layer (not separate timestamp check)
    - argon2id password hashing via PasswordHasher — verify raises exceptions on failure, never returns False
    - In-memory brute-force counter using defaultdict(list) with sliding window purge on check
    - Auth middleware scoped to dashboard subapp only — main app API routes unaffected
    - on_startup hook (ensure_dashboard_credentials) loads/creates Fernet key and sets force_change flag
    - asyncio.Lock in app["config_lock"] for concurrent save_config() serialization
    - redact_secret() for browser-safe config display (no ANSI codes)
    - TDD — tests written first (RED), then implementation (GREEN)

key-files:
  created:
    - gateway/dashboard/auth.py
    - gateway/dashboard/views.py
    - tests/gateway/dashboard/__init__.py
    - tests/gateway/dashboard/test_auth.py
  modified:
    - gateway/dashboard/__init__.py

key-decisions:
  - "verify_session_token uses Fernet's built-in ttl= parameter — TTL enforced cryptographically, not by JSON timestamp check"
  - "test_verify_session_token_expired patches time.time() at token creation time to produce genuinely old Fernet token"
  - "redact_secret() is a standalone browser-safe function — does NOT call hermes_cli.config.redact_key() which embeds ANSI codes"

patterns-established:
  - "Pattern 1: All config writes inside dashboard handlers use async with request.app['config_lock']"
  - "Pattern 2: Auth middleware raises web.HTTPFound('/dashboard/login') — not return, so middleware chain is bypassed"
  - "Pattern 3: handle_change_password calls is_managed() and returns HTTP 400 before touching config"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05]

# Metrics
duration: 15min
completed: 2026-03-30
---

# Phase 01 Plan 02: Auth Layer Summary

**Fernet-encrypted session cookies + argon2id password hashing + brute-force protection wired into aiohttp subapp with auth middleware scoped to /dashboard/ only**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-30T09:59:29Z
- **Completed:** 2026-03-30T10:14:00Z
- **Tasks:** 2 of 2
- **Files modified:** 5

## Accomplishments

- Implemented complete `gateway/dashboard/auth.py`: Fernet session token (24h TTL enforced cryptographically), argon2id password hashing and verification, in-memory brute-force protection (5 attempts / 60s per IP), browser-safe secret redaction, login/logout/change-password HTTP handlers, first-run password generation on_startup hook
- Wired `create_dashboard_app()` in `gateway/dashboard/__init__.py`: auth middleware on subapp only, all 5 routes registered, `ensure_dashboard_credentials` as on_startup hook, `asyncio.Lock` for concurrent config writes
- Created `gateway/dashboard/views.py` with `handle_index()` dashboard home handler
- 11 unit tests covering all security primitives (token verify, password verify, brute-force, redaction) — all passing

## Task Commits

1. **Task 1: Implement auth.py — session, password, middleware, handlers** - `6bad43ca` (feat)
2. **Task 2: Wire auth into create_dashboard_app() and register all routes** - `9f75b196` (feat)

## Files Created/Modified

- `gateway/dashboard/auth.py` — Full auth layer: SESSION_COOKIE, SESSION_TTL, Fernet session, argon2 verify, brute-force, auth_middleware, handle_login, handle_logout, handle_change_password, ensure_dashboard_credentials
- `gateway/dashboard/__init__.py` — create_dashboard_app() wired with auth_middleware, all routes, on_startup hook, config_lock
- `gateway/dashboard/views.py` — handle_index() for dashboard home page (template renders index.html)
- `tests/gateway/dashboard/__init__.py` — Empty package marker
- `tests/gateway/dashboard/test_auth.py` — 11 unit tests for auth primitives (no HTTP, no config mocks)

## Decisions Made

- `verify_session_token` relies on Fernet's built-in `ttl=` parameter rather than checking the JSON `ts` field — this is correct because Fernet embeds its own creation timestamp and raises `InvalidToken` when the token is older than `ttl` seconds. The JSON `ts` field is redundant for TTL but retained for auditing.
- `test_verify_session_token_expired` patches `time.time()` at token creation time to produce a Fernet token with an old embedded timestamp — this correctly exercises the Fernet TTL code path.
- `redact_secret()` is a separate function that returns plain strings with no ANSI codes — does not call `hermes_cli.config.redact_key()` which embeds terminal color codes incompatible with JSON responses.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_verify_session_token_expired — Fernet TTL is token-creation-time, not JSON payload timestamp**
- **Found during:** Task 1 (TDD GREEN phase — running tests after implementing auth.py)
- **Issue:** Initial test created a Fernet token with an old JSON `{"ts": ...}` but Fernet's TTL is enforced based on the token's own creation timestamp (embedded in the token). The token was fresh in Fernet's eyes, so `decrypt(ttl=86400)` succeeded and the test failed.
- **Fix:** Patched `time.time()` during token creation so the Fernet token itself has an old creation timestamp, then verified with real time — correctly exercising the `InvalidToken` path.
- **Files modified:** `tests/gateway/dashboard/test_auth.py`
- **Verification:** Test passes; `verify_session_token` returns False for the old token
- **Committed in:** `6bad43ca` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug in test approach)
**Impact on plan:** Fix was essential for test correctness. The implementation was correct; only the test strategy needed adjustment. No scope creep.

## Issues Encountered

None — implementation followed plan. The test expiry fix was discovered and resolved within Task 1 TDD cycle.

## Known Stubs

- `gateway/dashboard/templates/index.html` — Dashboard home is a stub with no real data; intentional — configuration UI added in Phase 2
- `gateway/dashboard/views.py:handle_index` — Returns empty dict, no data wired to template; intentional — Phase 2 adds config API and status data

These stubs do not prevent this plan's goal. Auth is fully functional. Dashboard home correctly requires login to access.

## User Setup Required

None — no external service configuration required. Install dependencies with:
```bash
pip install hermes-agent[dashboard]
```

## Next Phase Readiness

- `gateway/dashboard/auth.py` fully implemented — Plan 03 can mount the subapp in api_server.py
- All auth routes registered and auth middleware active — browser login flow works end-to-end once mounted
- `ensure_dashboard_credentials` on_startup generates first-run password automatically
- `config_lock` ready for Phase 2 concurrent config writes
- api_server.py NOT modified — Plan 03 is the sole integration point

---
*Phase: 01-foundation-and-auth*
*Completed: 2026-03-30*
