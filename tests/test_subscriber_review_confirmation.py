import unittest
from unittest.mock import patch
from subscriber_review_confirmation import (
    issue_keep_confirmation, consume_keep_confirmation, _digest, _value_digest)
from versioned_subscriber_sync import StaleRevision

STATE = {"revision": 4, "favs": {"a": {
    "value": None, "deleted": True, "revision": 3}}, "visited": {}}
VALUE = {"title": "Exhibition"}


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.conn.queries.append((sql, params))
        if sql.startswith("SELECT sender_id, kind"):
            self.row = self.conn.confirmation
        elif sql.startswith("UPDATE tan_private.subscriber_review_confirmations"):
            self.row = (b"used",)

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.queries = []
        self.confirmation = None
        self.commits = 0
        self.rollbacks = 0
        self.autocommit = False

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class ConfirmationTests(unittest.TestCase):
    def test_issue_binds_owner_item_and_value_and_commits(self):
        conn = Connection()
        with patch("subscriber_review_confirmation.read_for_verified_sender",
                   return_value=STATE):
            token = issue_keep_confirmation(
                conn, verified_sender_id="owner", kind="favs", key="a",
                base_revision=4, reviewed_item_revision=3, local_value=VALUE)
        self.assertEqual(len(token), 64)
        sql, params = conn.queries[0]
        self.assertIn("INSERT INTO tan_private.subscriber_review_confirmations", sql)
        self.assertEqual(params[1:6], ("owner", "favs", "a", 4, 3))
        self.assertEqual(params[-1], _value_digest(VALUE))
        self.assertEqual(conn.commits, 1)

    def test_issue_stale_tombstone_refused(self):
        conn = Connection()
        with patch("subscriber_review_confirmation.read_for_verified_sender",
                   return_value=STATE):
            with self.assertRaises(StaleRevision):
                issue_keep_confirmation(
                    conn, verified_sender_id="owner", kind="favs", key="a",
                    base_revision=3, reviewed_item_revision=3, local_value=VALUE)
        self.assertEqual(conn.queries, [])
        self.assertEqual(conn.rollbacks, 1)

    def test_issue_autocommit_refused(self):
        conn = Connection()
        conn.autocommit = True
        with self.assertRaises(ValueError):
            issue_keep_confirmation(
                conn, verified_sender_id="owner", kind="favs", key="a",
                base_revision=4, reviewed_item_revision=3, local_value=VALUE)

    def test_consume_same_owner_and_value_updates_in_same_transaction(self):
        conn = Connection()
        conn.confirmation = ("owner", "favs", "a", 4, 3,
                             "keep_saved", _value_digest(VALUE))
        with patch("subscriber_review_confirmation.read_for_verified_sender",
                   return_value=STATE), patch(
                       "subscriber_review_confirmation.update_for_verified_sender",
                       return_value={"revision": 5}) as update:
            result = consume_keep_confirmation(
                conn, verified_sender_id="owner", token="ab" * 32, local_value=VALUE)
        self.assertEqual(result["revision"], 5)
        self.assertEqual(update.call_args.kwargs["verified_sender_id"], "owner")
        self.assertEqual(update.call_args.kwargs["base_revision"], 4)
        self.assertIn("SET used_at", conn.queries[-1][0])

    def test_other_owner_cannot_use_token(self):
        conn = Connection()
        conn.confirmation = ("owner", "favs", "a", 4, 3,
                             "keep_saved", _value_digest(VALUE))
        with self.assertRaises(ValueError):
            consume_keep_confirmation(
                conn, verified_sender_id="attacker", token="ab" * 32,
                local_value=VALUE)
        self.assertEqual(len(conn.queries), 1)
        self.assertEqual(conn.rollbacks, 1)

    def test_changed_value_cannot_use_token(self):
        conn = Connection()
        conn.confirmation = ("owner", "favs", "a", 4, 3,
                             "keep_saved", _value_digest(VALUE))
        with self.assertRaises(ValueError):
            consume_keep_confirmation(
                conn, verified_sender_id="owner", token="ab" * 32,
                local_value={"title": "Different"})
        self.assertEqual(len(conn.queries), 1)

    def test_expired_or_used_token_refused(self):
        conn = Connection()
        with self.assertRaises(ValueError):
            consume_keep_confirmation(
                conn, verified_sender_id="owner", token="ab" * 32,
                local_value=VALUE)
        self.assertEqual(conn.rollbacks, 1)

    def test_stale_revision_rolls_back_token_consumption(self):
        conn = Connection()
        conn.confirmation = ("owner", "favs", "a", 4, 3,
                             "keep_saved", _value_digest(VALUE))
        stale = {"revision": 5, "favs": {"a": {
            "value": None, "deleted": True, "revision": 3}}, "visited": {}}
        with patch("subscriber_review_confirmation.read_for_verified_sender",
                   return_value=stale):
            with self.assertRaises(StaleRevision):
                consume_keep_confirmation(
                    conn, verified_sender_id="owner", token="ab" * 32,
                    local_value=VALUE)
        self.assertEqual(conn.rollbacks, 1)
        self.assertFalse(any("SET used_at" in q[0] for q in conn.queries))

    def test_bad_token_rejected(self):
        with self.assertRaises(ValueError):
            _digest("not-hex")

    def test_value_hash_canonical_order(self):
        self.assertEqual(_value_digest({"a": 1, "b": 2}),
                         _value_digest({"b": 2, "a": 1}))

    def test_non_json_value_rejected(self):
        with self.assertRaises(ValueError):
            _value_digest({"bad": object()})

    def test_autocommit_consume_rejected(self):
        conn = Connection()
        conn.autocommit = True
        with self.assertRaises(ValueError):
            consume_keep_confirmation(
                conn, verified_sender_id="owner", token="ab" * 32,
                local_value=VALUE)


if __name__ == "__main__":
    unittest.main()
