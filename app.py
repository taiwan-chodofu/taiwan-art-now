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
        "open_today": "Open Now",
        "has_ex": "With Exhibitions",
        "upcoming": "Upcoming",
        "curator": "Curator",
        "opens_in": "opens in",
        "days_left": "days left",
        "days_short": "d",
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
        "open_today": "本日開館中",
        "has_ex": "展覧会あり",
        "upcoming": "近日開始",
        "curator": "キュレーター",
        "opens_in": "あと",
        "days_left": "日で終了",
        "days_short": "日",
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
        "has_ex": "有展覽",
        "upcoming": "即將開幕",
        "curator": "策展人",
        "opens_in": "還有",
        "days_left": "天結束",
        "days_short": "天",
    },
}


def _get_display_title(exhibition, lang):
    """言語に応じた展覧会タイトルを返す。
    日本語/英語ページでは固有名詞は英語優先、中国語ページは中国語優先。
    """
    if lang == "zh":
        for key in ["title_zh", "title_en", "title_ja"]:
            if exhibition.get(key):
                return exhibition[key]
        return "(Untitled)"
    # ja or en: 英語優先
    for key in ["title_en", "title_ja", "title_zh"]:
        if exhibition.get(key):
            return exhibition[key]
    # 旧フォールバック（互換のため残す）
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
    """日付文字列をYYYY.MM.DD – YYYY.MM.DD形式に統一する。
    Returns: (normalized_str, start_dt, end_dt)
    """
    import re
    from datetime import datetime
    if not raw_dates:
        return "", None, None
    s = raw_dates.replace("／", "/")
    dates = re.findall(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", s)
    if len(dates) >= 2:
        start = f"{dates[0][0]}.{int(dates[0][1]):02d}.{int(dates[0][2]):02d}"
        end = f"{dates[1][0]}.{int(dates[1][1]):02d}.{int(dates[1][2]):02d}"
        try:
            start_dt = datetime(int(dates[0][0]), int(dates[0][1]), int(dates[0][2]))
        except ValueError:
            start_dt = None
        try:
            end_dt = datetime(int(dates[1][0]), int(dates[1][1]), int(dates[1][2]))
        except ValueError:
            end_dt = None
        return f"{start} – {end}", start_dt, end_dt
    if len(dates) == 1:
        start = f"{dates[0][0]}.{int(dates[0][1]):02d}.{int(dates[0][2]):02d}"
        try:
            start_dt = datetime(int(dates[0][0]), int(dates[0][1]), int(dates[0][2]))
        except ValueError:
            start_dt = None
        short_end = re.search(r"[–—\-]\s*(\d{1,2})[./](\d{1,2})", s)
        if short_end:
            em, ed = int(short_end.group(1)), int(short_end.group(2))
            ey = int(dates[0][0])
            end = f"{ey}.{em:02d}.{ed:02d}"
            try:
                end_dt = datetime(ey, em, ed)
            except ValueError:
                end_dt = None
            return f"{start} – {end}", start_dt, end_dt
        return f"{start} –", start_dt, None
    return raw_dates, None, None


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


def _calc_days_until_start(start_dt):
    """開始日までの日数を計算する。未来でなければNone、90日超もNone。"""
    if not start_dt:
        return None
    from datetime import datetime, timezone, timedelta
    tw_tz = timezone(timedelta(hours=8))
    delta = (start_dt - datetime.now(tw_tz).replace(tzinfo=None)).days
    if delta > 0 and delta <= 90:
        return delta
    return None


# 美術館の表示順序
MUSEUM_ORDER = ["honggah", "moca", "tfam", "clab", "thecube", "kdmofa", "ntcart", "chiayi", "tcma"]

# 地域の表示順序（北→南→東）
REGION_ORDER = [
    "taipei", "new_taipei", "taoyuan", "hsinchu", "yilan", "keelung",
    "taichung", "nantou", "chiayi", "tainan", "kaohsiung", "pingtung",
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
        normalized, start_dt, end_dt = _normalize_dates(ex.get("dates", ""))
        ex_by_museum[key].append({
            "title": _get_display_title(ex, lang),
            "dates": normalized,
            "days_left": _calc_days_left(end_dt),
            "days_until_start": _calc_days_until_start(start_dt),
            "status": ex.get("status", "unknown"),
            "location": ex.get("location", ""),
            "link": ex.get("link", ""),
            "artists": ex.get("artists", []),
            "curator": ex.get("curator", ""),
            "description": ex.get("description", ""),
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
            # 開催中の展覧会を最初、近日開始を後ろにソート
            exs.sort(key=lambda e: (
                0 if e.get("status") == "current" else
                (1 if e.get("status") == "upcoming" else 2),
                e.get("days_until_start") or 0,
            ))
            is_closed_today = _is_closed_today(m.get("closed_day"))
            has_current = any(e.get("status") == "current" or (
                e.get("status") == "unknown" and e.get("days_until_start") is None
            ) for e in exs)
            has_upcoming = any(e.get("status") == "upcoming" for e in exs)
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
                "has_current": has_current,
                "has_upcoming": has_upcoming,
                "exhibitions": exs,
            })

        active_count = sum(1 for me in museum_entries if me["has_current"])
        upcoming_count = sum(1 for me in museum_entries if me["has_upcoming"])
        if active_count == 0 and upcoming_count == 0:
            continue
        regions_data.append({
            "id": region_id,
            "name": _get_localized(
                master["regions"].get(region_id, {}), lang
            ),
            "active_count": active_count,
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


@app.route("/taishin")
def taishin():
    """台新藝術獎アーカイブページ。"""
    lang = request.args.get("lang", "ja")
    if lang not in TAISHIN_LABELS:
        lang = "ja"

    taishin_path = os.path.join(os.path.dirname(__file__), "taishin_award.json")
    try:
        with open(taishin_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        editions = list(reversed(data.get("editions", [])))
    except Exception:
        editions = []

    return render_template(
        "taishin.html",
        labels=TAISHIN_LABELS[lang],
        editions=editions,
        current_lang=lang,
        category_map=TAISHIN_CATEGORY_LABELS.get(lang, {}),
    )


TAISHIN_CATEGORY_LABELS = {
    "ja": {
        "視覺藝術獎": "視覚芸術賞",
        "視覺藝術": "視覚芸術",
        "表演藝術獎": "表演芸術賞",
        "表演藝術": "表演芸術",
        "年度大獎": "年度大賞",
        "年度入選獎": "年度入選",
        "評審團特別獎": "審査員特別賞",
    },
    "en": {
        "視覺藝術獎": "Visual Arts Award",
        "視覺藝術": "Visual Arts",
        "表演藝術獎": "Performing Arts Award",
        "表演藝術": "Performing Arts",
        "年度大獎": "Grand Prize",
        "年度入選獎": "Annual Selection",
        "評審團特別獎": "Jury Special Prize",
    },
    "zh": {},
}


TAISHIN_LABELS = {
    "en": {
        "title": "Taishin Arts Award — Winners & Finalists Archive",
        "subtitle": "Complete archive of Taiwan's most prestigious contemporary art award (2002–present)",
        "intro": "The Taishin Arts Award, established in 2002 by the Taishin Bank Foundation for Arts and Culture, is Taiwan's most important contemporary art prize. It recognizes outstanding works in visual arts and performing arts, with an annual Grand Prize of NT$1.5 million. This page archives all winners and finalists since the award's inception.",
        "winners": "Winners",
        "finalists": "Finalists",
        "articles": "Related Articles",
        "back": "Exhibitions",
    },
    "ja": {
        "title": "台新芸術賞 — 受賞者・ファイナリスト一覧",
        "subtitle": "台湾最高峰の現代芸術賞・全記録（2002年〜現在）",
        "intro": "台新芸術賞（Taishin Arts Award）は、台新銀行文化芸術基金会が2002年に創設した台湾最重要の現代芸術賞です。視覚芸術と舞台芸術の優れた作品を表彰し、年度大賞の賞金はNT$150万（約700万円）。このページでは創設以来の全受賞者とファイナリストを一覧できます。",
        "winners": "受賞者",
        "finalists": "ファイナリスト",
        "articles": "関連記事",
        "back": "展覧会情報",
    },
    "zh": {
        "title": "台新藝術獎 — 歷屆得獎者與入圍名單",
        "subtitle": "台灣最重要當代藝術獎項完整紀錄（2002年至今）",
        "intro": "台新藝術獎由台新銀行文化藝術基金會於2002年創立，是台灣最具指標性的當代藝術獎項。表彰視覺藝術與表演藝術領域的傑出作品，年度大獎獎金為新台幣150萬元。本頁彙整自創獎以來所有得獎者與入圍作品。",
        "winners": "得獎者",
        "finalists": "入圍",
        "articles": "相關報導",
        "back": "展覽資訊",
    },
}


@app.route("/archive")
def archive():
    """過去（終了済み）展覧会アーカイブ。"""
    from scraper import load_archive
    lang = request.args.get("lang", "ja")
    if lang not in ARCHIVE_LABELS:
        lang = "ja"
    master = _load_master()
    museum_names = {m["id"]: _get_localized(m["name"], lang) for m in master["museums"]}
    items = []
    for ex in load_archive():
        items.append({
            "title": _get_display_title(ex, lang),
            "museum_name": museum_names.get(ex.get("museum", ""), ex.get("museum", "")),
            "dates": ex.get("dates", ""),
            "link": ex.get("link", ""),
            "artists": ex.get("artists", []),
        })
    items.sort(key=lambda x: x["dates"], reverse=True)
    return render_template(
        "archive.html",
        labels=ARCHIVE_LABELS[lang],
        items=items,
        current_lang=lang,
    )


ARCHIVE_LABELS = {
    "en": {
        "title": "Archive — Taiwan Art Now",
        "subtitle": "Past exhibitions in Taiwan",
        "back": "Exhibitions",
        "no_data": "No archived exhibitions yet.",
    },
    "ja": {
        "title": "アーカイブ — Taiwan Art Now",
        "subtitle": "台湾の過去の展覧会",
        "back": "展覧会情報",
        "no_data": "まだアーカイブはありません。",
    },
    "zh": {
        "title": "歷年展覽 — Taiwan Art Now",
        "subtitle": "台灣過去的展覽",
        "back": "展覽資訊",
        "no_data": "暫無歷年展覽資料。",
    },
}


@app.route("/search")
def search():
    """展覧会・アーティスト・施設の横断検索。"""
    from scraper import fetch_all_exhibitions, get_artist_index
    lang = request.args.get("lang", "ja")
    if lang not in SEARCH_LABELS:
        lang = "ja"
    query = request.args.get("q", "").strip().lower()
    results = {"exhibitions": [], "artists": [], "museums": []}
    if query and len(query) >= 2:
        master = _load_master()
        museum_names = {m["id"]: _get_localized(m["name"], lang) for m in master["museums"]}
        # 展覧会検索
        for ex in fetch_all_exhibitions():
            haystack = " ".join([
                ex.get("title_en", ""), ex.get("title_zh", ""), ex.get("title_ja", ""),
                " ".join(ex.get("artists", [])), ex.get("curator", ""),
            ]).lower()
            if query in haystack:
                results["exhibitions"].append({
                    "title": _get_display_title(ex, lang),
                    "museum_name": museum_names.get(ex.get("museum", ""), ex.get("museum", "")),
                    "dates": ex.get("dates", ""),
                    "link": ex.get("link", ""),
                    "artists": ex.get("artists", []),
                })
        # アーティスト検索
        index = get_artist_index()
        for key, info in index.items():
            if query in info["name"].lower():
                results["artists"].append({
                    "key": key,
                    "name": info["name"],
                    "count": len(info["exhibitions"]),
                })
        results["artists"].sort(key=lambda x: -x["count"])
        # 施設検索
        for m in master["museums"]:
            names_text = " ".join(str(v) for v in m.get("name", {}).values()).lower()
            if query in names_text:
                results["museums"].append({
                    "id": m["id"],
                    "name": _get_localized(m["name"], lang),
                    "url": m.get("url", ""),
                })
    return render_template(
        "search.html",
        labels=SEARCH_LABELS[lang],
        query=query,
        results=results,
        current_lang=lang,
    )


SEARCH_LABELS = {
    "en": {
        "title": "Search — Taiwan Art Now",
        "placeholder": "Search exhibitions, artists, museums…",
        "back": "Exhibitions",
        "exhibitions": "Exhibitions",
        "artists": "Artists",
        "museums": "Museums",
        "no_results": "No results.",
        "type_to_search": "Type at least 2 characters to search.",
    },
    "ja": {
        "title": "検索 — Taiwan Art Now",
        "placeholder": "展覧会・アーティスト・美術館を検索…",
        "back": "展覧会情報",
        "exhibitions": "展覧会",
        "artists": "アーティスト",
        "museums": "美術館",
        "no_results": "結果なし。",
        "type_to_search": "2文字以上入力してください。",
    },
    "zh": {
        "title": "搜尋 — Taiwan Art Now",
        "placeholder": "搜尋展覽、藝術家、美術館…",
        "back": "展覽資訊",
        "exhibitions": "展覽",
        "artists": "藝術家",
        "museums": "美術館",
        "no_results": "無結果。",
        "type_to_search": "請輸入2個字元以上進行搜尋。",
    },
}


@app.route("/artists")
def artists_index():
    """全アーティスト一覧ページ（展覧会数の多い順）。"""
    from scraper import get_artist_index
    lang = request.args.get("lang", "ja")
    if lang not in ARTIST_LABELS:
        lang = "ja"
    index = get_artist_index()
    artists_list = sorted(
        [{"key": k, "name": v["name"], "count": len(v["exhibitions"])}
         for k, v in index.items()],
        key=lambda x: -x["count"],
    )
    return render_template(
        "artists.html",
        labels=ARTIST_LABELS[lang],
        artists=artists_list,
        current_lang=lang,
    )


@app.route("/artist/<artist_key>")
def artist_detail(artist_key):
    """アーティスト個別ページ。"""
    from scraper import get_artist_index, MUSEUMS
    lang = request.args.get("lang", "ja")
    if lang not in ARTIST_LABELS:
        lang = "ja"
    index = get_artist_index()
    info = index.get(artist_key)
    if not info:
        return render_template(
            "artists.html",
            labels=ARTIST_LABELS[lang],
            artists=[],
            current_lang=lang,
            not_found=artist_key,
        )
    master = _load_master()
    museum_names = {m["id"]: _get_localized(m["name"], lang) for m in master["museums"]}
    exhibitions = []
    for ex in info["exhibitions"]:
        exhibitions.append({
            "title": ex["title"],
            "dates": ex["dates"],
            "museum_name": museum_names.get(ex["museum"], ex["museum"]),
            "link": ex["link"],
        })
    return render_template(
        "artist_detail.html",
        labels=ARTIST_LABELS[lang],
        artist_name=info["name"],
        exhibitions=exhibitions,
        current_lang=lang,
    )


ARTIST_LABELS = {
    "en": {
        "title": "Artists — Taiwan Art Now",
        "subtitle": "Artists exhibiting in Taiwan",
        "back": "Exhibitions",
        "exhibitions": "Exhibitions",
        "venue": "Venue",
        "no_data": "No exhibition data available yet for this artist.",
    },
    "ja": {
        "title": "アーティスト一覧 — Taiwan Art Now",
        "subtitle": "台湾で展示中のアーティスト",
        "back": "展覧会情報",
        "exhibitions": "展覧会",
        "venue": "会場",
        "no_data": "このアーティストの展覧会データはまだありません。",
    },
    "zh": {
        "title": "藝術家 — Taiwan Art Now",
        "subtitle": "在台灣展出的藝術家",
        "back": "展覽資訊",
        "exhibitions": "展覽",
        "venue": "場地",
        "no_data": "暫無此藝術家的展覽資料。",
    },
}


@app.route("/health")
def health():
    """ヘルスチェック用（cron ping向け軽量エンドポイント）。"""
    return "ok", 200


if __name__ == "__main__":
    app.run(debug=True, port=5050)
