-- REVIEW-ONLY; not applied to any Supabase project.
create table if not exists tan_private.browser_sessions (
    token_hash text primary key check (token_hash ~ '^[0-9a-f]{64}$'),
    sender_id text not null references tan_private.messenger_subscribers(sender_id),
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    revoked_at timestamptz,
    constraint browser_session_expiry_check check (expires_at > created_at)
);
create index if not exists browser_sessions_sender_idx
    on tan_private.browser_sessions(sender_id);
alter table tan_private.browser_sessions enable row level security;
revoke all on tan_private.browser_sessions from public, anon, authenticated;
-- No anon/authenticated policies; server-only DB access.
-- Session tokens must be issued only after verified Meta challenge completion.
-- Cookie transport, CSRF defenses, atomic revocation and cleanup NOT implemented.
