import unittest
from unittest.mock import patch
from flask import Flask
from subscriber_review_api_routes import review_blueprint


class Connection:
    autocommit = False
    def __init__(self):
        self.rollbacks = 0
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def rollback(self): self.rollbacks += 1


class ReviewHTTPTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, TAN_CANONICAL_ORIGIN="https://example.test")
        self.conn = Connection()
        app.config["TAN_PRIVATE_DB_CONNECT"] = lambda: self.conn
        app.register_blueprint(review_blueprint)
        self.client = app.test_client()
        self.client.set_cookie("__Host-tan_session", "synthetic")
        self.headers = {"Origin": "https://example.test"}
        self.issue = {"choice": "keep_saved", "kind": "favs", "key": "a",
                      "base_revision": 4, "reviewed_item_revision": 3,
                      "local_value": {"title": "A"}}
        self.consume = {"token": "ab" * 32, "local_value": {"title": "A"}}

    def post(self, endpoint, data):
        return self.client.post("/api/private-subscribers/v2/review/keep/" + endpoint,
                                json=data, headers=self.headers)

    def test_issue_uses_session_owner(self):
        with patch("subscriber_review_api_routes._sender_in_transaction",
                   return_value="owner"), patch(
                   "subscriber_review_api_routes.issue_keep_confirmation",
                   return_value="ab" * 32) as issue:
            response = self.post("issue", self.issue)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(issue.call_args.kwargs["verified_sender_id"], "owner")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_consume_uses_session_owner(self):
        with patch("subscriber_review_api_routes._sender_in_transaction",
                   return_value="owner"), patch(
                   "subscriber_review_api_routes.consume_keep_confirmation",
                   return_value={"revision": 5}) as consume:
            response = self.post("consume", self.consume)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(consume.call_args.kwargs["verified_sender_id"], "owner")

    def test_other_choice_rejected(self):
        self.assertEqual(self.post("issue", dict(self.issue, choice="remove_from_list")).status_code, 400)

    def test_sender_injection_rejected(self):
        self.assertEqual(self.post("issue", dict(self.issue, sender_id="victim")).status_code, 400)

    def test_missing_session_denied(self):
        with patch("subscriber_review_api_routes._sender_in_transaction",
                   return_value=None):
            self.assertEqual(self.post("issue", self.issue).status_code, 403)

    def test_cross_origin_denied(self):
        response = self.client.post("/api/private-subscribers/v2/review/keep/issue",
            json=self.issue, headers={"Origin": "https://attacker.test"})
        self.assertEqual(response.status_code, 403)

    def test_autocommit_denied(self):
        self.conn.autocommit = True
        self.assertEqual(self.post("issue", self.issue).status_code, 503)

    def test_stale_conflict_409(self):
        from versioned_subscriber_sync import StaleRevision
        with patch("subscriber_review_api_routes._sender_in_transaction",
                   return_value="owner"), patch(
                   "subscriber_review_api_routes.issue_keep_confirmation",
                   side_effect=StaleRevision()):
            self.assertEqual(self.post("issue", self.issue).status_code, 409)

    def test_replay_token_rejected(self):
        with patch("subscriber_review_api_routes._sender_in_transaction",
                   return_value="owner"), patch(
                   "subscriber_review_api_routes.consume_keep_confirmation",
                   side_effect=ValueError("used")):
            self.assertEqual(self.post("consume", self.consume).status_code, 400)

    def test_query_identity_denied(self):
        response = self.client.post(
            "/api/private-subscribers/v2/review/keep/issue?sender_id=victim",
            json=self.issue, headers=self.headers)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
