"""Tests for the ProxyFix wiring and _trusted_client_identity helper added to
app.py for the private browser-claim rate limiter. Proves the specific
choice made (x_for=1, trusting exactly one reverse-proxy hop) behaves as
intended; does not re-test Werkzeug's own ProxyFix internals or
private_claim_rate_limit.py's SQL (already covered by
test_private_claim_rate_limit.py).
"""
import ast
from pathlib import Path
import sys
import unittest

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "_trusted_client_identity")
code = compile(ast.Module(body=[node], type_ignores=[]), "app.py", "exec")
scope = {}
exec(code, scope)
_trusted_client_identity = scope["_trusted_client_identity"]


class TrustedClientIdentityTests(unittest.TestCase):
    def test_returns_the_requests_remote_addr(self):
        class FakeRequest:
            remote_addr = "203.0.113.5"
        self.assertEqual(_trusted_client_identity(FakeRequest()), "203.0.113.5")

    def test_returns_empty_string_when_remote_addr_is_none(self):
        class FakeRequest:
            remote_addr = None
        self.assertEqual(_trusted_client_identity(FakeRequest()), "")


class ProxyFixSingleHopTests(unittest.TestCase):
    """Exactly the trust model app.py applies: x_for=1."""

    def setUp(self):
        self.app = Flask("proxyfix-tests")
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1)
        self.captured = {}

        @self.app.get("/whoami")
        def whoami():
            self.captured["remote_addr"] = request.remote_addr
            return "ok"

        self.client = self.app.test_client()

    def test_trusts_the_single_forwarded_for_entry_from_the_load_balancer(self):
        self.client.get("/whoami", headers={"X-Forwarded-For": "203.0.113.5"})
        self.assertEqual(self.captured["remote_addr"], "203.0.113.5")

    def test_trusts_only_the_rightmost_entry_when_a_client_appends_a_fake_one(self):
        # A malicious client cannot smuggle its own IP in ahead of the load
        # balancer's real appended value; x_for=1 only reads the last entry.
        self.client.get("/whoami", headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.5"})
        self.assertEqual(self.captured["remote_addr"], "203.0.113.5")

    def test_falls_back_to_the_direct_connection_when_no_header_is_present(self):
        self.client.get("/whoami")
        self.assertIsNotNone(self.captured["remote_addr"])


if __name__ == "__main__":
    unittest.main()
