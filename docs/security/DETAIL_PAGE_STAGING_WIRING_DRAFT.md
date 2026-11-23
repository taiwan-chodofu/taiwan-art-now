# Exhibition detail staging wiring — DRAFT, no production mount

The isolated `draft_detail_action_adapter.js` has unit coverage, but the real `templates/exhibition_detail_page.html` still calls synchronous `toggleVisited()` and `toggleFav()`. **Do not replace these with async calls by string substitution.**

## Actual handler dependencies

- `exId` is normalized from `exhibition.stable_key`; current buttons call global `toggleVisited`/`toggleFav`.
- Existing visited entries are ISO timestamp strings; favorite entries are metadata objects with `title`, `museum`, `dates`, `url`.
- Existing handlers send analytics **before** localStorage persistence; then invoke `_syncSubscriberData()`, `updateBtns()`, and `_maybeWarnInAppSave()`.
- `_syncSubscriberData()` uses legacy `taiwan_art_ref` and `/api/subscribers/sync`; this is **not** authenticated versioned sync and must not be silently repurposed.

## Staging-only integration requirements

1. Load `draft_legacy_snapshot.js`, `draft_legacy_writer.js`, `draft_page_action.js`, `draft_page_controller.js`, and `draft_detail_action_adapter.js` in dependency order in an isolated rendered-template fixture. Do not load them into production until release blockers are resolved.
2. Construct a controller using `window.localStorage`, `navigator.locks`, normalized exhibition key, and the exact existing favorite metadata. Preserve the visited ISO timestamp shape.
3. Disable **both** action buttons for the relevant pending write, or clearly show per-button pending state, to prevent duplicate taps. Restore usability on every success/failure path.
4. Only after a confirmed persisted write: call `updateBtns()`, send the matching analytics event, invoke the existing notification sync, and show the in-app save warning if applicable.
5. On storage failure, do not update buttons, analytics, notification sync, deck or user registration claims. Show a localized, plain-language action: “保存できませんでした。ページを閉じず、少し待ってからもう一度押してください。” **Only** for a definite local write failure. For `uncertain_write`, tell the user to inspect the current button state after a safe explicit page reload; never blindly retry or claim no save.
6. Test two rapid taps on one button, simultaneous fav/visited taps, storage quota failure, unavailable Web Locks, cached old tab overwrites, and navigation away during a pending action.
7. Check actual browser HTML and Jinja escaping for exhibition title/venue/URL before connecting callback code. Do not embed unescaped dynamic metadata in new inline JavaScript.
8. The legacy home `migrateStore` and other page writers still bypass the shared lock. An isolated detail-page fixture passing does **not** authorize production deployment.

## Exit criteria

Real rendered-template Chromium tests must prove the exact button/analytics/notification ordering, and the broader stale-tab recovery, authenticated ownership, backup/restore, and rollback gates must be met. **NO-GO for merging or deploying PR #87.**
