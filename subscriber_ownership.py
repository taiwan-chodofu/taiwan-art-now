"""Draft fail-closed authorization helpers for subscriber API adapters.

Identifiers supplied by clients (sender_id, ref_code, push endpoint) are not
proof of ownership. Only a server-resolved, unexpired session may establish a
Messenger principal. Push subscriptions require a separately proven owner.
NOT wired into app.py; no production authorization claim is made.
"""
import hmac
from browser_session_store import resolve_sender


class AuthorizationDenied(Exception):
    pass


def authenticated_messenger_sender(conn, session_token):
    if not isinstance(session_token, str) or not session_token:
        raise AuthorizationDenied("authentication required")
    try:
        sender = resolve_sender(conn, token=session_token)
    except Exception as exc:
        raise AuthorizationDenied("authentication unavailable") from exc
    if not isinstance(sender, str) or not sender:
        raise AuthorizationDenied("authentication required")
    return sender


def require_messenger_owner(conn, session_token, requested_sender_id):
    sender = authenticated_messenger_sender(conn, session_token)
    if (not isinstance(requested_sender_id, str) or
            not hmac.compare_digest(sender, requested_sender_id)):
        raise AuthorizationDenied("not authorized")
    return sender


def require_push_owner(proven_endpoint, requested_endpoint):
    """A verified endpoint proof must come from a separate secure protocol.

    Browser-submitted endpoint alone must NEVER be passed as proven_endpoint.
    """
    if (not isinstance(proven_endpoint, str) or not proven_endpoint or
            not isinstance(requested_endpoint, str) or
            not hmac.compare_digest(proven_endpoint, requested_endpoint)):
        raise AuthorizationDenied("not authorized")
    return proven_endpoint
