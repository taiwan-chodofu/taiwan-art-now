"""Synthetic-only one-time Messenger link challenge tests."""
import unittest
from messenger_link_challenge import (
    generate_challenge, hash_challenge, issue_challenge, verify_and_consume,
)


class LinkChallengeTests(unittest.TestCase):
    def test_secure_random_token(self):
        a, b = generate_challenge(), generate_challenge()
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 40)
        self.assertEqual(len(hash_challenge(a)), 64)

    def test_consumed_once(self):
        token = generate_challenge()
        state = issue_challenge(token, now=1000, ttl=120)
        self.assertTrue(verify_and_consume(state, token, "verified-meta-sender", now=1001))
        self.assertEqual(state["sender_id"], "verified-meta-sender")
        self.assertFalse(verify_and_consume(state, token, "verified-meta-sender", now=1002))

    def test_wrong_token_does_not_mutate(self):
        token = generate_challenge()
        state = issue_challenge(token, now=1000)
        original = dict(state)
        self.assertFalse(verify_and_consume(state, generate_challenge(), "verified", now=1001))
        self.assertEqual(state, original)

    def test_expired_rejected(self):
        token = generate_challenge()
        state = issue_challenge(token, now=1000, ttl=30)
        self.assertFalse(verify_and_consume(state, token, "verified", now=1030))
        self.assertIsNone(state["consumed_at"])

    def test_future_issue_rejected(self):
        token = generate_challenge()
        state = issue_challenge(token, now=1000)
        self.assertFalse(verify_and_consume(state, token, "verified", now=999))

    def test_wrong_sender_rejected_when_bound(self):
        token = generate_challenge()
        state = issue_challenge(token, now=1000)
        state["sender_id"] = "expected-verified-sender"
        self.assertFalse(verify_and_consume(state, token, "other-verified-sender", now=1001))
        self.assertIsNone(state["consumed_at"])

    def test_empty_sender_rejected(self):
        token = generate_challenge()
        state = issue_challenge(token, now=1000)
        self.assertFalse(verify_and_consume(state, token, "", now=1001))

    def test_invalid_ttl_rejected(self):
        for ttl in (0, 901, -1, 10.5, "600"):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                issue_challenge("synthetic", now=1000, ttl=ttl)

    def test_malformed_record_rejected(self):
        token = generate_challenge()
        for record in (None, {}, {"expires_at": "soon"}, []):
            with self.subTest(record=record):
                self.assertFalse(verify_and_consume(record, token, "verified", now=1001))


if __name__ == "__main__":
    unittest.main()
