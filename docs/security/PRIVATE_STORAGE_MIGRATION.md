# Private subscriber storage migration plan (Issue #83)

Status: design only; **do not deploy or delete existing data**.
Updated: 2026-11-22

## Verified current risks
- `app.py` saves subscriber and Web Push JSON to files in the application directory and calls `_save_to_github`, which commits updates to this public repository.
- The public repository contains `subscribers.json` and `push_subscribers.json`. Do not copy or display their contents in issues, logs, or PRs.
- The Messenger/Instagram webhook creates public GitHub Issues containing sender identifiers, message text, and attachment URLs.
- Render Free web services use ephemeral local filesystems, so removing GitHub persistence without replacement would lose writes on restart.

## Storage decision proposed
Use a private external PostgreSQL datastore such as Supabase Free for the initial migration, with a clear backup/restore process and an upgrade option. Render Free Postgres expires after 30 days; Render Free Key Value can lose data on restart. Supabase Free may pause after inactivity and does not include automatic backups; maintain encrypted offsite backups and monitor activity. **Do not** put database credentials or exports in Git.

## Required design
- Server-side database credentials in Render environment only. Do not expose service-role keys to browsers.
- Tables keyed by opaque internal identifiers, with unique constraints and transactional updates for users, ref mappings, preferences, and push subscriptions. Encrypt sensitive fields or use a documented appropriate protection strategy.
- Add server-side authentication and ownership verification before allowing client mutations. Messenger sender IDs, ref codes, and push endpoints are identifiers, not sufficient proof of authorization. Design a migration for existing subscribers.
- Replace public GitHub data writes only after verified private-store import and cutover. Avoid automatic fallback to public GitHub on failure.
- Replace public issue ingestion with a private inbox/workflow. Keep any user-submitted content and IDs out of public issue titles and bodies.

## Safe migration sequence
1. Owner privately creates a private database, restricted credentials, and an encrypted backup destination.
2. In a secure environment, export current subscriber and push data, validate counts/schema, and store an encrypted backup. Never download these data into AI chat or commit to the repo.
3. Implement private-store adapter behind a feature flag, migration scripts, read/write tests, and dual-read validation without public dual-writes.
4. Run a controlled migration and compare record counts, referential integrity, and notification behavior; agree on rollback.
5. Switch production writes to private store and disable GitHub data writes and public Messenger issue ingestion atomically.
6. Verify real flows and monitoring; then remove current public JSON files and address historical commits/issues, GitHub caches/forks, and credential rotation. Treat prior exposure as irreversible even after history rewrite.
7. Document data-retention, access, deletion and backup policy.

## Release gates
- Owner approval of data store, credentials, backups, downtime and migration.
- No public data in test fixtures. Test synthetic subscriber and push payloads.
- Unauthorized mutation tests, webhook verification tests, persistence/restart tests, notification regression tests, migration rollback drill.
- Never claim security is restored until live data exposure and historical public copies are addressed.

## References
- https://render.com/docs/free
- https://supabase.com/pricing
- https://supabase.com/kb/faqs/platform/free-project-pausing
