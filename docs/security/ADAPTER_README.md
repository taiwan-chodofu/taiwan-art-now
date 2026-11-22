# Private subscriber adapter — draft only

This is **not production-integrated**. The new `private_subscriber_store.py` functions preserve the legacy JSON document shapes and use the private Supabase PostgreSQL schema.

## Requirements and caveats
- Install `psycopg[binary]` in the trusted execution environment before running the importer.
- Set `TAN_DATABASE_URL` to a server-side PostgreSQL connection string, using Supabase's supported IPv4-compatible pooler if Render's network requires it. Never commit or print credentials.
- `scripts/import_private_subscribers.py` must be run with repository root on `PYTHONPATH`. Default is dry-run; `--execute` uses one transaction for both datasets, checks that the destination is empty under locks, and compares the full round-trip before commit.
- No production routes call this adapter yet. The legacy public GitHub writes remain in the deployed app.
- The adapter now includes `mutate_messenger(callback)` and `mutate_push(callback)` which read and write under one PostgreSQL transaction and advisory lock, avoiding lost updates **when every writer uses these methods**. The original `load_*`/`save_*` functions are still unsafe as separate read-modify-write pairs; production routes are not yet migrated. Prefer per-row updates for long-term scalability.
- Existing endpoints also have insufficient caller authorization; fix independently before cutover.
- Synthetic-only validation tests are in `tests/test_private_subscriber_import.py`; five equivalent local validation cases passed. No live integration test has been run for the Python adapter; only an isolated SQL transaction smoke test using synthetic rows with ROLLBACK has passed.
- Run validation tests with `python -m unittest discover -s tests -p 'test_private_subscriber_import.py'`.
- Import is atomic across both datasets, but requires a **quiesced source**: the public GitHub JSON can change while being exported, and importer cannot detect changes after snapshot. Obtain an owner-controlled encrypted backup and plan a maintenance window before real migration.
- Before running on live subscriber records, arrange encrypted backups, stop public writes, and verify no subscriber changes are lost during cutover.
- No real subscriber records should be placed in PRs, logs, or tests.

## Transactional route migration building blocks

`subscriber_mutations.py` now defines pure, testable operations for Messenger favorites/visited, ref linking, unsubscribe, notification settings, and Web Push subscribe/sync/unsubscribe. Call them **inside** `mutate_messenger(lambda state: ...)` or `mutate_push(lambda state: ...)` only **after** independent caller authorization. The pure functions are not an authorization system.

Tests: `python -m unittest discover -s tests -p 'test_subscriber_mutations.py'`.

Do **not** wire these into Flask routes yet. The existing API accepts client-controlled sender IDs, refs and endpoints; switching its persistence to the private DB without fixing authorization would carry the same IDOR vulnerability into the new store. Messenger identity needs verified platform-originated proof, and browser subscriptions need an authenticated ownership mechanism or a carefully designed possession-token scheme. Never treat endpoint strings or publicly guessable identifiers as sufficient authorization.

No claim is made that the new transition tests have been executed in CI yet.

## Meta webhook authentication — draft integration

The draft now validates `X-Hub-Signature-256` against the exact raw request body with HMAC-SHA256 and constant-time comparison **before parsing events**. The verifier fails closed when `META_APP_SECRET` is absent. This protects the POST `/webhook` origin, but does **not** authenticate separate browser-facing subscriber APIs. Seven synthetic-only verifier tests were added in `tests/test_webhook_security.py`.

**Release gate:** Set `META_APP_SECRET` to the correct Meta App Secret in Render's server-side environment, verify legitimate Meta webhook deliveries in a staging deployment, and only then merge/deploy. Never place the secret in GitHub, issues, PRs, logs, or the browser. Without this setup, all webhook POSTs will receive HTTP 403. GET verification remains a separate flow.

The **deployed** webhook still creates public GitHub issues containing sender IDs and messages; the **draft PR** replaces this with private intake. The deployed public JSON persistence also remains unchanged.

## Private inbound message inbox — draft integration

Supabase now has `tan_private.inbound_messages` (RLS on, no anon/authenticated grants). An isolated SQL insert/read smoke test succeeded and was rolled back.

The draft Flask webhook now calls `private_inbox.store_inbound` instead of creating a **public GitHub issue** containing sender ID, text, and images. On storage failure it returns HTTP 503 and does not fall back to public GitHub. This change is **not deployed**.

Ten synthetic-only inbox validation/dedup tests are present (execution not yet verified). The inbox now has a unique `event_key` index; `private_inbox.event_key_for` prefers Meta message `mid` and falls back to a hash of the complete event. Synthetic SQL duplicate-insert test passed (2 attempts -> 1 row, rolled back). Verify actual Messenger/Instagram event payload shapes in staging. **Only inbox insertion is deduplicated**: earlier subscription side effects and multi-event webhook batch retries are not fully idempotent. Define a private admin review workflow, retention policy, and redacted operational logging before cutover.

**Deployment blockers:** Set `META_APP_SECRET` and `TAN_DATABASE_URL` securely in Render; verify database connectivity and Meta signature validation in staging; ensure no public GitHub message creation path remains; establish backup/restore; confirm privacy notice and retention; verify retries. Do not merge/deploy this PR as-is.

## Owner inbox review (CLI only)

`private_inbox_admin.py` offers metadata-only listing and status changes, with no new HTTP admin endpoint. Run only from a trusted owner environment with a server-side `TAN_DATABASE_URL`:

```sh
python private_inbox_admin.py list --status new --limit 20
python private_inbox_admin.py mark 123 --status reviewed
```

The list deliberately excludes sender IDs, message text, image URLs, and event keys. The tool does not yet offer secure viewing of full message content; a separate authenticated private review interface or trusted console workflow is required. Avoid terminal transcripts, screenshots, or logging of subscriber data. Five synthetic-only argument validation tests are included in `tests/test_private_inbox_admin.py` (not yet executed). No production connection has been configured.

Retention period and deletion automation still need owner approval; do not silently delete existing submissions.

## Automated checks and release blockers

The draft adds `.github/workflows/private-subscriber-tests.yml` for syntax compilation and synthetic-only tests. The workflow requires no database credentials and must pass before merge. GitHub Actions run 45024353595 completed successfully on the draft branch: 20 private tests + 9 mutation tests + 7 webhook signature tests = **36 synthetic unit tests passed**, and syntax compilation passed. This is not a live database, Flask request, or Meta webhook integration test.

The draft also extends `.gitignore` for local private backup files. **Gitignore does not untrack existing committed `subscribers.json` or `push_subscribers.json`, nor erase Git history.** These remain separate urgent privacy remediation tasks. Never store plaintext backups in the repository.

### Operational log privacy

The draft webhook now logs only a fixed error message on private inbox persistence failure, rather than exception details that could contain personal data or SQL parameters. It still returns HTTP 503 to request retry. Audit other logging paths before deployment.

## Meta GET verification token (security regression)

The draft removes the hard-coded GET webhook verification token and reads `MESSENGER_VERIFY_TOKEN` from Render's server-side environment. When missing, GET verification returns 403. **Before deployment**, set both `MESSENGER_VERIFY_TOKEN` (the value configured in the Meta developer webhook settings) and `META_APP_SECRET` (the Meta app secret). The previously hard-coded token must be treated as exposed and rotated at Meta. Do not commit either secret.

The draft now adds AST-based regression checks for the actual Flask source: GET token configuration, POST signature verification before JSON parsing, no public GitHub Issue writes in the webhook function, and redacted persistence failure logging. These are **static source checks**, not live Flask request tests. The CI workflow was updated to include them; verify the newest run before merge.

## Synthetic Flask HTTP request tests

`tests/test_flask_webhook_http.py` extracts the actual `webhook_receive` function from `app.py` via Python AST and registers it on an isolated Flask test app, avoiding scraper startup, production subscriber JSON and live credentials. Tests cover unsigned 403, tampered 403, signed empty batch 200, signed message to a mocked private inbox, and private storage failure 503. This exercises Flask request parsing and signature verification, **but not the full application startup or live Meta/Supabase connectivity**. GitHub Actions installs pinned Flask for this test. Check the newest CI run; success was not yet available at the time of this commit.

## Message replay side effects

For ordinary inbound submissions, `store_inbound` returns False on duplicate `event_key`. The draft webhook now skips the subsequent auto-subscription write on duplicates; a synthetic Flask HTTP test checks this. This does **not** make the whole webhook idempotent: standalone referrals, postbacks, subscribe/unsubscribe keywords and outgoing replies still need transactional deduplication. A 503 after earlier events in a multi-event batch can replay those earlier side effects. Do not deploy before those flows are handled safely and verified in staging.

## Signed batch prevalidation

The draft now validates Meta's top-level object, entry and messaging arrays, sender IDs, message/postback/referral objects, text and attachment shapes **before processing any event in a batch**. Malformed signed payloads return 400 without private inbox or subscription writes. Synthetic Flask tests include a batch whose first event is valid and second is malformed, guarding against partial processing. This is structural validation, not an exhaustive Meta schema validator; limits and attachment URLs still need staging checks. This does not solve partial side effects caused by database errors in otherwise valid batches, nor replay of subscription commands and replies.

## Input hardening and unresolved command replay

The draft validates inbox dedup keys as 64 lowercase hexadecimal characters, rejects non-object events/messages, and rejects whitespace in HTTPS image URLs. GET Meta verification now also requires a challenge string. Synthetic regression tests were added; check latest CI.

**Do not treat subscriber commands as idempotent yet.** Referrals, postbacks, subscribe/unsubscribe keywords and outbound replies still mutate legacy public JSON and/or send replies without an atomic event-processing ledger. Reusing the inbound message inbox's unique key as a command ledger without a transactional claim/complete/retry design could lose commands after crashes. Before implementation, define a separate event state machine (pending/processing/completed with retry recovery) and coordinate its transaction with subscriber writes; do not deploy the partial draft.
