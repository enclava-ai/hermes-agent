# Architecture Research

**Domain:** Self-contained web config dashboard integrated into existing aiohttp gateway
**Researched:** 2026-03-30
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Browser (user's browser)                         │
│  GET /dashboard/*   POST /dashboard/api/*   Static assets           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP on port 8642
┌───────────────────────────────▼─────────────────────────────────────┐
│                    Gateway Process (aiohttp)                          │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  APIServerAdapter  (gateway/platforms/api_server.py)           │  │
│  │                                                                │  │
│  │  web.Application (main app, frozen at runner.setup())          │  │
│  │  ├── /health, /v1/*, /api/jobs/*   (existing routes)           │  │
│  │  └── /dashboard/ subapp  ◄── attached BEFORE runner.setup()   │  │
│  │       ├── /dashboard/              (login redirect or UI)      │  │
│  │       ├── /dashboard/login        (POST → set session cookie)  │  │
│  │       ├── /dashboard/logout       (clear cookie, redirect)     │  │
│  │       ├── /dashboard/static/*     (HTML, CSS, JS assets)       │  │
│  │       └── /dashboard/api/*        (config read/write JSON)     │  │
│  └────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Python function calls
┌────────────────────────────▼────────────────────────────────────────┐
│                    Config Layer                                       │
│  hermes_cli/config.py  load_config() / save_config()                │
│  ~/.hermes/config.yaml  (YAML, owner-only 0600)                     │
│  ~/.hermes/.env         (secrets, owner-only 0600)                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| `gateway/dashboard/__init__.py` | Factory: builds and returns dashboard sub-app | `web.Application` with all routes and middlewares registered |
| `gateway/dashboard/auth.py` | Session-cookie auth: login, logout, middleware | Encrypted cookie via `itsdangerous` or `cryptography.fernet`; no external session store needed |
| `gateway/dashboard/config_api.py` | REST handlers for config read/write | Thin wrappers over `hermes_cli/config.py`; `load_config()` / `save_config()` |
| `gateway/dashboard/status_api.py` | Read-only status snapshot (platforms, health) | Reads from `GatewayRunner` reference passed via `subapp["gateway_runner"]` |
| `gateway/dashboard/static/` | HTML pages, vanilla JS, optional HTMX CDN | Served via `subapp.router.add_static()` |
| `hermes_cli/config.py` | Authoritative config read/write (already exists) | Reused as-is — no modifications |

## Recommended Project Structure

```
gateway/
└── dashboard/                    # new self-contained module
    ├── __init__.py               # create_dashboard_app() factory
    ├── auth.py                   # session cookie auth + middleware
    ├── config_api.py             # /api/config CRUD handlers
    ├── status_api.py             # /api/status read-only handlers
    └── static/
        ├── index.html            # SPA shell / login page
        ├── dashboard.html        # main settings UI
        ├── onboarding.html       # first-run wizard
        ├── app.js                # vanilla JS glue (fetch + HTMX hooks)
        └── style.css             # minimal styles
```

### Structure Rationale

- **`dashboard/`:** Isolated directory is the entire "no upstream file changes" contract. Drop the folder → feature gone, no residue.
- **`__init__.py` exposes one function:** The single attachment point (`create_dashboard_app()`) keeps the integration seam tiny.
- **`static/` stays flat:** No build tooling. Files are served directly by aiohttp `add_static()`. No minification pipeline to maintain.
- **`config_api.py` vs `status_api.py`:** Separating write-capable endpoints from read-only ones makes auth middleware easier to reason about (all `/api/config` routes require auth; `/api/status` likewise, but the separation is clear).

## Architectural Patterns

### Pattern 1: Sub-Application Attachment (before freeze)

**What:** The dashboard is a `web.Application` mounted at `/dashboard/` via `app.add_subapp()` in `APIServerAdapter.connect()`, before `runner.setup()` is called.

**When to use:** Any time you want to bolt a self-contained set of routes onto an existing aiohttp app without touching its existing route table.

**Trade-offs:**
- Pro: Middleware chain is properly inherited (top-level CORS and security headers propagate down).
- Pro: `on_startup` / `on_shutdown` signals propagate to the sub-app automatically.
- Con: Cannot attach a sub-app at runtime after `runner.setup()` — must be done in `connect()`.
- Con: Routes must be added to the sub-app before `add_subapp()` is called (aiohttp freezes the sub-app on attachment).

**Integration point (one place in existing code):**

The existing `APIServerAdapter.connect()` method builds the `web.Application` and registers routes. The dashboard sub-app attaches here:

```python
# Inside APIServerAdapter.connect() — the ONLY existing-file touch point
# This can also be injected via an on_startup signal hook to stay zero-touch.
from gateway.dashboard import create_dashboard_app
dashboard = create_dashboard_app(gateway_runner=self)
self._app.add_subapp('/dashboard', dashboard)
```

To remain truly zero-modification to upstream files, an alternative is to monkey-patch via `on_startup`, but the cleanest approach for a fork is a single import added to `connect()`.

**Confidence:** HIGH — verified against aiohttp 3.13.4 docs and source. Sub-app freeze order is explicit in aiohttp internals.

### Pattern 2: Encrypted Cookie Session (no external store)

**What:** Login POST validates username+password against a hashed credential stored in `~/.hermes/.env` or `config.yaml`, then sets an encrypted signed cookie. A middleware on the dashboard sub-app checks this cookie on every request.

**When to use:** Single-user dashboard with no need for Redis or database-backed sessions.

**Trade-offs:**
- Pro: Zero extra dependencies beyond `cryptography` (likely already installed) or `itsdangerous`.
- Pro: Stateless on the server — no session store to maintain.
- Con: No server-side session invalidation (logout just clears the browser cookie; the token remains valid until expiry). Acceptable for a single-user local dashboard.

**Implementation sketch:**

```python
# auth.py
from cryptography.fernet import Fernet
import json, time

SESSION_COOKIE = "hermes_dash_session"
SESSION_TTL = 86400  # 24 hours

def make_token(fernet: Fernet) -> str:
    payload = json.dumps({"ts": time.time()}).encode()
    return fernet.encrypt(payload).decode()

def verify_token(fernet: Fernet, token: str, ttl: int = SESSION_TTL) -> bool:
    try:
        payload = json.loads(fernet.decrypt(token.encode(), ttl=ttl))
        return True
    except Exception:
        return False

@web.middleware
async def auth_middleware(request, handler):
    if request.path in ("/dashboard/login", "/dashboard/static/"):
        return await handler(request)
    token = request.cookies.get(SESSION_COOKIE)
    fernet = request.app["fernet"]
    if not token or not verify_token(fernet, token):
        raise web.HTTPFound("/dashboard/login")
    return await handler(request)
```

### Pattern 3: Config Read/Write via Existing Module

**What:** All dashboard API handlers call `hermes_cli.config.load_config()` and `save_config()` directly — no new config abstraction layer.

**When to use:** Always. The existing module already handles atomic writes, file permissions (0600), managed-mode guard, and env var expansion.

**Trade-offs:**
- Pro: Reuses battle-tested, already-deployed logic.
- Pro: Zero risk of diverging from what the CLI does — same code path.
- Con: `load_config()` reads from disk on every call (not cached). Acceptable for a low-traffic admin UI.

**Live reload:** On `save_config()`, the gateway process reads config on next request because `load_config()` is called fresh. For settings that require agent restart (e.g., model name), the dashboard should display a "restart required" notice rather than attempting a live agent swap. Platform connection settings (e.g., new API key) are applied on next platform reconnect — already the existing behavior.

**Confidence:** HIGH — `load_config()` and `save_config()` are well-defined public functions already used by the CLI in the same process.

## Data Flow

### Login Flow

```
Browser POST /dashboard/login (username, password)
    ↓
auth.py handle_login()
    ↓
compare against hashed credential in config["dashboard"]["password_hash"]
    ↓ (match)
set Set-Cookie: hermes_dash_session=<encrypted_token>; HttpOnly; SameSite=Strict
    ↓
redirect 302 → /dashboard/
```

### Config Read Flow

```
Browser GET /dashboard/api/config/<section>
    ↓
auth_middleware validates session cookie
    ↓
config_api.py handle_get_config()
    ↓
hermes_cli.config.load_config()   # reads ~/.hermes/config.yaml
    ↓
filter sensitive fields (API keys → "***")
    ↓
JSON response → Browser renders section form
```

### Config Write Flow

```
Browser POST /dashboard/api/config/<section>  (JSON body)
    ↓
auth_middleware validates session cookie
    ↓
config_api.py handle_save_config()
    ↓
hermes_cli.config.load_config()   # load current
    ↓
deep_merge(current, patch)        # apply only changed keys
    ↓
hermes_cli.config.save_config()   # atomic write → ~/.hermes/config.yaml
    ↓
JSON 200 OK → Browser shows "Saved" confirmation
```

### Static Asset Flow

```
Browser GET /dashboard/static/app.js
    ↓
aiohttp add_static() handler
    ↓
sendfile() syscall → file served directly from gateway/dashboard/static/
```

### Key Data Flows

1. **No shared mutable state between dashboard and AI agent:** Config is always read from disk. The agent reads config at startup and on session reset. Dashboard writes to disk. No in-process cache to invalidate.
2. **Status API reads live gateway state:** `status_api.py` holds a reference to `GatewayRunner` (passed into `create_dashboard_app(gateway_runner=...)`) and reads `runner.adapters` to report platform connection status.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single-user local install | Current design — monolith is correct, no changes needed |
| Docker / Enclava deployment | No changes; aiohttp serves from within the container, port 8642 already exposed |
| NixOS managed mode | `save_config()` already guards against writes in managed mode; dashboard should surface this error to the user |
| Multi-profile | Dashboard serves one profile's config at a time — whichever profile the gateway process was started with |

### Scaling Priorities

1. **First constraint:** NixOS managed mode — config writes must be blocked at the API layer with a clear 403 response + explanation. Already handled by `is_managed()` in `save_config()`.
2. **Second constraint:** Concurrent writes — `save_config()` uses atomic write (temp file + rename). Safe for single-user dashboard; no locking needed.

## Anti-Patterns

### Anti-Pattern 1: Registering Routes After runner.setup()

**What people do:** Attempt to call `app.router.add_route()` or `app.add_subapp()` after the `AppRunner` has started.

**Why it's wrong:** aiohttp freezes the application on `runner.setup()`. Any route added after freeze raises `RuntimeError: Cannot register a resource into frozen router`. The entire dashboard would silently fail to attach.

**Do this instead:** Always configure the dashboard sub-app inside `APIServerAdapter.connect()`, before `self._runner = web.AppRunner(self._app)` — the existing runner setup sequence already provides the right hook point.

### Anti-Pattern 2: Bypassing hermes_cli/config.py for Config Reads

**What people do:** Parse `~/.hermes/config.yaml` with `yaml.safe_load()` directly in dashboard handlers.

**Why it's wrong:** `hermes_cli/config.py` does env var expansion (`_expand_env_vars`), deep-merge with `DEFAULT_CONFIG`, normalization (`_normalize_max_turns_config`), and managed-mode guards. Bypassing it produces raw YAML that may be missing defaults, contain unexpanded `${VAR}` tokens, or write back configs that diverge from what the agent actually uses.

**Do this instead:** Always call `load_config()` / `save_config()`. These are public, stable functions.

### Anti-Pattern 3: Serving Secrets to the Browser

**What people do:** Serialize the full config dict (including API keys from `.env`) and send it to the browser.

**Why it's wrong:** API keys appear in browser developer tools, network logs, and browser history. The `.env` file is intentionally separate from `config.yaml` precisely to avoid this.

**Do this instead:** Dashboard API returns redacted values (`"***"`) for any key that matches known secret patterns (`*_KEY`, `*_TOKEN`, `*_SECRET`). Writes to secret fields go to `.env` via `save_env()`, not to `config.yaml`.

### Anti-Pattern 4: Using SimpleCookieStorage for Sessions

**What people do:** Use `aiohttp_session.SimpleCookieStorage` for session management because it requires no setup.

**Why it's wrong:** `SimpleCookieStorage` stores session data as plain JSON in the cookie — no encryption or signing. An attacker with cookie access can forge admin sessions.

**Do this instead:** Use `cryptography.Fernet` for a signed + encrypted session token, or `aiohttp_session.EncryptedCookieStorage`. For this project, a minimal hand-rolled Fernet cookie (as shown in Pattern 2) avoids the `aiohttp-session` dependency while being equally secure.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Browser | HTTP over port 8642 (existing port) | No new port; dashboard lives under `/dashboard/` prefix |
| `~/.hermes/config.yaml` | Direct file I/O via `hermes_cli.config` | Atomic writes; 0600 permissions managed by existing code |
| `~/.hermes/.env` | Direct file I/O via `hermes_cli.config.load_env()` / `save_env()` | API keys; never returned to browser in plaintext |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `dashboard` sub-app ↔ `APIServerAdapter` | `subapp["gateway_runner"]` (AppKey reference) | Set during `create_dashboard_app(gateway_runner=...)` call |
| `dashboard/config_api.py` ↔ `hermes_cli/config.py` | Direct Python import | Only public functions `load_config()`, `save_config()`, `load_env()`, `save_env()` |
| `dashboard/status_api.py` ↔ `GatewayRunner` | Python attribute access on passed reference | Read-only; no writes back to gateway state |
| `dashboard/auth.py` ↔ `config.yaml` | `load_config()` to read hashed credential | Dashboard password hash stored under `config["dashboard"]["password_hash"]` |

## Suggested Build Order

Dependencies between components drive this order:

1. **Auth layer first** (`auth.py` + login/logout handlers + static login page)
   — Everything else requires a working session. No auth = no secure dashboard.

2. **Config read API + basic UI** (`config_api.py` GET handlers + rendered HTML forms)
   — Validates the sub-app attachment pattern works and config data flows to browser.

3. **Config write API** (`config_api.py` POST/PATCH handlers)
   — Builds on GET; requires careful secret filtering and managed-mode handling.

4. **Status API** (`status_api.py` + status panel in UI)
   — Read-only; depends on `GatewayRunner` reference being wired up.

5. **Onboarding wizard** (multi-step first-run flow)
   — Built last because it orchestrates all prior pieces (auth setup, platform config, LLM config) in a guided sequence.

## Sources

- [aiohttp 3.13.4 Web Advanced — Sub-Applications](https://docs.aiohttp.org/en/stable/web_advanced.html)
- [aiohttp 3.13.4 Server Reference — add_static](https://docs.aiohttp.org/en/stable/web_reference.html)
- [aiohttp-session documentation — EncryptedCookieStorage](https://aiohttp-session.readthedocs.io/en/stable/reference.html)
- [aiohttp GitHub issue #2656 — routes must be added before add_subapp](https://github.com/aio-libs/aiohttp/issues/2656)
- [HTMX documentation](https://htmx.org/docs/)
- [asyncinotify 4.4.0 — async inotify for config watching](https://asyncinotify.readthedocs.io/)

---
*Architecture research for: aiohttp web config dashboard integration*
*Researched: 2026-03-30*
