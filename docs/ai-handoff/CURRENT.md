# Current AI handoff

Updated: 2026-11-22
Author: ChatGPT
Status: Collaboration infrastructure proposed on `chore/ai-handoff-foundation`; awaiting review and merge.

## Goal
Establish a durable handoff between ChatGPT and Claude Code for Taiwan Art Now, then address the highest-priority security and data-integrity issues incrementally.

## Findings from prior static code review (reconfirm before implementing)
- `app.py`: subscriber and Web Push mutation endpoints rely on caller-supplied identifiers; review authentication/authorization and backwards compatibility.
- `app.py`: preview-token fallback should be removed or fail closed; review deployment configuration.
- `scraper.py`: expired exhibition handling can write manual/archive files during scraping; review side effects and data consistency.
- `.github/workflows/archive-expired.yml`: archive and validation steps use `|| true`; investigate correct no-op versus error exit semantics.
- Exhibition detail and OG URLs use museum-local array indexes, which may change after reordering.

## Proposed implementation order
1. Security: subscriber API authorization and preview access. Design safe migration for existing users before code changes.
2. Data integrity: archive/validation workflow, atomic writes, tests, and failure handling.
3. Stable exhibition IDs: legacy redirects and migration for local favorites/visited references.

## Current work
- Created shared AI collaboration rules, Claude Code entry point, and handoff/decision log in a feature branch.
- No application code or production exhibition/subscriber data changed.
- No runtime tests run for application behavior.

## Next agent
- Review this collaboration PR; do not merge without owner approval.
- After merge, open a scoped issue for security review and implementation.
- Before modifying subscriber flows, document threat model, credential verification, backward-compatible migration, rollback and tests.

## Source of truth
Repository: https://github.com/taiwan-chodofu/taiwan-art-now
This file records shared work only; private AI conversation history is not automatically synced.

## 2026-11-24 — Active handoff for #83 / draft PR #87

Branch feat/private-subscriber-storage-adapter-83, reviewed baseline aada244. The PR reports 784 commits and 210 changed files at this baseline. Its scope grew from the private storage adapter and guarded import to session ownership, revisioned item writes, migration review, four-page legacy writer audits, browser fixtures and backup drills. The older collaboration-foundation status above is historical. Latest baseline Actions run 45206023027 passed all five jobs.

This change updates the isolated staging app factory, draft browser bridge/lifecycle and explicit restore client, isolated exhibition fixture, browser/unit/DB tests and handoff notes. The review fixture previously sent tombstone restores to the ordinary changes route, which the server rejects. Explicit review now uses the actual consent protocol. Ambiguous writes and stale descriptors trigger a read-only check. Old replies cannot replace a later displayed revision. The PostgreSQL drill now exports the inserted source row, and a read-only staging factory exercises interruption between issuing and consuming a confirmation.

Local checks: 407 Node tests passed. Python discovery ran 336 with 18 database-only skips. Local Chromium startup was denied by the executor's socket policy; check the latest Actions run for Chromium and disposable PostgreSQL. Real hardware with a previously installed PWA, independently stored encrypted backups, isolated-environment restore with retention and timing, provider routing/draining during rollback, and existing-user migration remain unverified. Production release is blocked. For the next staging rehearsal use only synthetic identities and a separate database. Compare per-item values, revisions and tombstones before and after the rehearsal. This PR remains draft.

Follow-up: run 45393903927 exposed a test counting consumed confirmations for all owners. Scope that assertion to its issued token. The installed service worker previously cached every successful GET and could replay an offline response with its original no-store header. The draft reader now checks the controlling worker before fetching private state and discards results across controller changes. The updated worker bypasses the private endpoint on both online and offline paths. Added a real Chromium worker installation/offline test on a temporary loopback origin. Local Node suite: 409 passed. Physical iOS PWA upgrade remains pending.

Additional integration drill: the disposable DB job starts a loopback-only TLS Flask app, uses two independent Chromium cookie sessions, drops the consume response after a real PostgreSQL commit, checks both flags, then restores the entire private schema with pg_dump/pg_restore into an empty second database and compares every row of each source table. This measures disposable recovery only. The page cancels work before POST if disposed during a read or consent issuance. Both collections and the migration review use the same accepted state, and server comparisons tolerate JSON object member reordering. Local verification: 412 Node tests and Python discovery (336 run, 18 DB-only skips). The installed-worker and five-job baseline is run 45394367135. The PR Checks tab tracks the new drill.

Run 45394876665 passed all five jobs at ef5cb0a, including the TLS browser/Flask/PostgreSQL drill, simulated read-only restart, installed-worker offline test and separate-database restore. Final follow-up consolidates authenticated reads for the earlier bootstrap coordinator, verifies its writes by GET, uses structural JSON comparison for additive migration and recovery, and confines the service worker network-only exception to the private API namespace to preserve the public exhibition offline behavior. Node verification: 413 passed. The PR description records the final head CI result.

## 2026-11-24 — Migration acknowledgement follow-up
Reviewed the additive migration entrypoint at afde858. It still acknowledged a successful POST without authenticated readback. Require structural equality between the validated POST state and a fresh authenticated GET before reporting saved, including paths where an old tab changed local storage during the request. Treat a server error after POST as unknown_commit. Preserve the existing one-retry limit for explicit 409 responses. Added regressions for missing durable readback, JSONB ordering with independent want/seen and a 503 after POST. Local Node suite passed 416 tests. Updated existing mocked review flows to model the new readback before a later deletion or unavailable read. Production migration remains blocked by the existing physical-device and legacy-writer gates.

## 2026-11-24 — Real legacy migration rehearsal
Added a separate synthetic owner with two cookie sessions to the disposable HTTPS fixture. The browser migrates a real legacy favorite object and visited ISO timestamp, loses the POST reply after the database commit, and checks that both local maps remain byte-for-byte unchanged. An explicit second invocation reads the existing state without another POST. The second browser removes want, and the first browser's stale local registration must produce a deletion review without restoring it or changing seen. This exercises the existing migration implementation through authenticated Flask and PostgreSQL. Syntax and diff checks passed locally. Full browser evidence is recorded in PR Checks for this commit.

## 2026-11-25 — Complete detail template staging integration
The actual detail template now selects one writer at server render time using TAN_ISOLATED_DETAIL_SYNC, enabled only by the disposable fixture. It emits disabled controls with no legacy handlers in isolated mode and mounts the authenticated lifecycle. Default rendering retains legacy handlers. A full-template browser test checks three mutations, independent flags, absence of the legacy function and unchanged local favorites. Local render checks passed in both modes, 416 Node tests passed, and Python discovery passed 336 tests with 18 DB-only skips. CI must verify the full Chromium/PostgreSQL path. Remaining work includes restoration from tombstones on the real detail surface, other three page integrations, stable-key migration and physical old PWA verification.

## 2026-11-25 — Explicit detail restoration
The isolated detail page labels a tombstoned registration as an explicit restore action in Japanese and Taiwanese Mandarin. Its user click invokes the existing owner-bound issue/consume protocol with the displayed revision and tombstone revision. Both buttons share the existing busy lock. Expired review triggers read-only refresh and an uncertain consume never resends. The real detail browser test now drops a committed consume response and also clicks a stale restore descriptor after another tab has restored it. Local Node suite passed 416 tests; full browser and database evidence is tracked by PR Checks. Other page integrations and physical PWA validation remain pending.
