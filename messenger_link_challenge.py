"""Server-side one-time Messenger link challenge primitives.

Not wired to production routes. A verified Meta webhook must supply sender_id;
never trust browser-submitted sender_id as proof of identity.
"""
import hashlib
import hmac
import secrets
import time

DEFAULT_TTL_SECONDS = 600


def generate_challenge():
    """URL-safe 256-bit random challenge; only its hash is persisted."""
    return secrets.token_urlsafe(32)


def hash_challenge(token):
    if not isinstance(token, str) or not token or len(token) > 256:
        raise ValueError("Invalid challenge token")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_challenge(token, now=None, ttl=DEFAULT_TTL_SECONDS):
    if not isinstance(ttl, int) or not 1 <= ttl <= 900:
        raise ValueError("Invalid challenge TTL")
    now = time.time() if now is None else now
    if not isinstance(now, (int, float)) or not 0 <= now < 10**12:
        raise ValueError("Invalid issue time")
    return {"token_hash": hash_challenge(token), "issued_at": now,
            "expires_at": now + ttl, "consumed_at": None, "sender_id": None}


def verify_and_consume(record, token, verified_sender_id, now=None):
    """Pure state transition. Caller MUST persist atomically under a DB lock.

    verified_sender_id must come from a signature-verified Meta event. This
    helper cannot verify Meta provenance itself and grants no session.
    """
    now = time.time() if now is None else now
    if not isinstance(record, dict) or not isinstance(verified_sender_id, str) or not verified_sender_id:
        return False
    if not isinstance(now, (int, float)):
        return False
    if record.get("consumed_at") is not None:
        return False
    expiry = record.get("expires_at")
    issued = record.get("issued_at")
    stored_hash = record.get("token_hash")
    if (not isinstance(expiry, (int, float)) or
            not isinstance(issued, (int, float)) or
            not isinstance(stored_hash, str) or len(stored_hash) != 64 or
            now < issued or now >= expiry):
        return False
    try:
        supplied_hash = hash_challenge(token)
    except ValueError:
        return False
    if not hmac.compare_digest(stored_hash, supplied_hash):
        return False
    expected_sender = record.get("sender_id")
    if expected_sender is not None and expected_sender != verified_sender_id:
        return False
    record["sender_id"] = verified_sender_id
    record["consumed_at"] = now
    return True
