"""Draft two-secret Messenger/browser link handshake. NOT wired to app.py.

The Messenger code and browser claim secret are independently random. Only
the Messenger code is sent to Meta; the claim secret must remain exclusively
in the initiating browser. Verified sender IDs MUST come from a signed Meta
webhook, never from a browser request.
"""
import secrets
from messenger_link_challenge import hash_challenge
from browser_session import (
    generate_session_token, token_digest, DEFAULT_SESSION_TTL, MAX_SESSION_TTL,
)


def _claim_digest(secret):
    return hash_challenge(secret)


def issue_pair(conn, *, ttl_seconds=600):
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 900:
        raise ValueError("Invalid challenge TTL")
    messenger_code = secrets.token_urlsafe(32)
    browser_secret = secrets.token_urlsafe(32)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """insert into tan_private.messenger_link_challenges
                   (token_hash, browser_claim_hash, expires_at)
                   values (%s, %s, now() + (%s * interval '1 second'))""",
                (hash_challenge(messenger_code), _claim_digest(browser_secret), ttl_seconds),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return messenger_code, browser_secret


def mark_meta_verified(conn, *, messenger_code, verified_sender_id):
    """Only a signature-verified Meta webhook handler may call this."""
    if not isinstance(verified_sender_id, str) or not verified_sender_id.strip():
        raise ValueError("Verified Meta sender required")
    code_hash = hash_challenge(messenger_code)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """update tan_private.messenger_link_challenges
                   set sender_id = %s, verified_at = now()
                   where token_hash = %s and sender_id is null
                     and verified_at is null and consumed_at is null
                     and expires_at > now()
                   returning token_hash""",
                (verified_sender_id, code_hash),
            )
            marked = cur.fetchone() is not None
        conn.commit()
        return marked
    except Exception:
        conn.rollback()
        raise


def claim_browser_session(conn, *, messenger_code, browser_secret,
                          ttl_seconds=DEFAULT_SESSION_TTL):
    """Browser must prove both secrets; session token returned ONLY to browser.

    The server must enforce same-origin/CSRF and rate limits before calling.
    A verified Meta sender is obtained from the locked DB row, never browser.
    """
    if (not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool)
            or not 1 <= ttl_seconds <= MAX_SESSION_TTL):
        raise ValueError("Invalid session TTL")
    code_hash = hash_challenge(messenger_code)
    claim_hash = _claim_digest(browser_secret)
    session_token = generate_session_token()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """update tan_private.messenger_link_challenges
                   set consumed_at = now()
                   where token_hash = %s and browser_claim_hash = %s
                     and verified_at is not null and sender_id is not null
                     and consumed_at is null and expires_at > now()
                   returning sender_id""",
                (code_hash, claim_hash),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return None
            cur.execute(
                """insert into tan_private.browser_sessions
                   (token_hash, sender_id, expires_at)
                   values (%s, %s, now() + (%s * interval '1 second'))""",
                (token_digest(session_token), row[0], ttl_seconds),
            )
        conn.commit()
        return session_token
    except Exception:
        conn.rollback()
        raise
