"""Offline integrity checks for two owner-controlled subscriber backup files.

Does not create or encrypt backups, connect to databases, or print user data.
Keep the expected SHA-256 manifest separately from the backup files.
"""
import argparse
import hashlib
import sys
import json
from pathlib import Path


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_files(messenger_path, push_path, expected=None):
    messenger_path, push_path = Path(messenger_path), Path(push_path)
    if messenger_path.resolve() == push_path.resolve():
        raise ValueError("Messenger and Push backups must be distinct files")
    hashes = {"messenger_sha256": file_digest(messenger_path),
              "push_sha256": file_digest(push_path)}
    if expected is not None:
        if set(expected) != set(hashes):
            raise ValueError("Invalid checksum manifest")
        if any(not isinstance(expected[k], str) or
               len(expected[k]) != 64 or
               not __import__("hmac").compare_digest(hashes[k], expected[k])
               for k in hashes):
            raise ValueError("Backup integrity mismatch")
    messenger = json.loads(messenger_path.read_text(encoding="utf-8"))
    push = json.loads(push_path.read_text(encoding="utf-8"))
    # Work when imported by path from tests as well as run as a script.
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from import_private_subscribers import validate_snapshot
    counts = validate_snapshot(messenger, push)
    return hashes, {"users": counts[0], "refs": counts[1], "push": counts[2]}


def main():
    parser = argparse.ArgumentParser(description="Offline subscriber backup integrity check")
    parser.add_argument("--messenger", type=Path, required=True)
    parser.add_argument("--push", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path,
                        help="Independent manifest created at backup time")
    args = parser.parse_args()
    expected = None
    if args.expected_manifest:
        expected = json.loads(args.expected_manifest.read_text(encoding="utf-8"))
    hashes, counts = verify_files(args.messenger, args.push, expected)
    if expected is None:
        print("UNVERIFIED BASELINE: store these checksums separately at backup time.")
        print(json.dumps(hashes, sort_keys=True))
    else:
        print("Backup checksums match the independent manifest.")
    print("Snapshot structure validated; record counts:", json.dumps(counts, sort_keys=True))
    print("No restore, encryption, source consistency, or database connection verified.")


if __name__ == "__main__":
    main()
