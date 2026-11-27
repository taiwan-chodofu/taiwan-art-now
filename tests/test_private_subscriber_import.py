"""Tests use synthetic records only; never load production subscriber files."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_private_subscribers.py"
spec = importlib.util.spec_from_file_location("import_private_subscribers", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.messenger = {
            "users": {"synthetic-sender": {"weekly_digest": True, "favs": {"art": True}}},
            "refs": {"synthetic-ref": "synthetic-sender"},
        }
        self.push = {"subscriptions": {
            "https://example.invalid/synthetic": {
                "endpoint": "https://example.invalid/synthetic",
                "keys": {"auth": "synthetic", "p256dh": "synthetic"},
            },
        }}

    def test_valid_snapshot(self):
        self.assertEqual(module.validate_snapshot(self.messenger, self.push), (1, 1, 1))

    def test_orphan_ref_rejected(self):
        self.messenger["refs"]["synthetic-ref"] = "missing-sender"
        with self.assertRaises(ValueError):
            module.validate_snapshot(self.messenger, self.push)

    def test_endpoint_mismatch_rejected(self):
        self.push["subscriptions"]["https://example.invalid/synthetic"]["endpoint"] = "other"
        with self.assertRaises(ValueError):
            module.validate_snapshot(self.messenger, self.push)

    def test_invalid_profile_rejected(self):
        self.messenger["users"]["synthetic-sender"] = []
        with self.assertRaises(ValueError):
            module.validate_snapshot(self.messenger, self.push)

    def test_missing_root_key_rejected(self):
        del self.messenger["users"]
        with self.assertRaises(ValueError):
            module.validate_snapshot(self.messenger, self.push)

if __name__ == "__main__":
    unittest.main()
