"""
Dashboard authentication layer.

Implements:
- Fernet-encrypted session cookie (hermes_dash_session)
- argon2id password verification
- First-run password generation
- Auth middleware (dashboard subapp only)
- Login / logout / change-password handlers
- In-memory brute-force rate limiting

Populated in Phase 1 Plan 02.
"""
