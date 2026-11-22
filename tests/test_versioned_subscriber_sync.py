"""Synthetic tests for revisioned tombstone sync; no real database."""
from copy import deepcopy
import unittest
from versioned_subscriber_sync import (
    StaleRevision, apply_changes, empty_state, validate_state, visible_items,
)


def change(kind="favs", key="exhibition-a", operation=None):
    return {
        "favs": {key: {"set": True} if operation is None else operation}
        if kind == "favs" else {},
        "visited": {key: {"set": True} if operation is None else operation}
        if kind == "visited" else {},
    }


class VersionedSyncTests(unittest.TestCase):
    def test_initial_state(self):
        state = empty_state()
        self.assertEqual(validate_state(state), 0)
        self.assertEqual(visible_items(state), {"favs": {}, "visited": {}})

    def test_set_increments_revision(self):
        state = apply_changes(empty_state(), base_revision=0, changes=change())
        self.assertEqual(state["revision"], 1)
        self.assertTrue(visible_items(state)["favs"]["exhibition-a"])

    def test_delete_creates_tombstone(self):
        first = apply_changes(empty_state(), base_revision=0, changes=change())
        deleted = apply_changes(first, base_revision=1,
                                changes=change(operation={"delete": True}))
        self.assertEqual(deleted["revision"], 2)
        self.assertTrue(deleted["favs"]["exhibition-a"]["deleted"])
        self.assertIsNone(deleted["favs"]["exhibition-a"]["value"])
        self.assertNotIn("exhibition-a", visible_items(deleted)["favs"])

    def test_stale_device_cannot_resurrect_deleted_item(self):
        first = apply_changes(empty_state(), base_revision=0, changes=change())
        deleted = apply_changes(first, base_revision=1,
                                changes=change(operation={"delete": True}))
        with self.assertRaises(StaleRevision):
            apply_changes(deleted, base_revision=1, changes=change())

    def test_stale_update_cannot_overwrite_other_device(self):
        current = apply_changes(empty_state(), base_revision=0, changes=change())
        with self.assertRaises(StaleRevision):
            apply_changes(current, base_revision=0,
                          changes=change(kind="visited"))

    def test_delete_unknown_item_still_records_tombstone(self):
        state = apply_changes(empty_state(), base_revision=0,
                              changes=change(operation={"delete": True}))
        self.assertTrue(state["favs"]["exhibition-a"]["deleted"])

    def test_noop_does_not_increment_revision(self):
        initial = empty_state()
        self.assertEqual(apply_changes(initial, base_revision=0,
                                       changes={"favs": {}, "visited": {}}),
                         initial)

    def test_inputs_are_not_mutated(self):
        initial = empty_state()
        changes = change()
        before = deepcopy((initial, changes))
        apply_changes(initial, base_revision=0, changes=changes)
        self.assertEqual((initial, changes), before)

    def test_both_maps_share_batch_revision(self):
        changes = {"favs": {"a": {"set": True}},
                   "visited": {"b": {"set": True}}}
        state = apply_changes(empty_state(), base_revision=0, changes=changes)
        self.assertEqual(state["favs"]["a"]["revision"], 1)
        self.assertEqual(state["visited"]["b"]["revision"], 1)

    def test_invalid_base_revision_rejected(self):
        with self.assertRaises(ValueError):
            apply_changes(empty_state(), base_revision=True, changes=change())

    def test_invalid_operation_rejected(self):
        with self.assertRaises(ValueError):
            apply_changes(empty_state(), base_revision=0,
                          changes=change(operation={"delete": False}))

    def test_tombstone_with_value_rejected(self):
        state = {"revision": 1, "favs": {"a": {
            "value": True, "deleted": True, "revision": 1}}, "visited": {}}
        with self.assertRaises(ValueError):
            validate_state(state)

    def test_future_item_revision_rejected(self):
        state = {"revision": 1, "favs": {"a": {
            "value": True, "deleted": False, "revision": 2}}, "visited": {}}
        with self.assertRaises(ValueError):
            validate_state(state)

    def test_missing_change_map_rejected(self):
        with self.assertRaises(ValueError):
            apply_changes(empty_state(), base_revision=0,
                          changes={"favs": {}})

    def test_null_value_rejected(self):
        with self.assertRaises(ValueError):
            apply_changes(empty_state(), base_revision=0,
                          changes=change(operation={"set": None}))


if __name__ == "__main__":
    unittest.main()
