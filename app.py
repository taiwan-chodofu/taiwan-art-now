"""台湾現代アート展覧会情報アプリ"""

from flask import Flask, render_template, request
from scraper import fetch_all_exhibitions, MUSEUMS

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
        "lang_pl": "Polski",
        "refresh": "Refresh",
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
        "lang_pl": "Polski",
        "refresh": "更新",
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
        "lang_pl": "Polski",
        "refresh": "重新整理",
    },
    "pl": {
        "title": "Wystawy sztuki współczesnej na Tajwanie",
        "subtitle": "Aktualne wystawy w głównych muzeach na Tajwanie",
        "museum": "Muzeum",
        "exhibition": "Wystawa",
        "dates": "Termin",
        "location": "Miejsce",
        "link": "Szczegóły",
        "no_data": "Brak danych o wystawach. Spróbuj ponownie później.",
        "last_updated": "Ostatnia aktualizacja",
        "lang_en": "English",
        "lang_ja": "日本語",
        "lang_zh": "中文",
        "lang_pl": "Polski",
        "refresh": "Odśwież",
    },
}


def _get_display_title(exhibition, lang):
    """言語に応じた展覧会タイトルを返す。"""
    key = f"title_{lang}"
    title = exhibition.get(key, "")
    if title:
        return title
    # フォールバック: en → zh → ja → pl
    for fallback in ["title_en", "title_zh", "title_ja", "title_pl"]:
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
    from datetime import datetime
    delta = (end_dt - datetime.now()).days
    if 0 <= delta <= 14:
        return delta
    return None


# 美術館の表示順序
MUSEUM_ORDER = ["honggah", "moca", "tfam", "clab", "thecube", "kdmofa", "ntcart", "chiayi", "tcma"]


@app.route("/")
def index():
    """メインページ: 美術館ごとにグループ化して展覧会一覧を表示する。"""
    lang = request.args.get("lang", "ja")
    if lang not in UI_LABELS:
        lang = "ja"

    force_refresh = request.args.get("refresh") == "1"
    if force_refresh:
        import os
        cache_path = os.path.join(os.path.dirname(__file__), "cache.json")
        if os.path.exists(cache_path):
            os.remove(cache_path)

    exhibitions = fetch_all_exhibitions()

    # 美術館ごとにグループ化
    grouped = {}
    for ex in exhibitions:
        key = ex.get("museum", "other")
        if key not in grouped:
            grouped[key] = {
                "info": _get_museum_info(key, lang),
                "exhibitions": [],
            }
        normalized, end_dt = _normalize_dates(ex.get("dates", ""))
        grouped[key]["exhibitions"].append({
            "title": _get_display_title(ex, lang),
            "dates": normalized,
            "days_left": _calc_days_left(end_dt),
            "location": ex.get("location", ""),
            "link": ex.get("link", ""),
        })

    # 表示順序に並べる
    museum_groups = []
    for key in MUSEUM_ORDER:
        if key in grouped:
            museum_groups.append(grouped[key])

    labels = UI_LABELS[lang]
    return render_template(
        "index.html",
        labels=labels,
        museum_groups=museum_groups,
        current_lang=lang,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5050)
