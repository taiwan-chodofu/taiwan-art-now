"""Owner-only command-line review of private inbound messages.

Runs in a trusted shell with TAN_DATABASE_URL. No public HTTP route.
Default output contains no sender IDs, message text, image URLs or secrets.
"""
import argparse
from private_subscriber_store import _connect

VALID_STATUSES = ("new", "reviewed", "archived")


def list_metadata(limit=20, status="new"):
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if status not in VALID_STATUSES:
        raise ValueError("invalid status")
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """select id,channel,received_at,status,
                      length(message_text),jsonb_array_length(image_urls)
               from tan_private.inbound_messages
               where status=%s order by received_at desc,id desc limit %s""",
            (status, limit),
        )
        return cur.fetchall()


def mark_status(message_id, status):
    if not isinstance(message_id, int) or message_id < 1:
        raise ValueError("invalid message ID")
    if status not in ("reviewed", "archived"):
        raise ValueError("invalid destination status")
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "update tan_private.inbound_messages set status=%s where id=%s",
            (status, message_id),
        )
        return cur.rowcount == 1


def main():
    parser = argparse.ArgumentParser(description="Private inbox metadata review")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--status", choices=VALID_STATUSES, default="new")
    listing.add_argument("--limit", type=int, default=20)
    marking = sub.add_parser("mark")
    marking.add_argument("message_id", type=int)
    marking.add_argument("--status", choices=("reviewed", "archived"), required=True)
    args = parser.parse_args()
    if args.command == "list":
        print("id | channel | received_at | status | text_length | image_count")
        for row in list_metadata(args.limit, args.status):
            print(" | ".join(str(item) for item in row))
    elif args.command == "mark":
        if not mark_status(args.message_id, args.status):
            raise SystemExit("Message ID not found")
        print("Status updated")


if __name__ == "__main__":
    main()
