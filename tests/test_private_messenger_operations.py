"""Synthetic tests for session-owned subscriber mutations; no real DB."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import private_messenger_operations as ops


class FakeStore:
    def __init__(self):
        self.data = {
            "users": {
                "owner": {"favs": {"a": True}, "visited": {}, "weekly_digest": True},
                "victim": {"favs": {"secret": True}, "visited": {}, "weekly_digest": True},
            },
            "refs": {"owner-ref": "owner", "victim-ref": "victim"},
        }
        self.mutations = 0

    def load_messenger(self):
        return deepcopy(self.data)

    def mutate_messenger(self, mutator):
        working = deepcopy(self.data)
        mutator(working)
        self.data = working
        self.mutations += 1


class MessengerOperationsTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.session = patch("private_messenger_operations.resolve_sender",
                             return_value="owner")
        self.session.start()
        self.addCleanup(self.session.stop)

    def test_status_only_returns_owner_settings(self):
        result = ops.status(object(), "token", self.store)
        self.assertTrue(result["subscribed"])
        self.assertNotIn("users", result)
        self.assertNotIn("refs", result)

    def test_sync_only_changes_authenticated_owner(self):
        before = deepcopy(self.store.data["users"]["victim"])
        result = ops.sync(object(), "token",
                          {"favs": {"new": True}, "visited": {}}, self.store)
        self.assertEqual(result["status"], "synced")
        self.assertEqual(self.store.data["users"]["owner"]["favs"], {"new": True})
        self.assertEqual(self.store.data["users"]["victim"], before)

    def test_settings_only_change_owner(self):
        ops.settings(object(), "token", {"weekly_digest": False}, self.store)
        self.assertFalse(self.store.data["users"]["owner"]["weekly_digest"])
        self.assertTrue(self.store.data["users"]["victim"]["weekly_digest"])

    def test_unsubscribe_preserves_other_user_and_ref(self):
        ops.unsubscribe(object(), "token", {}, self.store)
        self.assertNotIn("owner", self.store.data["users"])
        self.assertNotIn("owner-ref", self.store.data["refs"])
        self.assertIn("victim", self.store.data["users"])
        self.assertEqual(self.store.data["refs"]["victim-ref"], "victim")

    def test_client_supplied_sender_rejected_before_mutation(self):
        with self.assertRaises(ops.SubscriberAccessDenied):
            ops.sync(object(), "token",
                     {"sender_id": "victim", "favs": {}, "visited": {}}, self.store)
        self.assertEqual(self.store.mutations, 0)

    def test_client_supplied_ref_rejected(self):
        with self.assertRaises(ops.SubscriberAccessDenied):
            ops.unsubscribe(object(), "token", {"ref": "victim-ref"}, self.store)
        self.assertEqual(self.store.mutations, 0)

    def test_invalid_session_rejected(self):
        with patch("private_messenger_operations.resolve_sender", return_value=None):
            with self.assertRaises(ops.SubscriberAccessDenied):
                ops.settings(object(), "token", {"weekly_digest": False}, self.store)
        self.assertEqual(self.store.mutations, 0)

    def test_missing_session_rejected(self):
        with self.assertRaises(ops.SubscriberAccessDenied):
            ops.status(object(), None, self.store)

    def test_session_database_error_rejected(self):
        with patch("private_messenger_operations.resolve_sender",
                   side_effect=RuntimeError("synthetic outage")):
            with self.assertRaises(ops.SubscriberAccessDenied):
                ops.sync(object(), "token", {"favs": {}, "visited": {}}, self.store)
        self.assertEqual(self.store.mutations, 0)

    def test_malformed_sync_fields_rejected(self):
        with self.assertRaises(ValueError):
            ops.sync(object(), "token", {"favs": {}}, self.store)
        self.assertEqual(self.store.mutations, 0)

    def test_invalid_setting_rejected_without_mutation(self):
        with self.assertRaises(ValueError):
            ops.settings(object(), "token", {"weekly_digest": "false"}, self.store)
        self.assertEqual(self.store.mutations, 0)

    def test_missing_subscriber_does_not_create_user(self):
        del self.store.data["users"]["owner"]
        with self.assertRaises(ops.SubscriberNotFound):
            ops.sync(object(), "token", {"favs": {}, "visited": {}}, self.store)
        self.assertEqual(self.store.mutations, 0)


if __name__ == "__main__":
    unittest.main()
