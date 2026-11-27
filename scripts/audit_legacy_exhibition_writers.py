#!/usr/bin/env python3
"""Draft-only fail-closed inventory of legacy exhibition writers.
No template modifications, database access, or user data reads.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "templates/index.html": {"favs": 2, "visited": 2},
    "templates/discover.html": {"favs": 1, "visited": 1},
    "templates/nearby.html": {"favs": 1, "visited": 1},
    "templates/exhibition_detail_page.html": {"favs": 1, "visited": 1},
}
DIRECT = re.compile(r"localStorage\s*\.\s*setItem\s*\(\s*['\"]taiwan_art_(favs|visited)['\"]")
DYNAMIC = re.compile(r"localStorage\s*\.\s*setItem\s*\(\s*storeName\s*,")
FAILURE = 0
for filename, expected in TEMPLATES.items():
    source = (ROOT / filename).read_text(encoding="utf-8")
    counts = {kind: len(re.findall(r"localStorage\s*\.\s*setItem\s*\(\s*['\"]taiwan_art_" + kind + r"['\"]", source))
              for kind in ("favs", "visited")}
    dynamic = len(DYNAMIC.findall(source))
    print(f"{filename}: direct={counts}, dynamic_storeName={dynamic}")
    if counts != expected or (filename == "templates/index.html" and dynamic != 1) or (
        filename != "templates/index.html" and dynamic
    ):
        print("ERROR: legacy writer inventory changed; review migration before proceeding", file=sys.stderr)
        FAILURE = 1
if FAILURE:
    sys.exit(1)
print("PASS: all known legacy write sites remain inventoried; this is NOT a cutover safety pass")
