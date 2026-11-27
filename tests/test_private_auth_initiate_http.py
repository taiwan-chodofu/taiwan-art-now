"""Flask request-level tests for the *actual* /api/private-auth/initiate
route extracted from app.py. Same AST-isolation technique as
test_flask_webhook_http.py: no network, database, or scraper imports.
"""
import ast
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
route = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == "private_auth_initiate")
route.decorator_list = []
code = compile(ast.Module(body=[route], type_ignores=[]), "app.py", "exec")
app = Flask("private-auth-initiate-tests")
app.config["TAN_CANONICAL_ORIGIN"] = "https://example.test"
scope = {"request": request, "jsonify": jsonify, "app": app}
exec(code, scope)
app.add_url_rule("/api/private-auth/initiate", "private_auth_initiate",
                  scope["private_auth_initiate"], methods=["POST"])


class PrivateAuthInitiateHttpTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_cross_origin_post_is_forbidden(self):
        result = self.client.post("/api/private-auth/initiate",
                                   headers={"Origin": "https://evil.test"})
        self.assertEqual(result.status_code, 403)

    def test_missing_connector_is_unavailable(self):
        app.config.pop("TAN_PRIVATE_DB_CONNECT", None)
        result = self.client.post("/api/private-auth/initiate",
                                   headers={"Origin": "https://example.test"})
        self.assertEqual(result.status_code, 503)

    def test_connector_failure_is_unavailable_and_does_not_leak_detail(self):
        def broken_connect():
            raise RuntimeError("relation \"tan_private.messenger_link_challenges\" does not exist")
        app.config["TAN_PRIVATE_DB_CONNECT"] = broken_connect
        result = self.client.post("/api/private-auth/initiate",
                                   headers={"Origin": "https://example.test"})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn(b"messenger_link_challenges", result.data)

    def test_same_origin_post_issues_a_pair_via_the_configured_connector(self):
        import messenger_browser_claim

        class FakeConn:
            def __enter__(self):
                return "synthetic-conn"

            def __exit__(self, *exc):
                return False

        app.config["TAN_PRIVATE_DB_CONNECT"] = lambda: FakeConn()
        with patch.object(messenger_browser_claim, "issue_pair",
                           return_value=("synthetic-code", "synthetic-secret")) as issue:
            result = self.client.post("/api/private-auth/initiate",
                                       headers={"Origin": "https://example.test"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json(), {"messenger_code": "synthetic-code",
                                              "browser_secret": "synthetic-secret"})
        self.assertEqual(result.headers.get("Cache-Control"), "no-store")
        issue.assert_called_once_with("synthetic-conn")


if __name__ == "__main__":
    unittest.main()
