"""Isolated, server-side browser session primitives (NOT wired to routes).

Only a separately verified Meta link may authorize issuing a session. Never
accept a browser-supplied sender ID as proof of identity.
"""
import hashlib
import hmac
import secrets
import time

DEFAULT_SESSION_TTL = 3600
MAX_SESSION_TTL = 86400


def generate_session_token():
    return secrets.token_urlsafe(32)


def token_digest(token):
    if not isinstance(token, str) or not token or len(token) > 256:
        raise ValueError("Invalid session token")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session_record(token, verified_sender_id, *, now=None, ttl=DEFAULT_SESSION_TTL):
    if not isinstance(verified_sender_id, str) or not verified_sender_id.strip():
        raise ValueError("Verified sender required")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or not 1 <= ttl <= MAX_SESSION_TTL:
        raise ValueError("Invalid session TTL")
    now = time.time() if now is None else now
    if not isinstance(now, (int, float)) or isinstance(now, bool) or not 0 <= now < 10**12:
        raise ValueError("Invalid issue time")
    return {
        "token_hash": token_digest(token),
        "sender_id": verified_sender_id,
        "issued_at": now,
        "expires_at": now + ttl,
        "revoked_at": None,
    }


def validate_session(record, token, *, now=None):
    now = time.time() if now is None else now
    if not isinstance(record, dict) or not isinstance(now, (int, float)):
        return False
    if record.get("revoked_at") is not None:
        return False
    issued, expiry, stored = (
        record.get("issued_at"), record.get("expires_at"), record.get("token_hash"))
    if (not isinstance(issued, (int, float)) or
            not isinstance(expiry, (int, float)) or
            not isinstance(stored, str) or len(stored) != 64 or
            not isinstance(record.get("sender_id"), str) or
            not record["sender_id"] or now < issued or now >= expiry):
        return False
    try:
        candidate = token_digest(token)
    except ValueError:
        return False
    return hmac.compare_digest(stored, candidate)


def revoke_session(record, *, now=None):
    if not isinstance(record, dict) or record.get("revoked_at") is not None:
        return False
    record["revoked_at"] = time.time() if now is None else now
    return True
