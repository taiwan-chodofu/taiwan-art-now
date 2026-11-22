"""Isolated session-owned Messenger API Blueprint. NOT registered in app.py.

Routes use new contracts with no sender_id/ref supplied by clients. Production
cutover requires private storage migration and verified session issuance.
"""
from flask import Blueprint, current_app, jsonify, request
from browser_cookie_security import COOKIE_NAME, require_same_origin
from private_messenger_operations import (
    SubscriberAccessDenied, SubscriberNotFound,
    status, sync, settings, unsubscribe,
)

messenger_blueprint = Blueprint("private_messenger_api_draft", __name__)


def _execute(operation, *, payload=None):
    if not require_same_origin(
        request.method, request.headers.get("Origin"),
        current_app.config.get("TAN_CANONICAL_ORIGIN"),
        request.headers.get("Sec-Fetch-Site"),
    ):
        return jsonify(error="forbidden"), 403
    connector = current_app.config.get("TAN_PRIVATE_DB_CONNECT")
    store = current_app.config.get("TAN_PRIVATE_MESSENGER_STORE")
    if not callable(connector) or store is None:
        return jsonify(error="unavailable"), 503
    try:
        with connector() as conn:
            token = request.cookies.get(COOKIE_NAME)
            if payload is None:
                result = operation(conn, token, store)
            else:
                result = operation(conn, token, payload, store)
    except SubscriberAccessDenied:
        return jsonify(error="forbidden"), 403
    except SubscriberNotFound:
        return jsonify(error="not_found"), 404
    except ValueError:
        return jsonify(error="invalid_request"), 400
    except Exception:
        current_app.logger.warning("Private Messenger API unavailable")
        return jsonify(error="unavailable"), 503
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


def _post(operation):
    if not request.is_json:
        return jsonify(error="invalid_request"), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="invalid_request"), 400
    return _execute(operation, payload=payload)


@messenger_blueprint.get("/api/private-subscribers/status")
def subscriber_status():
    return _execute(status)


@messenger_blueprint.post("/api/private-subscribers/sync")
def subscriber_sync():
    return _post(sync)


@messenger_blueprint.post("/api/private-subscribers/settings")
def subscriber_settings():
    return _post(settings)


@messenger_blueprint.post("/api/private-subscribers/unsubscribe")
def subscriber_unsubscribe():
    return _post(unsubscribe)
