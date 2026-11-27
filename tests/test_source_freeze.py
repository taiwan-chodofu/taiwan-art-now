"""Synthetic source snapshot drift tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/check_source_freeze.py"
spec = importlib.util.spec_from_file_location("check_source_freeze", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceFreezeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.before_m = root / "before_m.json"
        self.before_p = root / "before_p.json"
        self.after_m = root / "after_m.json"
        self.after_p = root / "after_p.json"
        self.before_m.write_text(json.dumps({"users": {"synthetic": {"favs": {}}},
                                              "refs": {"ref": "synthetic"}}))
        self.before_p.write_text(json.dumps({"subscriptions": {}}))
        self.after_m.write_bytes(self.before_m.read_bytes())
        self.after_p.write_bytes(self.before_p.read_bytes())

    def compare(self):
        return module.compare_snapshots(self.before_m, self.before_p, self.after_m, self.after_p)

    def test_unchanged(self):
        result = self.compare()
        self.assertTrue(result["unchanged"])
        self.assertEqual(result["before_counts"], result["after_counts"])

    def test_change_in_profile_detected(self):
        self.after_m.write_text(json.dumps({"users": {"synthetic": {"favs": {"new": True}}},
                                             "refs": {"ref": "synthetic"}}))
        self.assertFalse(self.compare()["unchanged"])

    def test_push_change_detected(self):
        self.after_p.write_text(json.dumps({"subscriptions": {
            "https://example.invalid/p": {"endpoint": "https://example.invalid/p"}
        }}))
        self.assertFalse(self.compare()["unchanged"])

    def test_format_change_is_conservatively_detected(self):
        self.after_m.write_bytes(self.before_m.read_bytes() + b" ")
        self.assertFalse(self.compare()["unchanged"])

    def test_same_snapshot_file_pair_rejected(self):
        with self.assertRaises(ValueError):
            module.compare_snapshots(self.before_m, self.before_m, self.after_m, self.after_p)

    def test_corrupt_snapshot_rejected(self):
        self.after_m.write_text("{")
        with self.assertRaises(json.JSONDecodeError):
            self.compare()


if __name__ == "__main__":
    unittest.main()
