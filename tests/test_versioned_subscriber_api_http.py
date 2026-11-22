"""Synthetic HTTP tests: session-owned v2 and stale revision 409."""
import unittest
from unittest.mock import patch
from flask import Flask
from versioned_subscriber_api_routes import versioned_blueprint
from versioned_subscriber_sync import StaleRevision


class Cursor:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.db.query = sql
        self.db.params = params

    def fetchone(self):
        if "subscriber_sync_states" in self.db.query:
            return (self.db.state,) if self.db.state is not None else None
        return (self.db.sender,) if self.db.sender else None


class Connection:
    def __init__(self, sender="owner"):
        self.sender = sender
        self.commits = 0
        self.rollbacks = 0
        self.query = None
        self.state = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class VersionedHTTPTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["TAN_CANONICAL_ORIGIN"] = "https://example.test"
        self.db = Connection()
        app.config["TAN_PRIVATE_DB_CONNECT"] = lambda: self.db
        app.register_blueprint(versioned_blueprint)
        self.client = app.test_client()
        self.client.set_cookie("__Host-tan_session", "synthetic-token")
        self.headers = {"Origin": "https://example.test"}
        self.payload = {"base_revision": 1,
                        "changes": {"favs": {"a": {"delete": True}}, "visited": {}}}

    def test_autocommit_rejected_before_session_lookup(self):
        self.db.autocommit = True
        response = self.client.post("/api/private-subscribers/v2/changes",
                                    json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(self.db.query)

    def test_generic_api_cannot_resurrect_tombstone(self):
        self.db.state = {"revision": 1, "favs": {"a": {
            "value": None, "deleted": True, "revision": 1}}, "visited": {}}
        payload = {"base_revision": 1, "changes": {
            "favs": {"a": {"set": {"title": "Stale"}}}, "visited": {}}}
        with patch("versioned_subscriber_api_routes.update_for_verified_sender") as update:
            response = self.client.post("/api/private-subscribers/v2/changes",
                                        json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        update.assert_not_called()

    def test_generic_api_allows_non_tombstone_addition(self):
        payload = {"base_revision": 0, "changes": {
            "favs": {"new": {"set": {"title": "New"}}}, "visited": {}}}
        with patch("versioned_subscriber_api_routes.update_for_verified_sender",
                   return_value={"revision": 1}) as update:
            response = self.client.post("/api/private-subscribers/v2/changes",
                                        json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        update.assert_called_once()

    def test_stale_revision_is_409(self):
        with patch("versioned_subscriber_api_routes.update_for_verified_sender",
                   side_effect=StaleRevision("stale")):
            response = self.client.post("/api/private-subscribers/v2/changes",
                                        json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json, {"error": "stale_revision"})

    def test_verified_owner_only_passed_to_store(self):
        with patch("versioned_subscriber_api_routes.update_for_verified_sender",
                   return_value={"revision": 2}) as update:
            response = self.client.post("/api/private-subscribers/v2/changes",
                                        json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(update.call_args.kwargs["verified_sender_id"], "owner")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("FOR UPDATE", self.db.query)

    def test_browser_sender_id_rejected(self):
        payload = dict(self.payload, sender_id="victim")
        response = self.client.post("/api/private-subscribers/v2/changes",
                                    json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_missing_session_is_403(self):
        self.client.delete_cookie("__Host-tan_session")
        response = self.client.post("/api/private-subscribers/v2/changes",
                                    json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 403)

    def test_revoked_session_is_403(self):
        self.db.sender = None
        response = self.client.post("/api/private-subscribers/v2/changes",
                                    json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.db.rollbacks, 1)

    def test_cross_origin_is_403(self):
        response = self.client.post("/api/private-subscribers/v2/changes",
                                    json=self.payload,
                                    headers={"Origin": "https://attacker.test"})
        self.assertEqual(response.status_code, 403)

    def test_read_uses_cookie_owner(self):
        with patch("versioned_subscriber_api_routes.read_for_verified_sender",
                   return_value={"revision": 3}) as read:
            response = self.client.get("/api/private-subscribers/v2/state")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(read.call_args.kwargs["verified_sender_id"], "owner")
        self.assertEqual(self.db.commits, 1)

    def test_read_rejects_sender_query(self):
        response = self.client.get("/api/private-subscribers/v2/state?sender_id=victim")
        self.assertEqual(response.status_code, 400)

    def test_unavailable_database_is_503(self):
        self.db.sender = "owner"
        with patch("versioned_subscriber_api_routes.update_for_verified_sender",
                   side_effect=RuntimeError("synthetic outage")):
            response = self.client.post("/api/private-subscribers/v2/changes",
                                        json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 503)

    def test_invalid_revision_is_400(self):
        with patch("versioned_subscriber_api_routes.update_for_verified_sender",
                   side_effect=ValueError("invalid")):
            response = self.client.post("/api/private-subscribers/v2/changes",
                                        json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
