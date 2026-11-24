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
