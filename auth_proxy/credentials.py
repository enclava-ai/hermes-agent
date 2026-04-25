"""Credential storage for the auth-proxy.

Stores a single admin username + scrypt-hashed password in
``~/.hermes/.dashboard_auth.json``. Stdlib only (hashlib.scrypt) so no
extra dependency.

File schema:
    {
      "username": "admin",
      "salt": "<base64>",
      "hash":  "<base64>",
      "version": 1
    }
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# scrypt cost parameters — RFC 7914 recommendation for interactive logins.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16


def credentials_path() -> Path:
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / ".dashboard_auth.json"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _from_b64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )


@dataclass(frozen=True)
class Credentials:
    username: str
    salt: bytes
    hash: bytes


def load_credentials() -> Optional[Credentials]:
    path = credentials_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Credentials(
            username=data["username"],
            salt=_from_b64(data["salt"]),
            hash=_from_b64(data["hash"]),
        )
    except (OSError, KeyError, ValueError) as e:
        logger.warning("auth_proxy: credentials file unreadable: %s", e)
        return None


def save_credentials(username: str, password: str) -> None:
    if not username or not password:
        raise ValueError("username and password are required")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")

    salt = os.urandom(_SALT_BYTES)
    hashed = _hash_password(password, salt)
    payload = {
        "username": username,
        "salt": _b64(salt),
        "hash": _b64(hashed),
        "version": 1,
    }
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def verify_password(creds: Credentials, username: str, password: str) -> bool:
    """Constant-time username + password verification."""
    if not hmac.compare_digest(creds.username.encode("utf-8"), username.encode("utf-8")):
        # Still compute the hash to avoid timing leaks on the username path.
        _hash_password(password, creds.salt)
        return False
    candidate = _hash_password(password, creds.salt)
    return hmac.compare_digest(candidate, creds.hash)
