"""Private inbound message storage. Server-side use only; no public fallback."""
from urllib.parse import urlsplit

def validate_inbound(channel, sender_id, message_text, image_urls):
    if channel not in ("Messenger", "Instagram"):
        raise ValueError("Unsupported channel")
    if not isinstance(sender_id, str) or not sender_id or len(sender_id) > 256:
        raise ValueError("Invalid sender")
    if not isinstance(message_text, str) or len(message_text) > 20000:
        raise ValueError("Invalid message")
    if not isinstance(image_urls, list) or len(image_urls) > 10:
        raise ValueError("Invalid images")
    for url in image_urls:
        if not isinstance(url, str) or len(url) > 4096:
            raise ValueError("Invalid image URL")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Image URL must be HTTPS")
    return channel, sender_id, message_text, image_urls

def store_inbound(channel, sender_id, message_text, image_urls):
    from psycopg.types.json import Jsonb
    from private_subscriber_store import _connect
    args = validate_inbound(channel, sender_id, message_text, image_urls)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """insert into tan_private.inbound_messages
               (channel,sender_id,message_text,image_urls)
               values (%s,%s,%s,%s)""",
            (args[0], args[1], args[2], Jsonb(args[3])),
        )
