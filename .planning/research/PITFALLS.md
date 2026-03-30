# Pitfalls Research

**Domain:** Web config dashboard added to existing Python agent platform (aiohttp)
**Researched:** 2026-03-30
**Confidence:** HIGH (codebase-verified + official docs confirmed)

## Critical Pitfalls

### Pitfall 1: Mounting the Dashboard Onto the Frozen aiohttp App

**What goes wrong:**
The existing `APIServerAdapter.connect()` creates a `web.Application`, adds routes, calls `web.AppRunner.setup()`, and starts `TCPSite` — all in one shot. Once `runner.setup()` has been called, the router is frozen and new routes cannot be added. Any attempt to bolt dashboard routes onto `self._app` after the fact raises `RuntimeError: Cannot register a resource into frozen router`.

**Why it happens:**
Developers assume they can monkey-patch routes onto the existing app from outside, or register a subapp after startup. aiohttp freezes the router on `AppRunner.setup()` — this is by design and enforced at runtime.

**How to avoid:**
The dashboard module must be loaded and its subapp registered on `self._app` *before* `runner.setup()` is called. The cleanest pattern is to have `api_server.py` call a well-defined hook: `if dashboard_available: app.add_subapp('/dashboard', dashboard_app)`. The dashboard module registers itself; the API server just calls the hook. Because the project must not modify `api_server.py`, the hook must instead be injected via a startup signal or the dashboard module must be an entirely separate aiohttp `web.Application` on the same port — which aiohttp does not support. The practical resolution: run the dashboard as a second `TCPSite` bound to the same runner, or accept that `api_server.py` needs a minimal one-line hook added (which counts as modifying one upstream file, a deliberate trade-off to document).

**Warning signs:**
- `RuntimeError: Cannot register a resource into frozen router` during startup
- Dashboard routes returning 404 while API routes work fine

**Phase to address:**
Foundation / integration phase — the route registration architecture must be decided before any dashboard handlers are written.

---

### Pitfall 2: Config Written by Dashboard Not Picked Up by Running Agent

**What goes wrong:**
The gateway runner loads config at startup (`_load_gateway_config()`) and stores values in instance variables (e.g., `self.config`, `self._reasoning_config`). Saving a new `config.yaml` from the dashboard writes the file correctly but the running agent continues using the stale in-memory copy. Users see their changes "saved" yet nothing changes until they restart — with no explanation.

**Why it happens:**
`load_config()` and `_load_gateway_config()` are called once at startup; results are stored in instance state. There is no SIGHUP handler or polling loop in the gateway to detect file changes. `save_config()` in `hermes_cli/config.py` already performs atomic writes (`atomic_yaml_write` via `os.replace`), so the file is always consistent — the problem is purely the in-memory cache.

**How to avoid:**
1. The dashboard's save endpoint must return a clear "restart required for some settings to take effect" message, categorised by which settings are hot-reloadable vs. not.
2. For settings the gateway does re-read per-session (e.g., `_load_gateway_config()` is called per new session at line 3736 and 4941 in `run.py`), they are effectively hot-reloaded for new sessions — document this.
3. Add a `/dashboard/api/restart` endpoint that sends SIGTERM to the gateway PID and lets the process manager (systemd, Docker, Enclava) restart it. Do not try to reload in-process.

**Warning signs:**
- "Save successful" toast but agent behaviour unchanged mid-session
- Users filing bugs that the model change "didn't work"

**Phase to address:**
Live config editing phase — must be designed before the save endpoint is wired up.

---

### Pitfall 3: Secrets Exposed to the Browser

**What goes wrong:**
The config API returns the full config dict (including `~/.hermes/.env` contents) to the browser as JSON. API keys, bot tokens, and OAuth credentials are then visible in browser DevTools network panel, stored in browser history, and potentially leaked to browser extensions.

**Why it happens:**
`load_config()` expands env vars inline (`_expand_env_vars`), so the returned dict contains actual secret values. Developers copy this dict straight into the JSON response because it "works" for displaying current settings.

**How to avoid:**
- Never serve `.env` values directly. The dashboard API for secrets must return only redacted versions (last 4 chars + stars) for display — identical to what `redact_key()` in `hermes_cli/config.py` already does.
- For editing, accept a new value from the browser and write it with `save_env_value()` / `save_env_value_secure()`. Never round-trip a secret back through the browser.
- Apply `X-Content-Type-Options: nosniff` and `Cache-Control: no-store` to all dashboard API responses (the existing `security_headers_middleware` already adds `nosniff` — verify it propagates to the dashboard subapp).
- The dashboard session cookie must be `HttpOnly` and `SameSite=Strict` to prevent JavaScript from reading it.

**Warning signs:**
- Network tab shows full API keys in JSON responses
- Config endpoint returns `OPENAI_API_KEY: sk-proj-...`

**Phase to address:**
Auth + config API phase — redaction strategy must be in the first API endpoint implementation, not retrofitted later.

---

### Pitfall 4: Session Auth Using SimpleCookieStorage (Plaintext)

**What goes wrong:**
`aiohttp_session` with `SimpleCookieStorage` stores session data as a plain base64-encoded JSON string in the cookie. The browser can read and tamper with this directly. An attacker can forge a session cookie claiming to be authenticated without knowing the password.

**Why it happens:**
`SimpleCookieStorage` is the easiest to set up and has no external dependencies. Tutorials use it for brevity. Developers copy tutorial code into production.

**How to avoid:**
Use `EncryptedCookieStorage` with a randomly generated 32-byte key stored in `~/.hermes/.env` (e.g., `DASHBOARD_SECRET_KEY`). The key is generated once on first run if absent. This requires `cryptography` or `aiohttp-session[secure]` — verify it is already in the dependency tree, or add it. Alternatively, implement a minimal stateless token: hash `(username + password + timestamp_bucket)` with HMAC-SHA256, store the token in a `HttpOnly` cookie, and verify on each request — no external library needed.

**Warning signs:**
- Session cookie value is human-readable JSON after base64 decode
- `SimpleCookieStorage` in import statements

**Phase to address:**
Auth implementation phase.

---

### Pitfall 5: Dashboard Auth Middleware Leaking Into API Routes

**What goes wrong:**
If the dashboard auth middleware is registered on the main aiohttp app (not a scoped subapp), it intercepts every request — including `/v1/chat/completions`, `/health`, and `/api/jobs`. OpenAI-compatible clients that don't send a browser session cookie get 302 redirects to `/dashboard/login` instead of JSON error responses. This breaks Open WebUI, LobeChat, and every other API consumer.

**Why it happens:**
Middleware in aiohttp is applied to ALL routes on the app it is registered on. When the dashboard is added to the main `self._app` with shared middlewares, there is no automatic scoping.

**How to avoid:**
Use `app.add_subapp('/dashboard', dashboard_subapp)` where `dashboard_subapp` has its own middleware list including the auth check. The main app's middleware chain is applied first, then the subapp's — but the auth check only lives in the subapp. API routes on the main app never see the dashboard auth middleware. Also ensure the CORS middleware on the main app explicitly skips `/dashboard/*` paths or returns correctly shaped errors.

**Warning signs:**
- Open WebUI loses connection after dashboard is added
- API clients receive HTML login page instead of JSON 401

**Phase to address:**
Foundation / integration phase — route isolation must be verified before auth middleware is written.

---

### Pitfall 6: First-Run Wizard State Lost on Browser Refresh

**What goes wrong:**
The wizard collects values across multiple steps (platform tokens, model choice, etc.). If a user refreshes mid-wizard, all entered values are lost and they restart from step 1. In a server-side HTMX pattern, if the server stores wizard state only in-memory (a Python dict keyed by session), a gateway restart also wipes in-progress setups.

**Why it happens:**
Developers treat wizard state as ephemeral form state, not persisting it. In an HTMX hypermedia pattern, each step submits to the server, which renders the next step — but the accumulated state for previous steps must live somewhere durable.

**How to avoid:**
Two options:
1. Persist partial wizard state to `~/.hermes/wizard_draft.yaml` after each step. On load, resume from the draft. Clear on completion.
2. Pass accumulated values as hidden fields in each wizard step's HTML form (stateless server). Option 2 is simpler but exposes in-progress secrets in the DOM. Prefer option 1.

**Warning signs:**
- Wizard resets on F5
- Support requests from users who lost their token after navigating back

**Phase to address:**
First-run wizard phase.

---

### Pitfall 7: Editing Config.yaml Destroys Comments and Key Order

**What goes wrong:**
The dashboard reads `config.yaml`, modifies a key via the Python `yaml` library, and writes it back with `yaml.dump()`. All YAML comments (the inline documentation that helps users understand each setting) are stripped because `PyYAML` does not preserve comments. Key order may also be scrambled. Users who then open their config in a text editor find it unrecognizable.

**Why it happens:**
`yaml.safe_load` / `yaml.dump` does not preserve the comment tree. This is a known limitation of PyYAML (and most YAML parsers). The existing `save_config()` in `hermes_cli/config.py` already demonstrates the best available workaround: it dumps the structured data first, then appends static comment blocks as raw strings. But it cannot restore user-authored inline comments.

**How to avoid:**
- Use `ruamel.yaml` with `preserve_quotes=True` and `RoundTripLoader` if comment preservation is mandatory. Check if `ruamel.yaml` is already in the dependency tree before adding it.
- If using PyYAML (already present), document clearly in the UI: "Saving from the dashboard will reformat config.yaml. Hand-written comments outside the known sections will be removed." This sets expectations.
- Scope dashboard writes to specific keys only (using `_set_nested` from `hermes_cli/config.py`), reload the full file, merge the change, and write back — never reconstruct the entire file from scratch in the dashboard.

**Warning signs:**
- Users report their config "looks different" after first save
- Inline comments disappear from `config.yaml`

**Phase to address:**
Live config editing phase.

---

### Pitfall 8: NixOS/Managed Mode Not Checked Before Writing

**What goes wrong:**
On NixOS managed deployments (`HERMES_MANAGED=true` or `.managed` marker file exists), configuration is managed declaratively via `configuration.nix`. The dashboard's save endpoint calls `save_config()` or `save_env_value()` and appears to succeed (or silently fails depending on error handling), but the next NixOS activation overwrites the changes. Users lose their dashboard-configured settings.

**Why it happens:**
`save_config()` already checks `is_managed()` and prints an error to stderr — but a web endpoint that calls it won't surface that stderr message to the browser user.

**How to avoid:**
Every dashboard API endpoint that modifies config must call `is_managed()` before proceeding and return HTTP 403 with a JSON body explaining that this instance is managed by NixOS. The dashboard UI should also show a persistent banner: "This instance is NixOS-managed. Configuration changes made here will be overwritten on next system activation."

**Warning signs:**
- Config saves return 200 but changes disappear after `nixos-rebuild switch`
- `HERMES_MANAGED` environment variable is set

**Phase to address:**
Live config editing phase — this check must be in every write endpoint from day one.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode dashboard password in config.yaml as plaintext | No crypto dependency | Password exposed in YAML comments, git history, logs | Never — use hashed storage (`bcrypt` or PBKDF2) |
| Store session in plain cookie | No dependency on `cryptography` | Session forgeable without password | Never in production — use HMAC or encrypted cookie |
| Return full config dict (with expanded env vars) in API | Simple implementation | API keys in browser network tab | Never |
| Skip CSRF token on state-mutating endpoints | Simpler JS | CSRF attacks possible if dashboard is on same origin as other sites user visits | Only if `SameSite=Strict` cookie is enforced AND the user understands the trade-off |
| Write entire config.yaml on each field save | Simple save logic | Comment destruction, unnecessary writes, potential race if agent reads simultaneously | MVP only, document the limitation |
| In-process config reload (monkeypatching `gateway.run` state) | No restart UX | Gateway state becomes inconsistent, subtle bugs with cached model clients | Never — restart is safer |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| aiohttp subapp | Adding subapp after `runner.setup()` | Register subapp before `runner.setup()` is called in `connect()` |
| `hermes_cli/config.py` `save_config()` | Calling without checking `is_managed()` | Call `is_managed()` in the web handler before delegating to `save_config()` |
| `hermes_cli/config.py` `load_config()` | Using the return value directly in JSON response | Filter through redaction layer before serializing |
| `atomic_yaml_write` | Concurrent dashboard saves racing each other | Use an asyncio lock (`asyncio.Lock`) in the dashboard module; `atomic_yaml_write` is crash-safe but not concurrency-safe across two coroutines |
| CORS middleware on existing `self._app` | Dashboard subapp CORS differs from API CORS | aiohttp subapp middleware chains from parent then child; explicit CORS handling needed per-subapp |
| Docker / Enclava deployments | Assuming `~/.hermes` is writable | Dashboard must verify write permissions at startup and surface a clear error if the volume is read-only |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Reading `config.yaml` on every dashboard page load | Slow page renders under load | Cache config in memory; invalidate on save | Negligible at 1 user, but wasteful even then — cache it |
| Serving static files (CSS/JS/HTML) via Python `open()` in handlers | Each request opens a file; no ETags | Use `aiohttp.web.FileResponse` which handles ETags and `If-None-Match` | Noticeable on dashboard reload-heavy development workflows |
| YAML parse on every config API call | CPU spike on repeated polling | Parse once at load, invalidate on write | 100+ rapid API calls |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing dashboard on `0.0.0.0` without auth check | Anyone on the LAN can access config and secrets | Default to `127.0.0.1`; require explicit opt-in to expose externally; enforce auth regardless of bind address |
| Storing dashboard password in `config.yaml` as plaintext | Password readable by anyone with file access | Store as `bcrypt` hash or PBKDF2 hash; never store raw password |
| No brute-force protection on `/dashboard/login` | Offline password guessing against the login endpoint | Rate-limit: track failed attempts per IP in-memory; lock out for 60s after 5 failures |
| Missing `HttpOnly` flag on session cookie | JavaScript can read and exfiltrate the session token | Set `httponly=True` in `aiohttp_session` or manual cookie creation |
| Missing `SameSite=Strict` on session cookie | CSRF attacks from other browser tabs | Set `samesite='Strict'` on the session cookie |
| Serving `~/.hermes/.env` as a static file or raw config export | Full secret exposure | Never serve `.env` contents — only individual redacted values via typed API endpoints |
| Using `yaml.load()` instead of `yaml.safe_load()` for user-uploaded configs | Arbitrary Python object construction / RCE | Always use `yaml.safe_load()` — already enforced in existing codebase, maintain this in dashboard API |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| HTMX silent 5XX failures | User clicks save, nothing happens, no feedback | Add `htmx:responseError` global event listener; show a toast on any non-2xx response |
| Wizard "back" button re-POSTing previous step | Duplicate writes; user confusion about state | Use PRG (Post/Redirect/Get) pattern for wizard steps, or disable back and use explicit "Previous" button that loads from server-side draft |
| "Saved!" toast with no indication restart is needed | User thinks change is live when it isn't | Show context-aware feedback: "Saved. Restart the gateway for this to take effect." vs. "Saved. Active for new sessions immediately." |
| Config form shows raw YAML keys (`agent.max_turns`) | Non-technical users confused | Map config keys to human-friendly labels and group into logical sections (Model, Memory, Platforms, etc.) |
| No validation before writing to config | User enters invalid model name; agent breaks | Validate known fields (model name format, numeric ranges, boolean flags) before writing; return field-level errors |
| First-run wizard skippable with no way back | User skips setup, agent fails to connect anywhere | If wizard is skipped with zero platforms configured, detect on next page load and prompt return to wizard |

---

## "Looks Done But Isn't" Checklist

- [ ] **Auth on ALL dashboard routes:** Every `/dashboard/*` path — including static files, API endpoints, and the status page — must require auth. Forgetting to protect `/dashboard/api/status` exposes agent health data.
- [ ] **Redaction on ALL config read endpoints:** Any endpoint that returns config values must pass through the redaction layer. Check new endpoints added during each feature phase.
- [ ] **NixOS managed-mode guard on ALL write endpoints:** Every POST/PATCH/PUT/DELETE handler that modifies config must call `is_managed()` before proceeding.
- [ ] **HTMX error feedback wired up:** Default HTMX silently drops 5XX responses. Verify a global `htmx:responseError` handler is in the base HTML template before any feature is considered done.
- [ ] **Wizard draft cleanup on completion:** `wizard_draft.yaml` (or equivalent) must be deleted after the wizard completes. A leftover draft causes the wizard to "resume" unexpectedly on the next visit.
- [ ] **Session cookie attributes:** Verify `HttpOnly`, `SameSite=Strict`, and `Secure` (if HTTPS) flags are set. Check with browser DevTools Application > Cookies after implementing auth.
- [ ] **Static files have correct content types:** Vanilla JS/CSS served with wrong MIME type are blocked by browsers in strict mode. Use `aiohttp.web.FileResponse` or explicit `content_type` arguments.
- [ ] **Dashboard works when `api_server` platform is disabled:** If a user has not enabled the API server platform, the dashboard has no port to listen on. Document this dependency clearly and surface it in the first-run wizard.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Router frozen — dashboard routes not registered | HIGH | Refactor mount point to pre-setup hook; all dashboard route handlers must be re-examined for correct prefix |
| Secrets exposed in API responses | HIGH | Rotate all exposed keys immediately; add redaction layer; audit logs for any scraping of the endpoint |
| Config.yaml destroyed (comments stripped, invalid YAML) | MEDIUM | Restore from backup (atomic write preserves previous file in tmp if process crashed mid-write); add schema validation before write |
| NixOS writes silently overwritten | LOW | Surface managed-mode check; user must re-apply changes via `configuration.nix` |
| HTMX silent failures shipping to users | MEDIUM | Add global error handler to base template; re-test all wizard steps for error cases |
| Auth middleware leaking to API routes | HIGH | Move auth middleware to subapp scope only; retest all API clients (Open WebUI, curl) after fix |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Router frozen / mount timing | Phase 1: Foundation & route architecture | `curl /dashboard/` returns 200; `curl /v1/models` still returns JSON |
| Auth middleware leaking to API routes | Phase 1: Foundation & route architecture | OpenAI-compatible client (e.g., `curl -H 'Authorization: Bearer x' /v1/chat/completions`) works before and after dashboard is added |
| Session auth using SimpleCookieStorage | Phase 2: Auth implementation | Session cookie is opaque (not human-readable JSON) in DevTools |
| Secrets exposed to browser | Phase 2: Auth + config API | Network tab shows `"OPENAI_API_KEY": "sk-proj-...***"` (redacted) not full key |
| NixOS managed-mode not checked | Phase 3: Live config editing | `HERMES_MANAGED=true hermes gateway` — save attempt returns HTTP 403 with explanation |
| Config YAML comments destroyed | Phase 3: Live config editing | After dashboard save, `config.yaml` still contains comment headers (verify manually) |
| Live config not picked up by agent | Phase 3: Live config editing | UI shows "restart required" badge for settings that need restart; new sessions pick up per-session-loaded settings without restart |
| First-run wizard state lost on refresh | Phase 4: First-run wizard | Refresh mid-wizard on step 3 — resumes at step 3 with previously entered values intact |
| HTMX silent 5XX failures | All phases | Simulate a 500 from any wizard step — a visible error toast appears |
| Brute-force on login | Phase 2: Auth implementation | 6 rapid POST /dashboard/login with wrong password — 6th returns 429 or locked response |

---

## Sources

- aiohttp Web Server Advanced (subapp routing, middleware scoping): https://docs.aiohttp.org/en/stable/web_advanced.html
- aiohttp frozen router behavior: https://github.com/aio-libs/aiohttp/issues/3701
- aiohttp-session security (SimpleCookieStorage vs EncryptedCookieStorage): https://github.com/aio-libs/aiohttp-session
- HTMX silent error handling: https://thomashunter.name/posts/2025-11-05-a-few-months-with-htmx
- HTMX for admin dashboards (internal use case analysis): https://adjoe.io/company/engineer-blog/how-to-simplify-web-development-with-htmx/
- .env secrets exposure risks: https://medium.com/@360Security/exposing-sensitive-data-from-env-1b0104b2cf65
- Python config race conditions and locking: https://medium.com/pythoneers/avoiding-race-conditions-in-python-in-2025-best-practices-for-async-and-threads-4e006579a622
- SIGHUP-based config reload pattern: https://medium.com/@snnapys-devops/keep-your-python-running-reloading-configuration-on-the-fly-with-sighup-8cac1179c24d
- aiohttp-security (identity and authorization policy): https://aiohttp-security.readthedocs.io/en/latest/usage.html
- Codebase analysis: `gateway/platforms/api_server.py` (route registration, middleware, app lifecycle)
- Codebase analysis: `hermes_cli/config.py` (`save_config`, `load_config`, `is_managed`, `save_env_value`, `redact_key`)
- Codebase analysis: `gateway/run.py` (`_load_gateway_config`, per-session config reload pattern)
- Codebase analysis: `utils.py` (`atomic_yaml_write` implementation)

---
*Pitfalls research for: Web config dashboard on Hermes Agent (aiohttp, vanilla JS, YAML config, single-user auth)*
*Researched: 2026-03-30*
