# Private subscriber adapter — draft only

This is **not production-integrated**. The new `private_subscriber_store.py` functions preserve the legacy JSON document shapes and use the private Supabase PostgreSQL schema.

## Requirements and caveats
- Install `psycopg[binary]` in the trusted execution environment before running the importer.
- Set `TAN_DATABASE_URL` to a server-side PostgreSQL connection string, using Supabase's supported IPv4-compatible pooler if Render's network requires it. Never commit or print credentials.
- `scripts/import_private_subscribers.py` must be run with repository root on `PYTHONPATH`. Default is dry-run; `--execute` writes only if the destination is empty.
- No production routes call this adapter yet. The legacy public GitHub writes remain in the deployed app.
- The adapter's full-document read/modify/write model is **not concurrency-safe** across independent application requests. Advisory locks in the write phase alone cannot protect changes made between a read and write. Replace with transactional per-user/per-endpoint operations before enabling production writes.
- Existing endpoints also have insufficient caller authorization; fix independently before cutover.
- Before running on live subscriber records, arrange encrypted backups, stop public writes, and verify no subscriber changes are lost during cutover.
- No real subscriber records should be placed in PRs, logs, or tests.
