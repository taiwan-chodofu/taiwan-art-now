"""Unit tests for the *actual* _try_mark_meta_verified helper in app.py.

Isolates only this function's AST (same technique as test_flask_webhook_http.py)
so these tests exercise the real bridge logic without importing the scraper-
dependent parts of app.py, and without a live database.
"""
import ast
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "_try_mark_meta_verified")
code = compile(ast.Module(body=[node], type_ignores=[]), "app.py", "exec")
scope = {}
exec(code, scope)
_try_mark_meta_verified = scope["_try_mark_meta_verified"]


class TryMarkMetaVerifiedTests(unittest.TestCase):
    def test_calls_mark_meta_verified_with_a_connection_from_the_real_connector(self):
        import messenger_browser_claim
        import private_subscriber_store

        class FakeConn:
            def __enter__(self):
                return "synthetic-conn"

            def __exit__(self, *exc):
                return False

        with patch.object(private_subscriber_store, "_connect", return_value=FakeConn()) as connect:
            with patch.object(messenger_browser_claim, "mark_meta_verified") as verify:
                _try_mark_meta_verified("synthetic-code", "synthetic-sender")
        connect.assert_called_once_with()
        verify.assert_called_once_with("synthetic-conn", messenger_code="synthetic-code",
                                        verified_sender_id="synthetic-sender")

    def test_a_connector_failure_never_raises_out_of_the_webhook_path(self):
        import private_subscriber_store
        with patch.object(private_subscriber_store, "_connect", side_effect=RuntimeError("no such table")):
            _try_mark_meta_verified("synthetic-code", "synthetic-sender")  # must not raise

    def test_a_mark_meta_verified_failure_never_raises_out_of_the_webhook_path(self):
        import messenger_browser_claim
        import private_subscriber_store

        class FakeConn:
            def __enter__(self):
                return "synthetic-conn"

            def __exit__(self, *exc):
                return False

        with patch.object(private_subscriber_store, "_connect", return_value=FakeConn()):
            with patch.object(messenger_browser_claim, "mark_meta_verified",
                               side_effect=RuntimeError("synthetic")):
                _try_mark_meta_verified("synthetic-code", "synthetic-sender")  # must not raise


if __name__ == "__main__":
    unittest.main()
