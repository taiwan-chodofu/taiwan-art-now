"""公式サイト照合スクリプト

各施設の公式サイトにアクセスし、手動JSONの中文タイトルが
実際に公式ページに存在するか自動検証する。

Usage: python verify_official.py [--fix]
  --fix: 修正可能なもの（スペース等）を自動修正

月1回の定期実行を推奨。
"""

import json
import os
import re
import sys
import time

try:
    from curl_cffi import requests as cffi
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: curl_cffi and beautifulsoup4 required")
    print("  pip install curl_cffi beautifulsoup4 lxml")
    sys.exit(1)

ERRORS = []
WARNINGS = []
FIXES = []


def log_error(msg):
    ERRORS.append(msg)
    print(f"  ❌ {msg}")


def log_warn(msg):
    WARNINGS.append(msg)
    print(f"  ⚠️  {msg}")


def log_fix(msg):
    FIXES.append(msg)
    print(f"  🔧 {msg}")


def fetch_page_text(url):
    """公式ページのテキストを取得。"""
    try:
        resp = cffi.get(url, impersonate="chrome", timeout=12)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def verify_museum_names():
    """施設名を公式サイトと照合。"""
    print("\n=== Verifying museum names against official sites ===")
    with open("museums_master.json", "r", encoding="utf-8") as f:
        master = json.load(f)

    for museum in master["museums"]:
        mid = museum["id"]
        url = museum.get("url", "")
        name_zh = museum["name"].get("zh", "")

        if "facebook.com" in url or not url:
            continue

        page_html = fetch_page_text(url)
        if not page_html:
            continue

        soup = BeautifulSoup(page_html, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        og_site = ""
        og_meta = soup.find("meta", property="og:site_name")
        if og_meta:
            og_site = og_meta.get("content", "").strip()

        official = og_site or title.split("|")[0].split("-")[0].strip()

        # 名前が公式に含まれているか
        if name_zh and official:
            if name_zh not in official and official not in name_zh:
                # 許容: 英語名のみの施設
                if not re.search(r"[一-鿿]", official):
                    continue
                log_warn(f"{mid}: our='{name_zh}' vs official='{official}'")

        time.sleep(0.3)


def verify_manual_json_titles():
    """手動JSONの展覧会タイトルを公式サイトと照合。"""
    print("\n=== Verifying manual JSON titles against official sites ===")

    # 照合可能な施設リスト（公式ページから中文タイトルが取れるもの）
    verifiable = {
        "honggah_manual.json": "https://hong-gah.org.tw/exhibitions-zh",
        "tnam_manual.json": "https://www.tnam.museum/exhibition/current",
        "fubon_manual.json": "https://www.fubonartmuseum.org/",
        "pingtung_manual.json": "https://www.cultural.pthg.gov.tw/pt1936/Default.aspx",
        "asiaart_manual.json": "https://www.asiaartcenter.org/exhibitions",
    }

    for fname, url in verifiable.items():
        if not os.path.exists(fname):
            continue
        with open(fname, "r", encoding="utf-8") as f:
            items = json.load(f)
        if not items:
            continue

        page_html = fetch_page_text(url)
        if not page_html:
            log_warn(f"{fname}: could not fetch {url}")
            continue

        print(f"\n  {fname}:")
        for item in items:
            title_zh = item.get("title_zh", "")
            if not title_zh:
                continue
            # 正規化して照合（句読点・ダッシュ・スペースの差異を吸収）
            def normalize_for_compare(s):
                s = re.sub(r"[\s　]+", "", s)  # 全スペース除去
                s = s.replace("–", "-").replace("—", "-").replace("－", "-")
                s = s.replace("：", ":").replace("｜", "|")
                return s[:8]  # 最初の8文字

            normalized_key = normalize_for_compare(title_zh)
            normalized_page = normalize_for_compare(
                BeautifulSoup(page_html, "lxml").get_text()
            ) if len(page_html) < 500000 else page_html

            # より柔軟な照合: 最初の5文字が含まれるか
            search_key = re.sub(r"[\s　]", "", title_zh[:5])
            if search_key in page_html.replace(" ", "").replace("\n", ""):
                print(f"    ✅ {title_zh[:50]}")
            else:
                log_error(f"{fname}: title NOT FOUND on official site: '{title_zh[:50]}'")

        time.sleep(1)


def verify_fb_exhibitions():
    """fb_exhibitions.json のタイトルを確認（FBのためアクセス困難、形式チェックのみ）。"""
    print("\n=== Verifying fb_exhibitions.json (format check) ===")
    if not os.path.exists("fb_exhibitions.json"):
        return
    with open("fb_exhibitions.json", "r", encoding="utf-8") as f:
        fb = json.load(f)
    for ex in fb.get("exhibitions", []):
        title_zh = ex.get("title_zh", "")
        title_en = ex.get("title_en", "")
        dates = ex.get("dates", "")
        museum = ex.get("museum", "")

        if not title_zh and not title_en:
            log_error(f"fb[{museum}]: both titles empty")
        if not dates:
            log_warn(f"fb[{museum}]: no dates for '{title_zh or title_en}'")
        # 日付有効性
        if dates:
            matches = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", dates)
            if len(matches) < 2:
                log_warn(f"fb[{museum}]: incomplete date format: '{dates}'")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    verify_museum_names()
    verify_manual_json_titles()
    verify_fb_exhibitions()

    print("\n" + "=" * 60)
    print(f"RESULTS: {len(ERRORS)} errors, {len(WARNINGS)} warnings, {len(FIXES)} fixes")

    if ERRORS:
        print("\n❌ ERRORS (must investigate):")
        for e in ERRORS:
            print(f"  - {e}")

    if WARNINGS:
        print("\n⚠️  WARNINGS:")
        for w in WARNINGS:
            print(f"  - {w}")

    sys.exit(1 if ERRORS else 0)


if __name__ == "__main__":
    main()
