"""Flask request-level tests for the *actual* /connect-devices route
extracted from app.py. Same AST-isolation technique as
test_flask_webhook_http.py / test_private_auth_initiate_http.py.
"""
import ast
from pathlib import Path
import sys
import unittest

from flask import Flask, render_template, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
route = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == "connect_devices_page")
route.decorator_list = []
code = compile(ast.Module(body=[route], type_ignores=[]), "app.py", "exec")
app = Flask("connect-devices-tests", template_folder=str(ROOT / "templates"))
scope = {"request": request, "render_template": render_template, "app": app}
exec(code, scope)
app.add_url_rule("/connect-devices", "connect_devices_page", scope["connect_devices_page"],
                  methods=["GET"])


class ConnectDevicesPageHttpTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_default_language_is_japanese(self):
        result = self.client.get("/connect-devices")
        self.assertEqual(result.status_code, 200)
        self.assertIn("端末を連携".encode(), result.data)

    def test_lang_query_param_selects_the_right_copy(self):
        result = self.client.get("/connect-devices?lang=zh")
        self.assertEqual(result.status_code, 200)
        self.assertIn("連結裝置".encode(), result.data)

    def test_references_the_real_private_auth_endpoints(self):
        result = self.client.get("/connect-devices")
        self.assertIn(b"/api/private-auth/initiate", result.data)
        self.assertIn(b"/api/private-auth/claim", result.data)


if __name__ == "__main__":
    unittest.main()
