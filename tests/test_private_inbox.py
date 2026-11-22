"""Synthetic-only private inbox validation tests."""
import unittest
from private_inbox import validate_inbound, event_key_for


class InboxValidationTests(unittest.TestCase):
    def test_valid(self):
        result = validate_inbound("Messenger", "synthetic-sender", "hello", ["https://example.invalid/image.jpg"], "a"*64)
        self.assertEqual(result[0], "Messenger")

    def test_channel_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("unknown", "sender", "hi", [], "a"*64)

    def test_empty_sender_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "", "hi", [], "a"*64)

    def test_non_https_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "sender", "hi", ["http://example.invalid/a"], "a"*64)

    def test_oversize_message_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "sender", "x" * 20001, [], "a"*64)

    def test_nonlist_images_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Instagram", "sender", "hi", "https://example.invalid", "a"*64)

    def test_duplicate_mid_same_key(self):
        first = {"message": {"mid": "synthetic-mid", "text": "hello"}, "timestamp": 123}
        second = {"message": {"mid": "synthetic-mid", "text": "hello"}, "timestamp": 124}
        self.assertEqual(event_key_for("Messenger", "sender", first),
                         event_key_for("Messenger", "sender", second))

    def test_different_mid_different_key(self):
        first = {"message": {"mid": "synthetic-a"}}
        second = {"message": {"mid": "synthetic-b"}}
        self.assertNotEqual(event_key_for("Messenger", "sender", first),
                            event_key_for("Messenger", "sender", second))

    def test_event_without_mid_stable(self):
        event = {"timestamp": 123, "message": {"text": "synthetic"}}
        self.assertEqual(event_key_for("Instagram", "sender", event),
                         event_key_for("Instagram", "sender", event))

    def test_nonhex_event_key_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "sender", "hello", [], "z"*64)

    def test_malformed_event_rejected(self):
        for event in (None, [], {"message": "invalid"}):
            with self.subTest(event=event), self.assertRaises(ValueError):
                event_key_for("Messenger", "sender", event)

    def test_whitespace_image_url_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "sender", "hello",
                             ["https://example.invalid/has space"], "a"*64)

    def test_missing_key_rejected(self):
        with self.assertRaises(ValueError):
            validate_inbound("Messenger", "sender", "hello", [], "")

if __name__ == "__main__":
    unittest.main()
