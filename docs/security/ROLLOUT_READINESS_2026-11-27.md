# Rollout readiness — consolidated status, 2026-11-27

**Draft only. No production data change, no merge, no deploy authorization.** This
document supersedes the acceptance-evidence table in `STAGING_INTEGRATION_EXIT_CRITERIA.md`
(written at an earlier baseline that predates Discover/Home integration, the
auth-bootstrap webhook trigger, and the browser-claim UI — several of its rows
say "NOT RUN" for work that is now done and CI-green). That file's process
description (steps 1–8) and `STALE_TAB_CUTOVER_RUNBOOK_DRAFT.md`'s stop
conditions are still accurate design/decision-gate guidance and are not
replaced; only the *status snapshot* is. Treat this file as the single source
of truth for "what's actually true right now" on branch
`feat/private-subscriber-storage-adapter-83` (Draft PR #87); treat the other
`docs/security/*_DRAFT.md` files as design rationale, not status.

## The one fact that matters most: production behavior is unchanged today

No `TAN_ISOLATED_*_SYNC` config flag is set anywhere in `app.py` — they exist
only in the test fixture (`tests/fixtures/serve_disposable_sync.py`). Every
real page render (`index.html`, `discover.html`, `nearby.html`,
`exhibition_detail_page.html`) therefore still evaluates
`config.get("TAN_ISOLATED_..._SYNC", false)` to `false` and renders 100% of
the original legacy localStorage behavior. **None of the versioned-sync
rewrite work in this PR is live for any real user today, regardless of how
complete it is in code.** Flipping any of those four flags in production is
itself a future production action needing its own explicit approval and is
not covered by anything below.

Two things *are* already live in production from this PR, both deliberately
designed to be inert/fail-closed until the two pending approvals below land:

- `app.py`'s real `/webhook` handler now calls `mark_meta_verified` on a Meta
  referral (wrapped in `try/except: pass` since the schema doesn't exist yet
  — a no-op today, confirmed safe).
- `claim_blueprint`, `POST /api/private-auth/initiate`, and `GET
  /connect-devices` are registered unconditionally and reachable now (the
  latter linked from the site's "more" menu as of commit `dd1c792`). Both
  auth endpoints fail closed with a 503 "unavailable"/retry message — not a
  crash, not a partial write — because `TAN_RATE_LIMIT_HMAC_KEY` is unset and
  the `tan_private.messenger_link_challenges`/`browser_sessions` schema is not
  applied. Confirmed by reading the route handlers directly (both wrap the DB
  call in `try/except Exception`).

## Done and CI-verified (code level, isolated-sync fixture only)

| Area | Status |
|---|---|
| Detail page authenticated read/write, explicit tombstone restore | Done |
| Nearby page, same pattern | Done |
| Discover: authenticated action path, `recover()`/`dispose()`, tombstone-swipe restore UI, `createdRevisions` ownership re-check | Done |
| Discover: template wiring (increment 1 — swipe/undo/skip actions only; deck build, filter, restart, `saveDeckOrder` still read legacy localStorage even in isolated mode, by design — see DECISIONS.md 2026-11-26) | Partial, as scoped |
| Home: `toggleAction`, `migrateStore` collision fix, mylist-nav badge, `markVisitedFromMylist`/`removeFromMylist` | Done |
| `stable_key` date disambiguator (closes the legacy `_normalizeKey` collision precondition for production migration) | Done |
| Auth-bootstrap webhook trigger (`mark_meta_verified` wired into `/webhook`) | Done |
| `issue_pair` endpoint, `claim_blueprint`, `ProxyFix(x_for=1)`, rate limiter | Done |
| Browser-side claim UI (`/connect-devices`) with real Postgres E2E | Done |
| `/connect-devices` discoverable from site navigation | Done |

All of the above pass in CI (`synthetic-unit-tests`, `disposable-postgres-cas`,
`browser-sync-tests`, `draft-real-browser-e2e`, `draft-legacy-browser-e2e`) as
of commit `dd1c792`. "CI-verified" here means: against the disposable-Postgres
fixture and sanitized template renders, not a real staging deployment with
production-shaped traffic, real Messenger accounts, or real device hardware.

## Not done — still blocks enabling any `TAN_ISOLATED_*_SYNC` flag in production

Carried forward unchanged from `STAGING_INTEGRATION_EXIT_CRITERIA.md` /
`STALE_TAB_CUTOVER_RUNBOOK_DRAFT.md`, because none of this has been attempted
yet in this PR:

1. **Cross-screen / multi-tab / multi-device conflict testing.** Two real
   tabs or devices acting on the same owner's data concurrently, including an
   old cached/legacy tab writing after a modern tab, has only ever been
   tested per-screen with synthetic 1–2-tab Playwright scenarios inside a
   single CI job — never across screens in the same session, and never with
   a genuinely stale service-worker-cached tab from before this PR existed.
2. **Offline recovery.** Reconnect-and-refresh (`online`/`pageshow`) is
   implemented and unit-tested for detail/nearby; Discover/Home's own offline
   round-trip has not been separately exercised.
3. **Durable, independently-recoverable backup/restore.** Only the disposable
   CI database has ever been backed up and restored (`pg_dump`/`pg_restore`
   into a second throwaway database within the same CI job). No
   owner-controlled encrypted snapshot, retention policy, or restore-time
   measurement exists for anything resembling a real environment.
4. **Physical device / installed-PWA verification.** Every claim about
   stale-tab and offline behavior so far is Chromium-in-CI; no real iOS/
   Android installed PWA has been exercised against this code.

Stop conditions from `STALE_TAB_CUTOVER_RUNBOOK_DRAFT.md` remain in force
unchanged: a single active writer able to overwrite a complete map without
coordination, reproducible stale-tab loss without independent recoverability,
an untested backup/restore, unresolved ownership/CAS/rollback handling, or any
test that only detects loss rather than preventing/recovering it — any one of
these is still grounds to halt, and none has been newly disproven by the work
listed as "done" above (that work is about the authenticated-write path
itself, not about these four broader gates).

## Production actions still requiring the user's explicit approval

Neither of these is a code change in this branch; both are infrastructure
actions against the real environment and are listed here, not performed:

1. Apply the reviewed migration SQL (`docs/security/VERSIONED_SUBSCRIBER_SCHEMA_DRAFT.sql`,
   `MESSENGER_LINK_SCHEMA_DRAFT.sql`, `CLAIM_RATE_LIMIT_SCHEMA_DRAFT.sql`,
   `BROWSER_SESSION_SCHEMA_DRAFT.sql`, `SUBSCRIBER_REVIEW_CONFIRMATION_SCHEMA_DRAFT.sql`)
   to the real production database.
2. Set `TAN_RATE_LIMIT_HMAC_KEY` (≥32 chars) in Render's environment for the
   production service.

Until both land, every endpoint this PR adds continues to fail closed in
production exactly as designed — this is a safety property to preserve, not
a blocker to rush past.

## Current decision

Unchanged: **NO-GO for enabling any isolated-sync flag or merging PR #87 into
a live-serving state** until section "Not done" above is actually attempted
against a real (not disposable-CI) staging environment, and until the two
production actions above are separately approved and executed. The amount of
code now complete does not by itself change this — completeness and
rollout-safety are being tracked as two different gates on purpose.
