"""manual_exhibitions.json内でlinkを共有する展示のうち、descriptionが
個別に入っていない（=exhibition_details.jsonの共有エントリに依存してしまう）
ものを検出する。共有link自体は正当なケース(同一イベントの複数会場等)もあるため、
「description欠落」を実害の判定基準にする。

使い方: py check_shared_links.py
"""
import json
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent


def main():
    with open(BASE_DIR / "manual_exhibitions.json", encoding="utf-8") as f:
        exhibitions = json.load(f)["exhibitions"]

    by_link = defaultdict(list)
    for ex in exhibitions:
        link = ex.get("link", "")
        if link:
            by_link[link].append(ex)

    problems = []
    for link, exs in by_link.items():
        if len(exs) < 2:
            continue
        missing_desc = [ex for ex in exs if not ex.get("description")]
        if missing_desc:
            problems.append((link, exs, missing_desc))

    if not problems:
        print("OK: no shared-link exhibitions are missing their own description.")
        return

    print(f"Found {len(problems)} shared link(s) with at least one exhibition missing description:\n")
    for link, exs, missing_desc in problems:
        print(f"[SHARED LINK, {len(exs)} exhibitions] {link}")
        for ex in exs:
            flag = " <-- MISSING DESCRIPTION" if ex in missing_desc else ""
            print(f"    - {ex.get('museum','')}: {ex.get('title_zh','') or ex.get('title_en','')}{flag}")
        print()
    print(
        "These exhibitions will silently inherit whichever description happens to be\n"
        "cached in exhibition_details.json for this shared link (last-write-wins),\n"
        "which may belong to a different exhibition entirely. Add a description\n"
        "directly to manual_exhibitions.json for each one to fix."
    )


if __name__ == "__main__":
    main()
