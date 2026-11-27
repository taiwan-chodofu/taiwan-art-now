"""Synthetic tests: caller-provided IDs are never authentication."""
import unittest
from unittest.mock import patch
from subscriber_ownership import (
    AuthorizationDenied, authenticated_messenger_sender,
    require_messenger_owner, require_push_owner,
)


class OwnershipTests(unittest.TestCase):
    def test_session_identity_authorizes_own_id(self):
        with patch("subscriber_ownership.resolve_sender", return_value="owner"):
            self.assertEqual(require_messenger_owner(object(), "token", "owner"), "owner")

    def test_other_subscriber_id_denied(self):
        with patch("subscriber_ownership.resolve_sender", return_value="owner"):
            with self.assertRaises(AuthorizationDenied):
                require_messenger_owner(object(), "token", "victim")

    def test_missing_session_denied_before_lookup(self):
        with patch("subscriber_ownership.resolve_sender") as resolve:
            with self.assertRaises(AuthorizationDenied):
                authenticated_messenger_sender(object(), None)
            resolve.assert_not_called()

    def test_unknown_session_denied(self):
        with patch("subscriber_ownership.resolve_sender", return_value=None):
            with self.assertRaises(AuthorizationDenied):
                require_messenger_owner(object(), "token", "victim")

    def test_database_failure_denied(self):
        with patch("subscriber_ownership.resolve_sender", side_effect=RuntimeError("db")):
            with self.assertRaises(AuthorizationDenied):
                require_messenger_owner(object(), "token", "owner")

    def test_empty_requested_id_denied(self):
        with patch("subscriber_ownership.resolve_sender", return_value="owner"):
            with self.assertRaises(AuthorizationDenied):
                require_messenger_owner(object(), "token", "")

    def test_proven_push_endpoint_allows_matching_endpoint(self):
        self.assertEqual(require_push_owner("proof-endpoint", "proof-endpoint"),
                         "proof-endpoint")

    def test_unproven_push_endpoint_denied(self):
        with self.assertRaises(AuthorizationDenied):
            require_push_owner(None, "victim-endpoint")

    def test_other_push_endpoint_denied(self):
        with self.assertRaises(AuthorizationDenied):
            require_push_owner("own-endpoint", "victim-endpoint")


if __name__ == "__main__":
    unittest.main()
