"""Hermes auth-proxy — username/password gate in front of the upstream dashboard.

Self-contained companion that lives outside upstream's web_server. Adds a
proper login layer for deployments where Caddy/nginx basic_auth isn't an
option (NixOS module users, single-binary setups, etc.).

Architecture:

    [Browser] ──► [auth_proxy :9120] ──► [hermes web :127.0.0.1:9119]

Proxy behavior:
  - GET /__auth/login           → render login form
  - POST /__auth/login          → validate creds, set HMAC-signed cookie, 302
  - POST /__auth/logout         → clear cookie, 302 to login
  - GET /__auth/setup           → first-run "create credentials" form
  - everything else             → if cookie valid, reverse-proxy (HTTP + WS)
                                  to upstream; else redirect to /__auth/login

Credentials live in ~/.hermes/.dashboard_auth.json (scrypt hash).

This is NOT a plugin — it's a wrapper process. No upstream files modified.
"""
__all__ = ["server", "credentials"]
