"""Synthetic transactional CAS tests, no PostgreSQL connection."""
import unittest
from versioned_subscriber_store import update_for_verified_sender
from versioned_subscriber_sync import StaleRevision


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.db.queries.append(sql)
        if "pg_advisory_xact_lock" in sql:
            self.result = ("locked",)
        elif "SELECT state" in sql:
            self.result = (self.db.state,) if self.db.state is not None else None
        elif "INSERT INTO" in sql:
            self.result = ("owner",) if self.db.insert_success else None
        elif "UPDATE tan_private" in sql:
            self.result = ("owner",) if self.db.update_success else None

    def fetchone(self):
        return self.result


class FakeDB:
    def __init__(self, state=None):
        self.state = state
        self.queries = []
        self.commits = 0
        self.rollbacks = 0
        self.insert_success = True
        self.update_success = True

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def changes():
    return {"favs": {"a": {"set": True}}, "visited": {}}


class VersionedStoreTests(unittest.TestCase):
    def test_autocommit_rejected_before_any_write(self):
        db = FakeDB()
        db.autocommit = True
        with self.assertRaises(ValueError):
            update_for_verified_sender(
                db, verified_sender_id="owner", base_revision=0, changes=changes())
        self.assertEqual(db.queries, [])
        self.assertEqual(db.commits, 0)

    def test_bootstrap_uses_advisory_lock_and_insert(self):
        db = FakeDB()
        result = update_for_verified_sender(
            db, verified_sender_id="owner", base_revision=0, changes=changes())
        self.assertEqual(result["revision"], 1)
        self.assertEqual(db.commits, 1)
        self.assertIn("pg_advisory_xact_lock", " ".join(db.queries))
        self.assertIn("ON CONFLICT", " ".join(db.queries))

    def test_existing_state_uses_revision_guard(self):
        state = {"revision": 1, "favs": {"a": {
            "value": True, "deleted": False, "revision": 1}}, "visited": {}}
        db = FakeDB(state)
        result = update_for_verified_sender(
            db, verified_sender_id="owner", base_revision=1,
            changes={"favs": {"a": {"delete": True}}, "visited": {}})
        self.assertEqual(result["revision"], 2)
        self.assertTrue(result["favs"]["a"]["deleted"])
        self.assertIn("(state->>'revision')::bigint = %s", " ".join(db.queries))

    def test_stale_base_rolls_back(self):
        db = FakeDB({"revision": 1, "favs": {}, "visited": {}})
        with self.assertRaises(StaleRevision):
            update_for_verified_sender(
                db, verified_sender_id="owner", base_revision=0, changes=changes())
        self.assertEqual(db.rollbacks, 1)
        self.assertEqual(db.commits, 0)

    def test_insert_race_rolls_back(self):
        db = FakeDB()
        db.insert_success = False
        with self.assertRaises(StaleRevision):
            update_for_verified_sender(
                db, verified_sender_id="owner", base_revision=0, changes=changes())
        self.assertEqual(db.rollbacks, 1)

    def test_update_race_rolls_back(self):
        db = FakeDB({"revision": 1, "favs": {}, "visited": {}})
        db.update_success = False
        with self.assertRaises(StaleRevision):
            update_for_verified_sender(
                db, verified_sender_id="owner", base_revision=1, changes=changes())
        self.assertEqual(db.rollbacks, 1)

    def test_missing_verified_sender_rejected(self):
        with self.assertRaises(ValueError):
            update_for_verified_sender(
                FakeDB(), verified_sender_id="", base_revision=0,
                changes=changes())

    def test_empty_batch_does_not_insert(self):
        db = FakeDB()
        result = update_for_verified_sender(
            db, verified_sender_id="owner", base_revision=0,
            changes={"favs": {}, "visited": {}})
        self.assertEqual(result["revision"], 0)
        self.assertFalse(any("INSERT INTO" in sql for sql in db.queries))
        self.assertEqual(db.commits, 1)


if __name__ == "__main__":
    unittest.main()
