"""期限切れ展示を manual_exhibitions.json から archive.json に自動移動するスクリプト。
GitHub Actions日次cronまたは手動で実行。変更があればcommit & push。

archive前に展示の公式リンクを再取得し、記録済みの終了日より後の日付がページ内に
見つかった場合は「会期延長の可能性あり」として自動archiveせず、管理者にMessenger通知して
次回以降の手動確認に委ねる（2026-09-14のNCPI会期誤登録インシデントの再発防止）。"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent
MANUAL_FILE = BASE_DIR / "manual_exhibitions.json"
ARCHIVE_FILE = BASE_DIR / "archive.json"

TW_TZ = timezone(timedelta(hours=8))
MESSENGER_PAGE_TOKEN = os.environ.get("MESSENGER_PAGE_TOKEN", "")
NOTIFY_RECIPIENT_ID = "27481470654840665"  # 管理者(gokawa)のsender_id

DATE_RE = re.compile(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})")


def parse_end_date(dates_str):
    """dates文字列から終了日を抽出。"""
    if not dates_str:
        return None
    matches = DATE_RE.findall(dates_str)
    if len(matches) >= 2:
        try:
            return datetime(int(matches[1][0]), int(matches[1][1]), int(matches[1][2])).date()
        except ValueError:
            pass
    elif len(matches) == 1:
        try:
            return datetime(int(matches[0][0]), int(matches[0][1]), int(matches[0][2])).date()
        except ValueError:
            pass
    return None


def check_possible_extension(ex, today, recorded_end):
    """展示リンクを再取得し、記録済み終了日より後の日付がページ内にあるか確認。
    ネットワーク取得やパースに失敗した場合はNoneを返し、呼び出し側は通常通りarchiveする
    (取得不能を理由に無制限に居座らせない)。"""
    link = ex.get("link", "")
    title = ex.get("title_zh", "")
    if not link or not link.startswith("http") or not title:
        return None

    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(link, impersonate="chrome", timeout=15)
        if r.status_code != 200:
            return None
        text = r.text
    except Exception as e:
        logger.info("recheck fetch failed for %s: %s", link, e)
        return None

    if title not in text:
        # リンク先がもう当該展示のページではない可能性が高く、判断材料にならない
        return None

    found_dates = []
    for y, m, d in DATE_RE.findall(text):
        try:
            found_dates.append(datetime(int(y), int(m), int(d)).date())
        except ValueError:
            continue

    if not found_dates:
        return None

    max_found = max(found_dates)
    # 記録済み終了日より3日以上後、かつ今日以降の日付が見つかれば「延長の可能性あり」
    if max_found >= today and (max_found - recorded_end).days >= 3:
        return max_found
    return None


def send_recheck_notification(flagged):
    """会期延長の可能性がある展示をMessengerで管理者に通知。"""
    if not MESSENGER_PAGE_TOKEN or not flagged:
        return

    import urllib.request

    lines = ["⚠️ 会期延長の可能性があり、自動archiveをスキップした展示：\n"]
    for ex, recorded_end, found_date in flagged[:5]:
        lines.append(
            f"📍 {ex.get('title_zh', ex.get('title_en', '?'))}\n"
            f"   記録済み終了日: {recorded_end}　ページ内に検出: {found_date}\n"
            f"   {ex.get('link', '')}\n"
        )
    if len(flagged) > 5:
        lines.append(f"\n...他 {len(flagged) - 5} 件")
    lines.append("\n手動で会期を確認し、manual_exhibitions.jsonを更新してください。")

    message = "\n".join(lines)
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
        logger.info("Sent recheck notification for %d exhibitions", len(flagged))
    except Exception as e:
        logger.warning("Recheck notification failed: %s", e)


def run():
    today = datetime.now(TW_TZ).date()

    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manual = json.load(f)

    archive_data = {"exhibitions": []}
    if ARCHIVE_FILE.exists():
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive_data = json.load(f)
        except Exception:
            archive_data = {"exhibitions": []}

    archive_keys = {
        (ex.get("museum"), ex.get("title_zh") or ex.get("title_en"), ex.get("dates"))
        for ex in archive_data["exhibitions"]
    }

    kept = []
    archived = []
    flagged_for_recheck = []
    for ex in manual["exhibitions"]:
        end_date = parse_end_date(ex.get("dates", ""))
        if end_date and end_date < today:
            extension = check_possible_extension(ex, today, end_date)
            if extension:
                flagged_for_recheck.append((ex, end_date, extension))
                kept.append(ex)
                continue

            key = (ex.get("museum"), ex.get("title_zh") or ex.get("title_en"), ex.get("dates"))
            if key not in archive_keys:
                ex["status"] = "ended"
                archive_data["exhibitions"].append(ex)
                archive_keys.add(key)
            archived.append(ex.get("title_zh", ex.get("title_en", "?")))
        else:
            kept.append(ex)

    if flagged_for_recheck:
        print(f"Skipped {len(flagged_for_recheck)} exhibitions (possible date extension detected):")
        for ex, end_date, extension in flagged_for_recheck:
            print(f"  - {ex.get('title_zh', '?')}: recorded end {end_date}, found {extension} on page")
        send_recheck_notification(flagged_for_recheck)

    if not archived:
        print("No expired exhibitions found.")
        return bool(flagged_for_recheck)

    manual["exhibitions"] = kept
    with open(MANUAL_FILE, "w", encoding="utf-8") as f:
        json.dump(manual, f, ensure_ascii=False, indent=2)

    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)

    print(f"Archived {len(archived)} expired exhibitions:")
    for t in archived:
        print(f"  - {t}")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    changed = run()
    sys.exit(0 if changed else 1)
