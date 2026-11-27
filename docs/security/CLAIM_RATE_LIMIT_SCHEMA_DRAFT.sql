-- REVIEW-ONLY. DO NOT apply to production without explicit approval.
-- Server-only fixed-window counters. Use a 32+ char private HMAC key.
create table if not exists tan_private.auth_rate_limits (
    bucket_hash text primary key check (bucket_hash ~ '^[0-9a-f]{64}$'),
    attempts integer not null check (attempts >= 1),
    expires_at timestamptz not null
);
alter table tan_private.auth_rate_limits enable row level security;
revoke all on tan_private.auth_rate_limits from public, anon, authenticated;
-- Cleanup/retention policy and key rotation are pending review.
-- The server must not trust arbitrary forwarded IP headers.
