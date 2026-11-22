# Legacy favorites/visited write inventory — draft cutover audit

Source: the four current templates on `feat/private-subscriber-storage-adapter-83`. This is a source audit, **not** a live-site change.

| Surface | Writes to legacy keys | Notable behavior |
| --- | --- | --- |
| `templates/index.html` | `_saveVisited` / `_saveFavs` at ~1642–1643; direct `localStorage.setItem` in `removeFromMylist` at ~1495–1502; one-time `migrateStore` at ~1924–1929 | Action toggles add/delete; `markVisitedFromMylist` saves an **object** with `date,title,museum,dates,url,region`. Other main-list visited additions also save objects. |
| `templates/discover.html` | `_saveFavs` / `_saveVisited` at ~264–267, called on swipe actions and undo at ~518–537 | Both add and undo delete; visited additions are **objects**, not strings. |
| `templates/nearby.html` | direct `localStorage.setItem` at ~345 and ~359 | Toggle visited adds an **ISO string**; toggle favorite adds object. |
| `templates/exhibition_detail_page.html` | direct `localStorage.setItem` at ~509 and ~524 | Toggle visited adds an **ISO string**; favorite adds object. |

## Critical findings

1. **Mixed visited schema**: the draft `draft_legacy_snapshot.js` currently accepts **only ISO strings** for `taiwan_art_visited`, but `index.html` and `discover.html` write visited **objects**. This causes legitimate existing users' data to be rejected as `invalid_local`. Any sync/cutover must first support both shapes without flattening metadata or timestamps.
2. **Favorite metadata mismatch**: `index.html` and `discover.html` include `region` and `event`, but the draft legacy validator currently permits only `title,museum,dates,url`. This also blocks legitimate users. Do not silently strip the additional fields.
3. **No single write choke point**: at least four templates write the two keys, and `index.html` includes direct removal and migration paths beyond the main save helpers. Locking only the review screen is insufficient.
4. **Legacy deletions are physical key removal**, not explicit tombstones. No migration can infer deletion intent from absence.
5. Existing `/api/subscribers/sync` calls are not the new versioned CAS protocol. Any cutover must distinguish notification sync from private cross-device state.

## Required migration sequence (no production changes authorized)

- Expand read-only validation and tests for both legitimate visited formats and favorite metadata, retaining exact values.
- Introduce a shared, fail-closed, **asynchronous** write coordinator; migrate all listed writers and the one-time key migration, without silently changing UX or dropping writes. The existing handlers are synchronous, so this is a deliberate UI integration, not a string replacement.
- Re-read state inside the exclusive Web Lock, use per-item operations rather than replacing a stale whole map, and keep notification sync separate.
- Test real multi-tab races (including an older tab with cached legacy code), in-app browser storage isolation, and network/offline cases. Web Locks only protects participating writers; an old tab can bypass it.
- Do not mount the draft deletion bridge until this migration is complete and production rollout is separately approved.
