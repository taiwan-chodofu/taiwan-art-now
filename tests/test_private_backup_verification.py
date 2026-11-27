"""Synthetic backup verification tests; no subscriber records or DB credentials."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("verify_private_backup", SCRIPTS / "verify_private_backup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OfflineBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.messenger = Path(self.temp.name) / "messenger.json"
        self.push = Path(self.temp.name) / "push.json"
        self.messenger.write_text(json.dumps({"users": {"synthetic": {"favs": {}}},
                                               "refs": {"ref": "synthetic"}}), encoding="utf-8")
        self.push.write_text(json.dumps({"subscriptions": {
            "https://example.invalid/push": {"endpoint": "https://example.invalid/push"}
        }}), encoding="utf-8")

    def test_valid_snapshot_and_independent_manifest(self):
        hashes, counts = module.verify_files(self.messenger, self.push)
        self.assertEqual(counts, {"users": 1, "refs": 1, "push": 1})
        self.assertEqual(module.verify_files(self.messenger, self.push, hashes)[0], hashes)

    def test_modified_file_fails_integrity(self):
        hashes, _ = module.verify_files(self.messenger, self.push)
        self.messenger.write_text(self.messenger.read_text() + " ", encoding="utf-8")
        with self.assertRaises(ValueError):
            module.verify_files(self.messenger, self.push, hashes)

    def test_invalid_reference_rejected(self):
        self.messenger.write_text(json.dumps({"users": {}, "refs": {"ref": "missing"}}))
        with self.assertRaises(ValueError):
            module.verify_files(self.messenger, self.push)

    def test_same_path_rejected(self):
        with self.assertRaises(ValueError):
            module.verify_files(self.messenger, self.messenger)

    def test_bad_manifest_rejected(self):
        with self.assertRaises(ValueError):
            module.verify_files(self.messenger, self.push, {"messenger_sha256": "x"})


if __name__ == "__main__":
    unittest.main()
