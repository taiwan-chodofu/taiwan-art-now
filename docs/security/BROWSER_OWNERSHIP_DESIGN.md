# Browser subscriber ownership — implementation design (NOT deployed)

## Confirmed behavior in current draft source

- `templates/index.html` keeps Messenger `taiwan_art_ref` and connection state in `localStorage`. It calls `/api/subscribers/status?ref=...`, `/api/subscribers/sync` with `ref/favs/visited`, and `/api/subscribers/unsubscribe` with `ref`. Thus a ref acts as a bearer credential in today's browser flows, whether intended or not.
- The template obtains a browser PushSubscription via `serviceWorker.ready -> pushManager.getSubscription()` and sends `sub.toJSON()` to `/api/push/subscribe`. Subsequent favorite sync sends `endpoint/favs/visited`. Push endpoint alone is not proof of possession.
- The server's `/api/subscribers/link-ref` accepts any `ref` and `sender_id` pair for an existing user and rewrites `refs`; `/api/subscribers/settings` accepts `sender_id`; `/api/subscribers/status` accepts either `ref` or `sender_id`. These are not authenticated ownership proofs.
- The server's `/api/push/unsubscribe` and `/api/push/sync-favs` accept an endpoint without cryptographic proof. `/api/push/subscribe` accepts caller-supplied endpoint and keys.

## Recommended protocol — design only

1. **Messenger linking:** Require a short-lived, single-use, high-entropy server-generated challenge, completed through an authenticated Meta-originated event (validated signed webhook), before issuing a scoped browser session. Bind the session to the verified sender server-side; do not accept `sender_id` or a legacy `ref` as sufficient proof. Explicitly decide how legacy users re-link without losing their existing `favs`, `visited`, `weekly_digest`, or `fav_alerts`. Avoid putting long-lived bearer secrets in query parameters, referrer logs, analytics, or GitHub.
2. **Browser Push:** After `pushManager.subscribe`, issue a short-lived challenge delivered via a push message to the claimed endpoint and confirm it through the browser service worker before granting a scoped management session. Alternatively, use a separately authenticated account/session. A caller-supplied PushSubscription JSON or endpoint alone must not authorize read, overwrite, or delete. Rate-limit challenge issuance and prevent unsolicited push abuse. Assess service-worker and iOS/PWA support in staging.
3. **Session storage:** Use opaque random session tokens with server-side hashed storage, scope, expiry, rotation/revocation, SameSite Secure HttpOnly cookies, origin/CSRF protection for state-changing requests, and strict no-store on private responses. Treat existing localStorage `ref` as a *migration hint only*, not authorization.
4. **Route enforcement:** All eight browser endpoints must derive the authorized subscriber identity from the verified session; ignore or reject mismatching caller-supplied identifiers. Do not expose subscription preferences to unauthenticated callers. Require independent review of rate limiting, errors, cross-device migration, and privacy.
5. **Cutover:** Keep local favorites/visited intact while awaiting verified re-link. Run a staged, opt-in linking trial with synthetic accounts. Only after signed webhook verification, real-session negative tests (other-user ID, stolen ref, endpoint replay, CSRF), backup/restore drill and explicit owner approval should private DB writes be enabled.

## Release blockers and acceptance criteria

- [ ] Verify Meta challenge can be completed reliably in actual Messenger UX; test invalid/expired/reused challenge and mismatched sender.
- [ ] Verify browser Push challenge on supported browsers/iOS PWA, including notification permission denied/offline flows.
- [ ] Verify favorites/visited preserved on both failed and successful re-link; test legacy and cross-device users.
- [ ] Test eight routes with forged sender IDs, legacy refs, endpoints, CSRF and replay.
- [ ] Ensure no private data or auth tokens in URLs, public GitHub, logs, analytics, or CI artifacts.
- [ ] Independent encrypted backup + isolated restore test + writer quiescence, and explicit production approval.

This document is a design proposal, not a security implementation. Existing draft and production routes remain unsafe; no migration or deployment is authorized by this document.

## Implemented isolated challenge primitives (NOT authentication yet)

`messenger_link_challenge.py` now provides cryptographically random challenges, SHA-256 token hashing, bounded TTL (1–900 seconds; default 600), and a pure one-time consumption transition with optional pre-bound verified sender. Nine synthetic tests cover expiration, replay, wrong token, wrong sender, malformed records, and invalid TTL. **No persistent challenge table, atomic consume operation, Meta event binding, session issuance, route integration, or rate limiting exists yet.** In-memory/dict state is not suitable for multi-worker deployment. The `verified_sender_id` argument must only be supplied by a separately verified Meta webhook, never by a browser request. A signed webhook alone also does not prove that a browser initiating a challenge controls the Messenger account unless the full challenge flow binds them. Do not merge or deploy as an auth solution.

## Draft PostgreSQL atomic challenge adapter (NOT provisioned)

`messenger_link_store.py` drafts hashed challenge issuance and single conditional `UPDATE ... WHERE consumed_at IS NULL AND expires_at > now() RETURNING` consumption. The conditional update is the intended concurrency primitive; PostgreSQL row locking serializes competing updates. `docs/security/MESSENGER_LINK_SCHEMA_DRAFT.sql` is a **review-only** table definition and has NOT been applied to Supabase. Five fake-connection tests assert query shape and parameter handling, but do **not** prove actual concurrent transactions, Meta identity binding, failure rollback, rate limiting, or end-to-end login. Never use the returned challenge token in public logs or GitHub. Before any staging rollout, test two simultaneous independent database connections, transaction failure, TTL boundaries, challenge cleanup policy, webhook provenance, and verified browser session issuance.

## Rollback and disposable concurrency drill

The draft `messenger_link_store.py` now rolls back and propagates database exceptions for issue/consume; two synthetic mock tests assert rollback rather than partial success. `scripts/drill_messenger_link_concurrency.py` can test **two independent concurrent connections** only after an operator provisions a disposable isolated PostgreSQL database, creates the review-only challenge table, and sets `TAN_STAGING_DATABASE_URL` plus `TAN_STAGING_CONFIRM=disposable-isolated-database`. It refuses a missing staging URL and an identical `TAN_DATABASE_URL`, but distinct strings are **not proof** of isolation. Do not point it at the existing Supabase project. The script is not part of CI, has not been executed, and leaves a synthetic challenge row in the disposable database; destroy that database after the drill. The real concurrency guarantee is **not yet verified**.

## Additional staging guard (still NOT executed)

The opt-in concurrency drill now checks `current_database()` against an explicit `TAN_STAGING_DB_NAME` and requires exactly one `tan_private.staging_drill_guard` marker row. The marker DDL is in `docs/security/STAGING_DRILL_GUARD_DRAFT.sql` for a **separate disposable database only**. Five synthetic tests verify matching, wrong database, missing marker, invalid marker and generic database name. The guard reduces accidental targeting but does **not** prove the database is isolated or prevent someone from creating the marker in production; an operator must independently verify hosting/project identity before running. No real PostgreSQL concurrency drill has run.

## Isolated browser session primitives (NOT wired)

`browser_session.py` now contains 256-bit random session tokens, SHA-256 digests, bounded expiry (default one hour, maximum one day), pure validation and revocation transitions. Ten synthetic tests cover valid, expired, future, wrong, revoked and malformed sessions. `docs/security/BROWSER_SESSION_SCHEMA_DRAFT.sql` is a review-only private table design and has NOT been applied. **No authenticated cookie issuance, persistent DB session adapter, CSRF/origin validation, challenge-to-session transaction, rate limiting, or ownership enforcement on any of the eight browser API routes exists yet.** This code is not a deployable authentication solution. Cookie policy target: Secure + HttpOnly + SameSite, with explicit CSRF defense and no token in localStorage/URL/logs.
