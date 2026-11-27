"""Conservative, non-destructive reconciliation of legacy favorite/visited maps.

DRAFT ONLY: no deletion, no timestamp-based conflict resolution, no remote
writes. Conflicting values are surfaced to the caller for explicit review.
No subscriber identifiers or personal data are logged.
"""
from copy import deepcopy


class ReconciliationRequired(ValueError):
    pass


def _validate_map(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    if len(value) > 10000:
        raise ValueError(label + " exceeds item limit")
    for key in value:
        if not isinstance(key, str) or not key or len(key) > 512:
            raise ValueError(label + " has invalid item key")


def merge_additive(local, remote):
    """Return merged map and conflicting keys; never silently overwrite.

    Equal entries are retained. A key present on only one side is copied.
    A key present on both with different values is left at its remote value
    in the candidate and reported as a conflict; callers MUST NOT persist
    candidate while conflicts remain.
    """
    _validate_map(local, "local")
    _validate_map(remote, "remote")
    merged = deepcopy(remote)
    conflicts = []
    for key, value in local.items():
        if key not in remote:
            merged[key] = deepcopy(value)
        elif remote[key] != value:
            conflicts.append(key)
    return {"merged": merged, "conflicts": sorted(conflicts)}


def reconcile_favorites_visited(local, remote):
    if not isinstance(local, dict) or not isinstance(remote, dict):
        raise ValueError("Both snapshots must be objects")
    if set(local) != {"favs", "visited"} or set(remote) != {"favs", "visited"}:
        raise ValueError("Expected exactly favs and visited maps")
    results = {
        name: merge_additive(local[name], remote[name])
        for name in ("favs", "visited")
    }
    conflicts = {name: results[name]["conflicts"] for name in results
                 if results[name]["conflicts"]}
    if conflicts:
        # Return keys only, never values, in the exception.
        raise ReconciliationRequired("Conflicting item keys require explicit resolution")
    return {name: results[name]["merged"] for name in ("favs", "visited")}


def preview_reconciliation(local, remote):
    """Safe preview; conflicting values are never included in the result."""
    if not isinstance(local, dict) or not isinstance(remote, dict):
        raise ValueError("Both snapshots must be objects")
    if set(local) != {"favs", "visited"} or set(remote) != {"favs", "visited"}:
        raise ValueError("Expected exactly favs and visited maps")
    results = {name: merge_additive(local[name], remote[name])
               for name in ("favs", "visited")}
    return {
        "safe_to_apply": not any(results[name]["conflicts"] for name in results),
        "conflict_counts": {name: len(results[name]["conflicts"]) for name in results},
        "local_counts": {name: len(local[name]) for name in results},
        "remote_counts": {name: len(remote[name]) for name in results},
    }
