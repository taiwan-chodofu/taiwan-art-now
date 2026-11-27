"""Synthetic Meta signature tests; no real webhook payloads or credentials."""
import hashlib
import hmac
import unittest
from webhook_security import verify_meta_webhook


class MetaWebhookSignatureTests(unittest.TestCase):
    def setUp(self):
        self.body = b'{"object":"page","entry":[]}'
        self.secret = "synthetic-app-secret"
        self.signature = "sha256=" + hmac.new(
            self.secret.encode(), self.body, hashlib.sha256
        ).hexdigest()

    def test_valid_signature(self):
        self.assertTrue(verify_meta_webhook(self.body, self.signature, app_secret=self.secret))

    def test_tampered_payload(self):
        self.assertFalse(verify_meta_webhook(self.body + b" ", self.signature, app_secret=self.secret))

    def test_missing_secret_fails_closed(self):
        self.assertFalse(verify_meta_webhook(self.body, self.signature, app_secret=""))

    def test_missing_signature(self):
        self.assertFalse(verify_meta_webhook(self.body, "", app_secret=self.secret))

    def test_invalid_hex(self):
        self.assertFalse(verify_meta_webhook(self.body, "sha256=" + "z" * 64, app_secret=self.secret))

    def test_legacy_sha1_rejected(self):
        self.assertFalse(verify_meta_webhook(self.body, "sha1=" + "a" * 40, app_secret=self.secret))

    def test_uppercase_hex_accepted(self):
        self.assertTrue(verify_meta_webhook(self.body, self.signature.upper().replace("SHA256=", "sha256="), app_secret=self.secret))


if __name__ == "__main__":
    unittest.main()
