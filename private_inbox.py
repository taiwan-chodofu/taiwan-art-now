"""Private inbound message storage with retry deduplication."""
import hashlib
import json
import re
from urllib.parse import urlsplit


def event_key_for(channel, sender_id, event):
    """Stable key for Meta retries, without storing raw identifiers in the key.

    Message mid is preferred; otherwise hash the full signed event payload.
    A byte-identical event replay deduplicates; distinct timestamps remain distinct.
    """
    if not isinstance(event, dict):
        raise ValueError("Invalid event")
    message = event.get("message") or {}
    if not isinstance(message, dict):
        raise ValueError("Invalid event message")
    mid = message.get("mid")
    if isinstance(mid, str) and mid:
        payload = ["meta-mid", channel, sender_id, mid]
    else:
        payload = ["meta-event", channel, sender_id, event]
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_inbound(channel, sender_id, message_text, image_urls, event_key):
    if channel not in ("Messenger", "Instagram"):
        raise ValueError("Unsupported channel")
    if not isinstance(sender_id, str) or not sender_id or len(sender_id) > 256:
        raise ValueError("Invalid sender")
    if not isinstance(message_text, str) or len(message_text) > 20000:
        raise ValueError("Invalid message")
    if not isinstance(event_key, str) or re.fullmatch(r"[0-9a-f]{64}", event_key) is None:
        raise ValueError("Invalid event key")
    if not isinstance(image_urls, list) or len(image_urls) > 10:
        raise ValueError("Invalid images")
    for url in image_urls:
        if not isinstance(url, str) or len(url) > 4096:
            raise ValueError("Invalid image URL")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or any(c.isspace() for c in url)):
            raise ValueError("Image URL must be HTTPS")
    return channel, sender_id, message_text, image_urls, event_key


def store_inbound(channel, sender_id, message_text, image_urls, event_key):
    from psycopg.types.json import Jsonb
    from private_subscriber_store import _connect
    args = validate_inbound(channel, sender_id, message_text, image_urls, event_key)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """insert into tan_private.inbound_messages
               (channel,sender_id,message_text,image_urls,event_key)
               values (%s,%s,%s,%s,%s)
               on conflict (event_key) where event_key is not null do nothing""",
            (args[0], args[1], args[2], Jsonb(args[3]), args[4]),
        )
        return cur.rowcount == 1
