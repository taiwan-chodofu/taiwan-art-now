# Discover production-page integration audit (DRAFT, NOT FOR MERGE)

Source inspected: `templates/discover.html` on `feat/private-subscriber-storage-adapter-83`.
This is an implementation gap report, not a claim that the production page has been fixed.

## Observed unsafe sequence

- `commitSwipe(action)` immediately calls `deck.shift()`, begins fly-out animation, invokes `recordAction`, saves session deck order, and schedules `renderCard`.
- `recordAction` performs unguarded read/modify/write on `taiwan_art_favs` or `taiwan_art_visited`. A storage quota error can happen **after** the card has been removed from the in-memory deck.
- `undo()` pops history before validating whether the saved value still matches the original write. Another tab or another operation may have changed the entry.
- The draft `TanDraftDiscoverFlow` is isolated and not mounted in `templates/discover.html`; its passing Chromium fixture tests do not demonstrate page integration.

## Required safe integration contract

1. Preserve the current card, deck, and session deck order while a persistence action is pending. Disable buttons and pointer swipe commits during this interval.
2. For `like` and `visited`, await `TanDraftDiscoverFlow.swipe(card, action)`. Advance only on `written_under_cooperative_lock`; on any failure, reset the card transform and show a localized, accessible error without removing the card.
3. For `skip`, do not write a favorite or visited record. Advance exactly once, and retain undo history for the skipped card.
4. On success, perform deck shift, session deck persistence, analytics, and animation once. Ensure a delayed render cannot override a later undo or navigation (generation token/cancellation).
5. Undo the latest action through guarded `remove_if_equal`; if it returns `stale_undo`, preserve the current card, saved entry, and history, and explain that the saved exhibition changed.
6. Undo of a skipped card restores its position without any storage deletion.
7. Recheck the actual `/discover` page under Chromium with real DOM, pointer gestures, localStorage and Web Locks. Include quota failure, changed saved value, double tap during pending write, undo during animation, and page navigation/back.
8. Keep the PR in draft and do not merge or deploy. Existing legacy tabs that bypass Web Locks remain a separate documented concurrency blocker.

## Acceptance gate

A passing isolated fixture is insufficient. Require a browser test against the rendered Discover template, plus passing CI and manual review of accessibility, localization, and animation behavior, before considering any production rollout.
