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
                cur.execute("CREATE TABLE tan_private.subscriber_review_confirmations "
                            "(token_hash bytea primary key, sender_id text not null, "
                            "kind text not null, item_key text not null, "
                            "base_revision bigint not null, item_revision bigint not null, "
                            "choice text not null, value_hash bytea not null, "
                            "expires_at timestamptz not null, used_at timestamptz)")
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

    def test_fresh_revision_alone_cannot_restore_deleted_exhibit(self):
        import psycopg
        with psycopg.connect(self.url) as conn:
            before = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=before["revision"],
                changes={"favs": {"explicit-exhibit": {"delete": True}}, "visited": {}})
            tombstone = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            with self.assertRaises(StaleRevision):
                update_for_verified_sender(
                    conn, verified_sender_id="synthetic-owner",
                    base_revision=tombstone["revision"],
                    changes={"favs": {"explicit-exhibit": {"set": {"title": "Restored"}}},
                             "visited": {}})
            final = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            self.assertTrue(final["favs"]["explicit-exhibit"]["deleted"])

    def test_autocommit_connection_cannot_run_cas(self):
        import psycopg
        with psycopg.connect(self.url, autocommit=True) as conn:
            with self.assertRaises(ValueError):
                update_for_verified_sender(
                    conn, verified_sender_id="synthetic-owner",
                    base_revision=0,
                    changes={"favs": {"unsafe": {"set": True}}, "visited": {}})


    def test_review_token_single_use_and_owner_binding(self):
        import psycopg
        from subscriber_review_confirmation import (
            issue_keep_confirmation, consume_keep_confirmation)
        with psycopg.connect(self.url) as conn:
            current = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            deleted = update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=current["revision"],
                changes={"favs": {"token-exhibit": {"delete": True}}, "visited": {}})
            token = issue_keep_confirmation(
                conn, verified_sender_id="synthetic-owner", kind="favs",
                key="token-exhibit", base_revision=deleted["revision"],
                reviewed_item_revision=deleted["revision"],
                local_value={"title": "Restored"})
        with psycopg.connect(self.url) as conn:
            with self.assertRaises(ValueError):
                consume_keep_confirmation(
                    conn, verified_sender_id="wrong-owner", token=token,
                    local_value={"title": "Restored"})
        with psycopg.connect(self.url) as conn:
            restored = consume_keep_confirmation(
                conn, verified_sender_id="synthetic-owner", token=token,
                local_value={"title": "Restored"})
            self.assertFalse(restored["favs"]["token-exhibit"]["deleted"])
        with psycopg.connect(self.url) as conn:
            with self.assertRaises(ValueError):
                consume_keep_confirmation(
                    conn, verified_sender_id="synthetic-owner", token=token,
                    local_value={"title": "Restored"})
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM tan_private.subscriber_review_confirmations "
                            "WHERE used_at IS NOT NULL")
                self.assertEqual(cur.fetchone()[0], 1)

    def test_review_token_stale_revision_preserves_unused_token(self):
        import psycopg
        from subscriber_review_confirmation import (
            issue_keep_confirmation, consume_keep_confirmation, _digest)
        with psycopg.connect(self.url) as conn:
            before = read_for_verified_sender(conn, verified_sender_id="synthetic-owner")
            deleted = update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=before["revision"],
                changes={"favs": {"stale-token-exhibit": {"delete": True}},
                         "visited": {}})
            token = issue_keep_confirmation(
                conn, verified_sender_id="synthetic-owner", kind="favs",
                key="stale-token-exhibit", base_revision=deleted["revision"],
                reviewed_item_revision=deleted["revision"],
                local_value={"title": "Old"})
            update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=deleted["revision"],
                changes={"favs": {"newer-exhibit": {"set": True}}, "visited": {}})
        with psycopg.connect(self.url) as conn:
            with self.assertRaises(StaleRevision):
                consume_keep_confirmation(
                    conn, verified_sender_id="synthetic-owner", token=token,
                    local_value={"title": "Old"})
            with conn.cursor() as cur:
                cur.execute("SELECT used_at FROM tan_private.subscriber_review_confirmations "
                            "WHERE token_hash = %s", (_digest(token),))
                self.assertIsNone(cur.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
