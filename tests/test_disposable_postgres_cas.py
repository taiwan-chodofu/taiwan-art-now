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
                cur.execute("CREATE TABLE tan_private.browser_sessions "
                            "(token_hash text primary key, sender_id text not null "
                            "REFERENCES tan_private.messenger_subscribers(sender_id), "
                            "created_at timestamptz not null default now(), "
                            "expires_at timestamptz not null, revoked_at timestamptz)")
                cur.execute("CREATE TABLE tan_private.subscriber_sync_states "
                            "(sender_id text primary key REFERENCES "
                            "tan_private.messenger_subscribers(sender_id), "
                            "state jsonb not null, updated_at timestamptz default now())")
                # Simplified for this plain disposable container: same
                # columns/constraints as the drafts (docs/security/
                # MESSENGER_LINK_SCHEMA_DRAFT.sql, CLAIM_RATE_LIMIT_SCHEMA_
                # DRAFT.sql) minus the Supabase-specific RLS/role statements,
                # which don't apply here (no anon/authenticated roles exist
                # on this container) -- same convention the tables above
                # already use.
                cur.execute("CREATE TABLE tan_private.messenger_link_challenges "
                            "(token_hash text primary key, "
                            "browser_claim_hash text not null unique, "
                            "created_at timestamptz not null default now(), "
                            "expires_at timestamptz not null, "
                            "verified_at timestamptz, consumed_at timestamptz, "
                            "sender_id text)")
                cur.execute("CREATE TABLE tan_private.auth_rate_limits "
                            "(bucket_hash text primary key, "
                            "attempts integer not null, expires_at timestamptz not null)")

    def test_isolated_staging_factory_real_database_ownership_and_revocation(self):
        """The isolated app factory uses real PostgreSQL session ownership."""
        import psycopg
        from browser_cookie_security import COOKIE_NAME
        from browser_session import token_digest
        from isolated_versioned_staging_app import create_isolated_staging_app

        owners=("staging-owner-a", "staging-owner-b")
        tokens=("staging-session-a", "staging-session-b")
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                for owner, token in zip(owners,tokens):
                    cur.execute("INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",(owner,))
                    cur.execute("INSERT INTO tan_private.browser_sessions(token_hash,sender_id,expires_at) "
                                "VALUES (%s,%s,now()+interval '1 hour')",(token_digest(token),owner))
        app=create_isolated_staging_app(db_connect=lambda:psycopg.connect(self.url),
            canonical_origin="https://127.0.0.1",environment="isolated-staging")
        a,b=app.test_client(),app.test_client()
        a.set_cookie(COOKIE_NAME,tokens[0]);b.set_cookie(COOKIE_NAME,tokens[1])
        read="/api/private-subscribers/v2/state"
        write="/api/private-subscribers/v2/changes"
        origin={"Origin":"https://127.0.0.1"}
        saved=a.post(write,json={"base_revision":0,"changes":{
            "favs":{"a-only":{"set":{"title":"A"}}},"visited":{}}},headers=origin)
        self.assertEqual(saved.status_code,200)
        self.assertEqual(saved.json["revision"],1)
        other=b.get(read,headers=origin)
        self.assertEqual(other.status_code,200)
        self.assertEqual(other.json["revision"],0)
        self.assertEqual(other.json["favs"],{})
        self.assertEqual(a.post(write,json={"base_revision":1,"changes":{
            "favs":{},"visited":{}}},headers={"Origin":"https://evil.example"}).status_code,403)
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE tan_private.browser_sessions SET revoked_at=now() "
                            "WHERE token_hash=%s",(token_digest(tokens[0]),))
        self.assertEqual(a.get(read,headers=origin).status_code,403)
        self.assertEqual(a.post(write,json={"base_revision":1,"changes":{
            "favs":{},"visited":{}}},headers=origin).status_code,403)
        self.assertEqual(b.get(read,headers=origin).status_code,200)

    def test_isolated_staging_real_postgres_independent_want_seen_removal(self):
        """Isolated app + authenticated PostgreSQL: removing want retains seen."""
        import psycopg
        from browser_cookie_security import COOKIE_NAME
        from browser_session import token_digest
        from isolated_versioned_staging_app import create_isolated_staging_app

        owner, token = "staging-independent-owner", "staging-independent-session"
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)", (owner,))
                cur.execute("INSERT INTO tan_private.browser_sessions(token_hash,sender_id,expires_at) "
                            "VALUES (%s,%s,now()+interval '1 hour')", (token_digest(token),owner))
        app=create_isolated_staging_app(db_connect=lambda:psycopg.connect(self.url),
            canonical_origin="https://127.0.0.1",environment="isolated-staging")
        with app.test_client() as client:
            client.set_cookie(COOKIE_NAME,token)
            headers={"Origin":"https://127.0.0.1"}
            url="/api/private-subscribers/v2/changes"
            def write(revision, favs, visited):
                return client.post(url, json={"base_revision":revision,
                    "changes":{"favs":favs,"visited":visited}},headers=headers)
            first=write(0,{"art":{"set":{"title":"Art"}}},{})
            self.assertEqual(first.status_code,200)
            second=write(1,{},{"art":{"set":{"date":"2026-11-23"}}})
            self.assertEqual(second.status_code,200)
            removed=write(2,{"art":{"delete":True}},{})
            self.assertEqual(removed.status_code,200)
            self.assertEqual(removed.json["revision"],3)
            self.assertTrue(removed.json["favs"]["art"]["deleted"])
            self.assertFalse(removed.json["visited"]["art"]["deleted"])
            latest=client.get("/api/private-subscribers/v2/state",headers=headers)
            self.assertEqual(latest.status_code,200)
            self.assertEqual(latest.json,removed.json)
            self.assertEqual(latest.headers.get("Cache-Control"),"no-store")

            value = {"title": "Art"}
            self.assertEqual(write(3, {"art": {"set": value}}, {}).status_code, 409)
            issue = "/api/private-subscribers/v2/review/keep/issue"
            consume = "/api/private-subscribers/v2/review/keep/consume"
            choice = {"choice": "keep_saved", "kind": "favs", "key": "art",
                      "base_revision": 3, "reviewed_item_revision": 3, "local_value": value}
            issued = client.post(issue, json=choice, headers=headers)
            self.assertEqual(issued.status_code, 200)
            confirmation = {"token": issued.json["token"], "local_value": value}

            # Restart the isolated entrypoint read-only against the same state.
            frozen = create_isolated_staging_app(db_connect=lambda: psycopg.connect(self.url),
                canonical_origin="https://127.0.0.1", environment="isolated-staging", read_only=True)
            with frozen.test_client() as viewer:
                viewer.set_cookie(COOKIE_NAME, token)
                for path, body in [(url, {"base_revision": 3, "changes": {"favs": {}, "visited": {}}}),
                                   (issue, choice), (consume, confirmation)]:
                    self.assertEqual(viewer.post(path, json=body, headers=headers).status_code, 503)
                self.assertEqual(viewer.get("/api/private-subscribers/v2/state", headers=headers).json,
                                 removed.json)
            restored = client.post(consume, json=confirmation, headers=headers)
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json["revision"], 4)
            self.assertEqual(restored.json["favs"]["art"]["value"], value)
            self.assertEqual(restored.json["visited"], removed.json["visited"])
            self.assertEqual(client.post(consume, json=confirmation, headers=headers).status_code, 400)

    def test_isolated_staging_two_sessions_reject_stale_delete_and_preserve_seen(self):
        """A stale device cannot erase a newer independent seen registration."""
        import psycopg
        from browser_cookie_security import COOKIE_NAME
        from browser_session import token_digest
        from isolated_versioned_staging_app import create_isolated_staging_app

        owner="staging-two-session-owner"
        tokens=("staging-two-session-a","staging-two-session-b")
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",(owner,))
                for token in tokens:
                    cur.execute("INSERT INTO tan_private.browser_sessions(token_hash,sender_id,expires_at) "
                                "VALUES (%s,%s,now()+interval '1 hour')",(token_digest(token),owner))
        app=create_isolated_staging_app(db_connect=lambda:psycopg.connect(self.url),
            canonical_origin="https://127.0.0.1",environment="isolated-staging")
        a,b=app.test_client(),app.test_client()
        a.set_cookie(COOKIE_NAME,tokens[0])
        b.set_cookie(COOKIE_NAME,tokens[1])
        headers={"Origin":"https://127.0.0.1"}
        url="/api/private-subscribers/v2/changes"
        def write(client,revision,favs,visited):
            return client.post(url,json={"base_revision":revision,
                "changes":{"favs":favs,"visited":visited}},headers=headers)
        self.assertEqual(a.get("/api/private-subscribers/v2/state",headers=headers).json["revision"],0)
        self.assertEqual(b.get("/api/private-subscribers/v2/state",headers=headers).json["revision"],0)
        self.assertEqual(write(a,0,{"art":{"set":{"title":"Art"}}},{}).status_code,200)
        self.assertEqual(write(b,0,{},{"art":{"delete":True}}).status_code,409)
        self.assertEqual(write(b,1,{},{"art":{"set":{"date":"2026-11-23"}}}).status_code,200)
        self.assertEqual(write(a,1,{"art":{"delete":True}},{}).status_code,409)
        final=a.get("/api/private-subscribers/v2/state",headers=headers)
        self.assertEqual(final.status_code,200)
        self.assertEqual(final.json["revision"],2)
        self.assertFalse(final.json["favs"]["art"]["deleted"])
        self.assertFalse(final.json["visited"]["art"]["deleted"])

    def test_two_authenticated_clients_stale_cas_then_additive_retry(self):
        """Two cookies for one owner: stale write fails, fresh additive retry preserves both."""
        import psycopg
        from flask import Flask
        from browser_session import token_digest
        from browser_cookie_security import COOKIE_NAME
        from versioned_subscriber_api_routes import versioned_blueprint

        owner="http-two-devices-owner"
        tokens=("http-device-a-token","http-device-b-token")
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                    (owner,))
                for token in tokens:
                    cur.execute(
                        "INSERT INTO tan_private.browser_sessions "
                        "(token_hash,sender_id,expires_at) "
                        "VALUES (%s,%s,now()+interval '1 hour')",
                        (token_digest(token),owner))

        app=Flask(__name__)
        app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                          TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
        app.register_blueprint(versioned_blueprint)
        url="/api/private-subscribers/v2/changes"
        state_url="/api/private-subscribers/v2/state"
        headers={"Origin":"https://example.test"}

        a=app.test_client()
        b=app.test_client()
        a.set_cookie(COOKIE_NAME,tokens[0])
        b.set_cookie(COOKIE_NAME,tokens[1])
        initial_a=a.get(state_url)
        initial_b=b.get(state_url)
        self.assertEqual(initial_a.status_code,200)
        self.assertEqual(initial_b.status_code,200)
        self.assertEqual(initial_a.json["revision"],0)
        self.assertEqual(initial_b.json["revision"],0)

        first=a.post(url,json={"base_revision":0,"changes":{
            "favs":{"device-a-fav":{"set":{"title":"A"}}},"visited":{}}},
            headers=headers)
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json["revision"],1)

        stale=b.post(url,json={"base_revision":0,"changes":{
            "favs":{},"visited":{"device-b-visited":{
                "set":{"date":"2026-11-23T00:00:00.000Z","title":"B"}}}}},
            headers=headers)
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.json,{"error":"stale_revision"})

        refreshed=b.get(state_url)
        self.assertEqual(refreshed.status_code,200)
        self.assertEqual(refreshed.json["revision"],1)
        self.assertEqual(set(refreshed.json["favs"]),{"device-a-fav"})
        retry=b.post(url,json={"base_revision":1,"changes":{
            "favs":{},"visited":{"device-b-visited":{
                "set":{"date":"2026-11-23T00:00:00.000Z","title":"B"}}}}},
            headers=headers)
        self.assertEqual(retry.status_code,200)
        self.assertEqual(retry.json["revision"],2)
        self.assertEqual(set(retry.json["favs"]),{"device-a-fav"})
        self.assertEqual(set(retry.json["visited"]),{"device-b-visited"})
        final_a=a.get(state_url)
        self.assertEqual(final_a.status_code,200)
        self.assertEqual(final_a.json,retry.json)

    def test_authenticated_server_state_survives_uncooperative_legacy_tab_and_tombstone(self):
        """Real HTTP + disposable PostgreSQL: stale local map cannot change CAS state.

        A cached tab can still lose localStorage records. This test proves only
        that its independent local write cannot mutate the authenticated server.
        """
        import psycopg
        from flask import Flask
        from browser_session import token_digest
        from browser_cookie_security import COOKIE_NAME
        from versioned_subscriber_api_routes import versioned_blueprint

        owner, token = "http-stale-legacy-owner", "http-stale-legacy-token"
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                    (owner,))
                cur.execute(
                    "INSERT INTO tan_private.browser_sessions "
                    "(token_hash,sender_id,expires_at) "
                    "VALUES (%s,%s,now()+interval '1 hour')",
                    (token_digest(token),owner))

        app=Flask(__name__)
        app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                          TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
        app.register_blueprint(versioned_blueprint)
        with app.test_client() as client:
            client.set_cookie(COOKIE_NAME,token)
            path="/api/private-subscribers/v2/changes"
            state_path="/api/private-subscribers/v2/state"
            headers={"Origin":"https://example.test"}
            initial=client.get(state_path)
            self.assertEqual(initial.status_code,200)
            self.assertEqual(initial.json["revision"],0)

            local_legacy={"favs":{},"visited":{}}
            stale_copy={"favs":dict(local_legacy["favs"]),"visited":{}}
            saved=client.post(path,json={"base_revision":0,"changes":{
                "favs":{"modern":{"set":{"title":"Modern","museum":"M"}}},
                "visited":{}}},headers=headers)
            self.assertEqual(saved.status_code,200)
            self.assertEqual(saved.json["revision"],1)

            # The old tab replaces a stale localStorage map, bypassing Web Locks.
            local_legacy=stale_copy
            local_legacy["favs"]["old"]={"title":"Old","museum":"M"}
            self.assertNotIn("modern",local_legacy["favs"])
            still_saved=client.get(state_path)
            self.assertEqual(still_saved.status_code,200)
            self.assertIn("modern",still_saved.json["favs"])

            removed=client.post(path,json={"base_revision":1,"changes":{
                "favs":{"modern":{"delete":True}},"visited":{}}},headers=headers)
            self.assertEqual(removed.status_code,200)
            self.assertEqual(removed.json["revision"],2)
            self.assertTrue(removed.json["favs"]["modern"]["deleted"])

            # A stale request must not undo the explicit deletion.
            stale=client.post(path,json={"base_revision":1,"changes":{
                "favs":{"modern":{"set":{"title":"Stale","museum":"M"}}},
                "visited":{}}},headers=headers)
            self.assertEqual(stale.status_code,409)
            final=client.get(state_path)
            self.assertEqual(final.status_code,200)
            self.assertEqual(final.json["revision"],2)
            self.assertTrue(final.json["favs"]["modern"]["deleted"])

    def test_fresh_revision_cannot_silently_resurrect_tombstone(self):
        """Even after GET of latest revision, ordinary save cannot undo deletion."""
        import psycopg
        from flask import Flask
        from browser_session import token_digest
        from browser_cookie_security import COOKIE_NAME
        from versioned_subscriber_api_routes import versioned_blueprint

        owner, token = "http-tombstone-guard-owner", "http-tombstone-guard-token"
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                    (owner,))
                cur.execute(
                    "INSERT INTO tan_private.browser_sessions "
                    "(token_hash,sender_id,expires_at) "
                    "VALUES (%s,%s,now()+interval '1 hour')",
                    (token_digest(token),owner))

        app=Flask(__name__)
        app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                          TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
        app.register_blueprint(versioned_blueprint)
        with app.test_client() as client:
            client.set_cookie(COOKIE_NAME,token)
            path="/api/private-subscribers/v2/changes"
            state_path="/api/private-subscribers/v2/state"
            headers={"Origin":"https://example.test"}
            added=client.post(path,json={"base_revision":0,"changes":{
                "favs":{"exhibit":{"set":{"title":"Exhibit"}}},"visited":{}}},
                headers=headers)
            self.assertEqual(added.status_code,200)
            deleted=client.post(path,json={"base_revision":1,"changes":{
                "favs":{"exhibit":{"delete":True}},"visited":{}}},
                headers=headers)
            self.assertEqual(deleted.status_code,200)
            latest=client.get(state_path)
            self.assertEqual(latest.status_code,200)
            self.assertEqual(latest.json["revision"],2)
            self.assertTrue(latest.json["favs"]["exhibit"]["deleted"])

            # This is NOT a stale revision: explicit deletion still wins.
            resurrect=client.post(path,json={"base_revision":2,"changes":{
                "favs":{"exhibit":{"set":{"title":"Old cached value"}}},
                "visited":{}}},headers=headers)
            self.assertEqual(resurrect.status_code,409)
            final=client.get(state_path)
            self.assertEqual(final.status_code,200)
            self.assertEqual(final.json,latest.json)

    def test_two_authenticated_owners_cannot_read_or_modify_each_other(self):
        """Separate session cookies isolate GET and POST by verified DB owner."""
        import psycopg
        from flask import Flask
        from browser_session import token_digest
        from browser_cookie_security import COOKIE_NAME
        from versioned_subscriber_api_routes import versioned_blueprint

        owners=(("isolation-owner-a","isolation-token-a"),
                ("isolation-owner-b","isolation-token-b"))
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                for owner,token in owners:
                    cur.execute(
                        "INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                        (owner,))
                    cur.execute(
                        "INSERT INTO tan_private.browser_sessions "
                        "(token_hash,sender_id,expires_at) "
                        "VALUES (%s,%s,now()+interval '1 hour')",
                        (token_digest(token),owner))
        app=Flask(__name__)
        app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                          TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
        app.register_blueprint(versioned_blueprint)
        a,b=app.test_client(),app.test_client()
        a.set_cookie(COOKIE_NAME,owners[0][1])
        b.set_cookie(COOKIE_NAME,owners[1][1])
        path="/api/private-subscribers/v2/changes"
        state_path="/api/private-subscribers/v2/state"
        headers={"Origin":"https://example.test"}
        saved=a.post(path,json={"base_revision":0,"changes":{
            "favs":{"private-a":{"set":{"title":"Only A"}}},"visited":{}}},
            headers=headers)
        self.assertEqual(saved.status_code,200)
        b_state=b.get(state_path)
        self.assertEqual(b_state.status_code,200)
        self.assertEqual(b_state.json,{"revision":0,"favs":{},"visited":{}})
        b_saved=b.post(path,json={"base_revision":0,"changes":{
            "favs":{"private-b":{"set":{"title":"Only B"}}},"visited":{}}},
            headers=headers)
        self.assertEqual(b_saved.status_code,200)
        a_state=a.get(state_path)
        self.assertEqual(a_state.status_code,200)
        self.assertEqual(set(a_state.json["favs"]),{"private-a"})
        self.assertEqual(set(b.get(state_path).json["favs"]),{"private-b"})
        # An unauthenticated request cannot choose another owner's identity.
        anonymous=app.test_client()
        denied=anonymous.get(state_path)
        self.assertEqual(denied.status_code,403)
        denied_write=anonymous.post(path,json={"base_revision":1,"changes":{
            "favs":{"private-a":{"delete":True}},"visited":{}}},
            headers=headers)
        self.assertEqual(denied_write.status_code,403)
        self.assertEqual(set(a.get(state_path).json["favs"]),{"private-a"})

        # Identical exhibition keys are scoped independently to each owner.
        same_a=a.post(path,json={"base_revision":1,"changes":{
            "favs":{"shared-key":{"set":{"title":"A's private version"}}},
            "visited":{}}},headers=headers)
        same_b=b.post(path,json={"base_revision":1,"changes":{
            "favs":{"shared-key":{"set":{"title":"B's private version"}}},
            "visited":{}}},headers=headers)
        self.assertEqual(same_a.status_code,200)
        self.assertEqual(same_b.status_code,200)
        self.assertEqual(
            a.get(state_path).json["favs"]["shared-key"]["value"]["title"],
            "A's private version")
        self.assertEqual(
            b.get(state_path).json["favs"]["shared-key"]["value"]["title"],
            "B's private version")

        # A malicious origin cannot mutate even the authenticated owner's data.
        rejected=a.post(path,json={"base_revision":2,"changes":{
            "favs":{"shared-key":{"delete":True}},"visited":{}}},
            headers={"Origin":"https://evil.example"})
        self.assertEqual(rejected.status_code,403)
        self.assertFalse(a.get(state_path).json["favs"]["shared-key"]["deleted"])
        # Query-supplied identity cannot select another owner.
        self.assertEqual(a.get(state_path+"?sender_id="+owners[1][0]).status_code,400)

    def test_inflight_write_serializes_with_session_revocation(self):
        """A session lock covers a CAS write; post-revocation writes are denied."""
        import psycopg
        from flask import Flask
        from browser_session import token_digest
        from browser_cookie_security import COOKIE_NAME
        from versioned_subscriber_api_routes import versioned_blueprint
        from unittest.mock import patch

        owner,token="http-write-race-owner","http-write-race-token"
        digest=token_digest(token)
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                    (owner,))
                cur.execute(
                    "INSERT INTO tan_private.browser_sessions "
                    "(token_hash,sender_id,expires_at) "
                    "VALUES (%s,%s,now()+interval '1 hour')",(digest,owner))

        entered_write=threading.Event()
        release_write=threading.Event()
        revocation_started=threading.Event()
        revocation_finished=threading.Event()
        results={}
        original_update=update_for_verified_sender
        payload={"base_revision":0,"changes":{
            "favs":{"write-race-item":{"set":{"title":"Authenticated write"}}},
            "visited":{}}}

        def paused_update(conn, *, verified_sender_id, base_revision, changes):
            entered_write.set()
            if not release_write.wait(timeout=10):
                raise RuntimeError("Timed out waiting for test write release")
            return original_update(
                conn,verified_sender_id=verified_sender_id,
                base_revision=base_revision,changes=changes)

        def make_app():
            app=Flask(__name__)
            app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                              TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
            app.register_blueprint(versioned_blueprint)
            return app

        def write_request():
            with make_app().test_client() as client:
                client.set_cookie(COOKIE_NAME,token)
                with patch("versioned_subscriber_api_routes.update_for_verified_sender",
                           side_effect=paused_update):
                    response=client.post("/api/private-subscribers/v2/changes",
                                         json=payload,
                                         headers={"Origin":"https://example.test"})
                    results["first_status"]=response.status_code
                    results["first_body"]=response.json

        def revoke():
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    revocation_started.set()
                    cur.execute(
                        "UPDATE tan_private.browser_sessions SET revoked_at=now() "
                        "WHERE token_hash=%s",(digest,))
                conn.commit()
            revocation_finished.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            writer=pool.submit(write_request)
            try:
                self.assertTrue(entered_write.wait(timeout=10))
                revoker=pool.submit(revoke)
                self.assertTrue(revocation_started.wait(timeout=10))
                self.assertFalse(
                    revocation_finished.wait(timeout=0.25),
                    "Revocation must wait for in-flight authenticated CAS")
            finally:
                release_write.set()
            writer.result(timeout=10)
            revoker.result(timeout=10)

        self.assertEqual(results["first_status"],200)
        self.assertEqual(results["first_body"]["revision"],1)
        self.assertTrue(revocation_finished.is_set())
        with psycopg.connect(self.url) as conn:
            state=read_for_verified_sender(conn,verified_sender_id=owner)
        self.assertEqual(set(state["favs"]),{"write-race-item"})

        with make_app().test_client() as client:
            client.set_cookie(COOKIE_NAME,token)
            denied=client.post(
                "/api/private-subscribers/v2/changes",
                json={"base_revision":1,"changes":{
                    "favs":{"post-revoke-item":{"set":{"title":"Denied"}}},
                    "visited":{}}},
                headers={"Origin":"https://example.test"})
            self.assertEqual(denied.status_code,403)
        with psycopg.connect(self.url) as conn:
            after=read_for_verified_sender(conn,verified_sender_id=owner)
        self.assertEqual(after,state)

    def test_inflight_revocation_waits_for_authenticated_read_transaction(self):
        """Session row lock prevents revocation overtaking an in-flight GET."""
        import psycopg
        from flask import Flask
        from browser_session import token_digest
        from browser_cookie_security import COOKIE_NAME
        from versioned_subscriber_api_routes import versioned_blueprint
        from unittest.mock import patch

        owner, token = "http-race-owner", "http-race-token"
        digest = token_digest(token)
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)",
                    (owner,))
                cur.execute(
                    "INSERT INTO tan_private.browser_sessions "
                    "(token_hash,sender_id,expires_at) "
                    "VALUES (%s,%s,now()+interval '1 hour')", (digest,owner))
            update_for_verified_sender(
                conn,verified_sender_id=owner,base_revision=0,
                changes={"favs":{"race-private":{"set":{"title":"Race"}}},
                         "visited":{}})

        entered_read=threading.Event()
        release_read=threading.Event()
        revocation_started=threading.Event()
        revocation_finished=threading.Event()
        original_read=read_for_verified_sender
        results={}

        def blocked_read(conn, *, verified_sender_id):
            entered_read.set()
            if not release_read.wait(timeout=10):
                raise RuntimeError("Timed out waiting to release synthetic GET")
            return original_read(conn,verified_sender_id=verified_sender_id)

        def get_request():
            app=Flask(__name__)
            app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                              TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
            app.register_blueprint(versioned_blueprint)
            with app.test_client() as client:
                client.set_cookie(COOKIE_NAME,token)
                with patch("versioned_subscriber_api_routes.read_for_verified_sender",
                           side_effect=blocked_read):
                    response=client.get("/api/private-subscribers/v2/state")
                    results["get_status"]=response.status_code
                    results["get_favs"]=response.json.get("favs",{})

        def revoke():
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    revocation_started.set()
                    cur.execute(
                        "UPDATE tan_private.browser_sessions SET revoked_at=now() "
                        "WHERE token_hash=%s", (digest,))
                conn.commit()
            revocation_finished.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            getter=pool.submit(get_request)
            try:
                self.assertTrue(entered_read.wait(timeout=10))
                revoker=pool.submit(revoke)
                self.assertTrue(revocation_started.wait(timeout=10))
                self.assertFalse(
                    revocation_finished.wait(timeout=0.25),
                    "Revocation must wait for session FOR UPDATE lock")
            finally:
                release_read.set()
            getter.result(timeout=10)
            revoker.result(timeout=10)

        self.assertEqual(results["get_status"],200)
        self.assertEqual(set(results["get_favs"]),{"race-private"})
        self.assertTrue(revocation_finished.is_set())

        app=Flask(__name__)
        app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                          TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
        app.register_blueprint(versioned_blueprint)
        with app.test_client() as client:
            client.set_cookie(COOKIE_NAME,token)
            self.assertEqual(
                client.get("/api/private-subscribers/v2/state").status_code,403)

    def test_flask_cookie_session_real_postgres_isolation_and_revocation(self):
        """HTTP cookie lookup and private state read use real disposable DB."""
        import psycopg
        from flask import Flask
        from browser_session import token_digest
        from browser_cookie_security import COOKIE_NAME
        from versioned_subscriber_api_routes import versioned_blueprint

        owner_a, owner_b = "http-synthetic-owner-a", "http-synthetic-owner-b"
        token_a, token_b = "http-synthetic-token-a", "http-synthetic-token-b"
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tan_private.messenger_subscribers(sender_id) "
                    "VALUES (%s), (%s)", (owner_a, owner_b))
                cur.execute(
                    "INSERT INTO tan_private.browser_sessions "
                    "(token_hash,sender_id,expires_at) "
                    "VALUES (%s,%s,now()+interval '1 hour'), "
                    "(%s,%s,now()+interval '1 hour')",
                    (token_digest(token_a),owner_a,token_digest(token_b),owner_b))
            update_for_verified_sender(
                conn,verified_sender_id=owner_a,base_revision=0,
                changes={"favs":{"http-only-a":{"set":{"title":"Private A"}}},
                         "visited":{}})
            update_for_verified_sender(
                conn,verified_sender_id=owner_b,base_revision=0,
                changes={"favs":{"http-only-b":{"set":{"title":"Private B"}}},
                         "visited":{}})

        app=Flask(__name__)
        app.config.update(TESTING=True,TAN_CANONICAL_ORIGIN="https://example.test",
                          TAN_PRIVATE_DB_CONNECT=lambda:psycopg.connect(self.url))
        app.register_blueprint(versioned_blueprint)
        client=app.test_client()

        client.set_cookie(COOKIE_NAME,token_a)
        first=client.get("/api/private-subscribers/v2/state")
        self.assertEqual(first.status_code,200)
        self.assertEqual(set(first.json["favs"]),{"http-only-a"})
        self.assertEqual(first.headers["Cache-Control"],"no-store")

        client.set_cookie(COOKIE_NAME,token_b)
        second=client.get("/api/private-subscribers/v2/state")
        self.assertEqual(second.status_code,200)
        self.assertEqual(set(second.json["favs"]),{"http-only-b"})

        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tan_private.browser_sessions SET revoked_at=now() "
                    "WHERE token_hash=%s",(token_digest(token_a),))
        client.set_cookie(COOKIE_NAME,token_a)
        denied=client.get("/api/private-subscribers/v2/state")
        self.assertEqual(denied.status_code,403)

        client.set_cookie(COOKIE_NAME,token_b)
        still_allowed=client.get("/api/private-subscribers/v2/state")
        self.assertEqual(still_allowed.status_code,200)
        self.assertEqual(set(still_allowed.json["favs"]),{"http-only-b"})

        client.set_cookie(COOKIE_NAME,"unknown-token")
        self.assertEqual(client.get("/api/private-subscribers/v2/state").status_code,403)

    def test_two_verified_owners_are_strictly_isolated(self):
        """No sender can read or mutate another sender's state via the store."""
        import psycopg
        second = "synthetic-second-owner"
        with psycopg.connect(self.url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tan_private.messenger_subscribers (sender_id) "
                    "VALUES (%s) ON CONFLICT DO NOTHING", (second,))
            first_before = read_for_verified_sender(
                conn, verified_sender_id="synthetic-owner")
            second_before = read_for_verified_sender(
                conn, verified_sender_id=second)
            self.assertNotIn("owner-one-private", second_before["favs"])
            first_after = update_for_verified_sender(
                conn, verified_sender_id="synthetic-owner",
                base_revision=first_before["revision"],
                changes={"favs": {"owner-one-private": {
                    "set": {"title": "Private owner one"}}}, "visited": {}})
            second_after = update_for_verified_sender(
                conn, verified_sender_id=second,
                base_revision=second_before["revision"],
                changes={"favs": {"owner-two-private": {
                    "set": {"title": "Private owner two"}}}, "visited": {}})
            self.assertIn("owner-one-private", first_after["favs"])
            self.assertNotIn("owner-two-private", first_after["favs"])
            self.assertIn("owner-two-private", second_after["favs"])
            self.assertNotIn("owner-one-private", second_after["favs"])
        with psycopg.connect(self.url) as conn:
            first = read_for_verified_sender(
                conn, verified_sender_id="synthetic-owner")
            second_state = read_for_verified_sender(
                conn, verified_sender_id=second)
            self.assertNotIn("owner-two-private", first["favs"])
            self.assertNotIn("owner-one-private", second_state["favs"])
            self.assertEqual(second_state["revision"], 1)

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
            issue_keep_confirmation, consume_keep_confirmation, _digest)
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
                            "WHERE token_hash=%s AND used_at IS NOT NULL", (_digest(token),))
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
