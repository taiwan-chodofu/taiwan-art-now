"""Synthetic-only tests for ownership audit release gate."""
import importlib.util
from pathlib import Path
import unittest

script = Path(__file__).resolve().parents[1] / "scripts/audit_subscriber_ownership.py"
spec = importlib.util.spec_from_file_location("audit_subscriber_ownership", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OwnershipAuditTests(unittest.TestCase):
    def test_all_sensitive_routes_require_review(self):
        source = "\n".join("def %s():\n    pass" % name for name in module.PROTECTED)
        findings = module.audit_source(source)
        self.assertEqual(len(findings), 8)
        self.assertTrue(all(item["status"] == "ownership-review-required" for item in findings))

    def test_missing_route_is_not_approved(self):
        findings = module.audit_source("def harmless():\n    pass\n")
        self.assertEqual(len(findings), 8)
        self.assertTrue(all(item["status"] == "missing-review-required" for item in findings))

    def test_fake_auth_name_cannot_bypass_gate(self):
        source = "def api_sync_favs():\n    ownership_verified = True\n"
        findings = module.audit_source(source)
        self.assertEqual(findings[0]["status"], "ownership-review-required")


if __name__ == "__main__":
    unittest.main()
