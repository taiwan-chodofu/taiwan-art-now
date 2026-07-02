"""毎週水曜正午に登録ユーザーへ「7日以内に終了する展示」を配信するスクリプト。
GitHub Actionsで実行。MESSENGER_PAGE_TOKEN環境変数が必要。"""

import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
SUBSCRIBERS_FILE = BASE_DIR / "subscribers.json"
CACHE_FILE = BASE_DIR / "cache.json"
TW_TZ = timezone(timedelta(hours=8))


def load_subscribers():
    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}}


def load_exhibitions():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("exhibitions", [])
        except Exception:
            pass
    return []


def load_museum_regions():
    """museum_id -> region mapping."""
    master_path = BASE_DIR / "museums_master.json"
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            master = json.load(f)
        return {m["id"]: m.get("region", "other") for m in master.get("museums", [])}
    except Exception:
        return {}


REGION_NAMES = {
    "taipei": "台北", "new_taipei": "新北", "taoyuan": "桃園",
    "hsinchu": "新竹", "taichung": "台中", "tainan": "台南",
    "kaohsiung": "高雄", "pingtung": "屏東", "yilan": "宜蘭",
    "hualien": "花蓮", "taitung": "台東", "other": "其他",
}


def get_ending_soon(exhibitions, days=7):
    today = datetime.now(TW_TZ).date()
    museum_regions = load_museum_regions()
    ending = []
    for ex in exhibitions:
        dates = ex.get("dates", "")
        matches = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", dates)
        if len(matches) >= 2:
            try:
                end_date = datetime(int(matches[1][0]), int(matches[1][1]), int(matches[1][2])).date()
                days_left = (end_date - today).days
                if 0 <= days_left <= days:
                    artists = ex.get("artists", [])
                    artist_str = " · ".join(artists[:3])
                    if len(artists) > 3:
                        artist_str += f" 等{len(artists)}人"
                    museum_id = ex.get("museum", "")
                    region = museum_regions.get(museum_id, "other")
                    ending.append({
                        "title": ex.get("title_zh", "") or ex.get("title_en", ""),
                        "museum": museum_id,
                        "region": region,
                        "region_name": REGION_NAMES.get(region, region),
                        "artists": artist_str,
                        "days_left": days_left,
                        "end_date": end_date.strftime("%m/%d"),
                        "detail_url": f"https://taiwan-art-now.onrender.com/exhibition/{museum_id}/0?lang=zh",
                        "key": museum_id + "__" + (ex.get("title_zh", "") or ex.get("title_en", "")),
                    })
            except ValueError:
                pass
    ending.sort(key=lambda x: (x["days_left"], x["region"]))
    return ending


def format_digest(ending_exhibitions):
    if not ending_exhibitions:
        return None
    # Group by region, keep under 2000 char Messenger limit
    from collections import OrderedDict
    by_region = OrderedDict()
    for ex in ending_exhibitions:
        r = ex["region_name"]
        if r not in by_region:
            by_region[r] = []
        by_region[r].append(ex)

    lines = ["🎨 本週即將結束\n"]
    count = 0
    for region_name, exs in by_region.items():
        lines.append(f"▸ {region_name}")
        for ex in exs:
            if count >= 8:
                break
            artist = f" ({ex['artists']})" if ex.get('artists') else ""
            lines.append(f"{ex['title']}{artist}")
            lines.append(f"〜{ex['end_date']}")
            lines.append("")
            count += 1
        if count >= 8:
            break
    remaining = len(ending_exhibitions) - count
    if remaining > 0:
        lines.append(f"+{remaining}檔")

    lines.append("─────")
    lines.append("taiwan-art-now.onrender.com")
    lines.append("")
    lines.append("取消: 輸入「取消」")

    msg = "\n".join(lines)
    # Safety check: if over 2000 chars, truncate
    if len(msg) > 1950:
        msg = msg[:1900] + "\n\n→ https://taiwan-art-now.onrender.com/\n\n━━━━━━━━━━\n取消訂閱: 輸入「取消」"
    return msg


def format_fav_alert(exhibition):
    artist = f"\n{exhibition['artists']}" if exhibition.get('artists') else ""
    return (
        f"💡 收藏即將結束{artist}\n"
        f"{exhibition['title']}\n"
        f"〜{exhibition['end_date']} (剩{exhibition['days_left']}天)\n\n"
        f"{exhibition.get('detail_url', 'taiwan-art-now.onrender.com')}\n\n"
        f"─────\n"
        f"取消: 輸入「取消」"
    )


def send_message(sender_id, text, page_token):
    payload = json.dumps({
        "recipient": {"id": sender_id},
        "message": {"text": text},
    }).encode()
    req = urllib.request.Request(
        f"https://graph.facebook.com/v18.0/me/messages?access_token={page_token}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print(f"  Failed to send to {sender_id}: {e}")
        return False


def run():
    page_token = os.environ.get("MESSENGER_PAGE_TOKEN", "")
    if not page_token:
        print("MESSENGER_PAGE_TOKEN not set. Exiting.")
        return

    subs = load_subscribers()
    exhibitions = load_exhibitions()
    ending = get_ending_soon(exhibitions, days=7)

    print(f"Subscribers: {len(subs['users'])}")
    print(f"Ending within 7 days: {len(ending)}")

    if not ending:
        print("No exhibitions ending soon. No digest to send.")
        return

    digest_text = format_digest(ending)
    sent_count = 0

    for sender_id, user_data in subs["users"].items():
        # Weekly digest
        if user_data.get("weekly_digest", True) and digest_text:
            # Exclude visited exhibitions from digest for this user
            user_visited = set()
            visited_data = user_data.get("visited", {})
            for k in visited_data:
                user_visited.add(k.replace("/[^a-zA-Z0-9一-鿿㐀-䶿]/g", "_"))

            if send_message(sender_id, digest_text, page_token):
                sent_count += 1

        # Individual fav alerts (3 days)
        if user_data.get("fav_alerts", True):
            user_favs = user_data.get("favs", {})
            user_visited = user_data.get("visited", {})
            for ex in ending:
                if ex["days_left"] <= 3:
                    norm_key = re.sub(r"[^a-zA-Z0-9一-鿿㐀-䶿]", "_", ex["key"])
                    if norm_key in user_favs and norm_key not in user_visited:
                        alert_text = format_fav_alert(ex)
                        send_message(sender_id, alert_text, page_token)

    print(f"Weekly digest sent to {sent_count} subscribers.")


if __name__ == "__main__":
    run()
