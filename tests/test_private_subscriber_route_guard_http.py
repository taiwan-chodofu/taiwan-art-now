"""Synthetic HTTP tests of isolated guard; no production app registration."""
import unittest
from unittest.mock import patch
from flask import Flask, request
from private_subscriber_route_guard import protected_subscriber_route

ORIGIN = "https://taiwan-art-now.onrender.com"


class FakeConn:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


class RouteGuardHTTPTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TAN_CANONICAL_ORIGIN"] = ORIGIN
        app.config["TAN_PRIVATE_DB_CONNECT"] = lambda: FakeConn()
        self.calls = []
        calls = self.calls

        @app.post("/api/subscribers/settings")
        @protected_subscriber_route("/api/subscribers/settings")
        def settings():
            calls.append(request.environ["tan.verified_sender"])
            return {"ok": True}

        @app.post("/api/subscribers/unsubscribe")
        @protected_subscriber_route("/api/subscribers/unsubscribe")
        def unsubscribe():
            calls.append("unsubscribe")
            return {"ok": True}

        @app.get("/api/subscribers/status")
        @protected_subscriber_route("/api/subscribers/status")
        def status():
            calls.append("status")
            return {"ok": True}

        @app.post("/api/push/sync-favs")
        @protected_subscriber_route("/api/push/sync-favs")
        def push():
            calls.append("push")
            return {"ok": True}

        self.client = app.test_client()
        self.client.set_cookie("__Host-tan_session", "synthetic-token")

    def post(self, path="/api/subscribers/settings", data=None, origin=ORIGIN):
        return self.client.post(path, json=data or {"sender_id": "owner"},
                                headers={"Origin": origin})

    def test_owner_allowed(self):
        with patch("private_subscriber_route_guard.authenticated_messenger_sender",
                   return_value="owner"):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, ["owner"])

    def test_other_user_denied_before_handler(self):
        with patch("private_subscriber_route_guard.authenticated_messenger_sender",
                   return_value="owner"):
            response = self.post(data={"sender_id": "victim"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_no_cookie_denied(self):
        self.client.delete_cookie("__Host-tan_session")
        with patch("private_subscriber_route_guard.authenticated_messenger_sender",
                   side_effect=__import__("subscriber_ownership").AuthorizationDenied()):
            response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_ref_only_unsubscribe_denied(self):
        with patch("private_subscriber_route_guard.authenticated_messenger_sender",
                   return_value="owner"):
            response = self.post("/api/subscribers/unsubscribe",
                                 {"ref": "victim-ref"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_ref_with_sender_also_denied(self):
        with patch("private_subscriber_route_guard.authenticated_messenger_sender",
                   return_value="owner"):
            response = self.post(data={"sender_id": "owner", "ref": "victim-ref"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_unscoped_status_denied(self):
        with patch("private_subscriber_route_guard.authenticated_messenger_sender",
                   return_value="owner"):
            response = self.client.get("/api/subscribers/status")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_push_blocked_without_endpoint_proof(self):
        response = self.post("/api/push/sync-favs",
                             {"endpoint": "victim-endpoint"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_cross_origin_rejected(self):
        response = self.post(origin="https://evil.example")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_db_failure_rejected(self):
        with patch("private_subscriber_route_guard.authenticated_messenger_sender",
                   side_effect=RuntimeError("synthetic outage")):
            response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
