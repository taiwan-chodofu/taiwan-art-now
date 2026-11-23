# Exhibition history: backup, restore, and stale-tab cutover (DRAFT)

**Not a production runbook.** No production route is mounted; do not deploy,
merge, migrate, export real user data, or enable writes without owner approval.

## Data invariants

- `favs` (想去 / 観たい) and `visited` (已看 / 観た) are independent.
- Absence from a legacy localStorage map is **not** evidence of deletion.
- Server tombstones are explicit deletions and must not be silently resurrected.
- A checkpoint in localStorage is not an independent durable backup.
- A successful synthetic CI restore is **not** proof that real backups exist.

## Staged preparation — stop before production

1. Inventory every page and cached PWA/service-worker version that can write
   `taiwan_art_favs` or `taiwan_art_visited`. Keep the legacy writer audit green.
2. In an isolated staging database, verify owner/session mapping and table
   permissions. The browser must not supply the authoritative owner ID.
3. Establish an owner-controlled, encrypted, access-restricted backup of the
   versioned server state, including both maps, revisions and tombstones.
   Store a SHA-256 manifest independently. Test retention and access controls.
4. Verify a snapshot with `scripts/verify_exhibition_state_backup.py` using
   `--snapshot` and `--expected-manifest` (offline, no writes).
5. Rehearse a restore to a **separate, disposable** database/owner; compare
   complete maps, revisions and tombstones. Never overwrite source records.
6. In a real Chromium staging session, keep an old cached tab open while a
   modern tab saves independent want/seen flags. Verify the old tab's stale
   whole-map write is detected and cannot change authenticated server state.
7. Confirm the user-facing recovery review names the specific exhibitions and
   gives a clear action: e.g. 「『観たい』の登録が見つかりました。復元する場合は『この展示を復元』を押してください。」
   Never silently restore or automatically retry an uncertain write.

## Release gates (all required)

- [ ] Authenticated server routes and verified session ownership reviewed.
- [ ] Production-safe shared writer/cutover prevents *new* uncoordinated writes.
- [ ] Old cached tabs: demonstrated protection, safe isolation or reliable
      recovery; merely showing a version banner is insufficient.
- [ ] Independent, encrypted, restorable backups and retention verified.
- [ ] Separate database restore rehearsal verified; source remains unchanged.
- [ ] Multi-device conflict, tombstone, offline/PWA and rollback tests pass.
- [ ] Human-reviewed staging UX copy in Japanese and Taiwanese Mandarin.
- [ ] Explicit owner approval for each production migration/deployment.

## Stop and rollback conditions

**Stop rollout** on any loss of independent flags, unauthorized cross-owner
read, failed backup integrity check, stale-tab overwrite without recoverable
server state, duplicate click handlers, or uncertain write reported as success.

During a stop: disable new sync writes using an independently reviewed
feature gate, preserve the last known-good server backup, collect redacted
logs, and inspect each affected exhibition's server revision. Do not
bulk-import local maps, auto-retry failed mutations, erase tombstones, or
interpret missing legacy entries as removals. Restore only with explicit
review and a fresh authenticated read. Re-run the disposable restore drill
before any subsequent rollout.

## What the current automated tests actually prove

- Node tests exercise explicit consent, stale revision/tombstone rejection and
  independent flags in a simulated old-tab overwrite.
- Disposable PostgreSQL CI tests exercise authenticated CAS and a synthetic
  checksum-verified replay into a separate synthetic owner.
- They do **not** prove continuous backups, actual old-tab prevention,
  encryption, production DB recovery, or that all live browser entrypoints
  are cut over.
