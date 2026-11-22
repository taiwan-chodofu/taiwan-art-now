"""Isolated Flask browser-claim blueprint; NOT registered in production app.

No Meta webhook handler or browser UI is wired. Deploy only after reviewing
rate limiting, challenge delivery, staging DB integration and route ownership.
"""
from flask import Blueprint, current_app, jsonify, request
from browser_cookie_security import require_same_origin, set_session_cookie
from messenger_browser_claim import claim_browser_session

claim_blueprint = Blueprint("private_browser_claim_draft", __name__)


@claim_blueprint.post("/api/private-auth/claim")
def claim():
    allowed = current_app.config.get("TAN_CANONICAL_ORIGIN")
    if not require_same_origin(
        request.method, request.headers.get("Origin"), allowed,
        request.headers.get("Sec-Fetch-Site"),
    ):
        return jsonify(error="forbidden"), 403
    if not request.is_json:
        return jsonify(error="invalid_request"), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) != {"messenger_code", "browser_secret"}:
        return jsonify(error="invalid_request"), 400
    code, secret = body["messenger_code"], body["browser_secret"]
    if not isinstance(code, str) or not isinstance(secret, str):
        return jsonify(error="invalid_request"), 400
    if not code or not secret or len(code) > 256 or len(secret) > 256:
        return jsonify(error="invalid_request"), 400
    connector = current_app.config.get("TAN_PRIVATE_DB_CONNECT")
    if not callable(connector):
        return jsonify(error="unavailable"), 503
    try:
        with connector() as conn:
            token = claim_browser_session(
                conn, messenger_code=code, browser_secret=secret)
    except Exception:
        current_app.logger.warning("Private claim unavailable")
        return jsonify(error="unavailable"), 503
    if token is None:
        return jsonify(error="not_verified"), 403
    response = jsonify(ok=True)
    return set_session_cookie(response, token)
