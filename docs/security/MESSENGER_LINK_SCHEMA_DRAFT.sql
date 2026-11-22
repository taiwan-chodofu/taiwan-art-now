-- REVIEW-ONLY draft; not applied to any Supabase project.
-- Provision only after explicit approval and independent staging review.
create table if not exists tan_private.messenger_link_challenges (
    token_hash text primary key
      check (token_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    consumed_at timestamptz,
    sender_id text,
    constraint link_challenge_expiry_check check (expires_at > created_at),
    constraint link_challenge_consume_check check (
      (consumed_at is null and sender_id is null)
      or (consumed_at is not null and sender_id is not null)
    )
);
alter table tan_private.messenger_link_challenges enable row level security;
revoke all on tan_private.messenger_link_challenges from public, anon, authenticated;
-- No anon/authenticated policies. Only explicitly privileged server connection.
-- Configure retention and secure cleanup before deploying; no deletion authorized.
