"""Synthetic-only validation tests for private inbox admin CLI."""
import unittest
from unittest.mock import patch
import private_inbox_admin as admin


class InboxAdminTests(unittest.TestCase):
    def test_rejects_bad_limit_without_db(self):
        for limit in (0, 101, -1, "20"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                admin.list_metadata(limit=limit)

    def test_rejects_bad_status_without_db(self):
        with self.assertRaises(ValueError):
            admin.list_metadata(status="anything")

    def test_rejects_invalid_mark(self):
        with self.assertRaises(ValueError):
            admin.mark_status(1, "new")

    def test_rejects_invalid_id(self):
        with self.assertRaises(ValueError):
            admin.mark_status(0, "reviewed")

    def test_db_not_called_for_bad_arguments(self):
        with patch.object(admin, "_connect") as connect:
            with self.assertRaises(ValueError):
                admin.mark_status(1, "deleted")
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
