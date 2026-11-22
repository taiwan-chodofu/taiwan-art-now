"""Flask request-level tests for the *actual* webhook function extracted from app.py.

The full application imports scrapers and external services; isolate only the
real route AST to avoid running unrelated startup jobs or reading subscriber JSON.
No network, database or real identifiers are used.
"""
import ast
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from flask import Flask, abort, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
route = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == "webhook_receive")
route.decorator_list = []
code = compile(ast.Module(body=[route], type_ignores=[]), "app.py", "exec")
app = Flask("webhook-integration-tests")
scope = {"request": request, "abort": abort, "app": app}
exec(code, scope)
app.add_url_rule("/webhook", "webhook_receive", scope["webhook_receive"], methods=["POST"])


def signed(payload, secret="synthetic-secret"):
    body = json.dumps(payload, separators=(",", ":")).encode()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {"Content-Type": "application/json",
                  "X-Hub-Signature-256": "sha256=" + digest}


class FlaskWebhookTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.secret = patch.dict(os.environ, {"META_APP_SECRET": "synthetic-secret"})
        self.secret.start()
        self.addCleanup(self.secret.stop)

    def test_unsigned_payload_is_forbidden(self):
        result = self.client.post("/webhook", data=b'{"entry":[]}',
                                  content_type="application/json")
        self.assertEqual(result.status_code, 403)

    def test_tampered_payload_is_forbidden(self):
        body, headers = signed({"entry": []})
        result = self.client.post("/webhook", data=body + b" ", headers=headers)
        self.assertEqual(result.status_code, 403)

    def test_signed_empty_batch_ok(self):
        body, headers = signed({"object": "page", "entry": []})
        result = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(result.status_code, 200)

    def test_signed_message_is_written_to_private_inbox(self):
        import private_inbox
        payload = {"object": "page", "entry": [{"messaging": [
            {"sender": {"id": "synthetic-sender"},
             "message": {"mid": "synthetic-mid", "text": "hello"}}]}]}
        body, headers = signed(payload)
        with patch.object(private_inbox, "store_inbound", return_value=True) as store:
            with patch.dict(scope, {"_add_subscriber": lambda *a, **k: None}):
                result = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(store.call_count, 1)
        self.assertEqual(store.call_args.args[:3], ("Messenger", "synthetic-sender", "hello"))
        self.assertEqual(len(store.call_args.args[4]), 64)

    def test_duplicate_message_does_not_resubscribe(self):
        import private_inbox
        payload = {"object": "page", "entry": [{"messaging": [
            {"sender": {"id": "synthetic-sender"},
             "message": {"mid": "synthetic-mid", "text": "hello"}}]}]}
        body, headers = signed(payload)
        subscriber_calls = []
        with patch.object(private_inbox, "store_inbound", return_value=False):
            with patch.dict(scope, {"_add_subscriber": lambda *a, **k: subscriber_calls.append(a)}):
                result = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(subscriber_calls, [])

    def test_storage_failure_is_retryable_and_no_public_fallback(self):
        import private_inbox
        payload = {"object": "instagram", "entry": [{"messaging": [
            {"sender": {"id": "synthetic-sender"},
             "message": {"mid": "synthetic-mid", "text": "hello"}}]}]}
        body, headers = signed(payload)
        with patch.object(private_inbox, "store_inbound", side_effect=RuntimeError("synthetic")):
            result = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(result.status_code, 503)


if __name__ == "__main__":
    unittest.main()
