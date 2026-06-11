"""データ品質検証スクリプト

全施設・全展覧会データの正確性を自動チェックする。
CI/CD的に定期実行、または手動JSONの更新前に実行する。

Usage: python validate_data.py [--fix] [--verbose]
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

ERRORS = []
WARNINGS = []

TW_TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(TW_TZ).replace(tzinfo=None)


def error(msg):
    ERRORS.append(msg)
    print(f"  ❌ ERROR: {msg}")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  ⚠️  WARN: {msg}")


def validate_museums_master():
    """museums_master.json の検証"""
    print("\n=== Validating museums_master.json ===")
    with open("museums_master.json", "r", encoding="utf-8") as f:
        master = json.load(f)

    for museum in master["museums"]:
        mid = museum["id"]
        name_zh = museum["name"].get("zh", "")
        name_en = museum["name"].get("en", "")
        url = museum.get("url", "")

        # 1. 中文名が空でないこと
        if not name_zh:
            error(f"{mid}: name_zh is empty")

        # 2. 中文名にASCII英語が混じっていないこと（ブランド名を除く）
        # 許容: C-LAB, TKG+, TAO ART, 182 art space, ss space space, Bluerider, Each Modern 等
        ascii_only_allowed = [
            "clab", "tkgplus", "taoart", "art182", "sssart",
            "bluerider", "eachmodern", "g333",
        ]
        if mid not in ascii_only_allowed and name_zh and re.match(r"^[A-Za-z\s\d\-\+\.]+$", name_zh):
            warn(f"{mid}: name_zh is purely ASCII: '{name_zh}' (should be Chinese?)")

        # 3. URLが有効か（facebook以外）
        if url and "facebook.com" not in url:
            if not url.startswith("https://"):
                warn(f"{mid}: URL doesn't start with https: {url}")

        # 4. 座標が設定されているか
        if not museum.get("lat") and not museum.get("lng"):
            pass  # 座標なしは許容（全施設には設定できない）

        # 5. scraper設定の整合性
        scraper = museum.get("scraper")
        if scraper and scraper.endswith("_manual"):
            manual_file = f"{mid}_manual.json"
            if not os.path.exists(manual_file):
                error(f"{mid}: scraper='{scraper}' but {manual_file} not found")


def validate_exhibition_data():
    """展覧会データ（cache.json + manual JSON）の検証"""
    print("\n=== Validating exhibition data ===")

    # 手動JSONファイル
    manual_files = [f for f in os.listdir(".") if f.endswith("_manual.json")]
    for fname in manual_files:
        with open(fname, "r", encoding="utf-8") as f:
            items = json.load(f)
        mid = fname.replace("_manual.json", "")
        for i, item in enumerate(items):
            title_zh = item.get("title_zh", "")
            title_en = item.get("title_en", "")
            dates = item.get("dates", "")

            # 1. 少なくとも1つのタイトルがあること
            if not title_zh and not title_en:
                error(f"{fname}[{i}]: both title_zh and title_en are empty")

            # 2. title_zhが英語のみでないこと
            if title_zh and not re.search(r"[一-鿿]", title_zh) and len(title_zh) > 10:
                warn(f"{fname}[{i}]: title_zh has no CJK: '{title_zh[:50]}'")

            # 3. title_enが中国語のみでないこと
            if title_en and re.search(r"[一-鿿]", title_en) and not re.search(r"[A-Za-z]", title_en):
                warn(f"{fname}[{i}]: title_en is purely Chinese: '{title_en[:50]}'")

            # 4. 日付形式の検証
            if dates:
                date_matches = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", dates)
                if len(date_matches) >= 2:
                    try:
                        end_dt = datetime(
                            int(date_matches[1][0]),
                            int(date_matches[1][1]),
                            int(date_matches[1][2]),
                        )
                        if end_dt < TODAY:
                            warn(f"{fname}[{i}]: exhibition has ended: '{title_zh or title_en}' ({dates})")
                    except ValueError:
                        error(f"{fname}[{i}]: invalid date format: '{dates}'")

            # 5. 「推測禁止」チェック: title_zh に "—" (em-dash) + 英語名が含まれる場合は推測の可能性
            if title_zh and re.search(r"[—]\s*[A-Z][a-z]+\s+[A-Z]", title_zh):
                warn(f"{fname}[{i}]: title_zh may contain guessed translation: '{title_zh[:60]}'")


def validate_fb_exhibitions():
    """fb_exhibitions.json の検証"""
    print("\n=== Validating fb_exhibitions.json ===")
    if not os.path.exists("fb_exhibitions.json"):
        return
    with open("fb_exhibitions.json", "r", encoding="utf-8") as f:
        fb = json.load(f)
    for i, ex in enumerate(fb.get("exhibitions", [])):
        title_zh = ex.get("title_zh", "")
        if not title_zh:
            warn(f"fb_exhibitions[{i}]: title_zh is empty for museum '{ex.get('museum')}'")


def validate_taishin():
    """taishin_award.json の検証"""
    print("\n=== Validating taishin_award.json ===")
    if not os.path.exists("taishin_award.json"):
        return
    with open("taishin_award.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for ed in data.get("editions", []):
        for item in ed.get("winners", []) + ed.get("finalists", []):
            zh = item.get("artist_zh", "")
            en = item.get("artist_en", "")
            title_zh = item.get("title_zh", "")

            # artist_en がない
            if zh and not en:
                warn(f"taishin #{ed['edition']}: artist_en empty for '{zh}'")

            # title_zh がない
            if not title_zh:
                warn(f"taishin #{ed['edition']}: title_zh empty")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    validate_museums_master()
    validate_exhibition_data()
    validate_fb_exhibitions()
    validate_taishin()

    print("\n" + "=" * 60)
    print(f"RESULTS: {len(ERRORS)} errors, {len(WARNINGS)} warnings")
    if ERRORS:
        print("\n❌ ERRORS (must fix):")
        for e in ERRORS:
            print(f"  - {e}")
    if "--verbose" in sys.argv and WARNINGS:
        print("\n⚠️  WARNINGS:")
        for w in WARNINGS:
            print(f"  - {w}")

    sys.exit(1 if ERRORS else 0)


if __name__ == "__main__":
    main()
