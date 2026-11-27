"""Synthetic-only tests of frontend callsite inventory and release gate."""
import tempfile
import unittest
from pathlib import Path
from scripts.audit_frontend_subscriber_calls import (
    TEMPLATES, inspect_template, inventory,
)


class FrontendAuditTests(unittest.TestCase):
    def test_legacy_sync_detected(self):
        result = inspect_template("fetch('/api/subscribers/sync', {})",
                                  "templates/index.html")
        self.assertEqual(result[0]["route"], "/api/subscribers/sync")
        self.assertTrue(result[0]["migration_required"])

    def test_push_subscription_detected(self):
        result = inspect_template('fetch("/api/push/subscribe")', "template")
        self.assertTrue(result[0]["migration_required"])

    def test_vapid_public_key_not_blocked(self):
        result = inspect_template("fetch('/api/push/vapid-public-key')", "template")
        self.assertFalse(result[0]["migration_required"])

    def test_new_private_route_not_legacy(self):
        result = inspect_template("fetch('/api/private-subscribers/sync')", "template")
        self.assertEqual(result, [])

    def test_inventory_all_three_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in TEMPLATES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fetch('/api/subscribers/sync')", encoding="utf-8")
            result = inventory(root)
        self.assertEqual(len(result), 3)
        self.assertEqual({x["file"] for x in result}, set(TEMPLATES))


if __name__ == "__main__":
    unittest.main()
