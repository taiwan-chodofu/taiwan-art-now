"""Draft PostgreSQL-backed browser sessions, NOT wired to live routes.

Caller must only pass a sender ID verified through the completed Meta link
protocol. This module does not authenticate Meta, set cookies, or check CSRF.
"""
import os
from browser_session import (
    generate_session_token, token_digest, DEFAULT_SESSION_TTL, MAX_SESSION_TTL,
)


def _connect():
    import psycopg
    url = os.environ.get("TAN_DATABASE_URL", "")
    if not url:
        raise RuntimeError("TAN_DATABASE_URL is required")
    return psycopg.connect(url, connect_timeout=10)


def issue(conn, *, verified_sender_id, ttl_seconds=DEFAULT_SESSION_TTL):
    if not isinstance(verified_sender_id, str) or not verified_sender_id.strip():
        raise ValueError("Verified sender required")
    if (not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool)
            or not 1 <= ttl_seconds <= MAX_SESSION_TTL):
        raise ValueError("Invalid TTL")
    token = generate_session_token()
    digest = token_digest(token)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """insert into tan_private.browser_sessions
                   (token_hash, sender_id, expires_at)
                   values (%s, %s, now() + (%s * interval '1 second'))""",
                (digest, verified_sender_id, ttl_seconds),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return token


def resolve_sender(conn, *, token):
    """Return verified sender or None. DB exceptions propagate (fail closed)."""
    try:
        digest = token_digest(token)
    except ValueError:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """select sender_id from tan_private.browser_sessions
                   where token_hash = %s
                     and revoked_at is null
                     and expires_at > now()""",
                (digest,),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception:
        conn.rollback()
        raise


def revoke(conn, *, token):
    try:
        digest = token_digest(token)
    except ValueError:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """update tan_private.browser_sessions
                   set revoked_at = now()
                   where token_hash = %s
                     and revoked_at is null
                   returning token_hash""",
                (digest,),
            )
            revoked = cur.fetchone() is not None
        conn.commit()
        return revoked
    except Exception:
        conn.rollback()
        raise
