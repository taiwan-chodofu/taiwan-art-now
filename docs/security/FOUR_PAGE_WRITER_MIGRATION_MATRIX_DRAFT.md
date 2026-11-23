# Four-page bookmark writer migration matrix — draft only

Source reviewed: actual draft branch templates on 2026-11-23. This is a planning artifact, **not** a completed migration. No template currently uses `draft_page_controller.js` or `draft_page_action.js`.

| Surface / handler | Current storage operation | UI and side effects | Required migration contract |
| --- | --- | --- | --- |
| Home `toggleAction` | Read entire favs/visited map, modify one key, `_saveFavs`/`_saveVisited` | Re-renders and invokes legacy subscriber notification sync; analytics currently tied to action | Await per-key shared commit before analytics, render, or notification sync. Preserve visited metadata object and favorite metadata. |
| Home `markVisitedFromMylist` | Add visited metadata object and save full map | Analytics `mark_visited`, `renderMylist`, `_renderActions` | Commit visited only, leave favorite intact, then refresh both views. |
| Home `removeFromMylist` | Direct full-map `localStorage.setItem` on chosen collection | Re-renders list and action buttons | Explicit per-key removal only, after verified commit; do not infer a remote tombstone from local absence. |
| Home `migrateStore` | One-time dynamic `localStorage.setItem(storeName,...)` rewrites keys | Migration flag controls future runs | Needs a separately reviewed migration transaction and collision strategy. Never silently drop colliding old/new keys or mark migration complete after partial failure. |
| Discover swipe/undo | `_saveFavs`/`_saveVisited` full-map operations | Deck shift, animation, history, undo | Await verified write before advancing; undo must use exact-value guarded removal; skip never writes; seen must not clear want. |
| Nearby `toggleAction` | Direct full-map write | Analytics may run before write, then `_syncSubscriberData`, `renderAll` | Delay analytics, notification sync, and re-render until confirmed commit. Preserve visited ISO string and favorite metadata object. |
| Detail `toggleVisited` / `toggleFav` | Direct full-map write | Analytics may run before write, then `_syncSubscriberData`, `updateBtns` | Delay analytics, notification sync, and button update until confirmed commit. Preserve visited ISO string and favorite metadata object. |

## Cross-page invariants

1. `favs` (想去) and `visited` (已看) are independent flags. Marking seen never deletes want; watchlist is a **derived view** of want and not seen.
2. The writer must re-read the current per-collection map under the same cooperative lock and verify the actual persisted value. UI may only claim success after verification; ambiguous results must not trigger automatic retry.
3. Keep existing metadata values unchanged, including optional `region`/`event` and visited ISO-string **or** object forms. Never overwrite invalid or unfamiliar legacy storage with an empty map.
4. The existing `_syncSubscriberData` is **legacy notification sync**, not authenticated versioned bookmark reconciliation. Do not treat it as a safe replacement for local storage.
5. Web Locks cannot protect against an old cached/PWA tab that still writes full maps. Staging migration requires independent durable preservation, stale-client mitigation, authenticated server CAS and tested rollback.
6. The home one-time key migration must be included in the writer rollout, not merely the user-facing buttons.

## Proposed safe staging order

- Add real-template browser tests that assert storage failure leaves UI, analytics, notification sync and Discover deck unchanged.
- Move the least complex page handler (detail) behind the unmounted shared controller **in an isolated staging fixture**, preserving current callback signatures and display behavior.
- Repeat for nearby, home handlers including the one-time migration, and Discover swipe/undo.
- Reproduce cached-tab overwrite across old/new clients. Do **not** claim a safe rollout until independently preserved data can be recovered and explicit deletion conflicts can be reviewed.
- Require explicit owner approval for production configuration, migration, merge and deployment.

**Release decision: NO-GO.** This matrix does not change the deployed website or authorize activation of the draft adapter.
