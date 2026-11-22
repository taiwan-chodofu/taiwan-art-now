"""Static browser subscriber API ownership audit.

Reads source code only; does not call endpoints, access subscriber data, or
claim that an identifier is proof of ownership. A nonzero exit means release
is blocked, not that production routes were changed.
"""
import ast
import argparse
import json
from pathlib import Path

PROTECTED = {
    "api_sync_favs": "/api/subscribers/sync",
    "api_link_ref": "/api/subscribers/link-ref",
    "api_subscriber_status": "/api/subscribers/status",
    "api_unsubscribe": "/api/subscribers/unsubscribe",
    "api_subscriber_settings": "/api/subscribers/settings",
    "api_push_subscribe": "/api/push/subscribe",
    "api_push_unsubscribe": "/api/push/unsubscribe",
    "api_push_sync_favs": "/api/push/sync-favs",
}


def audit_source(source):
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    findings = []
    for function, route in PROTECTED.items():
        node = functions.get(function)
        if node is None:
            findings.append({"route": route, "status": "missing-review-required"})
            continue
        # This is deliberately an approval gate, not a heuristic that can
        # mistake a string/parameter name for a secure ownership check.
        findings.append({"route": route, "status": "ownership-review-required"})
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "app.py")
    parser.add_argument("--report-only", action="store_true",
                        help="Exit zero for CI inventory; never implies approval")
    args = parser.parse_args()
    findings = audit_source(args.source.read_text(encoding="utf-8"))
    print(json.dumps({"release_blocked": True, "routes": findings}, sort_keys=True))
    if not args.report_only:
        parser.exit(2, "Ownership authorization not independently verified; cutover blocked.\n")


if __name__ == "__main__":
    main()
