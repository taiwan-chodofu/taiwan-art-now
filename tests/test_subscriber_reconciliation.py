"""Synthetic, privacy-safe reconciliation tests."""
import unittest
from copy import deepcopy
from subscriber_reconciliation import (
    ReconciliationRequired, merge_additive, reconcile_favorites_visited,
    preview_reconciliation,
)


def snapshot(favs=None, visited=None):
    return {"favs": {} if favs is None else favs,
            "visited": {} if visited is None else visited}


class ReconciliationTests(unittest.TestCase):
    def test_union_of_distinct_items(self):
        result = reconcile_favorites_visited(
            snapshot({"local": True}), snapshot({"remote": True}))
        self.assertEqual(result["favs"], {"local": True, "remote": True})

    def test_identical_item_is_stable(self):
        result = merge_additive({"same": True}, {"same": True})
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["merged"], {"same": True})

    def test_conflicting_value_requires_review(self):
        with self.assertRaises(ReconciliationRequired):
            reconcile_favorites_visited(
                snapshot({"same": False}), snapshot({"same": True}))

    def test_conflict_preview_no_values(self):
        result = preview_reconciliation(
            snapshot({"same": False}), snapshot({"same": True}))
        self.assertFalse(result["safe_to_apply"])
        self.assertEqual(result["conflict_counts"]["favs"], 1)
        self.assertNotIn("merged", result)

    def test_missing_local_item_does_not_delete_remote(self):
        result = reconcile_favorites_visited(snapshot(), snapshot({"keep": True}))
        self.assertEqual(result["favs"], {"keep": True})

    def test_missing_remote_item_does_not_delete_local(self):
        result = reconcile_favorites_visited(snapshot({"keep": True}), snapshot())
        self.assertEqual(result["favs"], {"keep": True})

    def test_visited_independent_of_favs(self):
        result = reconcile_favorites_visited(
            snapshot(visited={"visited-local": True}),
            snapshot(visited={"visited-remote": True}))
        self.assertEqual(len(result["visited"]), 2)

    def test_does_not_mutate_inputs(self):
        local = snapshot({"a": {"x": True}})
        remote = snapshot({"b": {"y": True}})
        before = deepcopy((local, remote))
        reconcile_favorites_visited(local, remote)
        self.assertEqual((local, remote), before)

    def test_replay_idempotent(self):
        local = snapshot({"a": True})
        remote = snapshot({"b": True})
        once = reconcile_favorites_visited(local, remote)
        twice = reconcile_favorites_visited(local, once)
        self.assertEqual(once, twice)

    def test_invalid_map_rejected(self):
        with self.assertRaises(ValueError):
            merge_additive([], {})

    def test_invalid_key_rejected(self):
        with self.assertRaises(ValueError):
            merge_additive({"": True}, {})

    def test_unexpected_fields_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_favorites_visited({"favs": {}, "visited": {}, "sender_id": "x"},
                                        snapshot())

    def test_preview_empty_is_safe(self):
        self.assertTrue(preview_reconciliation(snapshot(), snapshot())["safe_to_apply"])


if __name__ == "__main__":
    unittest.main()
