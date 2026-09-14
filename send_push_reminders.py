"""毎日、♡行きたいで✓観たにしていない展示が残り10日になったらWeb Pushで個別通知するスクリプト。
GitHub Actionsで実行。VAPID_PRIVATE_KEY環境変数が必要。"""

import json
import os
import re

from send_weekly_digest import get_ending_soon, load_exhibitions, load_push_subscribers, save_push_subscribers_to_github

REMINDER_DAYS = 10


def send_web_push(subscription_info, title, body, url, vapid_private_key, vapid_claims_email):
    """Returns False (drop the subscription) only when the browser reports
    the endpoint as gone (404/410)."""
    from pywebpush import webpush, WebPushException

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": vapid_claims_email},
            timeout=10,
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            print(f"  Dropping expired push subscription: {e}")
            return False
        print(f"  Push failed: {e}")
        return True
    except Exception as e:
        print(f"  Push failed: {e}")
        return True


def run():
    vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_claims_email = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:contact@taiwan-art-now.onrender.com")
    if not vapid_private_key:
        print("VAPID_PRIVATE_KEY not set. Exiting.")
        return

    exhibitions = load_exhibitions()
    ending = get_ending_soon(exhibitions, days=REMINDER_DAYS)
    due = [ex for ex in ending if ex["days_left"] == REMINDER_DAYS]
    print(f"Exhibitions hitting the {REMINDER_DAYS}-day mark today: {len(due)}")
    if not due:
        return

    subs = load_push_subscribers()
    subscriptions = subs.get("subscriptions", {})
    alive = {}
    sent = 0
    for endpoint, info in subscriptions.items():
        favs = info.get("favs", {})
        visited = info.get("visited", {})
        keep = True
        for ex in due:
            norm_key = re.sub(r"[^a-zA-Z0-9一-鿿㐀-䶿]", "_", ex["key"])
            if norm_key not in favs or norm_key in visited:
                continue
            title = "♡ 你想去的展覽剩10天了"
            body = f"{ex['title']} — 記得安排時間去看看！"
            ok = send_web_push(
                {"endpoint": endpoint, "keys": info["keys"]},
                title, body, ex.get("detail_url", "https://taiwan-art-now.onrender.com/"),
                vapid_private_key, vapid_claims_email,
            )
            if ok:
                sent += 1
            else:
                keep = False
        if keep:
            alive[endpoint] = info
    print(f"Sent {sent} reminder(s).")
    if len(alive) != len(subscriptions):
        subs["subscriptions"] = alive
        save_push_subscribers_to_github(subs)


if __name__ == "__main__":
    run()
