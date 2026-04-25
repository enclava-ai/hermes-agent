# Hermes Auth Proxy

Username/password gate that sits in front of upstream's `hermes web` dashboard.

## When to use this

Use it when you want to expose the dashboard beyond `localhost` and **can't**
put a real reverse proxy (Caddy, nginx, Traefik) in front. Otherwise prefer
the reverse proxy — that's what upstream officially recommends.

## How it works

```
Browser ──HTTPS──► Caddy/nginx (TLS terminator, optional)
                          │
                          ▼
                  auth_proxy :9120  ──► hermes web :127.0.0.1:9119
                  (login form,
                   HMAC cookie,
                   reverse proxy)
```

- Binds whatever interface you want (default `0.0.0.0:9120`).
- Forces upstream to bind `127.0.0.1` so it's only reachable through the proxy.
- First-run renders a "create admin credentials" form. Creds get hashed with
  `hashlib.scrypt` and saved to `~/.hermes/.dashboard_auth.json`.
- Sessions are HMAC-signed cookies keyed off the credential hash, so changing
  the password invalidates every live session automatically.
- Forwards both HTTP and WebSocket (the dashboard uses `/api/pty` for the
  embedded TUI).

## Running it

```sh
# 1) Bind upstream to localhost only (otherwise you've defeated the proxy):
HERMES_DASHBOARD_BIND=127.0.0.1 hermes web --port 9119 &

# 2) Start the proxy on whatever interface you want to expose:
python -m auth_proxy --listen 0.0.0.0:9120 --upstream 127.0.0.1:9119
```

First request to any URL bounces to `/__auth/setup`. After you create
credentials you're auto-logged in and dropped at the dashboard root.

## Routes the proxy owns

| Path | Method | Purpose |
| --- | --- | --- |
| `/__auth/setup` | GET, POST | First-run admin credential creation |
| `/__auth/login` | GET, POST | Login form |
| `/__auth/logout` | POST | Clear cookie, redirect to login |
| everything else | * | Proxied to upstream |

## Why this lives outside the upstream `web_server.py`

- **Real security boundary.** A plugin can't gate `/index.html` (upstream
  injects the session token there). The proxy can — it's a separate process
  that controls the entire request path.
- **Zero upstream modifications.** Future merges from `upstream/main` never
  touch this directory. The only coupling is "upstream is an HTTP server on
  some host:port" — about as stable a contract as can exist.
- **Independent lifecycle.** You can disable the proxy by running upstream
  directly. You can run multiple proxies (e.g., one per Tailscale tailnet).

## Threats this does and doesn't address

| Threat | Status |
| --- | --- |
| Anonymous internet access to the dashboard | mitigated |
| Brute-force login | partially: 0.5s sleep on failure, no rate limiting yet |
| TLS interception | not handled — terminate TLS in Caddy/nginx in front |
| Compromised host | not handled — anyone with `~/.hermes` access wins |
| CSRF on `/api/*` | inherited from upstream's CSRF posture |

If you need rate limiting / IP allowlists / TLS / WAF features, run a real
proxy in front of this one. The auth proxy doesn't try to compete with that.

## Maintenance

Single Python module + one credentials file. Stdlib only except for
`aiohttp` (which Hermes already depends on). Future upstream merges should
not affect this directory.

If upstream renames the session-token global (`window.__HERMES_SESSION_TOKEN__`),
the proxy keeps working — it doesn't parse upstream's HTML at all, just
passes bytes through.
