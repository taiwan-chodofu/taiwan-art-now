"""Transactional PostgreSQL revision compare-and-swap, draft only.

Requires review-only tan_private.subscriber_sync_states table in an isolated
staging database. Caller must pass a sender resolved from an authenticated
server session; never accept browser-supplied sender IDs. No production wiring.
"""
from versioned_subscriber_sync import apply_changes, empty_state, StaleRevision, validate_state

# Internal-only capability. Ordinary callers cannot authorize restoration by
# passing a boolean or a browser-provided field.
_REVIEWED_RESTORE_CAPABILITY = object()


def update_for_verified_sender(conn, *, verified_sender_id, base_revision, changes,
                               _reviewed_restore_capability=None):
    if not isinstance(verified_sender_id, str) or not verified_sender_id:
        raise ValueError("Verified sender required")
    if getattr(conn, "autocommit", False):
        raise ValueError("Transactional connection required")
    from psycopg.types.json import Jsonb
    try:
        with conn.cursor() as cur:
            # Advisory lock serializes the absent-row bootstrap as well as
            # existing-row updates; hash collisions only reduce throughput.
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 830085))",
                (verified_sender_id,),
            )
            cur.execute(
                "SELECT state FROM tan_private.subscriber_sync_states "
                "WHERE sender_id = %s FOR UPDATE",
                (verified_sender_id,),
            )
            row = cur.fetchone()
            current = row[0] if row else empty_state()
            validate_state(current)
            if _reviewed_restore_capability is not _REVIEWED_RESTORE_CAPABILITY:
                for kind in ("favs", "visited"):
                    for key, operation in changes.get(kind, {}).items():
                        existing = current[kind].get(key)
                        if (existing and existing["deleted"] and
                                isinstance(operation, dict) and "set" in operation):
                            raise StaleRevision("Reviewed confirmation required for restoration")
            next_state = apply_changes(
                current, base_revision=base_revision, changes=changes
            )
            if next_state != current:
                if row:
                    cur.execute(
                        "UPDATE tan_private.subscriber_sync_states "
                        "SET state = %s, updated_at = now() "
                        "WHERE sender_id = %s AND (state->>'revision')::bigint = %s "
                        "RETURNING sender_id",
                        (Jsonb(next_state), verified_sender_id, base_revision),
                    )
                else:
                    cur.execute(
                        "INSERT INTO tan_private.subscriber_sync_states "
                        "(sender_id, state) VALUES (%s, %s) "
                        "ON CONFLICT (sender_id) DO NOTHING RETURNING sender_id",
                        (verified_sender_id, Jsonb(next_state)),
                    )
                if cur.fetchone() is None:
                    raise StaleRevision("Concurrent update detected")
        conn.commit()
        return next_state
    except Exception:
        conn.rollback()
        raise


def read_for_verified_sender(conn, *, verified_sender_id):
    if not isinstance(verified_sender_id, str) or not verified_sender_id:
        raise ValueError("Verified sender required")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT state FROM tan_private.subscriber_sync_states "
            "WHERE sender_id = %s",
            (verified_sender_id,),
        )
        row = cur.fetchone()
    return row[0] if row else empty_state()
