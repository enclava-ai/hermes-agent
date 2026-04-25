"""Reverse-proxy server with username/password gate.

Forwards HTTP and WebSocket traffic to upstream's hermes web server, but
only after validating an HMAC-signed session cookie. First-run renders a
"create admin credentials" form instead of the login page.

Run via:
    python -m auth_proxy --listen 0.0.0.0:9120 --upstream 127.0.0.1:9119
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

from auth_proxy.credentials import (
    Credentials,
    load_credentials,
    save_credentials,
    verify_password,
)

logger = logging.getLogger(__name__)

COOKIE_NAME = "hermes_auth"
COOKIE_TTL_SECONDS = 24 * 3600  # 24h sessions

# Hop-by-hop headers per RFC 7230 — must not be forwarded blindly.
_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    # We strip "content-length" because aiohttp recomputes it.
    "content-length",
})


# ---------------------------------------------------------------------------
# Cookie / session signing
# ---------------------------------------------------------------------------


def _signing_key() -> bytes:
    """Stable HMAC key derived from the credentials hash.

    Tying the cookie key to the password hash means changing the password
    automatically invalidates all live sessions — no extra revocation logic.
    """
    creds = load_credentials()
    if creds is None:
        # Pre-setup: ephemeral key. Anyone hitting the proxy before setup
        # will see /__auth/setup; cookies issued then are ignored after
        # real credentials exist.
        return b"hermes-auth-proxy-pre-setup"
    return hashlib.sha256(b"hermes-auth-proxy:v1:" + creds.hash).digest()


def _make_cookie_value(username: str, expiry_ts: int) -> str:
    body = f"{username}:{expiry_ts}".encode("utf-8")
    sig = hmac.new(_signing_key(), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body).decode("ascii") + "." + base64.urlsafe_b64encode(sig).decode("ascii")


def _validate_cookie(value: str) -> Optional[str]:
    """Return the username if the cookie is valid and unexpired, else None."""
    try:
        body_b64, sig_b64 = value.split(".", 1)
        body = base64.urlsafe_b64decode(body_b64.encode("ascii"))
        sig = base64.urlsafe_b64decode(sig_b64.encode("ascii"))
        expected = hmac.new(_signing_key(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        username, _, expiry_str = body.decode("utf-8").partition(":")
        if not username or not expiry_str.isdigit():
            return None
        if int(expiry_str) < int(time.time()):
            return None
        creds = load_credentials()
        if creds is None or creds.username != username:
            return None
        return username
    except (ValueError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Inline HTML — the proxy's only owned UI
# ---------------------------------------------------------------------------


_PAGE_CSS = """
:root { color-scheme: dark; font-family: ui-monospace, "JetBrains Mono", monospace; }
body { background:#0b0b0c; color:#eaeaea; margin:0; min-height:100vh;
       display:flex; align-items:center; justify-content:center; }
.box { width:340px; border:1px solid #333; padding:28px 24px; background:#111; }
h1 { font-size:14px; letter-spacing:0.18em; text-transform:uppercase; margin:0 0 18px; color:#9aa; }
label { display:block; font-size:11px; letter-spacing:0.12em; text-transform:uppercase; color:#888; margin:14px 0 4px; }
input { width:100%; box-sizing:border-box; background:#1b1b1c; border:1px solid #333; color:#eaeaea;
        padding:8px 10px; font:inherit; }
input:focus { outline:none; border-color:#666; }
button { margin-top:18px; width:100%; background:#222; border:1px solid #444; color:#eaeaea;
         padding:10px; font:inherit; cursor:pointer; letter-spacing:0.1em; text-transform:uppercase; font-size:12px; }
button:hover { background:#2a2a2a; }
.error { margin-top:10px; padding:8px 10px; border:1px solid #a33; color:#fbb; font-size:12px; }
.muted { color:#777; font-size:11px; margin-top:14px; line-height:1.5; }
"""


def _render_login(error: Optional[str] = None, next_url: str = "/") -> str:
    err_html = f'<div class="error">{error}</div>' if error else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Hermes — Sign in</title>
<style>{_PAGE_CSS}</style></head><body>
<form class="box" method="post" action="/__auth/login">
  <h1>Hermes Dashboard</h1>
  <input type="hidden" name="next" value="{_html_escape(next_url)}">
  <label>Username</label>
  <input name="username" autocomplete="username" autofocus required>
  <label>Password</label>
  <input name="password" type="password" autocomplete="current-password" required>
  <button type="submit">Sign in</button>
  {err_html}
</form></body></html>"""


def _render_setup(error: Optional[str] = None) -> str:
    err_html = f'<div class="error">{error}</div>' if error else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Hermes — Initial setup</title>
<style>{_PAGE_CSS}</style></head><body>
<form class="box" method="post" action="/__auth/setup">
  <h1>Create admin credentials</h1>
  <p class="muted">First-run setup. These credentials gate access to the Hermes dashboard at this URL.</p>
  <label>Username</label>
  <input name="username" value="admin" autocomplete="username" autofocus required>
  <label>Password (min 8)</label>
  <input name="password" type="password" autocomplete="new-password" minlength="8" required>
  <label>Confirm password</label>
  <input name="confirm" type="password" minlength="8" required>
  <button type="submit">Create &amp; sign in</button>
  {err_html}
</form></body></html>"""


def _html_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def handle_login_get(request: web.Request) -> web.Response:
    if load_credentials() is None:
        raise web.HTTPFound("/__auth/setup")
    next_url = request.query.get("next") or "/"
    return web.Response(text=_render_login(next_url=next_url), content_type="text/html")


async def handle_login_post(request: web.Request) -> web.StreamResponse:
    data = await request.post()
    creds = load_credentials()
    if creds is None:
        raise web.HTTPFound("/__auth/setup")
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    next_url = str(data.get("next", "/")) or "/"
    if not username or not password or not verify_password(creds, username, password):
        # Slow down brute-force attempts (cheaper than rate-limiting infra).
        await asyncio.sleep(0.5)
        return web.Response(
            text=_render_login(error="Invalid username or password.", next_url=next_url),
            content_type="text/html",
            status=401,
        )
    expiry = int(time.time()) + COOKIE_TTL_SECONDS
    cookie = _make_cookie_value(username, expiry)
    resp = web.HTTPFound(_safe_redirect(next_url))
    resp.set_cookie(
        COOKIE_NAME, cookie,
        max_age=COOKIE_TTL_SECONDS,
        httponly=True,
        samesite="Lax",
        secure=request.scheme == "https",
        path="/",
    )
    return resp


async def handle_logout(request: web.Request) -> web.StreamResponse:
    resp = web.HTTPFound("/__auth/login")
    resp.del_cookie(COOKIE_NAME, path="/")
    return resp


async def handle_setup_get(request: web.Request) -> web.Response:
    if load_credentials() is not None:
        raise web.HTTPFound("/__auth/login")
    return web.Response(text=_render_setup(), content_type="text/html")


async def handle_setup_post(request: web.Request) -> web.StreamResponse:
    if load_credentials() is not None:
        raise web.HTTPFound("/__auth/login")
    data = await request.post()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    confirm = str(data.get("confirm", ""))
    if password != confirm:
        return web.Response(
            text=_render_setup(error="Passwords do not match."),
            content_type="text/html", status=400,
        )
    try:
        save_credentials(username, password)
    except ValueError as e:
        return web.Response(
            text=_render_setup(error=str(e)),
            content_type="text/html", status=400,
        )
    expiry = int(time.time()) + COOKIE_TTL_SECONDS
    cookie = _make_cookie_value(username, expiry)
    resp = web.HTTPFound("/")
    resp.set_cookie(
        COOKIE_NAME, cookie,
        max_age=COOKIE_TTL_SECONDS,
        httponly=True, samesite="Lax",
        secure=request.scheme == "https",
        path="/",
    )
    return resp


def _safe_redirect(target: str) -> str:
    """Only allow same-origin relative paths to prevent open-redirect."""
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


# ---------------------------------------------------------------------------
# Reverse-proxy core (HTTP + WebSocket)
# ---------------------------------------------------------------------------


def _is_authed(request: web.Request) -> bool:
    cookie = request.cookies.get(COOKIE_NAME)
    return bool(cookie and _validate_cookie(cookie))


def _filter_request_headers(request: web.Request, upstream_host: str) -> dict:
    out = {}
    for k, v in request.headers.items():
        if k.lower() in _HOP_BY_HOP:
            continue
        out[k] = v
    out["host"] = upstream_host
    # Standard proxy hint headers.
    fwd = request.headers.get("X-Forwarded-For", "")
    peer = request.transport.get_extra_info("peername") if request.transport else None
    client_ip = peer[0] if peer else ""
    out["X-Forwarded-For"] = f"{fwd}, {client_ip}".strip(", ") if client_ip else fwd
    out["X-Forwarded-Proto"] = request.scheme
    out["X-Forwarded-Host"] = request.headers.get("Host", "")
    return out


def _filter_response_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


async def proxy_websocket(
    request: web.Request, upstream_url: str, upstream_host: str,
) -> web.WebSocketResponse:
    ws_server = web.WebSocketResponse()
    await ws_server.prepare(request)

    headers = _filter_request_headers(request, upstream_host)
    # aiohttp's WS client sets its own Sec-WebSocket-* headers — strip ours.
    for h in list(headers):
        if h.lower().startswith("sec-websocket"):
            headers.pop(h, None)

    session = aiohttp.ClientSession()
    try:
        ws_client = await session.ws_connect(
            upstream_url, headers=headers, autoping=True, max_msg_size=0,
        )
    except aiohttp.ClientError as e:
        logger.warning("auth_proxy: WS connect failed: %s", e)
        await ws_server.close(code=1011, message=b"upstream unreachable")
        await session.close()
        return ws_server

    async def s2c() -> None:
        async for msg in ws_client:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await ws_server.send_str(msg.data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                await ws_server.send_bytes(msg.data)
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
        await ws_server.close()

    async def c2s() -> None:
        async for msg in ws_server:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await ws_client.send_str(msg.data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                await ws_client.send_bytes(msg.data)
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
        await ws_client.close()

    try:
        await asyncio.gather(s2c(), c2s())
    finally:
        await ws_client.close()
        await session.close()
    return ws_server


async def proxy_http(
    request: web.Request, upstream_url: str, upstream_host: str,
    http_session: aiohttp.ClientSession,
) -> web.StreamResponse:
    headers = _filter_request_headers(request, upstream_host)
    body = await request.read() if request.can_read_body else None
    try:
        upstream_resp = await http_session.request(
            request.method,
            upstream_url,
            headers=headers,
            data=body,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=None, sock_read=300),
        )
    except aiohttp.ClientError as e:
        logger.warning("auth_proxy: upstream request failed (%s %s): %s",
                       request.method, request.path, e)
        return web.Response(status=502, text="Upstream unreachable")

    # Stream the body back to keep memory bounded for large responses (logs SSE etc).
    response = web.StreamResponse(
        status=upstream_resp.status,
        headers=_filter_response_headers(upstream_resp.headers),
    )
    await response.prepare(request)
    try:
        async for chunk in upstream_resp.content.iter_any():
            if chunk:
                await response.write(chunk)
    finally:
        upstream_resp.release()
    await response.write_eof()
    return response


# ---------------------------------------------------------------------------
# Catch-all dispatcher
# ---------------------------------------------------------------------------


def make_dispatcher(upstream_host: str, upstream_port: int):
    upstream_base = f"http://{upstream_host}:{upstream_port}"
    upstream_ws_base = f"ws://{upstream_host}:{upstream_port}"
    upstream_host_header = f"{upstream_host}:{upstream_port}"

    async def dispatch(request: web.Request) -> web.StreamResponse:
        path = request.match_info["path"]

        # Auth-proxy's own routes are claimed by explicit handlers below
        # via app.router.add_*. Anything reaching here is for upstream.
        if not _is_authed(request):
            # Save where the user wanted to go.
            qs = urlencode({"next": request.path_qs})
            raise web.HTTPFound(f"/__auth/login?{qs}")

        # WebSocket?
        if (request.headers.get("upgrade", "").lower() == "websocket"
                and request.headers.get("connection", "").lower().find("upgrade") != -1):
            ws_url = f"{upstream_ws_base}/{path}"
            if request.query_string:
                ws_url += f"?{request.query_string}"
            return await proxy_websocket(request, ws_url, upstream_host_header)

        url = f"{upstream_base}/{path}"
        if request.query_string:
            url += f"?{request.query_string}"
        return await proxy_http(request, url, upstream_host_header, request.app["http_session"])

    return dispatch


# ---------------------------------------------------------------------------
# App factory + lifecycle
# ---------------------------------------------------------------------------


def build_app(upstream_host: str, upstream_port: int) -> web.Application:
    app = web.Application(client_max_size=1024 * 1024 * 50)  # 50 MB upload ceiling

    # Auth routes — note these win against the catch-all because aiohttp
    # picks the first matching route registered.
    app.router.add_get("/__auth/login", handle_login_get)
    app.router.add_post("/__auth/login", handle_login_post)
    app.router.add_post("/__auth/logout", handle_logout)
    app.router.add_get("/__auth/setup", handle_setup_get)
    app.router.add_post("/__auth/setup", handle_setup_post)

    dispatch = make_dispatcher(upstream_host, upstream_port)
    # `{path:.*}` matches everything including empty path (root).
    app.router.add_route("*", "/{path:.*}", dispatch)

    async def _on_startup(app: web.Application) -> None:
        app["http_session"] = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(force_close=False),
            auto_decompress=False,  # leave bodies untouched for upstream's content-encoding
        )
        if load_credentials() is None:
            logger.warning(
                "auth_proxy: no credentials configured. Visit /__auth/setup to create them."
            )

    async def _on_cleanup(app: web.Application) -> None:
        await app["http_session"].close()

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app


def run(
    listen_host: str = "0.0.0.0",
    listen_port: int = 9120,
    upstream_host: str = "127.0.0.1",
    upstream_port: int = 9119,
) -> None:
    logging.basicConfig(
        level=os.environ.get("HERMES_AUTH_PROXY_LOG", "INFO").upper(),
        format="%(asctime)s %(levelname)s [auth_proxy] %(message)s",
    )
    app = build_app(upstream_host, upstream_port)
    logger.info("listening on %s:%d → upstream %s:%d",
                listen_host, listen_port, upstream_host, upstream_port)
    web.run_app(app, host=listen_host, port=listen_port, print=None)
