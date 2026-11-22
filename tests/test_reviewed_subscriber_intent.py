import unittest
from reviewed_subscriber_intent import plan_reviewed_conflict
from versioned_subscriber_sync import StaleRevision

STATE = {"revision": 4, "favs": {"exhibit": {
    "value": None, "deleted": True, "revision": 3}}, "visited": {}}


class ReviewedIntentTests(unittest.TestCase):
    def plan(self, **overrides):
        kwargs = dict(base_revision=4, kind="favs", key="exhibit",
                      choice="keep_saved", reviewed_item_revision=3,
                      local_value={"title": "Exhibit"})
        kwargs.update(overrides)
        return plan_reviewed_conflict(STATE, **kwargs)

    def test_explicit_keep_is_only_proposal(self):
        result = self.plan()
        self.assertEqual(result["status"], "requires_verified_consent_and_cas")
        self.assertEqual(result["changes"]["favs"]["exhibit"]["set"]["title"], "Exhibit")
        self.assertTrue(STATE["favs"]["exhibit"]["deleted"])

    def test_stale_server_revision_rejected(self):
        with self.assertRaises(StaleRevision):
            self.plan(base_revision=2)

    def test_stale_item_revision_rejected(self):
        with self.assertRaises(StaleRevision):
            self.plan(reviewed_item_revision=2)

    def test_missing_item_rejected(self):
        with self.assertRaises(StaleRevision):
            self.plan(key="missing")

    def test_no_deletion_conflict_rejected(self):
        state = {"revision": 4, "favs": {"exhibit": {
            "value": {"title": "A"}, "deleted": False, "revision": 3}},
            "visited": {}}
        with self.assertRaises(StaleRevision):
            plan_reviewed_conflict(state, base_revision=4, kind="favs",
                                   key="exhibit", choice="keep_saved",
                                   reviewed_item_revision=3, local_value=True)

    def test_remove_does_not_mutate_server_or_local(self):
        result = self.plan(choice="remove_from_list")
        self.assertEqual(result["status"], "requires_local_confirmation")
        self.assertEqual(result["changes"], {"favs": {}, "visited": {}})

    def test_defer_is_noop(self):
        self.assertEqual(self.plan(choice="decide_later")["changes"],
                         {"favs": {}, "visited": {}})

    def test_missing_local_value_rejected(self):
        with self.assertRaises(ValueError):
            self.plan(local_value=None)

    def test_non_json_local_value_rejected(self):
        with self.assertRaises(ValueError):
            self.plan(local_value={"unsafe": object()})

    def test_old_priority_choice_rejected(self):
        with self.assertRaises(ValueError):
            self.plan(choice="keep_local")

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            self.plan(kind="push")

    def test_bool_revision_rejected(self):
        with self.assertRaises(StaleRevision):
            self.plan(base_revision=True)

    def test_visited_tombstone_independent(self):
        state = {"revision": 4, "favs": {}, "visited": {"exhibit": {
            "value": None, "deleted": True, "revision": 3}}}
        result = plan_reviewed_conflict(state, base_revision=4,
            kind="visited", key="exhibit", choice="keep_saved",
            reviewed_item_revision=3, local_value="2026-11-22T00:00:00Z")
        self.assertIn("exhibit", result["changes"]["visited"])


if __name__ == "__main__":
    unittest.main()
