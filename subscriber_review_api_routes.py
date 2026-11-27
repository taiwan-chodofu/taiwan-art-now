"""Isolated explicit-keep HTTP flow. NOT registered in production app.

The issue endpoint is called only after a user selects keep_saved; the consume
endpoint revalidates the owner-bound, single-use token and current tombstone.
Neither endpoint accepts sender identity from the browser.
"""
from flask import Blueprint, current_app, jsonify, request
from browser_cookie_security import COOKIE_NAME, require_same_origin
from versioned_subscriber_api_routes import _sender_in_transaction
from subscriber_review_confirmation import (
    issue_keep_confirmation, consume_keep_confirmation)
from versioned_subscriber_sync import StaleRevision

review_blueprint = Blueprint("subscriber_review_draft", __name__)


def _handle(*, consume):
    if not require_same_origin(
        request.method, request.headers.get("Origin"),
        current_app.config.get("TAN_CANONICAL_ORIGIN"),
        request.headers.get("Sec-Fetch-Site"),
    ):
        return jsonify(error="forbidden"), 403
    if request.args or not request.is_json:
        return jsonify(error="invalid_request"), 400
    payload = request.get_json(silent=True)
    expected = ({"token", "local_value"} if consume else
                {"choice", "kind", "key", "base_revision",
                 "reviewed_item_revision", "local_value"})
    if not isinstance(payload, dict) or set(payload) != expected:
        return jsonify(error="invalid_request"), 400
    if not consume and payload["choice"] != "keep_saved":
        return jsonify(error="invalid_request"), 400
    connector = current_app.config.get("TAN_PRIVATE_DB_CONNECT")
    if not callable(connector):
        return jsonify(error="unavailable"), 503
    try:
        with connector() as conn:
            if getattr(conn, "autocommit", False):
                raise RuntimeError("Transactional connection required")
            sender = _sender_in_transaction(conn, request.cookies.get(COOKIE_NAME))
            if sender is None:
                conn.rollback()
                return jsonify(error="forbidden"), 403
            if consume:
                state = consume_keep_confirmation(
                    conn, verified_sender_id=sender,
                    token=payload["token"], local_value=payload["local_value"])
                response = jsonify(state)
            else:
                token = issue_keep_confirmation(
                    conn, verified_sender_id=sender,
                    kind=payload["kind"], key=payload["key"],
                    base_revision=payload["base_revision"],
                    reviewed_item_revision=payload["reviewed_item_revision"],
                    local_value=payload["local_value"])
                response = jsonify(token=token, expires_in_seconds=300)
    except StaleRevision:
        return jsonify(error="stale_revision"), 409
    except ValueError:
        return jsonify(error="invalid_confirmation" if consume else "invalid_request"), 400
    except Exception:
        current_app.logger.warning("Subscriber review draft unavailable")
        return jsonify(error="unavailable"), 503
    response.headers["Cache-Control"] = "no-store"
    return response


@review_blueprint.post("/api/private-subscribers/v2/review/keep/issue")
def issue_keep():
    return _handle(consume=False)


@review_blueprint.post("/api/private-subscribers/v2/review/keep/consume")
def consume_keep():
    return _handle(consume=True)
