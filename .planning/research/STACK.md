# Stack Research

**Domain:** Lightweight web config dashboard — vanilla JS + HTMX on existing aiohttp Python server
**Researched:** 2026-03-30
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| aiohttp | 3.13.4 (already in `messaging` extras) | HTTP server — routes, static files, middleware | Already the runtime for the gateway process; zero new dependency. Dashboard routes are additive handlers in the same `web.Application`. |
| aiohttp-jinja2 | 1.6 | Server-side Jinja2 template rendering | Official aio-libs integration; decorator-based `@aiohttp_jinja2.template` keeps handlers thin; Jinja2 is already a core dependency in `pyproject.toml`. |
| HTMX | 2.0.8 (CDN, no install) | Browser-side partial page swaps without JavaScript | Eliminates writing imperative JS for form submissions, toggle interactions, and live status updates. Server returns HTML fragments; no JSON/fetch boilerplate. HTMX 4.0 is alpha — do not use. |
| Pico CSS | 2.1.1 (CDN, no install) | Semantic styling with zero class clutter | Styles raw HTML elements automatically (no utility classes required). Single CDN link, no build step, responsive by default, WCAG 2.1 AAA compliant. Correct fit for a settings UI with forms, tables, and nav. |
| aiohttp-session | 2.12.1 | Cookie-based session storage for login state | Official aio-libs session library; `EncryptedCookieStorage` stores session data in an AES-encrypted cookie — no database required for single-user auth. |
| argon2-cffi | 25.1.0 | Password hashing for stored dashboard credential | OWASP-recommended algorithm (argon2id) for password storage; outperforms bcrypt on resistance to GPU attacks. Single call: `PasswordHasher().hash(password)` / `.verify(hash, password)`. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cryptography | already pulled in by `PyJWT[crypto]` | AES key generation for `EncryptedCookieStorage` | Use `secrets.token_bytes(32)` for the key (stdlib), stored in `~/.hermes/.env`. No new import needed — `cryptography` wheel is already on the machine. |
| PyYAML | 6.0.2 (already in core deps) | Read/write `~/.hermes/config.yaml` | Reuse `hermes_cli/config.py` which already wraps YAML I/O — no direct PyYAML calls needed in dashboard handlers. |
| HTMX `response-targets` extension | 2.0.x (CDN) | Route HTMX error responses to a dedicated error element | Load from `https://extensions.htmx.org` only if form error display becomes complex. Defer until needed. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| aiohttp's built-in static handler (`app.add_static`) | Serve `/dashboard/static/` during development | Use `append_version=True` for cache busting. Production deployments behind nginx or the Enclava reverse proxy should let nginx serve `/dashboard/static/` directly. |
| Jinja2 `FileSystemLoader` | Load templates from `gateway/dashboard/templates/` | Point to a path relative to `__file__` inside the dashboard module so it works regardless of cwd. |
| Browser DevTools | Debug HTMX requests | HTMX fires standard `fetch`-style XHR; Network tab shows full request/response. No extra tooling needed. |

## Installation

```bash
# New dependencies only — everything else is already in pyproject.toml
pip install aiohttp-jinja2==1.6 aiohttp-session==2.12.1 argon2-cffi==25.1.0
```

Add to `pyproject.toml` under a new `dashboard` optional dependency group:

```toml
dashboard = [
  "aiohttp>=3.13.3,<4",       # already in messaging; listed for explicitness
  "aiohttp-jinja2>=1.6,<2",
  "aiohttp-session>=2.12.1,<3",
  "argon2-cffi>=25.1.0,<26",
]
```

HTMX and Pico CSS are loaded from CDN in HTML templates — no Python install, no Node.js, no build step.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| HTMX 2.0.8 | Alpine.js 3.x | If dashboard needs significant client-side state (e.g., reactive form validation across many fields without a server round-trip). Alpine is complementary, not a replacement. |
| Pico CSS 2.1.1 | Bootstrap 5 | If the project already uses Bootstrap elsewhere or needs a wider component library (modals, dropdowns). Bootstrap requires more HTML scaffolding and is 10x larger. |
| argon2-cffi | bcrypt 4.x | bcrypt is acceptable if argon2-cffi is blocked by deployment constraints (bcrypt is more widely packaged in distro repos). argon2id is strictly preferred by OWASP 2025 guidelines. |
| aiohttp-session + EncryptedCookieStorage | JWT tokens in a cookie | JWT adds complexity (signing keys, expiry logic, token refresh) with no benefit for a single-user dashboard that has no API consumers. Session cookie is simpler and correct. |
| aiohttp-jinja2 | Raw string concatenation / f-strings | Never: XSS. Use Jinja2 auto-escaping unconditionally. |
| aiohttp-jinja2 | Mako templates | Mako is not in the existing dependency tree; Jinja2 is already pinned in core deps. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| React / Vue / Svelte | Require a Node.js build pipeline; produce a separate frontend artifact; contradict the project constraint of no build step | HTMX + Pico CSS loaded from CDN |
| HTMX 4.0 alpha | Pre-release; API not stable; docs sparse; targeting early/mid 2026 stable | HTMX 2.0.8 stable |
| `SimpleCookieStorage` | Stores session data as plain JSON in cookie — readable by the browser, trivially forgeable | `EncryptedCookieStorage` with a 32-byte secret key |
| `aiohttp-basicauth` (HTTP Basic Auth) | Browser prompts a native dialog; can't build a styled login page; no logout mechanism | Custom login form + `aiohttp-session` |
| Global Python variables for session state | aiohttp explicitly discourages singletons; breaks with multiple worker processes | `request.app['key']` for app-scoped state; `aiohttp-session` for user-scoped state |
| `follow_symlinks=True` on static handler | Path traversal vulnerability documented in aiohttp security notes | Default (symlinks restricted to static root) |
| Tailwind CSS (CDN play-CDN build) | The CDN version is a large runtime compiler (~400KB); the proper version requires a Node.js build step | Pico CSS (8KB, zero JS, CDN-safe) |

## Stack Patterns by Variant

**For HTML fragment responses (HTMX partial swaps):**
- Return `aiohttp.web.Response(text=rendered_html, content_type='text/html')` from handlers
- Use a separate Jinja2 template per fragment (e.g., `_platform_row.html`) so full-page and partial renders share markup
- Check `request.headers.get('HX-Request')` to distinguish HTMX from full-page requests if needed

**For form submission handlers:**
- Accept `POST application/x-www-form-urlencoded` (default HTML form encoding — no JSON, no fetch)
- Read with `data = await request.post()`
- On validation error: return HTTP 422 with an HTML fragment containing the error message targeted by `hx-target="#error-box"`
- On success: return HTTP 200 with updated fragment or use `HX-Redirect` response header for full-page navigation

**For the login flow:**
- Serve a full `login.html` page (no HTMX needed — standard form POST)
- On POST `/dashboard/login`: verify password with `argon2-cffi`, set `session['authenticated'] = True`, redirect to dashboard
- Use an aiohttp middleware that checks `session['authenticated']` on every `/dashboard/*` route; redirect to `/dashboard/login` if not set

**For deployment behind nginx (production):**
- Map `/dashboard/static/` to the filesystem in nginx config; bypass aiohttp for asset serving
- Keep aiohttp's `add_static` as a fallback for local/Docker runs where nginx is absent

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| aiohttp-jinja2 1.6 | aiohttp >=3.6.3, Jinja2 >=3.0 | Both satisfied: aiohttp 3.13.x is in use; Jinja2 3.1.5 is pinned in core deps. |
| aiohttp-session 2.12.1 | aiohttp 3.10+ (typing fix) | Compatible with aiohttp 3.13.x. No Redis needed — `EncryptedCookieStorage` is built-in. |
| argon2-cffi 25.1.0 | Python 3.8–3.14 | Project requires Python >=3.11 — fully compatible. |
| HTMX 2.0.8 | Any modern browser (no IE) | aiohttp already serves HTML; HTMX is a CDN script tag — no server-side compatibility concerns. |
| Pico CSS 2.1.1 | Any modern browser (no IE) | Pure CSS; no JS; no server interaction. |

## Sources

- [HTMX 2.0.8 CDN package.json](https://cdn.jsdelivr.net/npm/htmx.org/package.json) — version confirmed HIGH confidence
- [HTMX 2.0 release announcement](https://htmx.org/posts/2024-06-17-htmx-2-0-0-is-released/) — stable branch confirmed
- [HTMX 4.0 alpha announcement](https://four.htmx.org/posts/2025-11-10-htmx-4-0-0-alpha-is-released/) — pre-release, do not use
- [aiohttp 3.13.4 docs](https://docs.aiohttp.org/en/stable/) — static file serving patterns HIGH confidence
- [aiohttp-jinja2 PyPI](https://pypi.org/project/aiohttp-jinja2/) — version 1.6, November 2023 HIGH confidence
- [aiohttp-session PyPI](https://pypi.org/project/aiohttp-session/) — version 2.12.1, September 2024 HIGH confidence
- [argon2-cffi PyPI](https://pypi.org/project/argon2-cffi/) — version 25.1.0 HIGH confidence
- [Pico CSS releases](https://github.com/picocss/pico/releases) — version 2.1.1, March 2025 HIGH confidence
- [aiohttp web_advanced docs](https://docs.aiohttp.org/en/stable/web_advanced.html) — `add_static` patterns HIGH confidence
- [hermes-agent pyproject.toml](../pyproject.toml) — existing dependency constraints verified directly

---
*Stack research for: Hermes web config dashboard (vanilla JS + HTMX on aiohttp)*
*Researched: 2026-03-30*
