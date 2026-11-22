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
