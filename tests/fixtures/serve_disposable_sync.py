"""Loopback-only browser fixture for the disposable PostgreSQL Actions service."""
import sys
from pathlib import Path

import psycopg
from flask import send_file, render_template, request, jsonify
from werkzeug.serving import run_simple

from browser_cookie_security import require_same_origin
from browser_session import token_digest
from isolated_versioned_staging_app import create_isolated_staging_app
from messenger_browser_claim import issue_pair, mark_meta_verified
from private_browser_claim_routes import claim_blueprint

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
                "browser-home-owner": ("browser-home-session",),
                "browser-home-mylist-owner": ("browser-home-mylist-session",),
                "browser-discover-recover-owner": ("browser-discover-recover-session",),
                "browser-home-detail-cross-owner": ("browser-home-detail-cross-session",),
            }
            for owner, sessions in owners.items():
                cur.execute("INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                            (owner,))
                for session in sessions:
                    cur.execute("INSERT INTO tan_private.browser_sessions(token_hash,sender_id,expires_at) "
                                "VALUES (%s,%s,now()+interval '10 minutes')",
                                (token_digest(session), owner))
            # No pre-made browser_sessions row -- the connect-devices E2E
            # test's whole point is that the claim flow itself creates one.
            # browser_sessions.sender_id has a foreign key into this table,
            # so claim_browser_session's own INSERT would otherwise fail.
            cur.execute("INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                        ("synthetic-connect-sender",))

    app = create_isolated_staging_app(db_connect=lambda: psycopg.connect(DATABASE),
                                      environment="isolated-staging", canonical_origin=ORIGIN)

    app.config["TAN_ISOLATED_DETAIL_SYNC"] = True

    app.config["TAN_ISOLATED_NEARBY_SYNC"] = True

    app.config["TAN_ISOLATED_DISCOVER_SYNC"] = True

    app.config["TAN_ISOLATED_HOME_SYNC"] = True

    # Private browser-claim handshake, mirroring the real app.py wiring
    # (TAN_CANONICAL_ORIGIN/TAN_PRIVATE_DB_CONNECT already set by
    # create_isolated_staging_app above). An always-permit limiter is fine
    # for this isolated fixture -- private_claim_rate_limit.py's own SQL is
    # already covered by its dedicated unit tests, not re-tested here.
    app.config["TAN_PRIVATE_CLAIM_LIMITER"] = lambda req: True
    app.register_blueprint(claim_blueprint)

    @app.post("/api/private-auth/initiate")
    def actual_private_auth_initiate():
        if not require_same_origin(
            request.method, request.headers.get("Origin"), ORIGIN,
            request.headers.get("Sec-Fetch-Site"),
        ):
            return jsonify(error="forbidden"), 403
        with psycopg.connect(DATABASE) as conn:
            messenger_code, browser_secret = issue_pair(conn)
        response = jsonify(messenger_code=messenger_code, browser_secret=browser_secret)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/actual-mark-verified")
    def actual_mark_verified():
        """Test-only: simulates the signature-verified Meta webhook calling
        mark_meta_verified, without needing a real webhook round-trip."""
        body = request.get_json(silent=True) or {}
        with psycopg.connect(DATABASE) as conn:
            ok = mark_meta_verified(conn, messenger_code=body.get("messenger_code"),
                                    verified_sender_id=body.get("sender_id"))
        return jsonify(ok=ok)

    @app.get("/actual-connect-devices")
    def actual_connect_devices():
        return render_template("connect_devices.html", current_lang=request.args.get("lang", "ja"))

    @app.get("/actual-home")
    def actual_home():
        ex = {"title": "Synthetic Home Exhibition", "stable_key": "home-a",
              "detail_url": "/exhibition?key=home-a", "status": "current", "recently_added": False,
              "type": "exhibition", "days_until_start": None, "days_left": 5,
              "dates": "2026.01.01 - 2026.02.01", "artists": [], "excerpt": "Synthetic excerpt",
              "next_notice": None, "next_event": None}
        museum = {"id": "m1", "name": "Synthetic Museum", "category": "public", "closed_today": False,
                  "has_current": True, "has_upcoming": False, "exhibitions": [ex], "venue_events": [],
                  "lat": 0, "lng": 0, "hours": ""}
        region = {"id": "r1", "name": "Synthetic Region", "museums": [museum]}
        return render_template("index.html", current_lang=request.args.get("lang", "ja"),
            regions=[region], closing_soon=[], todays_events=[], labels={},
            region_names_json="{}", museum_name_to_id_json="{}",
            holiday_today=None, last_updated="2026-01-01")

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
        # ?key= lets a test address the exact same server-side item as
        # another screen's fixture route (e.g. Home's "home-a"), to exercise
        # genuine cross-screen reconnect/conflict behavior in one session --
        # previously only ever tested per-screen. Default preserves every
        # existing single-screen detail test unchanged.
        return render_template("exhibition_detail_page.html",
            current_lang=request.args.get("lang", "ja"), museum_id="synthetic", idx=0,
            structured_data={}, labels={}, other_exhibitions=[],
            exhibition={"title": "Synthetic Art", "stable_key": request.args.get("key", "actual-detail"),
                        "dates": "2026", "days_left": None, "artists": [], "description": "Synthetic exhibition"},
            museum={"name": "Synthetic Museum", "address": "", "url": ""})

    @app.get("/exhibition")
    def exhibition():
        return send_file(ROOT / "tests/fixtures/isolated_staging_exhibition.html")

    run_simple("127.0.0.1", 443, app, ssl_context=(cert, key), threaded=True)


if __name__ == "__main__":
    serve(*sys.argv[1:])
