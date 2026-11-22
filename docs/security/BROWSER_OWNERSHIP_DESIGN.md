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
