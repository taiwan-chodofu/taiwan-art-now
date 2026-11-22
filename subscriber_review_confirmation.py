"""Review-only, single-use consent token for explicit exhibition restoration.

NOT registered as an HTTP endpoint. Both functions require a verified owner
resolved from a locked server-side session, never a browser-supplied identity.
Token consumption and subscriber CAS share the SAME database transaction.
"""
import hashlib
import hmac
import json
import secrets

from reviewed_subscriber_intent import plan_reviewed_conflict
from versioned_subscriber_store import (read_for_verified_sender, update_for_verified_sender,
                                        _REVIEWED_RESTORE_CAPABILITY)
from versioned_subscriber_sync import StaleRevision

TOKEN_BYTES = 32


def _digest(token):
    if not isinstance(token, str) or len(token) != TOKEN_BYTES * 2:
        raise ValueError("Invalid confirmation token")
    try:
        return hashlib.sha256(bytes.fromhex(token)).digest()
    except ValueError as exc:
        raise ValueError("Invalid confirmation token") from exc


def _value_digest(value):
    try:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid saved exhibition value") from exc
    return hashlib.sha256(canonical.encode("utf-8")).digest()


def issue_keep_confirmation(conn, *, verified_sender_id, kind, key,
                            base_revision, reviewed_item_revision, local_value):
    """Issue short-lived consent only after server tombstone verification.

    Issuing a token is NOT itself user consent. A future HTTP endpoint must
    issue it only after a real user explicitly chooses 'keep saved'.
    """
    if not isinstance(verified_sender_id, str) or not verified_sender_id:
        raise ValueError("Verified sender required")
    if getattr(conn, "autocommit", False):
        raise ValueError("Transactional connection required")
    try:
        state = read_for_verified_sender(conn, verified_sender_id=verified_sender_id)
        plan = plan_reviewed_conflict(
            state, base_revision=base_revision, kind=kind, key=key,
            choice="keep_saved", reviewed_item_revision=reviewed_item_revision,
            local_value=local_value)
        if plan["status"] != "requires_verified_consent_and_cas":
            raise ValueError("Cannot issue confirmation")
        token = secrets.token_hex(TOKEN_BYTES)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tan_private.subscriber_review_confirmations "
                "(token_hash, sender_id, kind, item_key, base_revision, "
                "item_revision, choice, value_hash, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'keep_saved', %s, "
                "now() + interval '5 minutes')",
                (_digest(token), verified_sender_id, kind, key, base_revision,
                 reviewed_item_revision, _value_digest(local_value)))
        conn.commit()
        return token
    except Exception:
        conn.rollback()
        raise


def consume_keep_confirmation(conn, *, verified_sender_id, token, local_value):
    """Atomically consume consent and apply CAS, or roll back both.

    Requires locked authenticated session on conn held through commit.
    Does not accept owner, kind, key, or revision from browser as authority.
    """
    if not isinstance(verified_sender_id, str) or not verified_sender_id:
        raise ValueError("Verified sender required")
    if getattr(conn, "autocommit", False):
        raise ValueError("Transactional connection required")
    token_hash = _digest(token)
    value_hash = _value_digest(local_value)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sender_id, kind, item_key, base_revision, item_revision, "
                "choice, value_hash FROM tan_private.subscriber_review_confirmations "
                "WHERE token_hash = %s AND used_at IS NULL AND expires_at > now() "
                "FOR UPDATE", (token_hash,))
            row = cur.fetchone()
            if (row is None or not hmac.compare_digest(row[0], verified_sender_id)
                    or row[5] != "keep_saved"
                    or not hmac.compare_digest(bytes(row[6]), value_hash)):
                raise ValueError("Confirmation invalid or expired")
            _, kind, key, base_revision, item_revision, _, _ = row
            state = read_for_verified_sender(conn, verified_sender_id=verified_sender_id)
            proposal = plan_reviewed_conflict(
                state, base_revision=base_revision, kind=kind, key=key,
                choice="keep_saved", reviewed_item_revision=item_revision,
                local_value=local_value)
            cur.execute(
                "UPDATE tan_private.subscriber_review_confirmations "
                "SET used_at = now() WHERE token_hash = %s AND used_at IS NULL "
                "RETURNING token_hash", (token_hash,))
            if cur.fetchone() is None:
                raise ValueError("Confirmation already consumed")
        # update_for_verified_sender commits the *same* connection; token use
        # and CAS therefore become visible together, never separately.
        return update_for_verified_sender(
            conn, verified_sender_id=verified_sender_id,
            base_revision=proposal["base_revision"], changes=proposal["changes"],
            _reviewed_restore_capability=_REVIEWED_RESTORE_CAPABILITY)
    except Exception:
        conn.rollback()
        raise
