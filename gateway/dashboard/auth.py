"""
Dashboard authentication layer.

Implements:
- Fernet-encrypted session cookie (hermes_dash_session), 24h TTL
- argon2id password hashing and verification
- First-run password generation and force-change flag
- Auth middleware (dashboard subapp only — never on main app)
- Login / logout / change-password HTTP handlers
- In-memory brute-force rate limiting (5 attempts / 60s per IP)
- Secret redaction for browser-safe config display
"""
import json
import logging
import secrets
import string
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from aiohttp import web
    import aiohttp_jinja2
    from cryptography.fernet import Fernet, InvalidToken
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False

# --- Constants ---

SESSION_COOKIE = "hermes_dash_session"
SESSION_TTL = 86400  # 24 hours in seconds

EXEMPT_PATHS = {"/login", "/logout"}
EXEMPT_PREFIXES = ("/static",)

_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60

# --- Module-level state ---

_PH = PasswordHasher() if _DEPS_AVAILABLE else None  # type: ignore[assignment]
_FAILED_ATTEMPTS: dict[str, list[float]] = defaultdict(list)


# --- Brute-force protection ---

def _is_locked_out(ip: str) -> bool:
    now = time.time()
    _FAILED_ATTEMPTS[ip] = [t for t in _FAILED_ATTEMPTS[ip] if now - t < _LOCKOUT_SECONDS]
    return len(_FAILED_ATTEMPTS[ip]) >= _MAX_ATTEMPTS


def _record_failed(ip: str) -> None:
    _FAILED_ATTEMPTS[ip].append(time.time())


# --- Secret redaction (browser-safe, no ANSI codes) ---

def redact_secret(value: str) -> str:
    """Redact a secret for browser display. Returns prefix + *** or just ***."""
    if not value or len(value) < 8:
        return "***"
    return value[:4] + "***"


# --- Password helpers ---

def hash_password(password: str) -> str:
    return _PH.hash(password)


def verify_password(stored_hash: str, provided: str) -> bool:
    try:
        return _PH.verify(stored_hash, provided)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# --- Fernet session token ---

def make_session_token(fernet: "Fernet") -> str:
    payload = json.dumps({"ts": time.time()}).encode()
    return fernet.encrypt(payload).decode()


def verify_session_token(fernet: "Fernet", token: str) -> bool:
    try:
        raw = fernet.decrypt(token.encode(), ttl=SESSION_TTL)
        json.loads(raw)
        return True
    except (InvalidToken, Exception):
        return False


def set_session_cookie(response: "web.Response", fernet: "Fernet") -> None:
    token = make_session_token(fernet)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="Strict",
        max_age=SESSION_TTL,
        path="/dashboard",
    )


def clear_session_cookie(response: "web.Response") -> None:
    response.del_cookie(SESSION_COOKIE, path="/dashboard")


# --- Fernet key management ---

def load_or_create_fernet_key() -> "Fernet":
    """
    Load DASHBOARD_FERNET_KEY from ~/.hermes/.env, or generate and persist a new one.
    Must be called at startup — not on every request.
    """
    from hermes_cli.config import save_env_value
    from hermes_constants import get_hermes_home
    import os

    env_path = Path(get_hermes_home()) / ".env"
    existing = None

    # Read existing .env file for DASHBOARD_FERNET_KEY
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DASHBOARD_FERNET_KEY="):
                    existing = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if existing:
        try:
            return Fernet(existing.encode())
        except Exception:
            logger.warning("Dashboard: stored DASHBOARD_FERNET_KEY is invalid, regenerating")

    # Generate new key
    key = Fernet.generate_key()
    save_env_value("DASHBOARD_FERNET_KEY", key.decode())
    logger.info("Dashboard: generated new Fernet session key")
    return Fernet(key)


# --- First-run credential setup ---

async def ensure_dashboard_credentials(app: "web.Application") -> None:
    """
    on_startup hook. If no dashboard.password_hash in config.yaml, generate
    a first-run password, hash it, persist to config, and log plaintext once.
    Also loads/creates the Fernet key and stores it in app["fernet"].
    """
    from hermes_cli.config import load_config, save_config

    # Fernet key — must survive gateway restarts (Pitfall 4)
    app["fernet"] = load_or_create_fernet_key()

    config = load_config()
    dashboard_cfg = config.setdefault("dashboard", {})

    if not dashboard_cfg.get("password_hash"):
        import os
        env_password = os.environ.get("DASHBOARD_PASSWORD", "").strip()
        if env_password:
            password = env_password
            dashboard_cfg["force_change"] = True
            logger.info("Dashboard: using password from DASHBOARD_PASSWORD env var")
        else:
            password = _generate_password()
            dashboard_cfg["force_change"] = True
            logger.info(
                "Dashboard: first-run password is: %s — change it at /dashboard/",
                password,
            )
        dashboard_cfg["password_hash"] = hash_password(password)
        dashboard_cfg["username"] = os.environ.get("DASHBOARD_USERNAME", "admin").strip() or "admin"
        save_config(config)
        app["force_password_change"] = dashboard_cfg["force_change"]
    else:
        app["force_password_change"] = dashboard_cfg.get("force_change", False)


# --- Auth middleware ---

@web.middleware
async def auth_middleware(request: "web.Request", handler) -> "web.Response":
    """
    Redirect unauthenticated requests to /dashboard/login.
    Only active on the dashboard subapp — never on the main app.

    Note: request.path is the full URL path (e.g. /dashboard/login) in both
    standalone and subapp-mounted contexts. EXEMPT_PATHS stores short forms
    (/login, /logout); we also check the path suffix after stripping one
    prefix level so the middleware works whether the subapp is tested alone
    or mounted under /dashboard/.
    """
    # Strip one prefix level so /dashboard/login → /login when mounted
    _stripped = request.path
    parts = request.path.strip("/").split("/", 1)
    if len(parts) == 2:
        _stripped = "/" + parts[1]

    if _stripped in EXEMPT_PATHS or request.path in EXEMPT_PATHS:
        return await handler(request)
    if any(_stripped.startswith(p) or request.path.startswith(p) for p in EXEMPT_PREFIXES):
        return await handler(request)

    token = request.cookies.get(SESSION_COOKIE)
    fernet = request.app["fernet"]
    if not token or not verify_session_token(fernet, token):
        raise web.HTTPFound("/dashboard/login")

    return await handler(request)


# --- HTTP handlers ---

@aiohttp_jinja2.template("login.html")
async def handle_login_page(request: "web.Request") -> dict:
    return {"error": None, "username": ""}


async def handle_login(request: "web.Request") -> "web.Response":
    data = await request.post()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ip = request.remote or "unknown"

    if _is_locked_out(ip):
        return aiohttp_jinja2.render_template(
            "login.html", request,
            {"error": "Too many failed attempts. Try again in 60 seconds.", "username": username}
        )

    from hermes_cli.config import load_config
    config = load_config()
    dashboard_cfg = config.get("dashboard", {})
    stored_hash = dashboard_cfg.get("password_hash", "")
    stored_username = dashboard_cfg.get("username", "admin")

    if not stored_hash or username != stored_username or not verify_password(stored_hash, password):
        _record_failed(ip)
        return aiohttp_jinja2.render_template(
            "login.html", request,
            {"error": "Invalid username or password.", "username": username}
        )

    # Success — check if forced password change is required
    if request.app.get("force_password_change") or dashboard_cfg.get("force_change"):
        response = web.HTTPFound("/dashboard/change-password")
        set_session_cookie(response, request.app["fernet"])
        return response

    response = web.HTTPFound("/dashboard/")
    set_session_cookie(response, request.app["fernet"])
    return response


async def handle_logout(request: "web.Request") -> "web.Response":
    response = web.HTTPFound("/dashboard/login")
    clear_session_cookie(response)
    return response


@aiohttp_jinja2.template("change_password.html")
async def handle_change_password_page(request: "web.Request") -> dict:
    from hermes_cli.config import load_config
    config = load_config()
    username = config.get("dashboard", {}).get("username", "admin")
    return {"error": None, "username": username}


async def handle_change_password(request: "web.Request") -> "web.Response":
    data = await request.post()
    username = data.get("username", "").strip()
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not username:
        return aiohttp_jinja2.render_template(
            "change_password.html", request,
            {"error": "Username is required.", "username": username}
        )
    if len(new_password) < 8:
        return aiohttp_jinja2.render_template(
            "change_password.html", request,
            {"error": "Password must be at least 8 characters.", "username": username}
        )
    if new_password != confirm_password:
        return aiohttp_jinja2.render_template(
            "change_password.html", request,
            {"error": "Passwords do not match.", "username": username}
        )

    from hermes_cli.config import load_config, save_config, is_managed
    if is_managed():
        return aiohttp_jinja2.render_template(
            "change_password.html", request,
            {"error": "This installation is managed. Password changes must be made through the configuration management system.", "username": username}
        )

    async with request.app["config_lock"]:
        config = load_config()
        dashboard_cfg = config.setdefault("dashboard", {})
        dashboard_cfg["username"] = username
        dashboard_cfg["password_hash"] = hash_password(new_password)
        dashboard_cfg["force_change"] = False
        save_config(config)

    request.app["force_password_change"] = False
    response = web.HTTPFound("/dashboard/")
    set_session_cookie(response, request.app["fernet"])
    return response
