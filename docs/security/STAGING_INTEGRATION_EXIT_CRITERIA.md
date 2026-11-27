# Taiwan Art Now: isolated staging integration and exit criteria

**Superseded status snapshot — see `ROLLOUT_READINESS_2026-11-27.md` for the current state.**
The acceptance-evidence table below is frozen at head `b408a5e`; several rows
(Discover + detail integration, in particular) say "NOT RUN" for work that is
now done and CI-green. The process description (steps 1–8) is still accurate
decision-gate guidance and is not superseded, only this file's status claims.

**Draft only. No production changes, no real subscriber data, no merge or deploy authorization.**

## Verified in CI (head b408a5e)

- Synthetic unit and browser-sync tests passed.
- Disposable PostgreSQL CAS passed.
- Real Chromium suite passed, including staging integration of server-first actions against actual detail-page button markup. The page is a sanitized fixture, **not** a full live template or real authentication environment.

## Concrete staging architecture

1. Use a **separate** application instance and isolated PostgreSQL database, with distinct secrets, cookie domain, canonical origin and test-only messenger identities. Never point staging at production database, cookies or tokens.
2. Provision private schema from reviewed migration SQL, browser-session tables and subscriber state tables. Validate ownership/foreign keys, RLS/grants and transaction isolation. Deny access when the connector is absent.
3. Register the draft versioned API blueprint **only in staging**, under a staging-specific feature flag that fails closed. Verify same-origin checks, session expiry/revocation, missing cookies, cross-owner reads, CSRF/origin restrictions and concurrent revision conflicts with real HTTP and DB transactions.
4. Add an isolated staging entrypoint for Discover and detail that **replaces** old handlers, rather than attaching to existing legacy onclick functions. Confirm only one save handler exists per control and that no whole-map localStorage writes occur.
5. Verify authenticated GET → explicit action POST with base revision → fresh GET confirmation. Treat unknown POST outcomes as uncertain and lock the button until reload; do not retry blindly. Test Japanese and Traditional Chinese notices.
6. Use two devices and a third stale PWA tab. Prove server state survives stale localStorage overwrites; identify local-only changes separately. A missing old-map entry must never count as a deletion. Explicit tombstones must not resurrect.
7. Establish independent encrypted snapshot, manifest, retention and access controls; rehearse restoration to another isolated database. Test every exhibition entry, revisions, flags and tombstones. Document recovery time and any divergence.
8. Test rollback of feature gate without rolling back server revisions or overwriting any local maps. Stop on cross-owner access, unexplained disappearance, double handlers, mismatched backup or uncertain save falsely reported as success.

## Acceptance evidence to record

| Gate | Evidence required | Current status |
|---|---|---|
| Synthetic CI and browser tests | Green checks for PR head | PASS at b408a5e |
| Staging authentication + DB | Real HTTP traces, redacted, negative auth cases | NOT RUN |
| Discover + detail integration | Screenshots and automated end-to-end cases | Detail markup fixture only; Discover NOT RUN |
| Old cached tab / PWA | Real stale-client and two-device traces | Synthetic only |
| Durable backup + restore | Independent manifest and isolated restore comparison | NOT RUN |
| Operational rollback | Fail-closed flag and drill | NOT RUN |
| Production release | Explicit approval after every gate | NOT AUTHORIZED |

## Do not confuse these outcomes

- Green Playwright fixture != production integration.
- Passing disposable PostgreSQL tests != real staging database and authentication.
- LocalStorage isolation != recovering old local-only user data.
- Draft PR mergeability != permission to merge.

**Next executable milestone:** provision an isolated staging app/database and run authenticated HTTP integration. Do not register the blueprint in production app.py.
