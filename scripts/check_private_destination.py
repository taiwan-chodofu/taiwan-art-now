"""Read-only destination readiness check. Never prints private records.

Run in a trusted shell with TAN_DATABASE_URL set. This does not establish
source quiescence, backup integrity, ownership, or permission to cut over.
"""
import argparse
import json


TABLES = ("messenger_subscribers", "messenger_refs", "web_push_subscriptions")


def inspect_destination(connect):
    result = {}
    with connect() as conn, conn.cursor() as cur:
        for table in TABLES:
            # Fixed allowlisted identifiers, not user-provided SQL.
            cur.execute("select count(*) from tan_private." + table)
            result[table] = int(cur.fetchone()[0])
    return result


def main():
    parser = argparse.ArgumentParser(description="Read-only private destination preflight")
    parser.add_argument("--require-empty", action="store_true",
                        help="Exit nonzero if any destination table contains records")
    args = parser.parse_args()
    from private_subscriber_store import _connect
    counts = inspect_destination(_connect)
    print(json.dumps({"destination_counts": counts}, sort_keys=True))
    if args.require_empty and any(counts.values()):
        parser.exit(2, "Destination is not empty; import must not proceed.\n")
    print("Read-only check complete. Source snapshot and backups NOT verified.")


if __name__ == "__main__":
    main()
