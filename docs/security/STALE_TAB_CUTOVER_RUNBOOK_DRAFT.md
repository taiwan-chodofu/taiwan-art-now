# Stale-tab cutover runbook — DRAFT, release-blocking

This document is an operational decision gate, **not** an implemented mitigation or permission to deploy. Existing pages still use independent localStorage whole-map writers; cached/PWA tabs can bypass the new cooperative Web Lock and erase newer entries. The existing Chromium regression intentionally reproduces this loss.

## Before any staging rollout

1. Inventory every writer in `templates/index.html`, `templates/discover.html`, `templates/nearby.html`, `templates/exhibition_detail_page.html`, including the main-page dynamic `migrateStore` writer. Run `python scripts/audit_legacy_exhibition_writers.py` and review changes manually; a passing inventory does not prove safety.
2. Preserve **both** `taiwan_art_favs` and `taiwan_art_visited` without normalizing or discarding values. Visited values may be ISO strings **or** metadata objects. The two bookmark flags are independent; seen must not delete want.
3. Design a single shared per-item writer for every page and migration path, and verify persistence before updating UI. Web Locks protect only participating clients, not cached legacy clients.
4. Establish a separate, authenticated, durable server-side preservation path and owner-controlled encrypted backup, with a tested restore and count/content verification. A localStorage checkpoint is **not** a durable backup.
5. Define how a stale cached tab is detected and prevented from performing destructive legacy writes. A version banner or reload prompt alone does **not** prevent an already-running tab from writing. Include PWA/service-worker cache and offline cases.
6. Define explicit deletion intent and revisioned tombstones. Absence of a key in an older snapshot is **not** permission to delete a server record.
7. Test two real tabs where the old tab saves a stale map **after** the modern tab saves, then prove the modern record remains recoverable from independent preservation, without silent resurrection or accidental deletion.
8. Test rollback after partial rollout: server and local state must not silently diverge, and rollback must not reactivate an unauthenticated legacy API.

## Stop conditions

Stop the cutover and leave the current live site unchanged if any of the following holds:

- A single active writer or legacy migration path can still overwrite the complete map without coordination.
- Stale-tab loss can be reproduced without independent recoverability.
- Backup/restore has not been tested with synthetic data in staging and then approved for owner-controlled production handling.
- Authenticated browser ownership, server CAS, deletion conflict handling, or rollback is unresolved.
- A test only verifies that loss is detected, rather than prevented or safely recoverable.

## User-facing failure policy

Never say an exhibition was saved unless the write is verified. Never automatically retry an ambiguous server POST. For uncertain local state, explain the specific next action in ordinary language; avoid technical labels such as "CAS", "tombstone", or "refresh registration status". Do not direct a user to reload unless that is safe and the instruction explicitly says to reload the page.

## Current decision

**NO-GO for production migration or merging PR #87.** The draft Discover browser suite passing is not proof that old cached tabs, production ownership, or private subscriber migration are safe. Do not access live subscriber data, change Render configuration, migrate a database, merge, or deploy without a separate explicit approval.
