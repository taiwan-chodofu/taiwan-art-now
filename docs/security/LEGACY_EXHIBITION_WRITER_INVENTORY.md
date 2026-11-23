# Legacy favorites/visited write inventory — draft cutover audit

Source: the four current templates on `feat/private-subscriber-storage-adapter-83`. This is a source audit, **not** a live-site change.

| Surface | Writes to legacy keys | Notable behavior |
| --- | --- | --- |
| `templates/index.html` | `_saveVisited` / `_saveFavs` at ~1642–1643; direct `localStorage.setItem` in `removeFromMylist` at ~1495–1502; one-time `migrateStore` at ~1924–1929 | Action toggles add/delete; `markVisitedFromMylist` saves an **object** with `date,title,museum,dates,url,region`. Other main-list visited additions also save objects. |
| `templates/discover.html` | `_saveFavs` / `_saveVisited` at ~264–267, called on swipe actions and undo at ~518–537 | Both add and undo delete; visited additions are **objects**, not strings. |
| `templates/nearby.html` | direct `localStorage.setItem` at ~345 and ~359 | Toggle visited adds an **ISO string**; toggle favorite adds object. |
| `templates/exhibition_detail_page.html` | direct `localStorage.setItem` at ~509 and ~524 | Toggle visited adds an **ISO string**; favorite adds object. |

## Critical findings (initial audit; status updated 2026-11-23)

1. **Mixed visited schema**: main/discover save objects; nearby/detail save ISO strings. **Addressed in unmounted draft** by `draft_legacy_snapshot.js` and `tests/test_draft_legacy_real_shapes.cjs`; both are preserved without conversion. Not deployed.
2. **Favorite metadata mismatch**: main/discover include optional `region,event`. **Addressed in unmounted draft** validator and tests. Not deployed.
3. **No single write choke point**: all four templates plus direct removal and `migrateStore` still write legacy keys. **Open blocker**.
4. **Legacy deletions are physical key removal**, not explicit tombstones. Never infer deletion intent from absence. **Open migration constraint**.
5. Existing `/api/subscribers/sync` is notification sync, not private versioned CAS. **Open integration constraint**.
6. Web Locks protect only participating tabs. An old cached tab can overwrite a new tab's localStorage map. **Open blocker requiring rollout strategy**.

## Required migration sequence (no production changes authorized)

- Expand read-only validation and tests for both legitimate visited formats and favorite metadata, retaining exact values.
- Introduce a shared, fail-closed, **asynchronous** write coordinator; migrate all listed writers and the one-time key migration, without silently changing UX or dropping writes. The existing handlers are synchronous, so this is a deliberate UI integration, not a string replacement.
- Re-read state inside the exclusive Web Lock, use per-item operations rather than replacing a stale whole map, and keep notification sync separate.
- Test real multi-tab races (including an older tab with cached legacy code), in-app browser storage isolation, and network/offline cases. Web Locks only protects participating writers; an old tab can bypass it.
- Do not mount the draft deletion bridge until this migration is complete and production rollout is separately approved.

## Current draft status

The shared per-item Web Lock writer, persistence-first UI adapter, and isolated Chromium tests exist, but **none of the four real templates are wired**. Browser tests on a synthetic page are not production template E2E coverage. Old-tab bypass, legacy `migrateStore`, and remote sync remain blockers.

## Draft release gate update (2026-11-23)

CI 45094588186 succeeded for the two-device Chromium mock-CAS and explicit tombstone stop tests. The E2E suite still **intentionally reproduces loss** when a cached legacy tab bypasses Web Locks and overwrites the whole localStorage map. Therefore, successful CI does not prove old-tab safety. All four templates retain independent legacy writers, including the main-page one-time migration; none is mounted to the new adapter. The next safe rollout must coordinate or retire every writer and define a controlled stale-client strategy, rather than treating Web Locks as sufficient protection. The draft UI action adapter also now handles exceptions from busy-state callbacks without stranding its pending slot or reporting a completed write as failed; regression tests added, CI pending. No production changes.

## Post-write UI verification hardening

The unmounted `draft_action_commit.js` now verifies exact persisted JSON value equality for a `set`, not only presence of the exhibition key. A regression test injects a cached-tab-style same-key metadata replacement between the cooperative writer's successful readback and the UI adapter's final read. The adapter must report `uncertain_write` without firing `onCommitted`. This narrows false-success reporting but **does not prevent or repair** the stale-tab overwrite; it is not a substitute for a rollout-wide writer migration or independent server backup. CI pending.

## Combined cached-tab regression and release decision

Added a Chromium test with two actual tabs sharing browser localStorage: a modern cooperative writer saves an item, a separately retained append-only checkpoint records the verified snapshot, and an old tab subsequently overwrites the whole map from a stale copy. The loss detector must report the missing modern item and the old-tab addition as review-only, with **no automatic restoration**. This deliberately confirms the safety gap remains, rather than presenting detection as prevention. The checkpoint is localStorage-only and not durable against browser storage eviction, clearing, or device loss.

**Cutover must remain blocked** until (a) every template writer and main-page migration path are coordinated, (b) an independent owner-authenticated server-side preservation/backup path is available and tested, (c) stale cached/PWA tabs have an explicit safe handling and rollback plan, and (d) deletion intent and review are kept distinct from accidental absence. CI for the combined test pending. No live subscriber data or production routes were changed.

## Read-only cutover preflight (draft, not a rollout approval)

`static/js/draft_cutover_preflight.js` performs a fail-closed preview using an externally supplied checkpoint, the local loss detector, a strict authenticated no-store server GET, and additive merge planning. Missing/invalid checkpoints, missing or changed local records, unauthorized/offline server reads, and explicit remote tombstones prevent the `preflight_ready` result. No local writes, server writes, recovery, or template mounting occur. The companion Node tests exercise these boundaries. **Crucially, `preflight_ready` is advisory only:** localStorage checkpoints are not independent durable evidence, local additions may have occurred after a checkpoint, and old tabs can still overwrite between preflight and CAS. A production cutover requires an independently authenticated durable server backup, full writer migration and stale-client strategy, explicit approval, and staging end-to-end tests. CI pending.
