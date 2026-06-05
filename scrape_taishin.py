"""台新藝術獎（Taishin Arts Award）全回データスクレイパー

公式サイトから第1回〜最新回の受賞者・ファイナリスト情報を取得し、
taishin_award.json に保存する。
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

BASE_URL = "https://www.taishinart.org.tw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def fetch_page(path):
    url = f"{BASE_URL}/{path}" if not path.startswith("http") else path
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def get_edition_list():
    """全回のリスト（回数、年、URLパス）を取得する。"""
    soup = fetch_page("art-award-year.html")
    editions = []
    for a in soup.find_all("a", href=re.compile(r"art-award-year-news/\d{4}")):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        year_match = re.search(r"/(\d{4})$", href)
        edition_match = re.search(r"第(\d+)屆", text)
        if year_match and edition_match:
            editions.append({
                "edition": int(edition_match.group(1)),
                "year": int(year_match.group(1)),
                "label": text,
            })
    editions.sort(key=lambda x: x["edition"])
    return editions


def scrape_winners(year):
    """受賞者を取得する。"""
    try:
        soup = fetch_page(f"art-award-year-winner/{year}")
        return _parse_work_items(soup, year, is_winner=True)
    except Exception as e:
        print(f"  Winners {year} failed: {e}")
        return []


def scrape_finalists(year):
    """ファイナリスト全作品を取得する。"""
    try:
        soup = fetch_page(f"art-award-year-works/{year}")
        return _parse_work_items(soup, year, is_winner=False)
    except Exception as e:
        print(f"  Finalists {year} failed: {e}")
        return []


def _parse_work_items(soup, year, is_winner):
    """work-item要素から作品情報を抽出する。"""
    items = []
    for work in soup.select(".work-item"):
        type_el = work.select_one("a.type")
        title_el = work.select_one("h6")
        artist_el = work.select_one("p")
        link_el = work.select_one("a[href*='art-award-year-detail']")
        photo_el = work.select_one("a.photo")

        category = type_el.get_text(strip=True) if type_el else ""
        title = title_el.get_text(strip=True) if title_el else ""
        artist = artist_el.get_text(strip=True) if artist_el else ""
        detail_path = link_el.get("href", "") if link_el else ""

        image_url = ""
        if photo_el and photo_el.get("style"):
            img_match = re.search(r"url\(([^)]+)\)", photo_el["style"])
            if img_match:
                image_url = img_match.group(1)
                if not image_url.startswith("http"):
                    image_url = f"{BASE_URL}/{image_url}"

        detail_url = ""
        if detail_path:
            if not detail_path.startswith("http"):
                detail_url = f"{BASE_URL}/{detail_path}"
            else:
                detail_url = detail_path

        items.append({
            "category_zh": category,
            "title_zh": title,
            "artist_zh": artist,
            "detail_url": detail_url,
            "image_url": image_url,
            "is_winner": is_winner,
        })
    return items


def main():
    print("=== Taishin Arts Award Scraper ===\n")

    editions = get_edition_list()
    print(f"Found {len(editions)} editions (#{editions[0]['edition']} to #{editions[-1]['edition']})\n")

    all_data = []

    for ed in editions:
        print(f"Scraping #{ed['edition']} ({ed['label']})...")

        winners = scrape_winners(ed["year"])
        finalists = scrape_finalists(ed["year"])

        # ファイナリストから受賞者を除外（重複防止）
        winner_titles = {w["title_zh"] for w in winners}
        finalists_only = [f for f in finalists if f["title_zh"] not in winner_titles]

        edition_data = {
            "edition": ed["edition"],
            "year": ed["year"],
            "label": ed["label"],
            "winners": winners,
            "finalists": finalists_only,
        }
        all_data.append(edition_data)

        print(f"  Winners: {len(winners)}, Finalists: {len(finalists_only)}")
        time.sleep(1)

    output = {
        "generated": __import__("datetime").datetime.now().isoformat(),
        "source": "https://www.taishinart.org.tw",
        "editions": all_data,
    }

    output_path = os.path.join(os.path.dirname(__file__), "taishin_award.json")
    text = json.dumps(output, ensure_ascii=False, indent=2)
    text = re.sub(r"[\ud800-\udfff]", "", text)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    total_winners = sum(len(e["winners"]) for e in all_data)
    total_finalists = sum(len(e["finalists"]) for e in all_data)
    print(f"\n=== Done ===")
    print(f"Editions: {len(all_data)}")
    print(f"Total winners: {total_winners}")
    print(f"Total finalists: {total_finalists}")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
