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
# cache.json is gitignored and doesn't exist in the GitHub Actions checkout,
# so it can never be read here — read from the committed source of truth
# (manual_exhibitions.json) instead.
MANUAL_EXHIBITIONS_FILE = BASE_DIR / "manual_exhibitions.json"
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
    if MANUAL_EXHIBITIONS_FILE.exists():
        try:
            with open(MANUAL_EXHIBITIONS_FILE, "r", encoding="utf-8") as f:
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
                # days_left == 0 means it closes today — already too late
                # for a "closing soon" reminder to be useful, so skip it.
                if 1 <= days_left <= days:
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
    """Returns a list of messages (split by region if over 2000 chars)."""
    if not ending_exhibitions:
        return []
    from collections import OrderedDict
    by_region = OrderedDict()
    for ex in ending_exhibitions:
        r = ex["region_name"]
        if r not in by_region:
            by_region[r] = []
        by_region[r].append(ex)

    footer = "\n─────\ntaiwan-art-now.onrender.com\n\n取消: 輸入「取消」"

    # Build region blocks
    region_blocks = []
    for region_name, exs in by_region.items():
        block_lines = [f"▸ {region_name}"]
        for ex in exs:
            artist = f" ({ex['artists']})" if ex.get('artists') else ""
            block_lines.append(f"{ex['title']}{artist}")
            block_lines.append(f"〜{ex['end_date']}")
            block_lines.append("")
        region_blocks.append("\n".join(block_lines))

    # Assemble messages, split at region boundaries if needed
    header = "🎨 7天內即將結束\n\n"
    messages = []
    current = header
    for block in region_blocks:
        test = current + block + footer
        if len(test) > 1900 and current != header:
            # Send current, start new message
            messages.append(current.rstrip() + footer)
            current = "🎨 續\n\n" + block + "\n"
        else:
            current += block + "\n"

    # Add final message
    messages.append(current.rstrip() + footer)
    return messages


def format_fav_alert(exhibition):
    artist = f" ({exhibition['artists']})" if exhibition.get('artists') else ""
    return (
        f"♡ 你想去的展覽即將結束\n\n"
        f"{exhibition['title']}{artist}\n"
        f"〜{exhibition['end_date']} (剩{exhibition['days_left']}天)\n\n"
        f"→ {exhibition.get('detail_url', 'taiwan-art-now.onrender.com')}\n\n"
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

    digest_messages = format_digest(ending)
    sent_count = 0

    for sender_id, user_data in subs["users"].items():
        # Weekly digest
        if user_data.get("weekly_digest", True) and digest_messages:
            for msg in digest_messages:
                send_message(sender_id, msg, page_token)
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
