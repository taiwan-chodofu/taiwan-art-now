"""Synthetic two-secret handshake tests. No real DB or Meta calls."""
import unittest
from messenger_browser_claim import issue_pair, mark_meta_verified, claim_browser_session


class Cursor:
    def __init__(self, rows=None, fail_insert=False):
        self.rows = iter(rows or [])
        self.fail_insert = fail_insert
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))
        if self.fail_insert and "insert into tan_private.browser_sessions" in sql:
            raise RuntimeError("synthetic insert outage")

    def fetchone(self):
        return next(self.rows, None)


class Conn:
    def __init__(self, rows=None, fail_insert=False):
        self.cur = Cursor(rows, fail_insert)
        self.commits = self.rollbacks = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class ClaimTests(unittest.TestCase):
    def test_pair_secrets_distinct_and_only_hashes_persist(self):
        conn = Conn()
        code, secret = issue_pair(conn)
        self.assertNotEqual(code, secret)
        self.assertGreaterEqual(len(code), 40)
        self.assertGreaterEqual(len(secret), 40)
        self.assertNotIn(code, str(conn.cur.calls))
        self.assertNotIn(secret, str(conn.cur.calls))
        self.assertEqual(len(conn.cur.calls[0][1][0]), 64)
        self.assertEqual(len(conn.cur.calls[0][1][1]), 64)
        self.assertEqual(conn.commits, 1)

    def test_meta_marks_verified_without_session(self):
        conn = Conn(rows=[("claimed",)])
        self.assertTrue(mark_meta_verified(
            conn, messenger_code="synthetic", verified_sender_id="meta-sender"))
        self.assertEqual(len(conn.cur.calls), 1)
        self.assertIn("verified_at = now()", conn.cur.calls[0][0])
        self.assertEqual(conn.commits, 1)

    def test_meta_duplicate_rejected(self):
        conn = Conn()
        self.assertFalse(mark_meta_verified(
            conn, messenger_code="synthetic", verified_sender_id="meta-sender"))
        self.assertEqual(conn.commits, 1)

    def test_browser_claim_gets_sender_only_from_db(self):
        conn = Conn(rows=[("verified-meta-sender",)])
        token = claim_browser_session(
            conn, messenger_code="synthetic-code", browser_secret="synthetic-secret")
        self.assertIsInstance(token, str)
        self.assertEqual(len(conn.cur.calls), 2)
        self.assertEqual(conn.cur.calls[1][1][1], "verified-meta-sender")
        self.assertNotIn(token, str(conn.cur.calls))
        self.assertEqual((conn.commits, conn.rollbacks), (1, 0))

    def test_wrong_secret_or_unverified_cannot_issue_session(self):
        conn = Conn(rows=[])
        self.assertIsNone(claim_browser_session(
            conn, messenger_code="synthetic-code", browser_secret="wrong"))
        self.assertEqual(len(conn.cur.calls), 1)
        self.assertIn("browser_claim_hash = %s", conn.cur.calls[0][0])
        self.assertIn("verified_at is not null", conn.cur.calls[0][0])
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_session_insert_failure_rolls_back_claim(self):
        conn = Conn(rows=[("verified-meta",)], fail_insert=True)
        with self.assertRaises(RuntimeError):
            claim_browser_session(
                conn, messenger_code="synthetic-code", browser_secret="synthetic-secret")
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_invalid_meta_sender_rejected(self):
        conn = Conn()
        with self.assertRaises(ValueError):
            mark_meta_verified(conn, messenger_code="synthetic", verified_sender_id="")
        self.assertEqual(conn.cur.calls, [])

    def test_invalid_ttl_rejected(self):
        with self.assertRaises(ValueError):
            issue_pair(Conn(), ttl_seconds=True)
        with self.assertRaises(ValueError):
            claim_browser_session(Conn(), messenger_code="a",
                                  browser_secret="b", ttl_seconds=86401)


if __name__ == "__main__":
    unittest.main()
