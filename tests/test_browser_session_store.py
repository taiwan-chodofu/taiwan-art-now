"""Synthetic fake-connection tests for draft browser session DB adapter."""
import unittest
import browser_session_store


class Cursor:
    def __init__(self, row=None, failure=False):
        self.row, self.failure = row, failure
        self.sql, self.params = "", None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        if self.failure:
            raise RuntimeError("synthetic DB outage")
        self.sql, self.params = sql, params

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, row=None, failure=False):
        self.cur = Cursor(row, failure)
        self.commits = self.rollbacks = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class SessionStoreTests(unittest.TestCase):
    def test_issue_only_persists_hash(self):
        conn = Connection()
        token = browser_session_store.issue(conn, verified_sender_id="verified", ttl_seconds=120)
        self.assertNotIn(token, str(conn.cur.params))
        self.assertEqual(len(conn.cur.params[0]), 64)
        self.assertEqual(conn.cur.params[1:], ("verified", 120))
        self.assertEqual(conn.commits, 1)

    def test_valid_session_resolves_server_identity(self):
        conn = Connection(("verified-sender",))
        self.assertEqual(browser_session_store.resolve_sender(conn, token="synthetic"),
                         "verified-sender")
        sql = " ".join(conn.cur.sql.lower().split())
        self.assertIn("revoked_at is null", sql)
        self.assertIn("expires_at > now()", sql)

    def test_unknown_or_expired_session_rejected(self):
        conn = Connection(None)
        self.assertIsNone(browser_session_store.resolve_sender(conn, token="synthetic"))

    def test_revocation_is_conditional(self):
        conn = Connection(("digest",))
        self.assertTrue(browser_session_store.revoke(conn, token="synthetic"))
        self.assertIn("revoked_at is null", conn.cur.sql)

    def test_already_revoked_rejected(self):
        self.assertFalse(browser_session_store.revoke(Connection(None), token="synthetic"))

    def test_invalid_token_does_not_query(self):
        conn = Connection()
        self.assertIsNone(browser_session_store.resolve_sender(conn, token=None))
        self.assertFalse(browser_session_store.revoke(conn, token=None))
        self.assertEqual(conn.commits, 0)

    def test_invalid_sender_rejected(self):
        with self.assertRaises(ValueError):
            browser_session_store.issue(Connection(), verified_sender_id="")

    def test_invalid_ttl_rejected(self):
        with self.assertRaises(ValueError):
            browser_session_store.issue(Connection(), verified_sender_id="verified",
                                        ttl_seconds=True)

    def test_issue_db_failure_rolls_back(self):
        conn = Connection(failure=True)
        with self.assertRaises(RuntimeError):
            browser_session_store.issue(conn, verified_sender_id="verified")
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_resolve_db_failure_does_not_authenticate(self):
        conn = Connection(failure=True)
        with self.assertRaises(RuntimeError):
            browser_session_store.resolve_sender(conn, token="synthetic")
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_revoke_db_failure_rolls_back(self):
        conn = Connection(failure=True)
        with self.assertRaises(RuntimeError):
            browser_session_store.revoke(conn, token="synthetic")
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))


if __name__ == "__main__":
    unittest.main()
