"""Synthetic-only browser session lifecycle tests."""
import unittest
from browser_session import (
    generate_session_token, token_digest, create_session_record,
    validate_session, revoke_session,
)


class BrowserSessionTests(unittest.TestCase):
    def test_random_unique_tokens(self):
        a, b = generate_session_token(), generate_session_token()
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 40)

    def test_session_valid_within_ttl(self):
        token = generate_session_token()
        record = create_session_record(token, "verified-meta", now=100, ttl=60)
        self.assertTrue(validate_session(record, token, now=101))
        self.assertNotIn(token, str(record))

    def test_expired_session_rejected(self):
        token = generate_session_token()
        record = create_session_record(token, "verified-meta", now=100, ttl=60)
        self.assertFalse(validate_session(record, token, now=160))

    def test_future_session_rejected(self):
        token = generate_session_token()
        record = create_session_record(token, "verified-meta", now=100)
        self.assertFalse(validate_session(record, token, now=99))

    def test_wrong_token_rejected(self):
        token = generate_session_token()
        record = create_session_record(token, "verified-meta", now=100)
        self.assertFalse(validate_session(record, generate_session_token(), now=101))

    def test_revocation_rejected(self):
        token = generate_session_token()
        record = create_session_record(token, "verified-meta", now=100)
        self.assertTrue(revoke_session(record, now=102))
        self.assertFalse(validate_session(record, token, now=103))
        self.assertFalse(revoke_session(record, now=104))

    def test_missing_sender_rejected(self):
        with self.assertRaises(ValueError):
            create_session_record("synthetic", "", now=100)

    def test_invalid_ttl_rejected(self):
        for ttl in (0, 86401, -1, True, 1.5, "3600"):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                create_session_record("synthetic", "verified", now=100, ttl=ttl)

    def test_invalid_record_rejected(self):
        for record in ({}, None, {"token_hash": "bad"}, []):
            with self.subTest(record=record):
                self.assertFalse(validate_session(record, "synthetic", now=100))

    def test_invalid_token_rejected(self):
        token = generate_session_token()
        record = create_session_record(token, "verified", now=100)
        self.assertFalse(validate_session(record, None, now=101))
        self.assertFalse(validate_session(record, "x" * 257, now=101))


if __name__ == "__main__":
    unittest.main()
