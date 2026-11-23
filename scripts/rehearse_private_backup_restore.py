"""Offline rehearsal of an independently checksummed private subscriber backup.

Never touches production DB, localStorage, or network. Uses a disposable
in-memory destination and checks source-to-destination roundtrip equality.
This covers messenger/push snapshots, NOT exhibition flag server history.
"""
import argparse
import json
from pathlib import Path
from verify_private_backup import verify_files


def rehearse(messenger_path, push_path, manifest_path):
    if manifest_path is None:
        raise ValueError("An independent SHA-256 manifest is required")
    paths = [Path(messenger_path), Path(push_path), Path(manifest_path)]
    if len({p.resolve() for p in paths}) != 3:
        raise ValueError("Backup files and manifest must be distinct")
    manifest = json.loads(paths[2].read_text(encoding="utf-8"))
    hashes, counts = verify_files(paths[0], paths[1], manifest)
    # Rehydrate a disposable destination; no write-back to source files.
    source_messenger = json.loads(paths[0].read_text(encoding="utf-8"))
    source_push = json.loads(paths[1].read_text(encoding="utf-8"))
    destination = {"users": {}, "refs": {}, "subscriptions": {}}
    destination["users"].update(source_messenger["users"])
    destination["refs"].update(source_messenger.get("refs", {}))
    destination["subscriptions"].update(source_push["subscriptions"])
    if destination["users"] != source_messenger["users"] or \
       destination["refs"] != source_messenger.get("refs", {}) or \
       destination["subscriptions"] != source_push["subscriptions"]:
        raise ValueError("Disposable restore roundtrip mismatch")
    # Reject files modified between initial checksum and rehydration.
    verify_files(paths[0], paths[1], hashes)
    return {"status": "offline_rehearsal_passed", "counts": counts,
            "database_restore_verified": False, "exhibition_history_verified": False}


def main():
    parser = argparse.ArgumentParser(description="Offline private backup restore rehearsal")
    parser.add_argument("--messenger", type=Path, required=True)
    parser.add_argument("--push", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    args = parser.parse_args()
    result = rehearse(args.messenger, args.push, args.expected_manifest)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
