"""Synthetic-only private inbox validation tests."""
import unittest
from private_inbox import validate_inbound


class InboxValidationTests(unittest.TestCase):
    def test_valid(self):
        result = validate_inbound("Messenger", "synthetic-sender", "hello", ["https://example.invalid/image.jpg"])
        self.assertEqual(result[0], "Messenger")

    def test_channel_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("unknown", "sender", "hi", [])

    def test_empty_sender_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "", "hi", [])

    def test_non_https_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "sender", "hi", ["http://example.invalid/a"])

    def test_oversize_message_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "sender", "x" * 20001, [])

    def test_nonlist_images_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Instagram", "sender", "hi", "https://example.invalid")

if __name__ == "__main__":
    unittest.main()
