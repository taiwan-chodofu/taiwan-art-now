"""Opt-in integration drill for a dedicated disposable PostgreSQL staging DB.

Never run against production. Requires TAN_STAGING_DATABASE_URL, a manually
provisioned private schema/table, and explicit operator invocation.
No subscriber rows are read. Only synthetic tokens and sender IDs are used.
"""
import concurrent.futures
import os
import sys
from uuid import uuid4

import psycopg
from messenger_link_store import issue, consume


def main():
    url = os.environ.get("TAN_STAGING_DATABASE_URL")
    if not url:
        raise RuntimeError("TAN_STAGING_DATABASE_URL required")
    if os.environ.get("TAN_STAGING_CONFIRM") != "disposable-isolated-database":
        raise RuntimeError("Explicit disposable staging confirmation required")
    if url == os.environ.get("TAN_DATABASE_URL"):
        raise RuntimeError("Staging URL must differ from TAN_DATABASE_URL")
    # A dedicated, isolated DB is a human-verified prerequisite; connection
    # string differences alone do NOT prove production isolation.
    with psycopg.connect(url, connect_timeout=10) as conn:
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
