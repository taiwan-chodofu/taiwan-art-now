"""Isolated Flask authorization boundary for legacy subscriber routes.

NOT installed in app.py. Every protected endpoint must use this guard before
reading or writing subscriber storage. Web Push requires an independent proof
mechanism, not an endpoint supplied by the browser.
"""
from functools import wraps
from flask import current_app, jsonify, request
from browser_cookie_security import COOKIE_NAME, require_same_origin
from subscriber_ownership import (
    AuthorizationDenied, authenticated_messenger_sender,
)

MESSENGER_ROUTES = frozenset({
    "/api/subscribers/sync", "/api/subscribers/link-ref",
    "/api/subscribers/status", "/api/subscribers/unsubscribe",
    "/api/subscribers/settings",
})
PUSH_ROUTES = frozenset({
    "/api/push/subscribe", "/api/push/unsubscribe", "/api/push/sync-favs",
})


def protected_subscriber_route(route):
    if route not in MESSENGER_ROUTES | PUSH_ROUTES:
        raise ValueError("Unrecognized protected route")

    def decorate(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            origin = current_app.config.get("TAN_CANONICAL_ORIGIN")
            if not require_same_origin(request.method, request.headers.get("Origin"),
                                       origin, request.headers.get("Sec-Fetch-Site")):
                return jsonify(error="forbidden"), 403
            connector = current_app.config.get("TAN_PRIVATE_DB_CONNECT")
            if route in MESSENGER_ROUTES:
                if not callable(connector):
                    return jsonify(error="unavailable"), 503
                try:
                    with connector() as conn:
                        sender = authenticated_messenger_sender(
                            conn, request.cookies.get(COOKIE_NAME))
                        payload = (request.args if request.method == "GET"
                                   else request.get_json(silent=True))
                        if not isinstance(payload, dict) and request.method != "GET":
                            return jsonify(error="invalid_request"), 400
                        claimed = payload.get("sender_id") or ""
                        if payload.get("ref"):
                            # Legacy ref operations can select another user.
                            # Reject until the route is rewritten to resolve
                            # ref ownership against the authenticated sender.
                            return jsonify(error="migration_required"), 403
                        if claimed and claimed != sender:
                            return jsonify(error="forbidden"), 403
                        if not claimed:
                            return jsonify(error="migration_required"), 403
                        request.environ["tan.verified_sender"] = sender
                except AuthorizationDenied:
                    return jsonify(error="forbidden"), 403
                except Exception:
                    current_app.logger.warning("Subscriber authorization unavailable")
                    return jsonify(error="unavailable"), 503
            else:
                # Push endpoint proof is not implemented; block all push
                # mutations until a real proof-of-possession flow exists.
                return jsonify(error="migration_required"), 403
            return handler(*args, **kwargs)
        return wrapped
    return decorate
