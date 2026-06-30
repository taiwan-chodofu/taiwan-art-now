"""期限切れ展示を manual_exhibitions.json から archive.json に自動移動するスクリプト。
GitHub Actions日次cronまたは手動で実行。変更があればcommit & push。"""

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
MANUAL_FILE = BASE_DIR / "manual_exhibitions.json"
ARCHIVE_FILE = BASE_DIR / "archive.json"

TW_TZ = timezone(timedelta(hours=8))


def parse_end_date(dates_str):
    """dates文字列から終了日を抽出。"""
    if not dates_str:
        return None
    matches = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", dates_str)
    if len(matches) >= 2:
        try:
            return datetime(int(matches[1][0]), int(matches[1][1]), int(matches[1][2])).date()
        except ValueError:
            pass
    elif len(matches) == 1:
        try:
            return datetime(int(matches[0][0]), int(matches[0][1]), int(matches[0][2])).date()
        except ValueError:
            pass
    return None


def run():
    today = datetime.now(TW_TZ).date()

    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manual = json.load(f)

    archive_data = {"exhibitions": []}
    if ARCHIVE_FILE.exists():
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive_data = json.load(f)
        except Exception:
            archive_data = {"exhibitions": []}

    archive_keys = {
        (ex.get("museum"), ex.get("title_zh") or ex.get("title_en"), ex.get("dates"))
        for ex in archive_data["exhibitions"]
    }

    kept = []
    archived = []
    for ex in manual["exhibitions"]:
        end_date = parse_end_date(ex.get("dates", ""))
        if end_date and end_date < today:
            key = (ex.get("museum"), ex.get("title_zh") or ex.get("title_en"), ex.get("dates"))
            if key not in archive_keys:
                ex["status"] = "ended"
                archive_data["exhibitions"].append(ex)
                archive_keys.add(key)
            archived.append(ex.get("title_zh", ex.get("title_en", "?")))
        else:
            kept.append(ex)

    if not archived:
        print("No expired exhibitions found.")
        return False

    manual["exhibitions"] = kept
    with open(MANUAL_FILE, "w", encoding="utf-8") as f:
        json.dump(manual, f, ensure_ascii=False, indent=2)

    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)

    print(f"Archived {len(archived)} expired exhibitions:")
    for t in archived:
        print(f"  - {t}")
    return True


if __name__ == "__main__":
    changed = run()
    sys.exit(0 if changed else 1)
