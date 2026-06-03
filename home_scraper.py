"""家PC用: Facebook施設の展覧会情報をPlaywrightで取得し、JSONに保存する。

使い方: python home_scraper.py
出力: fb_exhibitions.json (GitHubにpushしてRenderで表示)
"""

import json
import re
import os
import time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

TW_TZ = timezone(timedelta(hours=8))

def _now_tw():
    return datetime.now(TW_TZ).replace(tzinfo=None)

# Facebook施設リスト
FB_MUSEUMS = [
    ("frees", "https://www.facebook.com/freesartspace"),
    ("vt", "https://www.facebook.com/vtartsalon"),
    ("fotoaura", "https://www.facebook.com/fotoaura.tw"),
    ("art182", "https://www.facebook.com/182artspace"),
    ("sinpin", "https://www.facebook.com/sinpinpier"),
    ("ttam", "https://www.facebook.com/taitungartmuseum"),
    ("inart", "https://www.facebook.com/inartspace"),
    ("powen", "https://www.facebook.com/powengallery"),
    ("yiyun", "https://www.facebook.com/yiyunart"),
    ("daxin", "https://www.facebook.com/DaXinArtMuseum/"),
    ("shumin", "https://www.facebook.com/shuminart"),
    ("hcrav", "https://www.facebook.com/hcrav"),
    ("zhongxing", "https://www.facebook.com/zhongxingccp"),
    ("hualiencp", "https://www.facebook.com/hualienvcpp"),
]

EXHIBITION_KEYWORDS = [
    "展", "Exhibition", "exhibition", "個展", "聯展",
    "Opening", "開幕", "Solo Show", "Group Show",
]

DATE_PATTERNS = [
    r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*[（(]\w+[）)]\s*[－\-–~]\s*(\d{4}[./]\d{1,2}[./]\d{1,2})",
    r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*\w*\.?\s*[－\-–~]\s*(\d{4}[./]\d{1,2}[./]\d{1,2})",
    r"展期[：:]*\s*(\d{4}[./]\d{1,2}[./]\d{1,2})\s*[－\-–~]\s*(\d{4}[./]\d{1,2}[./]\d{1,2})",
    r"展期[：:]*\s*(\d{1,2}[./]\d{1,2})\s*[－\-–~]\s*(\d{1,2}[./]\d{1,2})",
    r"(\d{1,2}/\d{1,2})\s*[－\-–~]\s*(\d{1,2}/\d{1,2})",
]


def scrape_fb_page(page, museum_id, fb_url):
    """Playwrightでページを開いて投稿テキストを取得する。"""
    exhibitions = []
    today = _now_tw()

    try:
        page.goto(fb_url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # ページ内テキストを取得（レンダリング後）
        body_text = page.inner_text("body")

        # 投稿ブロックを探す（Facebookの投稿は div[data-ad-preview] や role="article" 等）
        posts = page.query_selector_all('[role="article"], [data-ad-preview="message"]')

        post_texts = []
        if posts:
            for post in posts[:20]:
                try:
                    text = post.inner_text()
                    if text and len(text) > 20:
                        post_texts.append(text)
                except Exception:
                    pass

        # role="article" で取れなかった場合、ページ全体のテキストを使う
        if not post_texts:
            post_texts = [body_text]

        seen_titles = set()
        for text in post_texts:
            if not any(kw in text for kw in EXHIBITION_KEYWORDS):
                continue

            title, dates = extract_exhibition(text, today)
            if not title or title in seen_titles:
                continue

            # 日付があって終了済みならスキップ
            if dates:
                end_match = re.findall(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", dates)
                if len(end_match) >= 2:
                    try:
                        ey, em, ed = int(end_match[1][0]), int(end_match[1][1]), int(end_match[1][2])
                        if datetime(ey, em, ed) < today:
                            continue
                    except ValueError:
                        continue

            seen_titles.add(title)
            exhibitions.append({
                "museum": museum_id,
                "title_en": title,
                "title_zh": title,
                "title_ja": "",
                "dates": dates,
                "location": "",
                "link": fb_url,
            })

    except Exception as e:
        print(f"  ERROR: {e}")

    return exhibitions


def extract_exhibition(text, today):
    """投稿テキストから展覧会タイトルと日付を抽出する。"""
    dates = ""
    year = str(today.year)

    for pattern in DATE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            g1, g2 = m.group(1), m.group(2)
            # 短い形式（MM/DD）の場合は年を補完
            if len(g1) <= 5:
                g1 = f"{year}/{g1}"
                g2 = f"{year}/{g2}"
            dates = f"{g1} – {g2}"
            break

    # タイトル: 最初の意味のある行
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = ""
    for line in lines[:5]:
        if re.match(r"^[\d./\-–（）()\s]+$", line):
            continue
        if any(skip in line for skip in ["展期", "Exhibition Dates", "Venue", "http", "地點", "時間", "開放時間"]):
            continue
        if len(line) > 3 and len(line) < 100:
            title = line.strip()
            break

    return title, dates


def main():
    print(f"=== Taiwan Art Now — Home PC Scraper ===")
    print(f"Time: {_now_tw()}")
    print(f"Museums: {len(FB_MUSEUMS)}")
    print()

    all_exhibitions = []

    with sync_playwright() as p:
        # Chromeのユーザーデータを使ってログイン状態を引き継ぐ
        chrome_user_data = os.path.expandvars(
            r"%LOCALAPPDATA%\Google\Chrome\User Data"
        )
        browser = p.chromium.launch_persistent_context(
            user_data_dir=chrome_user_data,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            locale="zh-TW",
        )
        page = browser.new_page()

        for museum_id, fb_url in FB_MUSEUMS:
            print(f"Scraping {museum_id}... ", end="", flush=True)
            results = scrape_fb_page(page, museum_id, fb_url)
            all_exhibitions.extend(results)
            print(f"{len(results)} exhibitions found")
            time.sleep(2)

        browser.close()  # persistent context も close() でOK

    # 保存
    output = {
        "generated": _now_tw().isoformat(),
        "exhibitions": all_exhibitions,
    }
    output_path = os.path.join(os.path.dirname(__file__), "fb_exhibitions.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=== Done ===")
    print(f"Total: {len(all_exhibitions)} exhibitions")
    print(f"Saved to: {output_path}")

    if all_exhibitions:
        print("\nResults:")
        for ex in all_exhibitions:
            print(f"  [{ex['museum']}] \"{ex['title_en'][:50]}\" dates={ex['dates']}")


if __name__ == "__main__":
    main()
