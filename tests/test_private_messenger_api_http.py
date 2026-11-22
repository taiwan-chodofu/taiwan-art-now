"""Synthetic Flask tests for isolated authenticated Messenger API."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from flask import Flask
from private_messenger_api_routes import messenger_blueprint

ORIGIN = "https://taiwan-art-now.onrender.com"


class FakeConn:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


class FakeStore:
    def __init__(self):
        self.data = {"users": {
            "owner": {"favs": {}, "visited": {}, "weekly_digest": True},
            "victim": {"favs": {"secret": True}, "visited": {}, "weekly_digest": True},
        }, "refs": {"victim-ref": "victim"}}
        self.writes = 0

    def load_messenger(self):
        return deepcopy(self.data)

    def mutate_messenger(self, fn):
        state = deepcopy(self.data)
        fn(state)
        self.data = state
        self.writes += 1


class MessengerHTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TAN_CANONICAL_ORIGIN"] = ORIGIN
        self.app.config["TAN_PRIVATE_DB_CONNECT"] = lambda: FakeConn()
        self.store = FakeStore()
        self.app.config["TAN_PRIVATE_MESSENGER_STORE"] = self.store
        self.app.register_blueprint(messenger_blueprint)
        self.client = self.app.test_client()
        self.client.set_cookie("__Host-tan_session", "synthetic-session")
        self.mock = patch("private_messenger_operations.resolve_sender",
                          return_value="owner")
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def post(self, action, body, origin=ORIGIN):
        return self.client.post("/api/private-subscribers/" + action,
                                json=body, headers={"Origin": origin})

    def test_status_only_owner_settings(self):
        r = self.client.get("/api/private-subscribers/status")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json["subscribed"])
        self.assertNotIn("users", r.json)
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_status_rejects_legacy_sender_query(self):
        r = self.client.get("/api/private-subscribers/status?sender_id=victim")
        self.assertEqual(r.status_code, 400)

    def test_sync_preserves_other_user(self):
        before = deepcopy(self.store.data["users"]["victim"])
        r = self.post("sync", {"favs": {"new": True}, "visited": {}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.store.data["users"]["victim"], before)
        self.assertEqual(self.store.writes, 1)

    def test_settings_only_owner(self):
        r = self.post("settings", {"weekly_digest": False})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(self.store.data["users"]["owner"]["weekly_digest"])
        self.assertTrue(self.store.data["users"]["victim"]["weekly_digest"])

    def test_unsubscribe_preserves_victim_and_ref(self):
        r = self.post("unsubscribe", {})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("owner", self.store.data["users"])
        self.assertEqual(self.store.data["refs"]["victim-ref"], "victim")

    def test_cross_user_id_rejected(self):
        r = self.post("sync", {"sender_id": "victim",
                               "favs": {}, "visited": {}})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.store.writes, 0)

    def test_ref_only_unsubscribe_rejected(self):
        r = self.post("unsubscribe", {"ref": "victim-ref"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.store.writes, 0)

    def test_missing_session_rejected(self):
        self.client.delete_cookie("__Host-tan_session")
        r = self.post("settings", {"weekly_digest": False})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.store.writes, 0)

    def test_cross_origin_rejected(self):
        r = self.post("settings", {"weekly_digest": False},
                      origin="https://evil.example")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.store.writes, 0)

    def test_invalid_json_rejected(self):
        r = self.client.post("/api/private-subscribers/sync",
                             data="bad", headers={"Origin": ORIGIN})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.store.writes, 0)

    def test_db_outage_fails_closed(self):
        self.app.config["TAN_PRIVATE_DB_CONNECT"] = lambda: (_ for _ in ()).throw(
            RuntimeError("synthetic outage"))
        r = self.post("settings", {"weekly_digest": False})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.store.writes, 0)

    def test_store_outage_fails_closed(self):
        def fail(fn):
            raise RuntimeError("synthetic outage")
        self.store.mutate_messenger = fail
        r = self.post("settings", {"weekly_digest": False})
        self.assertEqual(r.status_code, 503)


if __name__ == "__main__":
    unittest.main()
