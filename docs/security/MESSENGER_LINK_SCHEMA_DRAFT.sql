-- REVIEW-ONLY draft; NOT applied to any Supabase project.
-- This replaces the earlier one-step schema for a two-secret protocol.
create table if not exists tan_private.messenger_link_challenges (
    token_hash text primary key check (token_hash ~ '^[0-9a-f]{64}$'),
    browser_claim_hash text not null unique
        check (browser_claim_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    verified_at timestamptz,
    consumed_at timestamptz,
    sender_id text,
    constraint link_challenge_expiry_check check (expires_at > created_at),
    constraint link_challenge_state_check check (
        (verified_at is null and consumed_at is null and sender_id is null)
        or (verified_at is not null and sender_id is not null)
    ),
    constraint link_challenge_claim_check check (
        consumed_at is null or (verified_at is not null and sender_id is not null)
    )
);
alter table tan_private.messenger_link_challenges enable row level security;
revoke all on tan_private.messenger_link_challenges from public, anon, authenticated;
-- No anon/authenticated policies. Only explicitly privileged server connection.
-- Browser claim secret must NEVER be included in Messenger messages, URLs,
-- logs, analytics, webhook payloads or other clients' responses.
-- Provision in disposable staging and review retention before deployment.
