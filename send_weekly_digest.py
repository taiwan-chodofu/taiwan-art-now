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


def get_ending_soon(exhibitions, days=7):
    today = datetime.now(TW_TZ).date()
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
                    ending.append({
                        "title": ex.get("title_zh", "") or ex.get("title_en", ""),
                        "museum": ex.get("museum", ""),
                        "artists": artist_str,
                        "days_left": days_left,
                        "end_date": end_date.strftime("%m/%d"),
                        "detail_url": f"https://taiwan-art-now.onrender.com/exhibition/{ex.get('museum', '')}/0?lang=zh",
                        "key": ex.get("museum", "") + "__" + (ex.get("title_zh", "") or ex.get("title_en", "")),
                    })
            except ValueError:
                pass
    ending.sort(key=lambda x: x["days_left"])
    return ending


def format_digest(ending_exhibitions):
    if not ending_exhibitions:
        return None
    lines = ["🎨 本週即將結束的展覽 / 今週終了する展示:\n"]
    for ex in ending_exhibitions[:8]:
        lines.append(f"📍 {ex['title']}")
        if ex.get('artists'):
            lines.append(f"   {ex['artists']}")
        lines.append(f"   〜{ex['end_date']} (剩{ex['days_left']}天)")
        lines.append(f"   → {ex['detail_url']}\n")
    if len(ending_exhibitions) > 8:
        lines.append(f"...其他 {len(ending_exhibitions) - 8} 檔展覽")
    lines.append("\n→ 完整列表 Full list:")
    lines.append("https://taiwan-art-now.onrender.com/?lang=zh")
    lines.append("\n━━━━━━━━━━")
    lines.append("解除通知 Unsubscribe: 輸入「取消」或「unsubscribe」")
    return "\n".join(lines)


def format_fav_alert(exhibition):
    artist_line = f"\n   {exhibition['artists']}" if exhibition.get('artists') else ""
    return (
        f"💡 你的收藏即將結束！/ あなたの♡展示が終了間近！\n\n"
        f"📍 {exhibition['title']}{artist_line}\n"
        f"   〜{exhibition['end_date']} (剩{exhibition['days_left']}天)\n\n"
        f"→ {exhibition.get('detail_url', 'https://taiwan-art-now.onrender.com/?lang=zh')}\n\n"
        f"━━━━━━━━━━\n"
        f"解除通知 Unsubscribe: 輸入「取消」或「unsubscribe」"
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
