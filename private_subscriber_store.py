"""Server-only PostgreSQL adapter. Not wired to production until approved cutover.

Uses a direct/pooled PostgreSQL connection; never expose credentials to the browser.
The private schema is not exposed to the Supabase Data API.
"""
import json
import os

def _connect():
    import psycopg
    url = os.environ.get("TAN_DATABASE_URL")
    if not url:
        raise RuntimeError("TAN_DATABASE_URL is required")
    return psycopg.connect(url, connect_timeout=10)

def load_messenger():
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("select sender_id, profile from tan_private.messenger_subscribers")
        users = {sid: profile for sid, profile in cur.fetchall()}
        cur.execute("select ref_code, sender_id from tan_private.messenger_refs")
        refs = dict(cur.fetchall())
    return {"users": users, "refs": refs}

def save_messenger(data):
    users = data.get("users", {})
    refs = data.get("refs", {})
    if not isinstance(users, dict) or not isinstance(refs, dict):
        raise ValueError("Invalid subscriber document")
    if any(sid not in users for sid in refs.values()):
        raise ValueError("Reference points to missing subscriber")
    from psycopg.types.json import Jsonb
    with _connect() as conn, conn.cursor() as cur:
        # Advisory lock serializes writers; caller must coordinate read-modify-write.
        cur.execute("select pg_advisory_xact_lock(830083)")
        cur.execute("delete from tan_private.messenger_refs")
        cur.execute("delete from tan_private.messenger_subscribers where not (sender_id = any(%s))", (list(users),))
        for sid, profile in users.items():
            cur.execute("""insert into tan_private.messenger_subscribers(sender_id,profile)
                           values (%s,%s) on conflict(sender_id)
                           do update set profile=excluded.profile,updated_at=now()""", (sid, Jsonb(profile)))
        for ref, sid in refs.items():
            cur.execute("""insert into tan_private.messenger_refs(ref_code,sender_id)
                           values (%s,%s)""", (ref, sid))

def load_push():
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("select endpoint, subscription from tan_private.web_push_subscriptions")
        return {"subscriptions": dict(cur.fetchall())}

def save_push(data):
    subscriptions = data.get("subscriptions", {})
    if not isinstance(subscriptions, dict):
        raise ValueError("Invalid push document")
    from psycopg.types.json import Jsonb
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(830084)")
        cur.execute("delete from tan_private.web_push_subscriptions where not (endpoint = any(%s))", (list(subscriptions),))
        for endpoint, subscription in subscriptions.items():
            cur.execute("""insert into tan_private.web_push_subscriptions(endpoint,subscription)
                           values (%s,%s) on conflict(endpoint)
                           do update set subscription=excluded.subscription,updated_at=now()""",
                        (endpoint, Jsonb(subscription)))

def mutate_messenger(mutator):
    """Atomically read, mutate, and persist one legacy Messenger document.

    The callback receives a mutable document and must not perform network I/O.
    All callers MUST use this instead of separate load/save calls to avoid
    lost updates. Raises on failure; no public-GitHub fallback.
    """
    from psycopg.types.json import Jsonb
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(830083)")
        cur.execute("select sender_id, profile from tan_private.messenger_subscribers")
        data = {"users": dict(cur.fetchall())}
        cur.execute("select ref_code, sender_id from tan_private.messenger_refs")
        data["refs"] = dict(cur.fetchall())
        result = mutator(data)
        users, refs = data["users"], data["refs"]
        if not isinstance(users, dict) or not isinstance(refs, dict):
            raise ValueError("Invalid subscriber document")
        if any(sid not in users for sid in refs.values()):
            raise ValueError("Orphan subscriber reference")
        cur.execute("delete from tan_private.messenger_refs")
        cur.execute("delete from tan_private.messenger_subscribers where not (sender_id = any(%s))", (list(users),))
        for sid, profile in users.items():
            cur.execute("""insert into tan_private.messenger_subscribers(sender_id,profile)
                           values (%s,%s) on conflict(sender_id)
                           do update set profile=excluded.profile,updated_at=now()""", (sid, Jsonb(profile)))
        for ref, sid in refs.items():
            cur.execute("insert into tan_private.messenger_refs(ref_code,sender_id) values (%s,%s)", (ref,sid))
        return result


def mutate_push(mutator):
    """Atomically read, mutate, and persist the Web Push document."""
    from psycopg.types.json import Jsonb
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(830084)")
        cur.execute("select endpoint, subscription from tan_private.web_push_subscriptions")
        data = {"subscriptions": dict(cur.fetchall())}
        result = mutator(data)
        subscriptions = data["subscriptions"]
        if not isinstance(subscriptions, dict):
            raise ValueError("Invalid push document")
        cur.execute("delete from tan_private.web_push_subscriptions where not (endpoint = any(%s))", (list(subscriptions),))
        for endpoint, subscription in subscriptions.items():
            cur.execute("""insert into tan_private.web_push_subscriptions(endpoint,subscription)
                           values (%s,%s) on conflict(endpoint)
                           do update set subscription=excluded.subscription,updated_at=now()""",
                        (endpoint, Jsonb(subscription)))
        return result

def import_snapshot_if_empty(messenger, push):
    """Atomically import both snapshots, refusing a nonempty destination.

    This is an initial import only. A live cutover still requires pausing
    legacy writers, capturing a fresh snapshot, and verifying consistency.
    """
    from psycopg.types.json import Jsonb
    users = messenger.get("users")
    refs = messenger.get("refs", {})
    subscriptions = push.get("subscriptions")
    if not all(isinstance(x, dict) for x in (users, refs, subscriptions)):
        raise ValueError("Invalid subscriber snapshot")
    if any(not isinstance(sid, str) or not isinstance(profile, dict)
           for sid, profile in users.items()):
        raise ValueError("Invalid Messenger subscriber")
    if any(not isinstance(ref, str) or sid not in users
           for ref, sid in refs.items()):
        raise ValueError("Invalid Messenger ref")
    if any(not isinstance(endpoint, str) or not isinstance(info, dict)
           or info.get("endpoint") != endpoint
           for endpoint, info in subscriptions.items()):
        raise ValueError("Invalid Web Push subscription")
    with _connect() as conn, conn.cursor() as cur:
        # Both locks in consistent order; check emptiness inside same transaction.
        cur.execute("select pg_advisory_xact_lock(830083)")
        cur.execute("select pg_advisory_xact_lock(830084)")
        for table in ("messenger_subscribers", "messenger_refs", "web_push_subscriptions"):
            cur.execute("select exists(select 1 from tan_private." + table + ")")
            if cur.fetchone()[0]:
                raise RuntimeError("Destination not empty; import refused")
        for sid, profile in users.items():
            cur.execute("insert into tan_private.messenger_subscribers(sender_id,profile) values (%s,%s)",
                        (sid, Jsonb(profile)))
        for ref, sid in refs.items():
            cur.execute("insert into tan_private.messenger_refs(ref_code,sender_id) values (%s,%s)",
                        (ref, sid))
        for endpoint, info in subscriptions.items():
            cur.execute("insert into tan_private.web_push_subscriptions(endpoint,subscription) values (%s,%s)",
                        (endpoint, Jsonb(info)))
        cur.execute("select sender_id,profile from tan_private.messenger_subscribers")
        stored_users = dict(cur.fetchall())
        cur.execute("select ref_code,sender_id from tan_private.messenger_refs")
        stored_refs = dict(cur.fetchall())
        cur.execute("select endpoint,subscription from tan_private.web_push_subscriptions")
        stored_push = dict(cur.fetchall())
        if stored_users != users or stored_refs != refs or stored_push != subscriptions:
            raise RuntimeError("Round-trip verification failed; rolling back")
    return {"users": len(users), "refs": len(refs), "push": len(subscriptions)}
