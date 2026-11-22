"""Draft PostgreSQL-backed one-time Messenger challenge store.

Not wired to app.py. The verified sender MUST come from a signature-verified
Meta webhook; browser-provided sender IDs are never sufficient.
"""
import os
from messenger_link_challenge import generate_challenge, hash_challenge


def _connect():
    import psycopg
    url = os.environ.get("TAN_DATABASE_URL", "")
    if not url:
        raise RuntimeError("TAN_DATABASE_URL is required")
    return psycopg.connect(url, connect_timeout=10)


def issue(conn, *, ttl_seconds=600):
    if not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 900:
        raise ValueError("Invalid TTL")
    token = generate_challenge()
    digest = hash_challenge(token)
    with conn.cursor() as cur:
        cur.execute(
            """insert into tan_private.messenger_link_challenges
               (token_hash, expires_at)
               values (%s, now() + (%s * interval '1 second'))""",
            (digest, ttl_seconds),
        )
    conn.commit()
    return token


def consume(conn, *, token, verified_sender_id):
    if not isinstance(verified_sender_id, str) or not verified_sender_id.strip():
        return False
    try:
        digest = hash_challenge(token)
    except ValueError:
        return False
    with conn.cursor() as cur:
        # One conditional UPDATE is atomic under concurrent PostgreSQL writers.
        # No SELECT-then-UPDATE race. Never log token, hash or sender ID.
        cur.execute(
            """update tan_private.messenger_link_challenges
               set consumed_at = now(), sender_id = %s
               where token_hash = %s
                 and consumed_at is null
                 and expires_at > now()
               returning token_hash""",
            (verified_sender_id, digest),
        )
        claimed = cur.fetchone() is not None
    conn.commit()
    return claimed
