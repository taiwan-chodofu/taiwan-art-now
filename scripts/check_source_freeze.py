"""Offline migration freeze guard: compare two independently captured snapshots.

Read-only. Does not pause writers, connect to DB, or print identifiers.
A matching pair proves only these two snapshots are byte-identical.
"""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("verify_private_backup", HERE / "verify_private_backup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def compare_snapshots(before_messenger, before_push, after_messenger, after_push):
    before_hashes, before_counts = module.verify_files(before_messenger, before_push)
    after_hashes, after_counts = module.verify_files(after_messenger, after_push)
    return {
        "unchanged": before_hashes == after_hashes,
        "before_counts": before_counts,
        "after_counts": after_counts,
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only source freeze comparison")
    for name in ("before-messenger", "before-push", "after-messenger", "after-push"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = compare_snapshots(args.before_messenger, args.before_push,
                               args.after_messenger, args.after_push)
    print(json.dumps(result, sort_keys=True))
    if not result["unchanged"]:
        parser.exit(2, "Source changed between snapshots; cutover must stop.\n")
    print("Snapshots match. This does NOT prove that all live writers are stopped.")


if __name__ == "__main__":
    main()
