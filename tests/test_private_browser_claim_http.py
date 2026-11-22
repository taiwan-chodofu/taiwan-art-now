"""Synthetic HTTP tests of isolated browser-claim blueprint (not app.py)."""
import unittest
from unittest.mock import patch
from flask import Flask
from private_browser_claim_routes import claim_blueprint

ORIGIN = "https://taiwan-art-now.onrender.com"
BODY = {"messenger_code": "synthetic-code", "browser_secret": "synthetic-secret"}


class FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ClaimHTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TAN_CANONICAL_ORIGIN"] = ORIGIN
        self.app.config["TAN_PRIVATE_DB_CONNECT"] = lambda: FakeConn()
        self.app.config["TAN_PRIVATE_CLAIM_LIMITER"] = lambda req: True
        self.app.register_blueprint(claim_blueprint)
        self.client = self.app.test_client()

    def post(self, origin=ORIGIN, body=BODY, **kwargs):
        headers = {"Origin": origin, "Sec-Fetch-Site": "same-origin"}
        headers.update(kwargs.pop("headers", {}))
        return self.client.post("/api/private-auth/claim",
                                json=body, headers=headers, **kwargs)

    def test_verified_claim_sets_secure_cookie(self):
        with patch("private_browser_claim_routes.claim_browser_session",
                   return_value="synthetic-session"):
            result = self.post()
        self.assertEqual(result.status_code, 200)
        cookie = result.headers["Set-Cookie"]
        for flag in ("__Host-tan_session=", "Secure", "HttpOnly",
                     "SameSite=Lax", "Path=/"):
            self.assertIn(flag, cookie)
        self.assertNotIn("synthetic-session", result.get_data(as_text=True))

    def test_unverified_does_not_set_cookie(self):
        with patch("private_browser_claim_routes.claim_browser_session",
                   return_value=None):
            result = self.post()
        self.assertEqual(result.status_code, 403)
        self.assertNotIn("Set-Cookie", result.headers)

    def test_wrong_origin_rejected_before_db(self):
        with patch("private_browser_claim_routes.claim_browser_session") as claim:
            result = self.post(origin="https://evil.example")
        self.assertEqual(result.status_code, 403)
        claim.assert_not_called()

    def test_missing_origin_rejected(self):
        result = self.client.post("/api/private-auth/claim", json=BODY)
        self.assertEqual(result.status_code, 403)

    def test_cross_site_fetch_metadata_rejected(self):
        result = self.post(headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(result.status_code, 403)

    def test_malformed_payload_rejected(self):
        for body in ({}, {"messenger_code": "a"}, [], {"messenger_code": 3,
                     "browser_secret": "x"}, {**BODY, "sender_id": "attacker"}):
            with self.subTest(body=body):
                self.assertEqual(self.post(body=body).status_code, 400)

    def test_database_failure_fails_closed(self):
        with patch("private_browser_claim_routes.claim_browser_session",
                   side_effect=RuntimeError("synthetic outage")):
            result = self.post()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("Set-Cookie", result.headers)

    def test_missing_connector_fails_closed(self):
        self.app.config.pop("TAN_PRIVATE_DB_CONNECT")
        result = self.post()
        self.assertEqual(result.status_code, 503)

    def test_missing_limiter_fails_closed(self):
        self.app.config.pop("TAN_PRIVATE_CLAIM_LIMITER")
        result = self.post()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("Set-Cookie", result.headers)

    def test_limiter_denies_before_claim(self):
        self.app.config["TAN_PRIVATE_CLAIM_LIMITER"] = lambda req: False
        with patch("private_browser_claim_routes.claim_browser_session") as claim:
            result = self.post()
        self.assertEqual(result.status_code, 429)
        claim.assert_not_called()

    def test_limiter_outage_fails_closed(self):
        def outage(req):
            raise RuntimeError("synthetic limiter outage")
        self.app.config["TAN_PRIVATE_CLAIM_LIMITER"] = outage
        result = self.post()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("Set-Cookie", result.headers)

    def test_non_json_rejected(self):
        result = self.client.post("/api/private-auth/claim",
                                  data="synthetic", headers={"Origin": ORIGIN})
        self.assertEqual(result.status_code, 400)


if __name__ == "__main__":
    unittest.main()
