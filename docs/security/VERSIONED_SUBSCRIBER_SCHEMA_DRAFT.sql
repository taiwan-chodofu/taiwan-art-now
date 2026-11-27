-- REVIEW ONLY. DO NOT APPLY TO PRODUCTION.
-- Requires an independently verified disposable staging database.
-- Browser/anon/authenticated roles have no table access.
create table if not exists tan_private.subscriber_sync_states (
    sender_id text primary key references tan_private.messenger_subscribers(sender_id),
    state jsonb not null,
    updated_at timestamptz not null default now(),
    constraint sync_state_shape_check check (
        jsonb_typeof(state) = 'object'
        and state ? 'revision'
        and state ? 'favs'
        and state ? 'visited'
        and jsonb_typeof(state->'favs') = 'object'
        and jsonb_typeof(state->'visited') = 'object'
        and jsonb_typeof(state->'revision') = 'number'
        and (state->>'revision') ~ '^(0|[1-9][0-9]{0,18})$'
        and (state->>'revision')::numeric <= 9223372036854775807
    )
);
alter table tan_private.subscriber_sync_states enable row level security;
revoke all on tan_private.subscriber_sync_states from public, anon, authenticated;
