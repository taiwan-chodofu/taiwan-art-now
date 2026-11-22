"""Read-only frontend subscriber callsite inventory; never reads user data.

This is a release-blocking inventory, not proof of ownership. Explicitly
requires review of local-first favorites, Messenger refs and Web Push flows.
"""
import argparse
import json
import re
from pathlib import Path

TEMPLATES = (
    "templates/index.html",
    "templates/nearby.html",
    "templates/exhibition_detail_page.html",
)
PATTERN = re.compile(r"""['"](/api/(?:subscribers|push)/[a-z-]+)""")
LEGACY_PREFIXES = ("/api/subscribers/", "/api/push/")
PUBLIC_KEY = "/api/push/vapid-public-key"


def inspect_template(text, path):
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in PATTERN.finditer(line):
            route = match.group(1)
            findings.append({
                "file": path, "line": lineno, "route": route,
                "migration_required": route != PUBLIC_KEY,
            })
    return findings


def inventory(root):
    findings = []
    for relative in TEMPLATES:
        findings.extend(inspect_template(
            (root / relative).read_text(encoding="utf-8"), relative))
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    findings = inventory(args.root)
    blocked = [item for item in findings if item["migration_required"]]
    print(json.dumps({
        "release_blocked": bool(blocked), "legacy_calls": len(blocked),
        "findings": findings,
    }, ensure_ascii=False, sort_keys=True))
    if blocked and not args.report_only:
        parser.exit(2, "Legacy browser subscriber calls remain; cutover blocked.\n")


if __name__ == "__main__":
    main()
