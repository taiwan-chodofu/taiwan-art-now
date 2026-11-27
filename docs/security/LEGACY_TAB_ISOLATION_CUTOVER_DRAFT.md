# Draft: legacy-tab isolation and safe subscriber cutover

Status: DESIGN ONLY — not approved for production. PR #87 remains draft.

## Threat model

An already-open legacy tab can continue writing `taiwan_art_favs` or
`taiwan_art_visited` in localStorage without acquiring the new Web Lock.
A read-before-write check, a post-write readback, storage events, and Web Locks
among upgraded tabs cannot make those legacy writes atomic or prevent them.
Consequently, **legacy localStorage is never an authoritative deletion source**.

## Cutover invariant

1. The authenticated, versioned server record is the authority after a
   successful explicit migration and server-side confirmation.
2. Legacy localStorage remains a read-only *candidate import source* for new
   code. New code must never write back a server-derived full snapshot to the
   legacy keys.
3. No absence from a legacy snapshot implies deletion. Deletion requires a
   verified explicit user intent, per-item server revision, and an atomic
   compare-and-swap transaction on the server.
4. Additive imports can propose missing entries but cannot resurrect an entry
   with a server tombstone or overwrite a newer per-item decision.
5. If identity, ownership, revision, or provenance is uncertain, stop and
   explain what was and was not saved; do not silently retry destructive work.
6. A user may explicitly review a tombstone-versus-legacy-save conflict. The
   decision must be scoped to that exhibition, not an entire device or list.

## Phased implementation plan

### Phase A: inventory (no cutover)

- Enumerate all writes to the two legacy localStorage keys, including inline
  template scripts, page controllers, undo paths, and storage-event handlers.
- Verify which live pages and previously cached scripts still use old writers.
- Add tests that emulate an uncooperative old tab writing between every
  read/write/verification boundary.

### Phase B: isolated draft reader and candidate import

- Read legacy maps without mutating them; validate shape and retain a local
  checkpoint for recovery.
- Compare candidates against authenticated server items and tombstones.
- Submit only explicit additive intents through the versioned API, each with
  idempotency key and expected revision; resolve CAS failures by re-fetching
  and recomputing candidates, not by blind retry.
- Do not interpret a missing item as an explicit removal.

### Phase C: new UI reads and writes server authority

- Route new saves, visits, and removals to item-level authenticated versioned
  operations; never use a full-map localStorage overwrite.
- Keep legacy keys separate as recovery evidence, not a second source of
  deletion truth.
- Confirm server state after an operation before showing success; if
  confirmation fails, report uncertainty and offer a concrete recheck action.

### Phase D: guarded release

- Exercise two new tabs, a stale legacy tab, two devices, offline/online,
  timeout-after-commit, duplicate retries, and tombstone conflicts.
- Confirm a real browser can keep an old tab open during the entire test.
- Check authorization, CSRF, session expiry, migration provenance, rollback,
  and production backup restoration in staging.
- Do not enable destructive UI or merge until all gates are explicitly met.

## Required regression scenarios

| Scenario | Expected result |
| --- | --- |
| Legacy tab writes old snapshot after new server save | Server save remains |
| Legacy tab writes old snapshot after explicit server deletion | Tombstone remains; no resurrection |
| Two new tabs save different exhibitions | Both remain |
| Two new tabs update same exhibition | One CAS wins; other re-reads and resolves |
| Legacy candidate missing a server exhibition | No deletion inferred |
| Legacy candidate conflicts with server tombstone | Review; no automatic restoration |
| Network timeout after server commit | Idempotent status check; no false success |
| Server or identity unavailable | No destructive write; actionable error |

## User-facing Traditional Chinese (Taiwan) copy

- Unknown result: 「目前無法確認這次變更是否已儲存。請重新開啟這個展覽，查看『想看』或『看過』的狀態，再決定是否操作。」
- Conflict requiring review: 「這個展覽在另一個裝置曾被移除，但這裡還保留著紀錄。你想保留這個展覽，還是維持移除？其他展覽不會受影響。」
- Temporary service failure: 「目前無法連線確認紀錄。請等網路恢復後，重新開啟這個展覽查看狀態；先不要重複點選。」

These messages are design copy, not evidence of a working UI.

## Release blocker

Do not treat the current cooperative localStorage lock or successful readback
as a complete stale-tab defense. A server-authoritative, isolated migration
must be implemented and tested before destructive cutover.
