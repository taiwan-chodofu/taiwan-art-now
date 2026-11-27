"""Import owner-provided private JSON backups to a new private database.

Run only in a trusted environment after making encrypted offline backups.
Do not commit or share the JSON files. The default is a validation-only dry run.
"""
import argparse
import json
from pathlib import Path

def validate_snapshot(messenger, push):
    users = messenger.get("users")
    refs = messenger.get("refs", {})
    subscriptions = push.get("subscriptions")
    if not all(isinstance(x, dict) for x in (users, refs, subscriptions)):
        raise ValueError("Invalid backup shape")
    if any(not isinstance(sid, str) or not isinstance(profile, dict)
           for sid, profile in users.items()):
        raise ValueError("Invalid subscriber")
    if any(not isinstance(ref, str) or sid not in users for ref, sid in refs.items()):
        raise ValueError("Invalid subscriber reference")
    if any(not isinstance(endpoint, str) or not isinstance(info, dict)
           or info.get("endpoint") != endpoint
           for endpoint, info in subscriptions.items()):
        raise ValueError("Invalid push subscription")
    return len(users), len(refs), len(subscriptions)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--messenger", type=Path, required=True)
    parser.add_argument("--push", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    messenger = json.loads(args.messenger.read_text(encoding="utf-8"))
    push = json.loads(args.push.read_text(encoding="utf-8"))
    counts = validate_snapshot(messenger, push)
    print("Validated source counts: users=%d, refs=%d, push=%d" % counts)
    if not args.execute:
        print("Dry run only. No database connection or writes.")
        return
    from private_subscriber_store import import_snapshot_if_empty
    result = import_snapshot_if_empty(messenger, push)
    print("Atomic import and round-trip verification succeeded:", result)

if __name__ == "__main__":
    main()
