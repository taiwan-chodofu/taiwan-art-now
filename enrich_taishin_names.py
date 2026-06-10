"""台新賞アーティスト英語名の漸進的修正スクリプト。

各作品の公式詳細ページを訪問し、ページ内で使われている英語名を
検出して taishin_award.json を更新する。

1回の実行で最大 N 件の詳細ページを訪問し、見つかった公式英語名で上書きする。
バックグラウンドで定期実行可能（Render の cron ping 時など）。

Usage: python enrich_taishin_names.py [--max N]
"""

import json
import os
import re
import time
import sys
import requests
from datetime import datetime

MAX_PER_RUN = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10
TAISHIN_FILE = os.path.join(os.path.dirname(__file__), "taishin_award.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 公式英語表記パターン（SURNAME Given-Name）
TW_NAME_RE = re.compile(r"\b([A-Z]{2,})\s+([A-Z][a-z]+(?:-[A-Z][a-z]+)*)\b")
# 西洋名パターン
WESTERN_NAME_RE = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b")


def extract_english_names_from_page(url):
    """詳細ページからアーティスト英語名を抽出する。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []
        text = resp.text
        # 台湾式 SURNAME Given-Name
        tw_names = TW_NAME_RE.findall(text)
        names = [f"{s} {g}" for s, g in tw_names]
        # 一般的なノイズを除外
        noise = {
            "Taishin Bank", "Taishin Arts", "Shopping Design",
            "ANPIS FOTO", "Facebook Page",
        }
        names = [n for n in names if n not in noise and len(n) > 4]
        return list(dict.fromkeys(names))
    except Exception:
        return []


def match_name(zh_name, en_candidates):
    """中国語名に対応する英語名候補を見つける。
    姓のローマ字化が一致するかで判定（完全自動は困難なので控えめに）。
    """
    if not zh_name or not en_candidates:
        return None
    # 中国語の姓（最初の1-2文字）のピンインを推定するのは困難
    # 代わに、候補が1つだけなら採用（個展の場合）
    if len(en_candidates) == 1:
        return en_candidates[0]
    return None


def main():
    with open(TAISHIN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # detail_url があって artist_en が推測値の可能性があるアイテムを探す
    targets = []
    for ed in data["editions"]:
        for item in ed.get("winners", []) + ed.get("finalists", []):
            detail_url = item.get("detail_url", "")
            artist_en = item.get("artist_en", "")
            artist_zh = item.get("artist_zh", "")
            if not detail_url or not artist_zh:
                continue
            # 既にsurname形式で確認済みなら、ページから再取得して検証
            if not item.get("_name_verified"):
                targets.append(item)

    print(f"Targets: {len(targets)} items need verification")
    print(f"Processing max {MAX_PER_RUN} this run")
    print()

    updated = 0
    for item in targets[:MAX_PER_RUN]:
        detail_url = item["detail_url"]
        current_en = item.get("artist_en", "")
        zh = item.get("artist_zh", "")

        names = extract_english_names_from_page(detail_url)
        if names:
            # 個展（1名のみ）なら直接採用
            best = match_name(zh, names)
            if best and best != current_en:
                print(f"  {zh}: '{current_en}' -> '{best}' (from {detail_url[-30:]})")
                item["artist_en"] = best
                item["_name_verified"] = True
                updated += 1
            elif best:
                item["_name_verified"] = True
        time.sleep(0.5)

    if updated > 0:
        text = json.dumps(data, ensure_ascii=False, indent=2)
        text = re.sub(r"[\ud800-\udfff]", "", text)
        with open(TAISHIN_FILE, "w", encoding="utf-8") as f:
            f.write(text)

    print(f"\nDone. Updated: {updated} names")


if __name__ == "__main__":
    main()
