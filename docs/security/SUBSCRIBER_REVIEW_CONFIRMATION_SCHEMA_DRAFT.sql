-- REVIEW ONLY. NEVER APPLY TO PRODUCTION WITHOUT SEPARATE APPROVAL.
-- Private, owner-bound, single-use confirmations for tombstone restoration.
-- Browser roles must never be granted direct access.
create table if not exists tan_private.subscriber_review_confirmations (
    token_hash bytea primary key,
    sender_id text not null references tan_private.messenger_subscribers(sender_id),
    kind text not null check (kind in ('favs', 'visited')),
    item_key text not null check (length(item_key) between 1 and 512),
    base_revision bigint not null check (base_revision >= 0),
    item_revision bigint not null check (item_revision > 0 and item_revision <= base_revision),
    choice text not null check (choice = 'keep_saved'),
    value_hash bytea not null,
    expires_at timestamptz not null,
    used_at timestamptz
);
create index if not exists subscriber_review_confirmations_expiry
    on tan_private.subscriber_review_confirmations (expires_at);
alter table tan_private.subscriber_review_confirmations enable row level security;
revoke all on tan_private.subscriber_review_confirmations
    from public, anon, authenticated;
