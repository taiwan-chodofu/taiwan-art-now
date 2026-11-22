"""Server-derived Messenger subscriber operations, draft only; NOT wired.

The verified sender is resolved from an opaque server-side session, never
from JSON, URL query, or a ref. Mutations use private transactional storage.
"""
from copy import deepcopy
from browser_session_store import resolve_sender
from subscriber_mutations import (
    SubscriberNotFound, sync_messenger, update_settings,
    unsubscribe_messenger,
)


class SubscriberAccessDenied(Exception):
    pass


def _verified_sender(conn, session_token):
    if not isinstance(session_token, str) or not session_token:
        raise SubscriberAccessDenied("session required")
    try:
        sender = resolve_sender(conn, token=session_token)
    except Exception as exc:
        raise SubscriberAccessDenied("session unavailable") from exc
    if not isinstance(sender, str) or not sender:
        raise SubscriberAccessDenied("session required")
    return sender


def _reject_client_identity(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    if any(key in payload for key in ("sender_id", "ref", "endpoint", "user_id")):
        raise SubscriberAccessDenied("client-supplied identity prohibited")


def status(conn, session_token, store):
    sender = _verified_sender(conn, session_token)
    # A read-only status query; do not return other subscribers or refs.
    data = store.load_messenger()
    user = data["users"].get(sender)
    if user is None:
        return {"subscribed": False}
    return {
        "subscribed": True,
        "weekly_digest": user.get("weekly_digest", True),
        "fav_alerts": user.get("fav_alerts", True),
    }


def sync(conn, session_token, payload, store):
    _reject_client_identity(payload)
    sender = _verified_sender(conn, session_token)
    if set(payload) != {"favs", "visited"}:
        raise ValueError("Unexpected sync fields")
    def mutate(data):
        sync_messenger(data, sender, payload["favs"], payload["visited"])
    store.mutate_messenger(mutate)
    return {"status": "synced"}


def settings(conn, session_token, payload, store):
    _reject_client_identity(payload)
    sender = _verified_sender(conn, session_token)
    if not payload or set(payload) - {"weekly_digest", "fav_alerts"}:
        raise ValueError("Unexpected settings fields")
    def mutate(data):
        update_settings(data, sender, **payload)
    store.mutate_messenger(mutate)
    return {"status": "updated"}


def unsubscribe(conn, session_token, payload, store):
    _reject_client_identity(payload)
    sender = _verified_sender(conn, session_token)
    if payload:
        raise ValueError("Unsubscribe body must be empty")
    def mutate(data):
        unsubscribe_messenger(data, sender)
    store.mutate_messenger(mutate)
    return {"status": "unsubscribed"}
