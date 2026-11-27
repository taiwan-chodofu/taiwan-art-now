"""Versioned per-item sync transitions, isolated draft; NOT connected to routes.

The server alone increments revision. Deletions are tombstones, not missing
keys. Every mutation must supply the last observed server revision. A stale
client is rejected without applying any writes; caller must refetch and
resolve conflicts explicitly. No automatic last-writer-wins behavior.
"""
from copy import deepcopy

MAX_ITEMS = 10000
MAX_KEY_LENGTH = 512
MAX_REVISION = 2**63 - 1
KINDS = ("favs", "visited")


class StaleRevision(ValueError):
    pass


def _revision(value):
    if type(value) is not int or not 0 <= value <= MAX_REVISION:
        raise ValueError("Invalid revision")
    return value


def empty_state():
    return {"revision": 0, "favs": {}, "visited": {}}


def validate_state(state):
    if not isinstance(state, dict) or set(state) != {"revision", *KINDS}:
        raise ValueError("Invalid sync state")
    revision = _revision(state["revision"])
    for kind in KINDS:
        items = state[kind]
        if not isinstance(items, dict) or len(items) > MAX_ITEMS:
            raise ValueError("Invalid item map")
        for key, entry in items.items():
            if not isinstance(key, str) or not key or len(key) > MAX_KEY_LENGTH:
                raise ValueError("Invalid item key")
            if not isinstance(entry, dict) or set(entry) != {"value", "deleted", "revision"}:
                raise ValueError("Invalid item entry")
            if type(entry["deleted"]) is not bool:
                raise ValueError("Invalid tombstone")
            item_revision = _revision(entry["revision"])
            if not 1 <= item_revision <= revision:
                raise ValueError("Item revision outside server state")
            if entry["deleted"] and entry["value"] is not None:
                raise ValueError("Tombstone must have null value")
    return revision


def apply_changes(state, *, base_revision, changes):
    """Apply one atomic conceptual batch to a detached state snapshot.

    Persistence must use a DB transaction with a revision compare-and-swap.
    This pure function does NOT provide concurrency safety on its own.
    """
    current = validate_state(state)
    if _revision(base_revision) != current:
        raise StaleRevision("Refetch before updating")
    if not isinstance(changes, dict) or set(changes) != set(KINDS):
        raise ValueError("Expected both change maps")
    if not all(isinstance(changes[kind], dict) for kind in KINDS):
        raise ValueError("Invalid change map")
    for kind in KINDS:
        if len(changes[kind]) > MAX_ITEMS:
            raise ValueError("Too many changes")
        for key, operation in changes[kind].items():
            if not isinstance(key, str) or not key or len(key) > MAX_KEY_LENGTH:
                raise ValueError("Invalid item key")
            if not isinstance(operation, dict) or set(operation) not in (
                {"set"}, {"delete"}
            ):
                raise ValueError("Invalid operation")
            if "delete" in operation and operation["delete"] is not True:
                raise ValueError("Invalid delete operation")
            if "set" in operation and operation["set"] is None:
                raise ValueError("Null reserved for tombstones")
    if not any(changes[kind] for kind in KINDS):
        return deepcopy(state)
    if current == MAX_REVISION:
        raise ValueError("Revision exhausted")
    result = deepcopy(state)
    next_revision = current + 1
    for kind in KINDS:
        for key, operation in changes[kind].items():
            if key not in result[kind] and len(result[kind]) >= MAX_ITEMS:
                raise ValueError("Item limit exceeded")
            deleted = "delete" in operation
            result[kind][key] = {
                "value": None if deleted else deepcopy(operation["set"]),
                "deleted": deleted,
                "revision": next_revision,
            }
    result["revision"] = next_revision
    return result


def visible_items(state):
    validate_state(state)
    return {
        kind: {key: deepcopy(entry["value"])
               for key, entry in state[kind].items() if not entry["deleted"]}
        for kind in KINDS
    }
