"""Draft shared PostgreSQL fixed-window rate limiter (NOT wired to production).

Caller MUST supply a trustworthy, bounded client identifier derived only
from a verified proxy configuration. Never accept X-Forwarded-For directly.
Uses a server-only HMAC key so client identifiers are not stored in plaintext.
"""
import hashlib
import hmac
import os


def bucket_key(kind, identifier, *, secret):
    if (not isinstance(kind, str) or kind not in ("client", "challenge") or
            not isinstance(identifier, str) or not 1 <= len(identifier) <= 512 or
            not isinstance(secret, str) or len(secret) < 32):
        raise ValueError("Invalid rate limit key")
    return hmac.new(secret.encode("utf-8"),
                    (kind + ":" + identifier).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def allow_attempt(conn, *, kind, identifier, limit=5, window_seconds=600,
                  secret=None):
    """Atomically count every attempt; False means limit reached.

    SQL errors propagate after rollback. Callers must reject requests on
    errors, not allow them. Uses database clock and one UPSERT statement.
    """
    if (not isinstance(limit, int) or isinstance(limit, bool) or
            not 1 <= limit <= 100 or
            not isinstance(window_seconds, int) or isinstance(window_seconds, bool) or
            not 1 <= window_seconds <= 86400):
        raise ValueError("Invalid rate limit policy")
    secret = os.environ.get("TAN_RATE_LIMIT_HMAC_KEY") if secret is None else secret
    key = bucket_key(kind, identifier, secret=secret)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """insert into tan_private.auth_rate_limits
                   (bucket_hash, attempts, expires_at)
                   values (%s, 1, now() + (%s * interval '1 second'))
                   on conflict (bucket_hash) do update
                   set attempts = case
                       when tan_private.auth_rate_limits.expires_at <= now()
                       then 1 else tan_private.auth_rate_limits.attempts + 1 end,
                       expires_at = case
                       when tan_private.auth_rate_limits.expires_at <= now()
                       then now() + (%s * interval '1 second')
                       else tan_private.auth_rate_limits.expires_at end
                   returning attempts""",
                (key, window_seconds, window_seconds),
            )
            row = cur.fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError("Rate limit storage returned no row")
        return row[0] <= limit
    except Exception:
        conn.rollback()
        raise


def require_both_buckets(conn, *, client_identifier, challenge_identifier,
                         secret=None):
    """Require both client and challenge budgets; no short-circuit.

    Uses separate committed UPSERTs; a denied request still consumes a count.
    This is fail-closed but NOT a single atomic two-bucket transaction.
    """
    client_ok = allow_attempt(conn, kind="client", identifier=client_identifier,
                              secret=secret)
    challenge_ok = allow_attempt(conn, kind="challenge",
                                 identifier=challenge_identifier, secret=secret)
    return client_ok and challenge_ok
