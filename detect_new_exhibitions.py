"""新展示検出スクリプト: 非池中をチェックし、未掲載の新展示をMessengerで通知する。
自動でcacheには入れない（通知のみ）。"""

import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent

# Messenger通知設定
MESSENGER_PAGE_TOKEN = os.environ.get("MESSENGER_PAGE_TOKEN", "")
NOTIFY_RECIPIENT_ID = "27481470654840665"  # 管理者(gokawa)のsender_id


def _normalize_title(title):
    """タイトルの表記揺れを吸収する正規化。"""
    t = title.strip().lower()
    t = re.sub(r"[【】「」『』《》〈〉\[\]：:；;—－\-·・．\s]", "", t)
    return t


def load_known_exhibitions():
    """既に掲載済み + 除外済みの展示タイトルセット（正規化済み）を取得。"""
    manual_path = BASE_DIR / "manual_exhibitions.json"
    excluded_path = BASE_DIR / "excluded_exhibitions.json"
    known = set()
    try:
        with open(manual_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ex in data.get("exhibitions", []):
            for t in (ex.get("title_zh", ""), ex.get("title_en", "")):
                if t:
                    known.add(_normalize_title(t))
    except Exception:
        pass
    # Load excluded (reviewed but not listed)
    try:
        with open(excluded_path, "r", encoding="utf-8") as f:
            excluded = json.load(f)
        for t in excluded.get("titles", []):
            if t:
                known.add(_normalize_title(t))
    except Exception:
        pass
    return known


def load_known_museum_ids():
    """museums_master.jsonの施設IDセットを取得。"""
    master_path = BASE_DIR / "museums_master.json"
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            master = json.load(f)
        return {m["id"] for m in master.get("museums", [])}
    except Exception:
        return set()


def fetch_artemperor_page(page=1):
    """非池中の展示一覧ページをスクレイプし、展示情報を抽出。"""
    from curl_cffi import requests as cffi_requests
    from bs4 import BeautifulSoup

    url = f"https://artemperor.tw/tidbits?page={page}"
    try:
        r = cffi_requests.get(url, impersonate="chrome", timeout=20)
        if r.status_code != 200:
            return []
    except Exception as e:
        logger.warning("artemperor fetch failed: %s", e)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    exhibitions = []

    seen_urls = set()
    all_links = soup.find_all("a", href=re.compile(r"artemperor\.tw/tidbits/\d+"))

    for a in all_links:
        href = a.get("href", "")
        if href in seen_urls:
            continue

        # Find h3 (gallery) and h2 (title) in parent container
        parent = a.parent
        if not parent:
            continue

        h3 = parent.find("h3")
        h2 = parent.find("h2")
        p = parent.find("p")

        if not h2:
            parent = parent.parent
            if parent:
                h3 = parent.find("h3")
                h2 = parent.find("h2")
                p = parent.find("p")

        if not h2:
            continue

        gallery = h3.get_text(strip=True) if h3 else ""
        title = h2.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # Skip non-exhibition content
        if gallery in ("訪談", "焦點人物", "藝文產業", ""):
            continue

        # Skip non-Taiwan galleries (Hong Kong etc.)
        NON_TAIWAN_GALLERIES = {"牛棚藝術村", "M+M Gallery"}
        if gallery in NON_TAIWAN_GALLERIES:
            continue

        dates = ""
        if p:
            dates_text = p.get_text(strip=True)
            date_match = re.search(r"日期：(.+?)｜", dates_text)
            if date_match:
                dates = date_match.group(1)

        seen_urls.add(href)
        exhibitions.append({
            "title": title,
            "gallery": gallery,
            "dates": dates,
            "url": href,
        })

    return exhibitions


def _load_gallery_to_museum():
    """museums_master.jsonからギャラリー名(zh/en) → museum_id マッピングを動的に構築する。
    新規施設が追加されるたびに手動でこの辞書を更新する必要がなくなる
    (2026-08-26: 安卓藝術/也趣藝廊/新浜碼頭/852藝術空間/大象藝術空間館/多納藝術/暮拉多元藝術空間
    等の欠落により、既に掲載済みの展示が繰り返し「新展示」として誤検出されていた)。"""
    master_path = BASE_DIR / "museums_master.json"
    mapping = {}
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            master = json.load(f)
        museums = master if isinstance(master, list) else master.get("museums", master)
        for m in museums:
            mid = m.get("id")
            if not mid:
                continue
            for lang in ("zh", "en", "ja"):
                name = (m.get("name", {}) or {}).get(lang, "")
                if name:
                    mapping[name] = mid
    except Exception:
        logger.warning("failed to load museums_master.json for gallery mapping", exc_info=True)
    return mapping


# 非池中のギャラリー名 → museum_id マッピング（museums_master.jsonから動的生成）
GALLERY_TO_MUSEUM = _load_gallery_to_museum()


def detect_new(pages=3):
    """新展示を検出して返す。終了済み展示は除外。"""
    known_titles = load_known_exhibitions()
    known_museums = load_known_museum_ids()
    new_exhibitions = []

    tw_tz = timezone(timedelta(hours=8))
    today = datetime.now(tw_tz).date()

    for page in range(1, pages + 1):
        items = fetch_artemperor_page(page)
        for item in items:
            # Skip expired exhibitions
            dates = item.get("dates", "")
            end_match = re.search(r"~\s*(\d{4})-(\d{2})-(\d{2})", dates)
            if end_match:
                try:
                    end_date = datetime(int(end_match.group(1)), int(end_match.group(2)), int(end_match.group(3))).date()
                    if end_date < today:
                        continue
                except ValueError:
                    pass

            title = item["title"].strip()
            title_norm = _normalize_title(title)

            # Skip if already known
            if title_norm in known_titles:
                continue
            # Also check partial match (8+ chars substring)
            if any(title_norm[:8] in kt or kt[:8] in title_norm for kt in known_titles if len(kt) >= 8):
                continue
            # 非池中の見出しは「タイトル+アーティスト名」が連結される場合がある
            # (例: "【相繫之縷……】魯伊・米蓋爾・萊陶・費雷拉") ため、既知タイトルが
            # 検出タイトルの部分文字列として含まれていれば既知とみなす
            if any(kt in title_norm for kt in known_titles if len(kt) >= 4):
                continue

            # Check if gallery maps to a known museum
            gallery = item["gallery"]
            museum_id = GALLERY_TO_MUSEUM.get(gallery)

            # Also check partial matches
            if not museum_id:
                for gname, mid in GALLERY_TO_MUSEUM.items():
                    if gname in gallery or gallery in gname:
                        museum_id = mid
                        break
            # Fuzzy match: 表記揺れ吸収。「高雄市新浜碼頭藝術學會」vs 既存の「新浜碼頭藝術空間」のように
            # 互いの完全な部分文字列ではないが、4文字以上の連続する共通部分があればマッチとみなす。
            # ただし「美術館」等の一般的すぎる接尾辞のみの一致では誤マッチするため除外する。
            if not museum_id:
                GENERIC_SUBSTRINGS = {"美術館", "藝術館", "藝術中心", "藝廊", "畫廊", "藝術空間", "文化園區", "紀念館", "當代館", "藝術村"}
                for gname, mid in GALLERY_TO_MUSEUM.items():
                    if len(gname) < 4 or len(gallery) < 4:
                        continue
                    # 英数字を含む共通部分は "ART"/"Gallery" 等の一般語で誤マッチしやすいため、
                    # 漢字のみの共通部分文字列に限定する（中文の表記揺れ吸収が目的）
                    common = next(
                        (gname[i:i + 4] for i in range(len(gname) - 3)
                         if gname[i:i + 4] in gallery and gname[i:i + 4].isascii() is False),
                        None,
                    )
                    if common and not any(g in common or common in g for g in GENERIC_SUBSTRINGS):
                        museum_id = mid
                        break

            # Only notify for known museums or notable galleries
            if museum_id or any(kw in gallery for kw in ["美術館", "藝術", "Gallery", "Museum"]):
                new_exhibitions.append({
                    "title": title,
                    "gallery": gallery,
                    "museum_id": museum_id or "unknown",
                    "dates": item["dates"],
                    "url": item["url"],
                })

    return new_exhibitions


def send_messenger_notification(new_exhibitions):
    """Messenger経由で管理者に新展示を通知。"""
    if not MESSENGER_PAGE_TOKEN or not new_exhibitions:
        return

    import urllib.request

    message_lines = ["🆕 新展示検出：\n"]
    for ex in new_exhibitions[:5]:  # 最大5件
        message_lines.append(
            f"📍 {ex['gallery']}\n"
            f"   {ex['title']}\n"
            f"   {ex['dates']}\n"
            f"   {ex['url']}\n"
        )

    if len(new_exhibitions) > 5:
        message_lines.append(f"\n...他 {len(new_exhibitions) - 5} 件")

    message = "\n".join(message_lines)

    payload = json.dumps({
        "recipient": {"id": NOTIFY_RECIPIENT_ID},
        "message": {"text": message},
    }).encode()

    req = urllib.request.Request(
        f"https://graph.facebook.com/v18.0/me/messages?access_token={MESSENGER_PAGE_TOKEN}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        logger.info("Sent Messenger notification: %d new exhibitions", len(new_exhibitions))
    except Exception as e:
        logger.warning("Messenger notification failed: %s", e)


def run():
    """メイン実行: 検出 → 通知。"""
    new = detect_new(pages=3)
    if new:
        print(f"Detected {len(new)} new exhibitions:")
        for ex in new:
            print(f"  [{ex['museum_id']}] {ex['gallery']} | {ex['title']} | {ex['dates']}")
        send_messenger_notification(new)
    else:
        print("No new exhibitions detected.")
    return new


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
