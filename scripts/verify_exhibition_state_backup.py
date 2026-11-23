"""Offline verification and disposable replay of versioned exhibition state.

Requires independently stored SHA-256 manifest. No DB, network or production
writes. This is NOT proof of scheduled durable backup or real database restore.
"""
import argparse
import hashlib
import hmac
import json
from pathlib import Path


def verify(snapshot_path, manifest_path):
    source, manifest = Path(snapshot_path), Path(manifest_path)
    if source.resolve() == manifest.resolve():
        raise ValueError('Manifest must be independent of snapshot')
    raw = source.read_bytes()
    expected = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(expected, dict) or set(expected) != {'sha256'} or \
       not isinstance(expected['sha256'], str) or len(expected['sha256']) != 64 or \
       not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected['sha256']):
        raise ValueError('Backup checksum mismatch')
    snapshot = json.loads(raw)
    from versioned_subscriber_sync import validate_state
    validate_state(snapshot)
    # Independent flags and tombstones are preserved byte-for-byte in a
    # disposable JSON roundtrip; never turn a missing entry into a deletion.
    replay = json.loads(json.dumps(snapshot, sort_keys=True))
    if replay != snapshot:
        raise ValueError('Roundtrip mismatch')
    if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(raw).digest():
        raise ValueError('Snapshot changed during verification')
    return {'status': 'offline_exhibition_replay_verified',
            'revision': snapshot['revision'],
            'want_entries': len(snapshot['favs']),
            'seen_entries': len(snapshot['visited']),
            'database_restore_verified': False,
            'durable_backup_verified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--expected-manifest', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.snapshot, args.expected_manifest), sort_keys=True))


if __name__ == '__main__':
    main()
