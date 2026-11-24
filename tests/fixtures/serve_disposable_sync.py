"""Loopback-only browser fixture for the disposable PostgreSQL Actions service."""
import sys
from pathlib import Path

import psycopg
from flask import send_file
from werkzeug.serving import run_simple

from browser_session import token_digest
from isolated_versioned_staging_app import create_isolated_staging_app

ORIGIN = "https://127.0.0.1"
DATABASE = "postgresql://tan_ci:synthetic_only_ci@127.0.0.1:5432/tan_ci_disposable"
ROOT = Path(__file__).resolve().parents[2]


def serve(cert, key):
    with psycopg.connect(DATABASE) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            if cur.fetchone() != ("tan_ci_disposable", "tan_ci"):
                raise RuntimeError("Unexpected disposable database identity")
            owners = {
                "browser-drill-owner": ("browser-drill-one", "browser-drill-two"),
                "browser-migration-owner": ("browser-migration-session", "browser-migration-other"),
            }
            for owner, sessions in owners.items():
                cur.execute("INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                            (owner,))
                for session in sessions:
                    cur.execute("INSERT INTO tan_private.browser_sessions(token_hash,sender_id,expires_at) "
                                "VALUES (%s,%s,now()+interval '10 minutes')",
                                (token_digest(session), owner))

    app = create_isolated_staging_app(db_connect=lambda: psycopg.connect(DATABASE),
                                      environment="isolated-staging", canonical_origin=ORIGIN)

    @app.get("/exhibition")
    def exhibition():
        return send_file(ROOT / "tests/fixtures/isolated_staging_exhibition.html")

    run_simple("127.0.0.1", 443, app, ssl_context=(cert, key), threaded=True)


if __name__ == "__main__":
    serve(*sys.argv[1:])
