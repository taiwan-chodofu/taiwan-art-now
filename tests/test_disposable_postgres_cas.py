"""Disposable CI PostgreSQL integration test. NEVER use production credentials.

Only runs with TAN_CI_DISPOSABLE_POSTGRES=1 and a localhost database whose
name is exactly tan_ci_disposable. The GitHub Actions service is ephemeral.
"""
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from versioned_subscriber_store import update_for_verified_sender, read_for_verified_sender
from versioned_subscriber_sync import StaleRevision

EXPECTED_DB = "tan_ci_disposable"


@unittest.skipUnless(os.environ.get("TAN_CI_DISPOSABLE_POSTGRES") == "1",
                     "Requires isolated disposable CI PostgreSQL service")
class DisposablePostgresCASTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from urllib.parse import urlsplit
        url = os.environ["TAN_CI_DATABASE_URL"]
        parsed = urlsplit(url)
        if parsed.hostname not in ("localhost", "127.0.0.1") or parsed.path != "/" + EXPECTED_DB:
            raise RuntimeError("Refusing non-local/non-disposable PostgreSQL target")
        if os.environ.get("TAN_DATABASE_URL") == url:
            raise RuntimeError("Production URL matches disposable target")
        cls.url = url
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                if cur.fetchone()[0] != EXPECTED_DB:
                    raise RuntimeError("Unexpected database identity")
                cur.execute("CREATE SCHEMA tan_private")
                cur.execute("CREATE TABLE tan_private.messenger_subscribers "
                            "(sender_id text primary key)")
                cur.execute("INSERT INTO tan_private.messenger_subscribers "
                            "(sender_id) VALUES ('synthetic-owner')")
                cur.execute("CREATE TABLE tan_private.subscriber_sync_states "
                            "(sender_id text primary key REFERENCES "
                            "tan_private.messenger_subscribers(sender_id), "
                            "state jsonb not null, updated_at timestamptz default now())")

    def test_concurrent_writers_only_one_succeeds(self):
        import psycopg
        barrier = threading.Barrier(8)
        def attempt(_):
            with psycopg.connect(self.url) as conn:
                barrier.wait(timeout=15)
                try:
                    result = update_for_verified_sender(
                        conn, verified_sender_id="synthetic-owner",
                        base_revision=0,
                        changes={"favs": {"synthetic-exhibit": {"set": True}},
                                 "visited": {}},
                    )
                    return ("success", result["revision"])
                except StaleRevision:
                    return ("stale", None)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(result[0] == "success" for result in results), 1)
        self.assertEqual(sum(result[0] == "stale" for result in results), 7)
        with psycopg.connect(self.url) as conn:
            state = read_for_verified_sender(
                conn, verified_sender_id="synthetic-owner")
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["favs"]["synthetic-exhibit"]["value"], True)

    def test_stale_addition_cannot_resurrect_tombstone(self):
        import psycopg
        with psycopg.connect(self.url) as conn:
            current = read_for_verified_sender(
                conn, verified_sender_id="synthetic-owner")
            initial_revision = current["revision"]
            update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=initial_revision,
                changes={"favs": {"deleted-exhibit": {"set": {"title": "Synthetic"}}},
                         "visited": {}})
            updated = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=updated["revision"],
                changes={"favs": {"deleted-exhibit": {"delete": True}}, "visited": {}})
        with psycopg.connect(self.url) as conn:
            with self.assertRaises(StaleRevision):
                update_for_verified_sender(
                    conn, verified_sender_id="synthetic-owner",
                    base_revision=initial_revision,
                    changes={"favs": {"deleted-exhibit": {"set": {"title": "Stale"}}},
                             "visited": {}})
            final = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            self.assertTrue(final["favs"]["deleted-exhibit"]["deleted"])
            self.assertIsNone(final["favs"]["deleted-exhibit"]["value"])

    def test_explicit_fresh_revision_can_restore_deleted_exhibit(self):
        import psycopg
        with psycopg.connect(self.url) as conn:
            before = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=before["revision"],
                changes={"favs": {"explicit-exhibit": {"delete": True}}, "visited": {}})
            tombstone = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            self.assertTrue(tombstone["favs"]["explicit-exhibit"]["deleted"])
            restored = update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=tombstone["revision"],
                changes={"favs": {"explicit-exhibit": {"set": {"title": "Restored"}}},
                         "visited": {}})
            self.assertFalse(restored["favs"]["explicit-exhibit"]["deleted"])
            self.assertEqual(restored["favs"]["explicit-exhibit"]["value"]["title"],
                             "Restored")

    def test_autocommit_connection_cannot_run_cas(self):
        import psycopg
        with psycopg.connect(self.url, autocommit=True) as conn:
            with self.assertRaises(ValueError):
                update_for_verified_sender(
                    conn, verified_sender_id="synthetic-owner",
                    base_revision=0,
                    changes={"favs": {"unsafe": {"set": True}}, "visited": {}})


if __name__ == "__main__":
    unittest.main()
