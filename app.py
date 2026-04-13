"""台湾現代アート展覧会情報アプリ"""

from flask import Flask, render_template, request
from scraper import fetch_all_exhibitions, MUSEUMS
import json
import os

app = Flask(__name__)

# 多言語UIラベル
UI_LABELS = {
    "en": {
        "title": "Taiwan Contemporary Art Exhibitions",
        "subtitle": "Current exhibitions at major museums in Taiwan",
        "museum": "Museum",
        "exhibition": "Exhibition",
        "dates": "Dates",
        "location": "Location",
        "link": "Details",
        "no_data": "No exhibition data available. Please try again later.",
        "last_updated": "Last updated",
        "lang_en": "English",
        "lang_ja": "日本語",
        "lang_zh": "中文",
        "refresh": "Refresh",
        "cat_public": "Public",
        "cat_alt": "Alt",
        "cat_commercial": "Gallery",
        "cat_private": "Private",
        "open_today": "Open Today",
    },
    "ja": {
        "title": "台湾 現代アート展覧会情報",
        "subtitle": "台湾の主要美術館で開催中の展覧会",
        "museum": "美術館",
        "exhibition": "展覧会",
        "dates": "会期",
        "location": "場所",
        "link": "詳細",
        "no_data": "展覧会データを取得できませんでした。後ほどお試しください。",
        "last_updated": "最終更新",
        "lang_en": "English",
        "lang_ja": "日本語",
        "lang_zh": "中文",
        "refresh": "更新",
        "cat_public": "公立",
        "cat_alt": "オルタナ",
        "cat_commercial": "ギャラリー",
        "cat_private": "私立",
        "open_today": "本日開館",
    },
    "zh": {
        "title": "台灣當代藝術展覽資訊",
        "subtitle": "台灣主要美術館目前展出中的展覽",
        "museum": "美術館",
        "exhibition": "展覽",
        "dates": "展期",
        "location": "地點",
        "link": "詳情",
        "no_data": "無法取得展覽資料，請稍後再試。",
        "last_updated": "最後更新",
        "lang_en": "English",
        "lang_ja": "日本語",
        "lang_zh": "中文",
        "refresh": "重新整理",
        "cat_public": "公立",
        "cat_alt": "替代",
        "cat_commercial": "畫廊",
        "cat_private": "私立",
        "open_today": "今日開放",
    },
}


def _get_display_title(exhibition, lang):
    """言語に応じた展覧会タイトルを返す。"""
    key = f"title_{lang}"
    title = exhibition.get(key, "")
    if title:
        return title
    # フォールバック: en → zh → ja → pl
    for fallback in ["title_en", "title_zh", "title_ja"]:
        if exhibition.get(fallback):
            return exhibition[fallback]
    return "(Untitled)"


def _get_museum_info(museum_key, lang):
    """美術館の多言語情報を返す（未対応言語は英語にフォールバック）。"""
    museum = MUSEUMS.get(museum_key, {})
    fallback = "en"
    return {
        "name": museum.get("name", {}).get(lang, museum.get("name", {}).get(fallback, museum_key)),
        "hours": museum.get("hours", {}).get(lang, museum.get("hours", {}).get(fallback, "")),
        "address": museum.get("address", {}).get(lang, museum.get("address", {}).get(fallback, "")),
        "url": museum.get("url", ""),
    }


def _normalize_dates(raw_dates):
    """日付文字列をYYYY.MM.DD – YYYY.MM.DD形式に統一する。"""
    import re
    from datetime import datetime
    if not raw_dates:
        return "", None
    # 全角スラッシュを半角に変換
    s = raw_dates.replace("／", "/")
    # 日付ペアを抽出
    dates = re.findall(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", s)
    if len(dates) >= 2:
        start = f"{dates[0][0]}.{int(dates[0][1]):02d}.{int(dates[0][2]):02d}"
        end = f"{dates[1][0]}.{int(dates[1][1]):02d}.{int(dates[1][2]):02d}"
        try:
            end_dt = datetime(int(dates[1][0]), int(dates[1][1]), int(dates[1][2]))
        except ValueError:
            end_dt = None
        return f"{start} – {end}", end_dt
    if len(dates) == 1:
        start = f"{dates[0][0]}.{int(dates[0][1]):02d}.{int(dates[0][2]):02d}"
        # 終了日なしの場合（MM.DD形式の終了日を探す）
        short_end = re.search(r"[–—\-]\s*(\d{1,2})[./](\d{1,2})", s)
        if short_end:
            em, ed = int(short_end.group(1)), int(short_end.group(2))
            ey = int(dates[0][0])
            end = f"{ey}.{em:02d}.{ed:02d}"
            try:
                end_dt = datetime(ey, em, ed)
            except ValueError:
                end_dt = None
            return f"{start} – {end}", end_dt
        return f"{start} –", None
    return raw_dates, None


def _calc_days_left(end_dt):
    """終了日までの残日数を計算する。Noneまたは14日超はNone。"""
    if not end_dt:
        return None
    from datetime import datetime, timezone, timedelta
    tw_tz = timezone(timedelta(hours=8))
    delta = (end_dt - datetime.now(tw_tz).replace(tzinfo=None)).days
    if 0 <= delta <= 14:
        return delta
    return None


# 美術館の表示順序
MUSEUM_ORDER = ["honggah", "moca", "tfam", "clab", "thecube", "kdmofa", "ntcart", "chiayi", "tcma"]

# 地域の表示順序（北→南→東）
REGION_ORDER = [
    "taipei", "new_taipei", "taoyuan", "hsinchu", "yilan", "keelung",
    "taichung", "nantou", "chiayi", "tainan", "kaohsiung",
    "hualien", "taitung",
]


def _load_master():
    """マスターデータJSONを読み込む。"""
    import os
    master_path = os.path.join(os.path.dirname(__file__), "museums_master.json")
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"regions": {}, "categories": {}, "museums": []}


def _get_localized(obj, lang):
    """多言語辞書から言語に応じた値を返す（英語フォールバック）。"""
    if isinstance(obj, dict):
        return obj.get(lang, obj.get("en", ""))
    return str(obj)


@app.route("/")
def index():
    """メインページ: 地域・カテゴリでグループ化して展覧会一覧を表示する。"""
    lang = request.args.get("lang", "ja")
    if lang not in UI_LABELS:
        lang = "ja"

    force_refresh = request.args.get("refresh") == "1"
    if force_refresh:
        cache_path = os.path.join(os.path.dirname(__file__), "cache.json")
        if os.path.exists(cache_path):
            os.remove(cache_path)

    master = _load_master()
    exhibitions = fetch_all_exhibitions()

    # 展覧会データをmuseum IDでインデックス化
    ex_by_museum = {}
    for ex in exhibitions:
        key = ex.get("museum", "")
        if key not in ex_by_museum:
            ex_by_museum[key] = []
        normalized, end_dt = _normalize_dates(ex.get("dates", ""))
        ex_by_museum[key].append({
            "title": _get_display_title(ex, lang),
            "dates": normalized,
            "days_left": _calc_days_left(end_dt),
            "location": ex.get("location", ""),
            "link": ex.get("link", ""),
        })

    # 地域ごとにグループ化
    regions_data = []
    for region_id in REGION_ORDER:
        region_museums = [
            m for m in master["museums"] if m["region"] == region_id
        ]

        if not region_museums:
            continue

        museum_entries = []
        for m in region_museums:
            mid = m["id"]
            exs = ex_by_museum.get(mid, [])
            is_closed_today = _is_closed_today(m.get("closed_day"))
            museum_entries.append({
                "id": mid,
                "name": _get_localized(m["name"], lang),
                "hours": _get_localized(m.get("hours", {}), lang),
                "address": _get_localized(m.get("address", {}), lang),
                "url": m.get("url", ""),
                "category": m.get("category", ""),
                "category_label": _get_localized(
                    master["categories"].get(m.get("category", ""), {}), lang
                ),
                "closed_today": is_closed_today,
                "has_schedule": m.get("closed_day") is not None,
                "exhibitions": exs,
            })

        regions_data.append({
            "id": region_id,
            "name": _get_localized(
                master["regions"].get(region_id, {}), lang
            ),
            "museums": museum_entries,
        })

    labels = UI_LABELS[lang]
    return render_template(
        "index.html",
        labels=labels,
        regions=regions_data,
        current_lang=lang,
    )


def _is_closed_today(closed_day):
    """本日が休館日かどうか判定する（0=月曜, 6=日曜）。台湾時間(UTC+8)基準。"""
    if closed_day is None:
        return False
    from datetime import datetime, timezone, timedelta
    tw_tz = timezone(timedelta(hours=8))
    return datetime.now(tw_tz).weekday() == closed_day


if __name__ == "__main__":
    app.run(debug=True, port=5050)
