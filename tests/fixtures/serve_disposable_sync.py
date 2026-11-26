"""Loopback-only browser fixture for the disposable PostgreSQL Actions service."""
import sys
from pathlib import Path

import psycopg
from flask import send_file, render_template, request
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
                "browser-discover-owner": ("browser-discover-session",),
                "browser-nearby-owner": ("browser-nearby-session",),
                "browser-detail-owner": ("browser-detail-session",),
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

    app.config["TAN_ISOLATED_DETAIL_SYNC"] = True

    app.config["TAN_ISOLATED_NEARBY_SYNC"] = True

    app.config["TAN_ISOLATED_DISCOVER_SYNC"] = True

    @app.get("/actual-discover")
    def actual_discover():
        cards = [
            {"stable_key": "discover-a", "title": "Synthetic Discover A", "museum": "Synthetic Museum",
             "dates": "2026", "detail_url": "/exhibition?key=discover-a",
             "excerpt": "Synthetic excerpt A", "region": "Synthetic Region", "days_left": None},
            {"stable_key": "discover-b", "title": "Synthetic Discover B", "museum": "Synthetic Museum",
             "dates": "2026", "detail_url": "/exhibition?key=discover-b",
             "excerpt": "Synthetic excerpt B", "region": "Synthetic Region", "days_left": None},
        ]
        labels = {"title": "Discover", "subtitle": "", "back": "Back", "heading": "Discover",
                  "count_left": "left", "today_last": "Today", "days_left": " days",
                  "view_details": "Details", "like": "Like", "seen": "Seen", "skip": "Skip",
                  "undo": "Undo", "empty": "Empty", "empty_sub": "", "restart": "Restart",
                  "scroll_more": "More", "tutorial_title": "Tutorial", "tutorial_like": "Like",
                  "tutorial_seen": "Seen", "tutorial_tap": "Tap", "tutorial_got_it": "OK"}
        return render_template("discover.html", current_lang=request.args.get("lang", "ja"),
                               cards=cards, labels=labels)

    @app.get("/actual-nearby")
    def actual_nearby():
        exhibitions = [{"title": "Synthetic " + key, "fav_key": key,
                        "dates": "2026", "detail_url": "/exhibition?key=" + key,
                        "days_left": None, "days_until_start": None}
                       for key in ("nearby-a", "nearby-b")]
        return render_template("nearby.html", current_lang="zh", museum_name="Synthetic Origin",
                               nearby=[{"name": "Synthetic Museum", "distance_km": 1,
                                        "exhibitions": exhibitions}])

    @app.get("/actual-detail")
    def actual_detail():
        return render_template("exhibition_detail_page.html",
            current_lang=request.args.get("lang", "ja"), museum_id="synthetic", idx=0,
            structured_data={}, labels={}, other_exhibitions=[],
            exhibition={"title": "Synthetic Art", "stable_key": "actual-detail",
                        "dates": "2026", "days_left": None, "artists": [], "description": "Synthetic exhibition"},
            museum={"name": "Synthetic Museum", "address": "", "url": ""})

    @app.get("/exhibition")
    def exhibition():
        return send_file(ROOT / "tests/fixtures/isolated_staging_exhibition.html")

    run_simple("127.0.0.1", 443, app, ssl_context=(cert, key), threaded=True)


if __name__ == "__main__":
    serve(*sys.argv[1:])
