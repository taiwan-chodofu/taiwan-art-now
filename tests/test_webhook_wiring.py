"""Static security regression tests against the actual Flask app source.

These checks do not execute Flask or call Meta/Supabase. They complement,
not replace, request-level integration tests.
"""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def function(name):
    return next(n for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


class WebhookWiringSafetyTests(unittest.TestCase):
    def test_verify_token_from_environment(self):
        assignment = next(n for n in TREE.body if isinstance(n, ast.Assign) and
                          any(isinstance(t, ast.Name) and t.id == "MESSENGER_VERIFY_TOKEN" for t in n.targets))
        self.assertIsInstance(assignment.value, ast.Call)
        self.assertEqual(ast.unparse(assignment.value), "os.environ.get('MESSENGER_VERIFY_TOKEN', '')")

    def test_get_verification_requires_configured_secret(self):
        source = ast.unparse(function("webhook_verify"))
        self.assertIn("MESSENGER_VERIFY_TOKEN and (token == MESSENGER_VERIFY_TOKEN)", source)

    def test_post_verifies_before_json_parsing(self):
        source = ast.unparse(function("webhook_receive"))
        self.assertLess(source.index("verify_meta_webhook("), source.index("request.get_json("))
        self.assertIn("abort(403)", source)

    def test_post_does_not_create_public_issue(self):
        source = ast.unparse(function("webhook_receive"))
        self.assertIn("store_inbound(", source)
        self.assertNotIn("api.github.com/repos", source)
        self.assertNotIn("issue_data", source)

    def test_private_write_precedes_auto_subscribe(self):
        source = ast.unparse(function("webhook_receive"))
        # Inspect the source segment after the auto-subscribe comment, not other subscription flows.
        tail = source.split("Preserve legacy auto-subscribe behavior only after private persistence.")[-1]
        self.assertIn("_add_subscriber(sender_id)", tail)
        self.assertLess(source.index("store_inbound("), source.rindex("_add_subscriber(sender_id)"))

    def test_post_private_write_error_is_redacted(self):
        source = ast.unparse(function("webhook_receive"))
        self.assertNotIn("logger.exception(", source)
        self.assertIn('return (\'Service Unavailable\', 503)', source)


if __name__ == "__main__":
    unittest.main()
