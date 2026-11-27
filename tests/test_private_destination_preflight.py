"""Synthetic-only tests for the read-only destination preflight."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import MagicMock

path = Path(__file__).resolve().parents[1] / "scripts/check_private_destination.py"
spec = importlib.util.spec_from_file_location("check_private_destination", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DestinationPreflightTests(unittest.TestCase):
    def test_queries_only_allowlisted_counts(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(0,), (0,), (0,)]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        result = module.inspect_destination(lambda: conn)
        self.assertEqual(result, dict.fromkeys(module.TABLES, 0))
        self.assertEqual(cursor.execute.call_count, 3)
        for call in cursor.execute.call_args_list:
            sql = call.args[0].lower()
            self.assertTrue(sql.startswith("select count(*) from tan_private."))
            self.assertNotIn("sender_id", sql)
            self.assertNotIn("endpoint", sql)

    def test_nonempty_is_visible_in_counts(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(2,), (1,), (3,)]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        result = module.inspect_destination(lambda: conn)
        self.assertEqual(result["messenger_subscribers"], 2)
        self.assertTrue(any(result.values()))


if __name__ == "__main__":
    unittest.main()
