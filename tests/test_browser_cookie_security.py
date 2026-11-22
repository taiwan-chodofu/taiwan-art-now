"""Synthetic Flask response tests for cookie flags and CSRF origin guards."""
import unittest
from flask import Flask, make_response
from browser_cookie_security import (
    COOKIE_NAME, require_same_origin, set_session_cookie, clear_session_cookie,
)


class CookieSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_cookie_security_flags(self):
        with self.app.app_context():
            response = set_session_cookie(make_response("ok"), "synthetic-session")
        cookie = response.headers["Set-Cookie"]
        self.assertIn(COOKIE_NAME + "=", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Path=/", cookie)
        self.assertNotIn("Domain=", cookie)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_clear_cookie(self):
        with self.app.app_context():
            response = clear_session_cookie(make_response("ok"))
        self.assertIn(COOKIE_NAME + "=", response.headers["Set-Cookie"])
        self.assertIn("Expires=", response.headers["Set-Cookie"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_same_origin_post_allowed(self):
        self.assertTrue(require_same_origin(
            "POST", "https://taiwan-art-now.onrender.com",
            "https://taiwan-art-now.onrender.com", "same-origin"))

    def test_cross_origin_rejected(self):
        self.assertFalse(require_same_origin(
            "POST", "https://evil.example",
            "https://taiwan-art-now.onrender.com", "cross-site"))

    def test_missing_origin_rejected(self):
        self.assertFalse(require_same_origin(
            "POST", None, "https://taiwan-art-now.onrender.com"))

    def test_malformed_origin_rejected(self):
        for origin in ("http://taiwan-art-now.onrender.com",
                       "https://taiwan-art-now.onrender.com.evil.example",
                       "https://taiwan-art-now.onrender.com/path",
                       "https://taiwan-art-now.onrender.com@evil.example"):
            with self.subTest(origin=origin):
                self.assertFalse(require_same_origin(
                    "DELETE", origin, "https://taiwan-art-now.onrender.com"))

    def test_cross_site_fetch_metadata_rejected(self):
        self.assertFalse(require_same_origin(
            "PATCH", "https://taiwan-art-now.onrender.com",
            "https://taiwan-art-now.onrender.com", "cross-site"))

    def test_safe_method_does_not_require_origin(self):
        self.assertTrue(require_same_origin(
            "GET", None, "https://taiwan-art-now.onrender.com"))

    def test_invalid_cookie_token_rejected(self):
        with self.app.app_context():
            for token in ("", "bad;cookie", "bad\nheader"):
                with self.subTest(token=token), self.assertRaises(ValueError):
                    set_session_cookie(make_response("ok"), token)

    def test_invalid_cookie_lifetime_rejected(self):
        with self.app.app_context():
            for ttl in (0, True, 86401):
                with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                    set_session_cookie(make_response("ok"), "synthetic", max_age=ttl)


if __name__ == "__main__":
    unittest.main()
