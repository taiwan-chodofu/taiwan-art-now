-- REVIEW ONLY. Run manually in a separately provisioned, disposable database.
-- Never execute in the existing production Supabase project.
create schema if not exists tan_private;
create table tan_private.staging_drill_guard (
    marker text primary key check (marker = 'disposable-isolated-database')
);
insert into tan_private.staging_drill_guard(marker)
values ('disposable-isolated-database');
revoke all on schema tan_private from public, anon, authenticated;
revoke all on tan_private.staging_drill_guard from public, anon, authenticated;
alter table tan_private.staging_drill_guard enable row level security;
-- Also provision MESSENGER_LINK_SCHEMA_DRAFT.sql in the disposable database.
-- Set TAN_STAGING_DB_NAME to the exact current_database() of that database.
-- The marker is an accident-prevention guard, NOT proof of isolation.
