"""毎日、♡行きたいで✓観たにしていない展示が残り10日/3日になったらWeb Pushで通知するスクリプト。
GitHub Actionsで実行。VAPID_PRIVATE_KEY環境変数が必要。

2段階にしているのは、10日前は「心の準備」程度で流されがちなため —
本当に見逃しを防ぐには締切直前（3日前）のもう一押しが必要という判断。
"""

import json
import os
import re

from send_weekly_digest import get_ending_soon, load_exhibitions, load_push_subscribers, save_push_subscribers_to_github

REMINDER_TIERS = [10, 3]
MYLIST_URL = "https://taiwan-art-now.onrender.com/?open=mylist"


def _truncate(text, n):
    return text if len(text) <= n else text[: n - 1] + "…"


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


def _build_notification(matches, days_left):
    """One exhibition: name it directly in the title so it's glanceable
    without expanding. Multiple: naming all of them risks an unreadably
    long body, so lead with one representative title + a count instead,
    and send people to their ♡ list (via MYLIST_URL) for the rest."""
    if len(matches) == 1:
        ex = matches[0]
        title = _truncate(ex["title"], 40)
        artist_prefix = f"{ex['artists']} — " if ex.get("artists") else ""
        body = f"{artist_prefix}還有{days_left}天，記得安排時間去看看！"
        url = ex.get("detail_url", MYLIST_URL)
    else:
        first = _truncate(matches[0]["title"], 24)
        title = f"♡ {len(matches)}個你想去的展覽剩{days_left}天了"
        body = f"《{first}》等{len(matches)}個展覽即將結束，記得安排時間去看看！"
        url = MYLIST_URL
    return title, body, url


def run():
    vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_claims_email = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:contact@taiwan-art-now.onrender.com")
    if not vapid_private_key:
        print("VAPID_PRIVATE_KEY not set. Exiting.")
        return

    exhibitions = load_exhibitions()
    due_by_tier = {}
    for days in REMINDER_TIERS:
        ending = get_ending_soon(exhibitions, days=days)
        due_by_tier[days] = [ex for ex in ending if ex["days_left"] == days]
        print(f"Exhibitions hitting the {days}-day mark today: {len(due_by_tier[days])}")
    if not any(due_by_tier.values()):
        return

    subs = load_push_subscribers()
    subscriptions = subs.get("subscriptions", {})
    alive = {}
    sent = 0
    for endpoint, info in subscriptions.items():
        favs = info.get("favs", {})
        visited = info.get("visited", {})
        keep = True
        for days, due in due_by_tier.items():
            matches = []
            for ex in due:
                norm_key = re.sub(r"[^a-zA-Z0-9一-鿿㐀-䶿]", "_", ex["key"])
                if norm_key in favs and norm_key not in visited:
                    matches.append(ex)
            if not matches:
                continue
            title, body, url = _build_notification(matches, days)
            ok = send_web_push(
                {"endpoint": endpoint, "keys": info["keys"]},
                title, body, url,
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
