"""
Unit tests for gateway.dashboard.auth.

Tests cover:
- Fernet session token creation and verification (valid, expired, tampered)
- Password verification (correct, wrong)
- Brute-force protection (not locked, locked, lockout expired)
- Secret redaction (long, short, empty)

No HTTP round-trips — tests pure Python functions only.
No mocks of hermes_cli.config — tests are isolated.
"""

import time

import pytest
from cryptography.fernet import Fernet

from gateway.dashboard.auth import (
    make_session_token,
    verify_session_token,
    verify_password,
    hash_password,
    redact_secret,
    _is_locked_out,
    _record_failed,
    _FAILED_ATTEMPTS,
    SESSION_TTL,
)


# --- Session token tests ---


def test_verify_session_token_valid():
    """A fresh token should verify as True."""
    fernet = Fernet(Fernet.generate_key())
    token = make_session_token(fernet)
    assert verify_session_token(fernet, token) is True


def test_verify_session_token_expired():
    """A token created more than SESSION_TTL seconds ago should return False.

    Fernet's ttl= parameter enforces expiry based on the token's embedded creation
    timestamp, not our JSON payload. To test expiry, we use unittest.mock.patch
    to freeze time at 'now - 25h' when encrypting, then verify with the real now.
    """
    import json
    from unittest.mock import patch

    fernet = Fernet(Fernet.generate_key())

    # Patch time.time() to return a timestamp 25 hours in the past so that
    # the Fernet token's embedded creation time is in the past.
    past_time = time.time() - (SESSION_TTL + 3600)  # 25 hours ago

    with patch("time.time", return_value=past_time):
        token = make_session_token(fernet)

    # Now verify with real time — the Fernet ttl check should raise InvalidToken
    assert verify_session_token(fernet, token) is False


def test_verify_session_token_tampered():
    """Garbage bytes should return False."""
    fernet = Fernet(Fernet.generate_key())
    assert verify_session_token(fernet, "notavalidtoken") is False


# --- Password verification tests ---


def test_verify_password_correct():
    """verify_password returns True when the plaintext matches the stored hash."""
    h = hash_password("correct-horse-battery-staple")
    assert verify_password(h, "correct-horse-battery-staple") is True


def test_verify_password_wrong():
    """verify_password returns False when the plaintext does not match."""
    h = hash_password("correct-horse-battery-staple")
    assert verify_password(h, "wrong-password") is False


# --- Brute-force protection tests ---


def test_is_locked_out_false():
    """IP with 0 attempts is not locked out."""
    ip = "192.0.2.1"
    _FAILED_ATTEMPTS.pop(ip, None)  # ensure clean state
    assert _is_locked_out(ip) is False


def test_is_locked_out_true():
    """IP with 5 failed attempts in the last 60s is locked out."""
    ip = "192.0.2.2"
    _FAILED_ATTEMPTS[ip] = [time.time()] * 5
    assert _is_locked_out(ip) is True


def test_is_locked_out_expired():
    """IP with 5 failed attempts all > 60s ago is not locked out."""
    ip = "192.0.2.3"
    old_time = time.time() - 120  # 2 minutes ago
    _FAILED_ATTEMPTS[ip] = [old_time] * 5
    assert _is_locked_out(ip) is False


# --- Secret redaction tests ---


def test_redact_secret_long():
    """Long secret (>= 8 chars): returns first 4 chars + ***."""
    result = redact_secret("sk-proj-1234567890abcdef")
    assert result == "sk-p***"


def test_redact_secret_short():
    """Short secret (< 8 chars): returns ***."""
    assert redact_secret("abc") == "***"


def test_redact_secret_empty():
    """Empty string: returns ***."""
    assert redact_secret("") == "***"
