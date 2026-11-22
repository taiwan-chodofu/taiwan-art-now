"""Synthetic transaction tests; no real subscriber data or database."""
import unittest
from messenger_session_exchange import exchange_verified_challenge


class Cursor:
    def __init__(self, claim=True, fail_insert=False):
        self.claim, self.fail_insert = claim, fail_insert
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if self.fail_insert and "insert into" in sql.lower():
            raise RuntimeError("synthetic insert failure")

    def fetchone(self):
        return ("claimed",) if self.claim else None


class Connection:
    def __init__(self, claim=True, fail_insert=False):
        self.cur = Cursor(claim, fail_insert)
        self.commits = self.rollbacks = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class ExchangeTests(unittest.TestCase):
    def test_success_commits_both_writes_once(self):
        conn = Connection()
        token = exchange_verified_challenge(
            conn, challenge_token="synthetic-challenge", verified_sender_id="verified-meta")
        self.assertIsInstance(token, str)
        self.assertEqual(len(conn.cur.queries), 2)
        self.assertEqual((conn.commits, conn.rollbacks), (1, 0))
        self.assertNotIn(token, str(conn.cur.queries))

    def test_replay_does_not_issue_session(self):
        conn = Connection(claim=False)
        self.assertIsNone(exchange_verified_challenge(
            conn, challenge_token="synthetic-challenge", verified_sender_id="verified-meta"))
        self.assertEqual(len(conn.cur.queries), 1)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_insert_failure_rolls_back_challenge(self):
        conn = Connection(fail_insert=True)
        with self.assertRaises(RuntimeError):
            exchange_verified_challenge(
                conn, challenge_token="synthetic-challenge", verified_sender_id="verified-meta")
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_invalid_sender_fails_before_db(self):
        conn = Connection()
        with self.assertRaises(ValueError):
            exchange_verified_challenge(
                conn, challenge_token="synthetic", verified_sender_id=" ")
        self.assertEqual(len(conn.cur.queries), 0)

    def test_invalid_ttl_fails_before_db(self):
        conn = Connection()
        with self.assertRaises(ValueError):
            exchange_verified_challenge(
                conn, challenge_token="synthetic", verified_sender_id="verified",
                ttl_seconds=True)
        self.assertEqual(len(conn.cur.queries), 0)

    def test_only_hashes_in_sql(self):
        conn = Connection()
        exchange_verified_challenge(
            conn, challenge_token="synthetic-challenge", verified_sender_id="verified")
        params = conn.cur.queries
        self.assertNotIn("synthetic-challenge", str(params))
        self.assertEqual(len(params[0][1][1]), 64)
        self.assertEqual(len(params[1][1][0]), 64)


if __name__ == "__main__":
    unittest.main()
