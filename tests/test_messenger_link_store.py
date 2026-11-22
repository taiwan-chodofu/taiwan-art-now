"""Synthetic fake-connection tests of PostgreSQL adapter SQL and parameters.

These tests do NOT prove real DB concurrency. A separate staging integration
test with two independent transactions is mandatory before deployment.
"""
import unittest
from unittest.mock import patch
import messenger_link_store


class Cursor:
    def __init__(self, row=None):
        self.row = row
        self.sql = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.sql, self.params = sql, params

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, row=None):
        self.cur = Cursor(row)
        self.commits = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1


class StoreTests(unittest.TestCase):
    def test_issue_stores_hash_not_raw_token(self):
        conn = Connection()
        token = messenger_link_store.issue(conn, ttl_seconds=120)
        self.assertNotIn(token, str(conn.cur.params))
        self.assertEqual(len(conn.cur.params[0]), 64)
        self.assertEqual(conn.cur.params[1], 120)
        self.assertEqual(conn.commits, 1)

    def test_atomic_consume_sql_conditions(self):
        conn = Connection(("hash",))
        self.assertTrue(messenger_link_store.consume(
            conn, token="synthetic", verified_sender_id="verified-meta"))
        sql = " ".join(conn.cur.sql.lower().split())
        self.assertIn("update tan_private.messenger_link_challenges", sql)
        self.assertIn("consumed_at is null", sql)
        self.assertIn("expires_at > now()", sql)
        self.assertIn("returning", sql)
        self.assertEqual(conn.commits, 1)

    def test_duplicate_or_expired_returns_false(self):
        conn = Connection(None)
        self.assertFalse(messenger_link_store.consume(
            conn, token="synthetic", verified_sender_id="verified-meta"))

    def test_empty_sender_rejected_without_sql(self):
        conn = Connection()
        self.assertFalse(messenger_link_store.consume(
            conn, token="synthetic", verified_sender_id=" "))
        self.assertEqual(conn.commits, 0)

    def test_invalid_ttl_rejected_without_sql(self):
        conn = Connection()
        with self.assertRaises(ValueError):
            messenger_link_store.issue(conn, ttl_seconds=901)
        self.assertEqual(conn.commits, 0)


if __name__ == "__main__":
    unittest.main()
