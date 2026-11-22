"""Import an owner-provided private JSON backup into the private database.

Run only in a trusted environment, after verifying encrypted backup.
NEVER pass JSON content to AI tools or commit it. This import is destructive
to destination rows not present in the supplied snapshot: run on an empty
destination, or explicitly confirm that overwrite is intended.
"""
import argparse
import json
from pathlib import Path
from private_subscriber_store import load_messenger, load_push, save_messenger, save_push

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--messenger", type=Path, required=True)
    parser.add_argument("--push", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    messenger = json.loads(args.messenger.read_text(encoding="utf-8"))
    push = json.loads(args.push.read_text(encoding="utf-8"))
    users = messenger.get("users", {})
    refs = messenger.get("refs", {})
    subscriptions = push.get("subscriptions", {})
    if not all(isinstance(x, dict) for x in (users, refs, subscriptions)):
        raise ValueError("Invalid backup shape")
    if any(sid not in users for sid in refs.values()):
        raise ValueError("Orphan ref in backup")
    print(f"Source counts: users={len(users)}, refs={len(refs)}, push={len(subscriptions)}")
    if not args.execute:
        print("Dry run only. No database writes.")
        return
    if any((load_messenger()["users"], load_messenger()["refs"], load_push()["subscriptions"])):
        raise RuntimeError("Destination not empty; refusing overwrite")
    save_messenger(messenger)
    save_push(push)
    imported_m = load_messenger()
    imported_p = load_push()
    if imported_m != {"users": users, "refs": refs} or imported_p != {"subscriptions": subscriptions}:
        raise RuntimeError("Import verification failed; investigate before cutover")
    print("Import verified by full round-trip comparison.")

if __name__ == "__main__":
    main()
