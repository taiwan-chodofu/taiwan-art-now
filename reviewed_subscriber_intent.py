"""Draft server-side exhibition intent policy, NOT wired to HTTP routes.

Only an authenticated owner may invoke this after reading their current state
inside the same transaction as an atomic revision compare-and-swap.
Browser-provided values are never proof of ownership or previous review.
"""
from copy import deepcopy
from versioned_subscriber_sync import validate_state, StaleRevision

KINDS = ("favs", "visited")


def plan_reviewed_conflict(state, *, base_revision, kind, key, choice,
                           reviewed_item_revision, local_value=None):
    """Return a *proposal*, never write; recheck tombstone and revision.

    The caller must verify user session and a fresh, server-issued,
    single-use confirmation bound to owner/item/revision/choice before calling
    a real writer. This function is not itself proof of user consent.
    """
    current_revision = validate_state(state)
    if type(base_revision) is not int or base_revision != current_revision:
        raise StaleRevision("Server state changed; review again")
    if kind not in KINDS or not isinstance(key, str) or not key or len(key) > 512:
        raise ValueError("Invalid exhibition")
    if choice not in ("keep_saved", "remove_from_list", "decide_later"):
        raise ValueError("Invalid decision")
    entry = state[kind].get(key)
    if (not entry or not entry["deleted"] or
            type(reviewed_item_revision) is not int or
            entry["revision"] != reviewed_item_revision):
        raise StaleRevision("Deletion conflict changed; review again")
    if choice == "decide_later":
        return {"status": "deferred", "base_revision": current_revision,
                "changes": {"favs": {}, "visited": {}}}
    if choice == "remove_from_list":
        # Tombstone already represents the desired remote state. Do not
        # delete local data here; a separate local CAS is required.
        return {"status": "requires_local_confirmation",
                "base_revision": current_revision,
                "changes": {"favs": {}, "visited": {}}}
    if local_value is None:
        raise ValueError("Explicit keep requires saved exhibition value")
    # Reject malformed JSON-compatible payloads before they reach psycopg.
    from json import dumps
    try:
        dumps(local_value, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid saved exhibition value") from exc
    changes = {"favs": {}, "visited": {}}
    changes[kind][key] = {"set": deepcopy(local_value)}
    return {"status": "requires_verified_consent_and_cas",
            "base_revision": current_revision, "changes": changes}
