"""Opt-in integration drill for a dedicated disposable PostgreSQL staging DB.

Never run against production. Requires TAN_STAGING_DATABASE_URL, a manually
provisioned private schema/table, and explicit operator invocation.
No subscriber rows are read. Only synthetic tokens and sender IDs are used.
"""
import concurrent.futures
import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from messenger_link_store import issue, consume


def main():
    url = os.environ.get("TAN_STAGING_DATABASE_URL")
    if not url:
        raise RuntimeError("TAN_STAGING_DATABASE_URL required")
    if os.environ.get("TAN_STAGING_CONFIRM") != "disposable-isolated-database":
        raise RuntimeError("Explicit disposable staging confirmation required")
    if url == os.environ.get("TAN_DATABASE_URL"):
        raise RuntimeError("Staging URL must differ from TAN_DATABASE_URL")
    # Connection-string inequality alone does not prove isolation.
    expected_name = os.environ.get("TAN_STAGING_DB_NAME", "")
    if not expected_name or expected_name in ("postgres", "template1"):
        raise RuntimeError("Dedicated TAN_STAGING_DB_NAME required")
    with psycopg.connect(url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database(), to_regclass('tan_private.staging_drill_guard')")
            database_name, guard_table = cur.fetchone()
            if database_name != expected_name or guard_table is None:
                raise RuntimeError("Database identity or staging guard missing")
            cur.execute("select marker from tan_private.staging_drill_guard limit 2")
            if cur.fetchall() != [("disposable-isolated-database",)]:
                raise RuntimeError("Invalid staging guard marker")
        token = issue(conn, ttl_seconds=120)
    synthetic_sender = "synthetic-" + uuid4().hex

    def attempt(_):
        with psycopg.connect(url, connect_timeout=10) as conn:
            return consume(conn, token=token, verified_sender_id=synthetic_sender)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    if sorted(results) != [False, True]:
        raise AssertionError("Expected exactly one successful consume")
    print("PASS: exactly one of two concurrent synthetic consumes succeeded")
    # Synthetic challenge row is intentionally not automatically deleted.
    # Run only in a disposable database; destroy the database after the drill.


if __name__ == "__main__":
    main()
