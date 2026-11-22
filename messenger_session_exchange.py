"""Draft atomic exchange of a VERIFIED Messenger challenge for a browser session.

This function MUST NOT be called from a public browser request with a
browser-provided sender ID. The caller must independently verify the Meta
webhook signature and sender provenance. The returned token must never be
sent to the Messenger webhook response or logged. This isolated primitive is
not a complete browser-link protocol; a separate browser-held secret and
authenticated polling/claim flow are still required.
"""
from browser_session import (
    generate_session_token, token_digest, DEFAULT_SESSION_TTL, MAX_SESSION_TTL,
)
from messenger_link_challenge import hash_challenge


def exchange_verified_challenge(conn, *, challenge_token, verified_sender_id,
                                ttl_seconds=DEFAULT_SESSION_TTL):
    if not isinstance(verified_sender_id, str) or not verified_sender_id.strip():
        raise ValueError("Verified Meta sender required")
    if (not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool)
            or not 1 <= ttl_seconds <= MAX_SESSION_TTL):
        raise ValueError("Invalid TTL")
    challenge_hash = hash_challenge(challenge_token)
    session_token = generate_session_token()
    session_hash = token_digest(session_token)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """update tan_private.messenger_link_challenges
                   set consumed_at = now(), sender_id = %s
                   where token_hash = %s
                     and consumed_at is null
                     and expires_at > now()
                   returning token_hash""",
                (verified_sender_id, challenge_hash),
            )
            if cur.fetchone() is None:
                conn.rollback()
                return None
            cur.execute(
                """insert into tan_private.browser_sessions
                   (token_hash, sender_id, expires_at)
                   values (%s, %s, now() + (%s * interval '1 second'))""",
                (session_hash, verified_sender_id, ttl_seconds),
            )
        conn.commit()
        return session_token
    except Exception:
        conn.rollback()
        raise
