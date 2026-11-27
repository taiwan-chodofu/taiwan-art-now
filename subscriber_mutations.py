"""Pure subscriber state transitions for use inside atomic database mutations.

These functions do not authenticate callers. Authorization must be checked
before invoking them from any HTTP route.
"""
from copy import deepcopy


class SubscriberNotFound(ValueError):
    pass


def sync_messenger(state, sender_id, favs, visited):
    if not isinstance(favs, dict) or not isinstance(visited, dict):
        raise ValueError("favs and visited must be objects")
    if sender_id not in state["users"]:
        raise SubscriberNotFound("not subscribed")
    state["users"][sender_id]["favs"] = deepcopy(favs)
    state["users"][sender_id]["visited"] = deepcopy(visited)


def link_ref(state, sender_id, ref_code):
    if not sender_id or not ref_code:
        raise ValueError("sender_id and ref required")
    if sender_id not in state["users"]:
        raise SubscriberNotFound("not subscribed")
    previous_owner = state["refs"].get(ref_code)
    if previous_owner and previous_owner != sender_id:
        raise ValueError("ref already linked")
    previous_ref = state["users"][sender_id].get("ref")
    if previous_ref and previous_ref != ref_code:
        state["refs"].pop(previous_ref, None)
    state["refs"][ref_code] = sender_id
    state["users"][sender_id]["ref"] = ref_code


def unsubscribe_messenger(state, sender_id):
    if sender_id not in state["users"]:
        raise SubscriberNotFound("not subscribed")
    del state["users"][sender_id]
    for ref, owner in list(state["refs"].items()):
        if owner == sender_id:
            del state["refs"][ref]


def update_settings(state, sender_id, *, weekly_digest=None, fav_alerts=None):
    if sender_id not in state["users"]:
        raise SubscriberNotFound("not subscribed")
    if weekly_digest is not None:
        if not isinstance(weekly_digest, bool):
            raise ValueError("weekly_digest must be boolean")
        state["users"][sender_id]["weekly_digest"] = weekly_digest
    if fav_alerts is not None:
        if not isinstance(fav_alerts, bool):
            raise ValueError("fav_alerts must be boolean")
        state["users"][sender_id]["fav_alerts"] = fav_alerts


def subscribe_push(state, endpoint, keys):
    if not endpoint or not isinstance(keys, dict) or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("invalid subscription")
    previous = state["subscriptions"].get(endpoint, {})
    state["subscriptions"][endpoint] = {
        "endpoint": endpoint,
        "keys": deepcopy(keys),
        "favs": deepcopy(previous.get("favs", {})),
        "visited": deepcopy(previous.get("visited", {})),
    }


def unsubscribe_push(state, endpoint):
    state["subscriptions"].pop(endpoint, None)


def sync_push(state, endpoint, favs, visited):
    if not isinstance(favs, dict) or not isinstance(visited, dict):
        raise ValueError("favs and visited must be objects")
    if endpoint not in state["subscriptions"]:
        raise SubscriberNotFound("not subscribed")
    state["subscriptions"][endpoint]["favs"] = deepcopy(favs)
    state["subscriptions"][endpoint]["visited"] = deepcopy(visited)
