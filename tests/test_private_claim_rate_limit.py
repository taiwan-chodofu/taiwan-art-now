"""Synthetic SQL-shape and failure tests for shared rate limiter."""
import unittest
from private_claim_rate_limit import bucket_key, allow_attempt, require_both_buckets


class Cursor:
    def __init__(self, row=(1,), fail=False):
        self.row, self.fail, self.calls = row, fail, []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, sql, params):
        if self.fail:
            raise RuntimeError("synthetic outage")
        self.calls.append((sql, params))
    def fetchone(self):
        return self.row


class Conn:
    def __init__(self, row=(1,), fail=False):
        self.cur = Cursor(row, fail)
        self.commits = self.rollbacks = 0
    def cursor(self):
        return self.cur
    def commit(self):
        self.commits += 1
    def rollback(self):
        self.rollbacks += 1


SECRET = "synthetic-test-only-secret-at-least-32"


class RateLimitTests(unittest.TestCase):
    def test_hmac_key_does_not_store_identifier(self):
        key = bucket_key("client", "synthetic-ip", secret=SECRET)
        self.assertEqual(len(key), 64)
        self.assertNotIn("synthetic-ip", key)

    def test_kind_separates_buckets(self):
        self.assertNotEqual(bucket_key("client", "same", secret=SECRET),
                            bucket_key("challenge", "same", secret=SECRET))

    def test_under_limit_allowed(self):
        conn = Conn((3,))
        self.assertTrue(allow_attempt(conn, kind="client", identifier="synthetic",
                                      secret=SECRET))
        self.assertEqual(conn.commits, 1)
        self.assertIn("on conflict", conn.cur.calls[0][0].lower())
        self.assertIn("returning attempts", conn.cur.calls[0][0].lower())

    def test_limit_reached_denied(self):
        self.assertFalse(allow_attempt(Conn((6,)), kind="client",
                                       identifier="synthetic", secret=SECRET))

    def test_exact_limit_allowed(self):
        self.assertTrue(allow_attempt(Conn((5,)), kind="client",
                                      identifier="synthetic", secret=SECRET))

    def test_db_outage_rolls_back(self):
        conn = Conn(fail=True)
        with self.assertRaises(RuntimeError):
            allow_attempt(conn, kind="client", identifier="synthetic", secret=SECRET)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_missing_row_fails_closed(self):
        conn = Conn(None)
        with self.assertRaises(RuntimeError):
            allow_attempt(conn, kind="client", identifier="synthetic", secret=SECRET)

    def test_invalid_policy_rejected(self):
        for limit in (0, True, 101):
            with self.assertRaises(ValueError):
                allow_attempt(Conn(), kind="client", identifier="x",
                              limit=limit, secret=SECRET)

    def test_missing_secret_rejected(self):
        with self.assertRaises(ValueError):
            bucket_key("client", "synthetic", secret=None)

    def test_both_buckets_checked(self):
        conn = Conn((1,))
        self.assertTrue(require_both_buckets(
            conn, client_identifier="synthetic-client",
            challenge_identifier="synthetic-challenge", secret=SECRET))
        self.assertEqual(len(conn.cur.calls), 2)

    def test_challenge_over_limit_denied(self):
        conn = Conn((6,))
        self.assertFalse(require_both_buckets(
            conn, client_identifier="synthetic-client",
            challenge_identifier="synthetic-challenge", secret=SECRET))


if __name__ == "__main__":
    unittest.main()
