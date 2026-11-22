"""Draft versioned HTTP API; deliberately NOT registered in app.py.

Cookie session lookup is locked and verified in the SAME database transaction
as revisioned writes, so a concurrent revocation cannot race the write.
"""
from flask import Blueprint, current_app, jsonify, request
from browser_cookie_security import COOKIE_NAME, require_same_origin
from browser_session import token_digest
from versioned_subscriber_store import (
    update_for_verified_sender, read_for_verified_sender,
)
from versioned_subscriber_sync import StaleRevision

versioned_blueprint = Blueprint("versioned_subscriber_draft", __name__)


def _sender_in_transaction(conn, token):
    try:
        digest = token_digest(token)
    except ValueError:
        return None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sender_id FROM tan_private.browser_sessions "
            "WHERE token_hash = %s AND revoked_at IS NULL "
            "AND expires_at > now() FOR UPDATE",
            (digest,),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _respond(*, write):
    if not require_same_origin(
        request.method, request.headers.get("Origin"),
        current_app.config.get("TAN_CANONICAL_ORIGIN"),
        request.headers.get("Sec-Fetch-Site"),
    ):
        return jsonify(error="forbidden"), 403
    if request.args:
        return jsonify(error="invalid_request"), 400
    connector = current_app.config.get("TAN_PRIVATE_DB_CONNECT")
    if not callable(connector):
        return jsonify(error="unavailable"), 503
    payload = None
    if write:
        if not request.is_json:
            return jsonify(error="invalid_request"), 400
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {"base_revision", "changes"}:
            return jsonify(error="invalid_request"), 400
    try:
        with connector() as conn:
            # FOR UPDATE protects ownership only when lookup and CAS share
            # a transaction; reject autocommit before the session lookup.
            if getattr(conn, "autocommit", False):
                raise RuntimeError("Transactional connection required")
            sender = _sender_in_transaction(conn, request.cookies.get(COOKIE_NAME))
            if sender is None:
                conn.rollback()
                return jsonify(error="forbidden"), 403
            if write:
                state = update_for_verified_sender(
                    conn, verified_sender_id=sender,
                    base_revision=payload["base_revision"],
                    changes=payload["changes"],
                )
            else:
                state = read_for_verified_sender(conn, verified_sender_id=sender)
                conn.commit()
    except StaleRevision:
        return jsonify(error="stale_revision"), 409
    except ValueError:
        return jsonify(error="invalid_request"), 400
    except Exception:
        current_app.logger.warning("Versioned subscriber API unavailable")
        return jsonify(error="unavailable"), 503
    response = jsonify(state)
    response.headers["Cache-Control"] = "no-store"
    return response


@versioned_blueprint.get("/api/private-subscribers/v2/state")
def read_state():
    return _respond(write=False)


@versioned_blueprint.post("/api/private-subscribers/v2/changes")
def write_changes():
    return _respond(write=True)
