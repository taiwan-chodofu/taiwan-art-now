"""Opt-in concurrency drill for a disposable, independently verified staging DB.

Never runs automatically in CI. Never connect to production. Requires an
isolated database with the review-only staging guard and rate-limit schema.
No real subscriber IDs or browser tokens are read or printed.
"""
import concurrent.futures
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from private_claim_rate_limit import allow_attempt
from scripts.drill_messenger_link_concurrency import verify_staging_identity

WORKERS = 12
LIMIT = 5


def check_configuration(env):
    url = env.get("TAN_STAGING_DATABASE_URL", "")
    if not url:
        raise RuntimeError("Dedicated TAN_STAGING_DATABASE_URL required")
    if env.get("TAN_STAGING_CONFIRM") != "disposable-isolated-database":
        raise RuntimeError("Explicit disposable staging confirmation required")
    if url == env.get("TAN_DATABASE_URL"):
        raise RuntimeError("Staging and production connection URLs must differ")
    name = env.get("TAN_STAGING_DB_NAME", "")
    if not name or name in ("postgres", "template1"):
        raise RuntimeError("Dedicated staging database name required")
    return url, name


def evaluate_results(results, *, limit=LIMIT):
    if len(results) != WORKERS:
        raise AssertionError("Unexpected number of workers")
    if any(type(result) is not bool for result in results):
        raise AssertionError("Non-boolean rate-limit result")
    if sum(results) != limit:
        raise AssertionError("Concurrent rate limit allowed unexpected count")


def main():
    import psycopg
    url, expected_name = check_configuration(os.environ)
    key = "synthetic-concurrency-" + uuid4().hex
    secret = "synthetic-rate-limit-drill-secret-32-bytes-minimum"
    # Preflight does not prove isolation. Operator must independently verify
    # the database endpoint and destroy the disposable database afterward.
    with psycopg.connect(url, connect_timeout=10) as conn:
        verify_staging_identity(conn, expected_name)
        with conn.cursor() as cur:
            cur.execute("select to_regclass('tan_private.auth_rate_limits')")
            if cur.fetchone()[0] is None:
                raise RuntimeError("Staging rate-limit table missing")

    def attempt(_):
        with psycopg.connect(url, connect_timeout=10) as conn:
            verify_staging_identity(conn, expected_name)
            return allow_attempt(conn, kind="challenge", identifier=key,
                                 limit=LIMIT, window_seconds=600, secret=secret)

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(attempt, range(WORKERS)))
    evaluate_results(results)
    print("PASS: exactly 5 of 12 concurrent synthetic attempts allowed")
    # This drill leaves only synthetic rate-limit counters in disposable DB.


if __name__ == "__main__":
    main()
