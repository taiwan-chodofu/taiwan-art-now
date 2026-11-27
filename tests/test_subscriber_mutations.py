"""Synthetic-only tests for atomic subscriber state transitions."""
import unittest
from subscriber_mutations import (
    SubscriberNotFound, link_ref, subscribe_push, sync_messenger, sync_push,
    unsubscribe_messenger, unsubscribe_push, update_settings,
)


class SubscriberMutationsTests(unittest.TestCase):
    def setUp(self):
        self.m = {"users": {"sender-a": {"ref": "ref-a", "favs": {"old": True}}},
                  "refs": {"ref-a": "sender-a", "ref-extra": "sender-a"}}
        self.p = {"subscriptions": {}}

    def test_sync_messenger(self):
        sync_messenger(self.m, "sender-a", {"new": True}, {"seen": True})
        self.assertEqual(self.m["users"]["sender-a"]["favs"], {"new": True})

    def test_sync_unknown_rejected(self):
        with self.assertRaises(SubscriberNotFound):
            sync_messenger(self.m, "unknown", {}, {})

    def test_link_ref_cleans_old_mapping(self):
        link_ref(self.m, "sender-a", "ref-new")
        self.assertNotIn("ref-a", self.m["refs"])
        self.assertEqual(self.m["refs"]["ref-new"], "sender-a")

    def test_link_ref_rejects_collision(self):
        self.m["users"]["sender-b"] = {}
        with self.assertRaises(ValueError):
            link_ref(self.m, "sender-b", "ref-a")
        self.assertEqual(self.m["refs"]["ref-a"], "sender-a")

    def test_unsubscribe_removes_all_refs(self):
        unsubscribe_messenger(self.m, "sender-a")
        self.assertEqual(self.m, {"users": {}, "refs": {}})

    def test_settings_requires_boolean(self):
        with self.assertRaises(ValueError):
            update_settings(self.m, "sender-a", weekly_digest="false")
        update_settings(self.m, "sender-a", weekly_digest=False)
        self.assertIs(self.m["users"]["sender-a"]["weekly_digest"], False)

    def test_push_resubscribe_preserves_favs(self):
        subscribe_push(self.p, "https://example.invalid/push", {"p256dh": "a", "auth": "b"})
        sync_push(self.p, "https://example.invalid/push", {"exhibit": True}, {"seen": True})
        subscribe_push(self.p, "https://example.invalid/push", {"p256dh": "new", "auth": "new"})
        self.assertEqual(self.p["subscriptions"]["https://example.invalid/push"]["favs"], {"exhibit": True})

    def test_push_unsubscribe(self):
        subscribe_push(self.p, "https://example.invalid/push", {"p256dh": "a", "auth": "b"})
        unsubscribe_push(self.p, "https://example.invalid/push")
        self.assertEqual(self.p["subscriptions"], {})

    def test_push_unknown_rejected(self):
        with self.assertRaises(SubscriberNotFound):
            sync_push(self.p, "unknown", {}, {})


if __name__ == "__main__":
    unittest.main()
