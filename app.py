"""台湾現代アート展覧会情報アプリ"""

from flask import Flask, render_template, request
from scraper import fetch_all_exhibitions, MUSEUMS
import json
import os

app = Flask(__name__)


@app.after_request
def add_no_cache_headers(response):
    """CLOSED TODAY等のリアルタイム情報がCDNにキャッシュされないようにする。"""
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


# 多言語UIラベル
UI_LABELS = {
    "en": {
        "title": "Taiwan Contemporary Art Exhibitions",
        "subtitle": "Taiwan contemporary art exhibitions",
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
        "subtitle": "台湾の現代アート展覧会情報",
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
        "subtitle": "台灣當代藝術展覽資訊",
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


def _get_description(ex, lang):
    """言語に応じた展覧会概要を返す。"""
    if lang == "ja":
        return ex.get("description_ja") or ex.get("description_en") or ex.get("description", "")
    elif lang == "en":
        return ex.get("description_en") or ex.get("description", "")
    return ex.get("description", "")


def _get_display_title(exhibition, lang):
    """言語に応じた展覧会タイトルを返す。
    en/jaページ: title_enがあれば「EN — 中文」形式で両方表示（現地で展示を探しやすくする）。
    zhページ: 中文優先、英語があれば後ろに添える。
    一方が他方を含む場合は長い方だけ表示（重複回避）。
    """
    title_en = exhibition.get("title_en", "").strip()
    title_zh = exhibition.get("title_zh", "").strip()

    def _should_combine(a, b):
        """2つのタイトルが十分に異なり、結合表示すべきか判定。"""
        if not a or not b or a == b:
            return False
        if a in b or b in a:
            return False
        return True

    if lang == "zh":
        return title_zh or title_en or "(Untitled)"

    # en / ja: 英語を先頭に、中文を添える
    if _should_combine(title_en, title_zh):
        return f"{title_en} — {title_zh}"
    # title_enがtitle_zhの一部なら、title_zh（より完全な方）を表示
    if title_en and title_zh:
        return title_zh if title_en in title_zh else (title_en if title_zh in title_en else title_en)
    return title_en or title_zh or "(Untitled)"


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
    dates = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", s)
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
    """終了日までの残日数を計算する。Noneまたは14日超はNone。
    最終日当日は1と表示（「今日が最後」）。"""
    if not end_dt:
        return None
    from datetime import datetime, timezone, timedelta
    tw_tz = timezone(timedelta(hours=8))
    today = datetime.now(tw_tz).date()
    end_date = end_dt.date() if hasattr(end_dt, 'date') else end_dt
    delta = (end_date - today).days
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
    lang = request.args.get("lang", "zh")
    if lang not in UI_LABELS:
        lang = "zh"

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
        # 展覧会のインデックス（詳細ページ用）
        museum_ex_idx = len([e for e in ex_by_museum.get(key, [])])
        next_event = None
        for evt in ex.get("events", []):
            try:
                from datetime import datetime
                evt_date = datetime.strptime(evt["date"], "%Y/%m/%d").date()
                from datetime import timezone, timedelta
                today_date = datetime.now(timezone(timedelta(hours=8))).date()
                if evt_date >= today_date:
                    days_until = (evt_date - today_date).days
                    evt_title = evt.get(f"title_{lang}", "") or evt.get("title_en", "") or evt.get("title_zh", "")
                    next_event = {"date": evt["date"], "time": evt.get("time", ""), "title": evt_title, "days_until": days_until}
                    break
            except (ValueError, KeyError):
                pass
        stable_key = key + "__" + (ex.get("title_zh", "") or ex.get("title_en", "") or "")
        ex_by_museum[key].append({
            "title": _get_display_title(ex, lang),
            "stable_key": stable_key,
            "dates": normalized,
            "days_left": _calc_days_left(end_dt),
            "days_until_start": _calc_days_until_start(start_dt),
            "status": ex.get("status", "unknown"),
            "location": ex.get("location", ""),
            "link": ex.get("link", ""),
            "detail_url": f"/exhibition/{key}/{museum_ex_idx}?lang={lang}",
            "artists": ex.get("artists", []),
            "curator": ex.get("curator", ""),
            "description": ex.get("description", ""),
            "next_event": next_event,
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
            is_closed_today = _is_closed_today(m.get("closed_day"), m.get("closed_days"))
            has_current = any(e.get("status") == "current" or (
                e.get("status") == "unknown" and e.get("days_until_start") is None
            ) for e in exs)
            has_upcoming = any(e.get("status") == "upcoming" for e in exs)
            venue_events = []
            from datetime import datetime, timezone, timedelta
            today_date = datetime.now(timezone(timedelta(hours=8))).date()
            for evt in m.get("events", []):
                try:
                    evt_date = datetime.strptime(evt["date"], "%Y/%m/%d").date()
                    if evt_date >= today_date:
                        days_until = (evt_date - today_date).days
                        evt_title = evt.get(f"title_{lang}", "") or evt.get("title_en", "") or evt.get("title_zh", "")
                        evt_note = evt.get(f"note_{lang}", "") or evt.get("note_en", "") or evt.get("note_zh", "")
                        venue_events.append({
                            "date": evt["date"],
                            "time": evt.get("time", ""),
                            "title": evt_title,
                            "note": evt_note,
                            "type": evt.get("type", "event"),
                            "link": evt.get("link", ""),
                            "days_until": days_until,
                        })
                except (ValueError, KeyError):
                    pass

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
                "lat": m.get("lat", 0),
                "lng": m.get("lng", 0),
                "exhibitions": exs,
                "venue_events": venue_events,
            })

        active_count = sum(1 for me in museum_entries if me["has_current"])
        upcoming_count = sum(1 for me in museum_entries if me["has_upcoming"])
        if not museum_entries:
            continue
        pinned_ids = {"honggah", "fotoaura"}
        museum_entries.sort(key=lambda me: (
            0 if me["id"] in pinned_ids else 1,
            0 if me["exhibitions"] else 1,
        ))
        regions_data.append({
            "id": region_id,
            "name": _get_localized(
                master["regions"].get(region_id, {}), lang
            ),
            "active_count": active_count,
            "museums": museum_entries,
        })

    closing_soon = []
    for mid, exs in ex_by_museum.items():
        museum_info = next((m for m in master["museums"] if m["id"] == mid), None)
        region_name = ""
        if museum_info:
            region_id = museum_info.get("region", "")
            region_name = _get_localized(master["regions"].get(region_id, {}), lang)
        for ex in exs:
            dl = ex.get("days_left")
            if dl is not None and 0 <= dl <= 7 and ex.get("status") != "upcoming":
                closing_soon.append({
                    "title": ex["title"],
                    "days_left": dl,
                    "museum": _get_localized(museum_info["name"], lang) if museum_info else mid,
                    "region": region_name,
                    "detail_url": ex["detail_url"],
                })
    closing_soon.sort(key=lambda x: x["days_left"])

    from datetime import datetime, timezone, timedelta
    today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d")
    todays_events = []
    for region in regions_data:
        for museum in region["museums"]:
            for evt in museum.get("venue_events", []):
                if evt["date"] == today_str:
                    todays_events.append({
                        "time": evt["time"],
                        "title": evt["title"],
                        "museum": museum["name"],
                        "museum_id": museum["id"],
                        "region": region["name"],
                    })
            for ex in museum.get("exhibitions", []):
                ne = ex.get("next_event")
                if ne and ne.get("days_until") == 0:
                    todays_events.append({
                        "time": ne["time"],
                        "title": ne["title"],
                        "museum": museum["name"],
                        "museum_id": museum["id"],
                        "region": region["name"],
                    })

    labels = UI_LABELS[lang]
    region_names = {r_id: _get_localized(r_data, lang) for r_id, r_data in master.get("regions", {}).items()}
    region_names["other"] = "Other" if lang == "en" else ("その他" if lang == "ja" else "其他")

    # Museum name -> id mapping for localStorage key migration
    museum_name_to_id = {}
    for m in master["museums"]:
        for l in ("zh", "en", "ja"):
            n = m.get("name", {}).get(l, "")
            if n:
                museum_name_to_id[n] = m["id"]

    holiday_today = _get_holiday_today()
    last_updated = _get_last_updated()

    return render_template(
        "index.html",
        labels=labels,
        regions=regions_data,
        closing_soon=closing_soon,
        todays_events=todays_events,
        current_lang=lang,
        region_names_json=json.dumps(region_names, ensure_ascii=False),
        museum_name_to_id_json=json.dumps(museum_name_to_id, ensure_ascii=False),
        holiday_today=holiday_today,
        last_updated=last_updated,
    )


TAIWAN_HOLIDAYS_2026 = {
    "2026-01-01": "元旦",
    "2026-02-16": "春節", "2026-02-17": "春節", "2026-02-18": "春節",
    "2026-02-19": "春節", "2026-02-20": "春節",
    "2026-02-27": "和平紀念日(補假)", "2026-02-28": "和平紀念日",
    "2026-04-03": "兒童節(補假)", "2026-04-04": "兒童節",
    "2026-04-05": "清明節", "2026-04-06": "清明節(補假)",
    "2026-05-01": "勞動節",
    "2026-06-19": "端午節",
    "2026-09-25": "中秋節",
    "2026-10-09": "國慶日(補假)", "2026-10-10": "國慶日",
    "2026-12-25": "行憲紀念日",
    "2026-12-31": "跨年",
}


def _get_holiday_today():
    """本日が台湾の祝祭日かどうか判定し、祝日名を返す。Noneなら平日。"""
    from datetime import datetime, timezone, timedelta
    tw_tz = timezone(timedelta(hours=8))
    today_str = datetime.now(tw_tz).strftime("%Y-%m-%d")
    return TAIWAN_HOLIDAYS_2026.get(today_str)


def _get_last_updated():
    """全展示のfetched_atのうち最新の日付を返す（サイトの最終更新表示用）。"""
    from datetime import datetime, timezone, timedelta
    details_path = os.path.join(os.path.dirname(__file__), "exhibition_details.json")
    try:
        with open(details_path, "r", encoding="utf-8") as f:
            details = json.load(f)
    except Exception:
        return None
    dates = [v.get("fetched_at") for v in details.values() if v.get("fetched_at")]
    if not dates:
        return None
    latest = max(dates)
    try:
        dt = datetime.fromisoformat(latest)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
        return dt.astimezone(timezone(timedelta(hours=8))).strftime("%Y.%m.%d")
    except Exception:
        return None


def _is_closed_today(closed_day, closed_days=None):
    """本日が休館日かどうか判定する（0=月曜, 6=日曜）。台湾時間(UTC+8)基準。
    祝祭日の場合はFalseを返す（祝日は別途注意喚起するため）。"""
    from datetime import datetime, timezone, timedelta
    tw_tz = timezone(timedelta(hours=8))
    # 祝祭日は曜日休館判定をスキップ（施設により対応が異なるため）
    today_str = datetime.now(tw_tz).strftime("%Y-%m-%d")
    if today_str in TAIWAN_HOLIDAYS_2026:
        return False
    today_weekday = datetime.now(tw_tz).weekday()
    if closed_days:
        return today_weekday in closed_days
    if closed_day is not None:
        return today_weekday == closed_day
    return False


@app.route("/taishin")
def taishin():
    """台新藝術獎アーカイブページ。"""
    lang = request.args.get("lang", "zh")
    if lang not in TAISHIN_LABELS:
        lang = "zh"

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


@app.route("/featured")
def featured():
    """台新賞受賞アーティストの動向ページ。"""
    lang = request.args.get("lang", "zh")
    if lang not in FEATURED_LABELS:
        lang = "zh"

    activities_path = os.path.join(os.path.dirname(__file__), "artist_activities.json")
    taishin_path = os.path.join(os.path.dirname(__file__), "taishin_award.json")

    artists_data = []
    try:
        with open(activities_path, "r", encoding="utf-8") as f:
            activities = json.load(f).get("artists", {})
        with open(taishin_path, "r", encoding="utf-8") as f:
            taishin = json.load(f)

        # 対象: 直近10年の視覚芸術賞+年度大賞
        target_cats = ["視覺藝術獎", "年度大獎"]
        for ed in reversed(taishin.get("editions", [])):
            if ed["edition"] < 15:
                break
            for w in ed.get("winners", []):
                if w.get("category_zh") not in target_cats:
                    continue
                en = w.get("artist_en", "")
                zh = w.get("artist_zh", "")
                if not en:
                    continue
                # 表演芸術系を除外（視覚芸術フォーカス）
                performing_keywords = ["劇團", "舞團", "劇場", "Theatre", "Dance", "Troupe"]
                if any(kw in zh or kw in en for kw in performing_keywords):
                    continue
                activity = activities.get(en, {})
                artists_data.append({
                    "artist_en": en,
                    "artist_zh": zh,
                    "edition": ed["edition"],
                    "category": w.get("category_zh", ""),
                    "articles": sorted(
                        activity.get("articles", []),
                        key=lambda a: a.get("date", ""), reverse=True,
                    ),
                    "current_exhibitions": activity.get("current_exhibitions", []),
                })
    except Exception:
        pass

    return render_template(
        "featured.html",
        labels=FEATURED_LABELS[lang],
        artists=artists_data,
        current_lang=lang,
    )


FEATURED_LABELS = {
    "en": {
        "title": "Featured Artists — Taiwan Art Now",
        "subtitle": "Recent activities of Taishin Arts Award visual arts winners",
        "intro": "Tracking the latest exhibitions and activities of Taishin Arts Award winners in visual arts and grand prize categories (2016–present). Articles sourced from ARTouch and other media.",
        "back": "Exhibitions",
        "no_articles": "No recent articles found.",
        "current_shows": "Current Exhibitions",
        "international": "International",
        "recent_press": "Recent Press",
    },
    "ja": {
        "title": "注目アーティスト — Taiwan Art Now",
        "subtitle": "台新芸術賞 視覚芸術賞受賞者の最新動向",
        "intro": "台新芸術賞の視覚芸術賞・年度大賞の受賞者（2016年以降）の最新展示活動を追跡しています。記事はARTouch等のメディアから収集。",
        "back": "展覧会情報",
        "no_articles": "最近の記事が見つかりません。",
        "current_shows": "現在の展示",
        "international": "国際的な活動",
        "recent_press": "最近の記事",
    },
    "zh": {
        "title": "焦點藝術家 — Taiwan Art Now",
        "subtitle": "台新藝術獎視覺藝術得主近期動態",
        "intro": "追蹤台新藝術獎視覺藝術獎與年度大獎得主（2016年至今）的最新展覽活動。報導來源為典藏ARTouch等藝術媒體。",
        "back": "展覽資訊",
        "no_articles": "暫無近期報導。",
        "current_shows": "現正展出",
        "international": "國際動態",
        "recent_press": "近期報導",
    },
}


@app.route("/archive")
def archive():
    """過去（終了済み）展覧会アーカイブ。"""
    from scraper import load_archive
    lang = request.args.get("lang", "zh")
    if lang not in ARCHIVE_LABELS:
        lang = "zh"
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


@app.route("/api/subscribers/sync", methods=["POST"])
def api_sync_favs():
    """Sync user favs/visited from client to server (tied to Messenger sender_id or ref)."""
    data = request.get_json(silent=True) or {}
    sender_id = data.get("sender_id", "")
    ref_code = data.get("ref", "")
    favs = data.get("favs", {})
    visited = data.get("visited", {})
    subs = _load_subscribers()
    # Resolve sender_id from ref if not provided directly
    if not sender_id and ref_code:
        sender_id = subs.get("refs", {}).get(ref_code, "")
    if not sender_id:
        return {"error": "sender_id or valid ref required"}, 400
    if sender_id not in subs["users"]:
        return {"error": "not subscribed"}, 404
    subs["users"][sender_id]["favs"] = favs
    subs["users"][sender_id]["visited"] = visited
    _save_subscribers(subs)
    return {"status": "synced"}


@app.route("/api/subscribers/link-ref", methods=["POST"])
def api_link_ref():
    """Link a ref code to an existing subscriber (for manual pairing)."""
    data = request.get_json(silent=True) or {}
    ref_code = data.get("ref", "")
    sender_id = data.get("sender_id", "")
    if not ref_code or not sender_id:
        return {"error": "ref and sender_id required"}, 400
    subs = _load_subscribers()
    if sender_id not in subs["users"]:
        return {"error": "sender_id not subscribed"}, 404
    if "refs" not in subs:
        subs["refs"] = {}
    subs["refs"][ref_code] = sender_id
    subs["users"][sender_id]["ref"] = ref_code
    _save_subscribers(subs)
    return {"status": "linked"}


@app.route("/api/subscribers/status")
def api_subscriber_status():
    """Check subscription status by sender_id or ref code."""
    sender_id = request.args.get("sender_id", "")
    ref_code = request.args.get("ref", "")
    subs = _load_subscribers()
    if ref_code:
        sid = subs.get("refs", {}).get(ref_code)
        if sid and sid in subs["users"]:
            user = subs["users"][sid]
            return {"subscribed": True, "weekly_digest": user.get("weekly_digest", True), "fav_alerts": user.get("fav_alerts", True)}
        return {"subscribed": False}
    if sender_id:
        user = subs["users"].get(sender_id)
        if user:
            return {"subscribed": True, "weekly_digest": user.get("weekly_digest", True), "fav_alerts": user.get("fav_alerts", True)}
    return {"subscribed": False}


@app.route("/api/subscribers/unsubscribe", methods=["POST"])
def api_unsubscribe():
    """Unsubscribe via ref code (called from site UI)."""
    data = request.get_json(silent=True) or {}
    ref_code = data.get("ref", "")
    if not ref_code:
        return {"error": "ref required"}, 400
    subs = _load_subscribers()
    sender_id = subs.get("refs", {}).get(ref_code)
    if sender_id and sender_id in subs["users"]:
        del subs["users"][sender_id]
        if ref_code in subs.get("refs", {}):
            del subs["refs"][ref_code]
        _save_subscribers(subs)
        return {"status": "unsubscribed"}
    return {"error": "not found"}, 404


@app.route("/api/subscribers/settings", methods=["POST"])
def api_subscriber_settings():
    """Update notification settings for a subscriber."""
    data = request.get_json(silent=True) or {}
    sender_id = data.get("sender_id", "")
    if not sender_id:
        return {"error": "sender_id required"}, 400
    subs = _load_subscribers()
    if sender_id not in subs["users"]:
        return {"error": "not subscribed"}, 404
    if "weekly_digest" in data:
        subs["users"][sender_id]["weekly_digest"] = bool(data["weekly_digest"])
    if "fav_alerts" in data:
        subs["users"][sender_id]["fav_alerts"] = bool(data["fav_alerts"])
    _save_subscribers(subs)
    return {"status": "updated"}


@app.route("/api/archive")
def api_archive():
    """Archive JSON API for mylist visited tab."""
    from scraper import load_archive
    master = _load_master()
    museum_names = {m["id"]: m.get("name", {}) for m in master["museums"]}
    items = []
    for ex in load_archive():
        mid = ex.get("museum", "")
        names = museum_names.get(mid, {})
        key_raw = (names.get("zh", mid) or mid) + "__" + (ex.get("title_zh", "") or ex.get("title_en", ""))
        items.append({
            "key": key_raw,
            "title_zh": ex.get("title_zh", ""),
            "title_en": ex.get("title_en", ""),
            "museum": names.get("zh", mid),
            "museum_en": names.get("en", mid),
            "dates": ex.get("dates", ""),
            "artists": ex.get("artists", []),
        })
    return {"exhibitions": items}


@app.route("/search")
def search():
    """展覧会・アーティスト・施設の横断検索。"""
    from scraper import fetch_all_exhibitions, get_artist_index
    lang = request.args.get("lang", "zh")
    if lang not in SEARCH_LABELS:
        lang = "zh"
    query = request.args.get("q", "").strip().lower()
    results = {"exhibitions": [], "artists": [], "museums": []}
    if query and len(query) >= 2:
        master = _load_master()
        museum_names = {m["id"]: _get_localized(m["name"], lang) for m in master["museums"]}
        # 展覧会検索（museum_ex_idxはトップページと同じ並び順で算出し、detail_urlを一致させる）
        museum_ex_counts = {}
        for ex in fetch_all_exhibitions():
            museum_id = ex.get("museum", "")
            museum_ex_idx = museum_ex_counts.get(museum_id, 0)
            museum_ex_counts[museum_id] = museum_ex_idx + 1
            haystack = " ".join([
                ex.get("title_en", ""), ex.get("title_zh", ""), ex.get("title_ja", ""),
                " ".join(ex.get("artists", [])), ex.get("curator", ""),
            ]).lower()
            if query in haystack:
                results["exhibitions"].append({
                    "title": _get_display_title(ex, lang),
                    "museum_name": museum_names.get(museum_id, museum_id),
                    "dates": ex.get("dates", ""),
                    "link": ex.get("link", ""),
                    "detail_url": f"/exhibition/{museum_id}/{museum_ex_idx}?lang={lang}",
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
    lang = request.args.get("lang", "zh")
    if lang not in ARTIST_LABELS:
        lang = "zh"
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
    lang = request.args.get("lang", "zh")
    if lang not in ARTIST_LABELS:
        lang = "zh"
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


@app.route("/exhibition/<museum_id>/<int:idx>")
def exhibition_detail(museum_id, idx):
    """展覧会個別ページ。"""
    lang = request.args.get("lang", "zh")
    from scraper import fetch_all_exhibitions
    master = _load_master()

    exhibitions = fetch_all_exhibitions()
    # museum_idに属する展覧会のidx番目
    museum_exs = [ex for ex in exhibitions if ex.get("museum") == museum_id]
    if idx >= len(museum_exs):
        return "Exhibition not found", 404

    ex = museum_exs[idx]
    normalized, start_dt, end_dt = _normalize_dates(ex.get("dates", ""))

    # 施設情報
    museum_info = None
    for m in master["museums"]:
        if m["id"] == museum_id:
            museum_info = m
            break

    stable_key = museum_id + "__" + (ex.get("title_zh", "") or ex.get("title_en", "") or "")

    # Other exhibitions at same museum
    other_exs = []
    for i, other in enumerate(museum_exs):
        if i == idx:
            continue
        other_norm, other_start, other_end = _normalize_dates(other.get("dates", ""))
        other_exs.append({
            "title": _get_display_title(other, lang),
            "dates": other_norm,
            "days_left": _calc_days_left(other_end),
            "detail_url": f"/exhibition/{museum_id}/{i}?lang={lang}",
        })

    return render_template(
        "exhibition_detail_page.html",
        exhibition={
            "title": _get_display_title(ex, lang),
            "title_zh": ex.get("title_zh", ""),
            "stable_key": stable_key,
            "dates": normalized,
            "days_left": _calc_days_left(end_dt),
            "days_until_start": _calc_days_until_start(start_dt),
            "artists": ex.get("artists", []),
            "curator": ex.get("curator", ""),
            "description": _get_description(ex, lang),
            "link": ex.get("link", ""),
            "status": ex.get("status", "unknown"),
        },
        museum={
            "id": museum_id,
            "name": _get_localized(museum_info["name"], lang) if museum_info else museum_id,
            "address": _get_localized(museum_info.get("address", {}), lang) if museum_info else "",
            "hours": _get_localized(museum_info.get("hours", {}), lang) if museum_info else "",
            "url": museum_info.get("url", "") if museum_info else "",
            "closed_today": _is_closed_today(museum_info.get("closed_day"), museum_info.get("closed_days")) if museum_info else False,
        },
        current_lang=lang,
        museum_id=museum_id,
        idx=idx,
        other_exhibitions=other_exs,
        has_coordinates=bool(museum_info and museum_info.get("lat")),
    )



@app.route("/og-image/exhibition/<museum_id>/<int:idx>")
def og_image_exhibition(museum_id, idx):
    """動的OGP画像生成（展示詳細ページ用）。"""
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO
    from scraper import fetch_all_exhibitions

    exhibitions = fetch_all_exhibitions()
    museum_exs = [ex for ex in exhibitions if ex.get("museum") == museum_id]
    if idx >= len(museum_exs):
        return "", 404

    ex = museum_exs[idx]
    master = _load_master()
    museum_info = next((m for m in master["museums"] if m["id"] == museum_id), None)
    museum_name = museum_info["name"].get("zh", museum_id) if museum_info else museum_id

    title_zh = ex.get("title_zh", "") or ex.get("title_en", "")
    title_en = ex.get("title_en", "")
    dates = ex.get("dates", "")
    artists = ex.get("artists", [])
    artist_str = " · ".join(artists[:3])
    if len(artists) > 3:
        artist_str += f" +{len(artists)-3}"

    import os
    import hashlib
    import random as rnd

    width, height = 1200, 630

    # CJK対応フォント（バンドル済みNoto Sans TC、繁体中文をそのまま表示するため必須）
    font_dir = os.path.join(os.path.dirname(__file__), "static", "fonts")
    bold_path = os.path.join(font_dir, "NotoSansTC-Bold.otf")
    regular_path = os.path.join(font_dir, "NotoSansTC-Regular.otf")

    try:
        title_font = ImageFont.truetype(bold_path, 56)
        sub_font = ImageFont.truetype(regular_path, 26)
        small_font = ImageFont.truetype(regular_path, 20)
        brand_font = ImageFont.truetype(bold_path, 22)
    except Exception:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        brand_font = ImageFont.load_default()

    # カテゴリごとの配色（怪可愛系：濃色ベース＋差し色）
    cat_palettes = {
        "public": {"bg": "#161a2e", "accent": "#7dd3fc", "line": "#2a3560"},
        "commercial": {"bg": "#1a2620", "accent": "#86efac", "line": "#2d4a38"},
        "alternative": {"bg": "#26182e", "accent": "#f0abfc", "line": "#4a2a56"},
        "private": {"bg": "#2e1f16", "accent": "#fdba74", "line": "#5a3a28"},
    }
    museum_cat = "public"
    for m in master.get("museums", []):
        if m["id"] == museum_id:
            museum_cat = m.get("category", "public")
            break
    palette = cat_palettes.get(museum_cat, cat_palettes["public"])
    bg_color = palette["bg"]
    accent = palette["accent"]
    ln_color = palette["line"]

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # タイトルからシードを作り、毎回同じ展示なら同じ模様になるようにする
    seed = int(hashlib.md5(title_zh.encode()).hexdigest()[:8], 16)
    rnd.seed(seed)
    for i in range(10):
        x, y = rnd.randint(0, width), rnd.randint(0, height)
        r = rnd.randint(40, 160)
        draw.ellipse([x - r, y - r, x + r, y + r], outline=ln_color, width=2)
    for i in range(50):
        x, y = rnd.randint(0, width), rnd.randint(0, height)
        s = rnd.randint(2, 5)
        draw.ellipse([x - s, y - s, x + s, y + s], fill=accent)

    # 左上にアクセントバー
    draw.rectangle([(0, 0), (10, height)], fill=accent)

    # タイトル（繁体中文）を折り返して表示。1行あたり最大14文字目安
    def wrap_cjk(text, max_chars):
        lines = []
        cur = ""
        for ch in text:
            cur += ch
            if len(cur) >= max_chars:
                lines.append(cur)
                cur = ""
        if cur:
            lines.append(cur)
        return lines[:3]

    title_lines = wrap_cjk(title_zh, 12)
    # 行数が多いほど開始位置を上げ、下の情報とぶつからないようにする
    ty = 240 - (len(title_lines) - 1) * 40
    for line in title_lines:
        draw.text((64, ty), line, fill="#000000", font=title_font)
        draw.text((60, ty - 4), line, fill="#ffffff", font=title_font)
        ty += 72

    # 英題（あれば小さく添える）
    if title_en and title_en != title_zh:
        draw.text((60, ty + 6), title_en[:60], fill=accent, font=sub_font)
        ty += 40

    info_y = ty + 40
    draw.text((60, info_y), museum_name, fill="#dddddd", font=sub_font)
    info_y += 34
    if dates:
        draw.text((60, info_y), dates, fill="#999999", font=small_font)
        info_y += 30
    if artist_str:
        draw.text((60, info_y), artist_str[:50], fill="#999999", font=small_font)

    # ブランドフッター
    draw.text((60, height - 60), "Taiwan Art Now", fill=accent, font=brand_font)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    from flask import send_file
    return send_file(buf, mimetype="image/png")


@app.route("/nearby/<museum_id>")
def nearby(museum_id):
    """指定施設の近くにある他の展示を返すAPIエンドポイント。"""
    import math
    lang = request.args.get("lang", "zh")
    master = _load_master()
    from scraper import fetch_all_exhibitions

    # 対象施設を探す
    target = None
    for m in master["museums"]:
        if m["id"] == museum_id:
            target = m
            break
    if not target or not target.get("lat"):
        return json.dumps({"error": "museum not found or no coordinates"}, ensure_ascii=False), 404

    lat1, lng1 = target["lat"], target["lng"]

    # 展覧会データ取得
    exhibitions = fetch_all_exhibitions()
    ex_by_museum = {}
    for ex in exhibitions:
        mid = ex.get("museum", "")
        if mid != museum_id:
            ex_by_museum.setdefault(mid, []).append(ex)

    # 距離計算（簡易ハーバーサイン）
    def distance_km(lat2, lng2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    # 近い施設を距離順で取得（5km以内）
    nearby_list = []
    for m in master["museums"]:
        if m["id"] == museum_id or not m.get("lat"):
            continue
        # Skip closed venues
        is_closed = _is_closed_today(m.get("closed_day"), m.get("closed_days"))
        if is_closed:
            continue
        dist = distance_km(m["lat"], m["lng"])
        if dist <= 5.0:
            exs = ex_by_museum.get(m["id"], [])
            if exs:
                venue_name = _get_localized(m["name"], lang)
                hours = _get_localized(m.get("hours", {}), lang)
                ex_items = []
                for i, ex in enumerate(exs[:3]):
                    normalized, start_dt, end_dt = _normalize_dates(ex.get("dates", ""))
                    # Find exhibition index in full museum list for detail_url
                    all_museum_exs = [e for e in exhibitions if e.get("museum") == m["id"]]
                    ex_idx = next((j for j, e in enumerate(all_museum_exs) if e.get("title_zh") == ex.get("title_zh")), i)
                    ex_items.append({
                        "title": _get_display_title(ex, lang),
                        "dates": normalized or ex.get("dates", ""),
                        "days_left": _calc_days_left(end_dt),
                        "days_until_start": _calc_days_until_start(start_dt),
                        "fav_key": m["id"] + "__" + (ex.get("title_zh", "") or ex.get("title_en", "") or ""),
                        "detail_url": f"/exhibition/{m['id']}/{ex_idx}?lang={lang}",
                    })
                nearby_list.append({
                    "museum_id": m["id"],
                    "name": venue_name,
                    "address": _get_localized(m.get("address", {}), lang),
                    "hours": hours,
                    "closed_today": is_closed,
                    "distance_km": round(dist, 1),
                    "exhibitions": ex_items,
                })

    nearby_list.sort(key=lambda x: x["distance_km"])
    return render_template(
        "nearby.html",
        museum_name=_get_localized(target["name"], lang),
        nearby=nearby_list[:5],
        current_lang=lang,
    )


@app.route("/calendar.ics")
def calendar_ics():
    """全展覧会のiCalカレンダーフィード。"""
    from scraper import fetch_all_exhibitions
    import re

    exhibitions = fetch_all_exhibitions()
    master = _load_master()
    museum_names = {m["id"]: m["name"].get("zh", m["name"].get("en", "")) for m in master["museums"]}

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Taiwan Art Now//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Taiwan Art Now",
    ]

    for ex in exhibitions:
        dates = ex.get("dates", "")
        date_matches = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", dates)
        if len(date_matches) < 2:
            continue
        try:
            sy, sm, sd = int(date_matches[0][0]), int(date_matches[0][1]), int(date_matches[0][2])
            ey, em, ed = int(date_matches[1][0]), int(date_matches[1][1]), int(date_matches[1][2])
        except (ValueError, IndexError):
            continue

        title = ex.get("title_zh") or ex.get("title_en") or ""
        museum = museum_names.get(ex.get("museum", ""), "")
        link = ex.get("link", "")
        uid = f"{ex.get('museum','')}-{sy}{sm:02d}{sd:02d}-{title[:10]}@taiwanartnow"

        lines.extend([
            "BEGIN:VEVENT",
            f"DTSTART;VALUE=DATE:{sy}{sm:02d}{sd:02d}",
            f"DTEND;VALUE=DATE:{ey}{em:02d}{ed:02d}",
            f"SUMMARY:{title}",
            f"LOCATION:{museum}",
            f"URL:{link}" if link else "",
            f"UID:{uid}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    ical = "\r\n".join(l for l in lines if l)

    return ical, 200, {
        "Content-Type": "text/calendar; charset=utf-8",
        "Content-Disposition": "attachment; filename=taiwan-art-now.ics",
    }


@app.route("/event.ics")
def event_ics():
    """単一イベントのiCalファイルを生成する。"""
    title = request.args.get("title", "Event")
    date = request.args.get("date", "")
    time_str = request.args.get("time", "")
    venue = request.args.get("venue", "")
    note = request.args.get("note", "")

    if not date:
        return "Missing date", 400

    date_clean = date.replace("/", "")
    if time_str:
        h, m = time_str.split(":")[:2]
        dtstart = f"{date_clean}T{h}{m}00"
        dtend_h = str(int(h) + 2).zfill(2)
        dtend = f"{date_clean}T{dtend_h}{m}00"
    else:
        dtstart = date_clean
        dtend = date_clean

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Taiwan Art Now//Event//EN",
        "BEGIN:VEVENT",
        f"DTSTART;TZID=Asia/Taipei:{dtstart}",
        f"DTEND;TZID=Asia/Taipei:{dtend}",
        f"SUMMARY:{title}",
        f"LOCATION:{venue}",
        f"DESCRIPTION:{note}",
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        "DESCRIPTION:Reminder",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    ical = "\r\n".join(lines)
    return ical, 200, {
        "Content-Type": "text/calendar; charset=utf-8",
        "Content-Disposition": f"attachment; filename=event-{date_clean}.ics",
    }


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/api/weather")
def weather_api():
    """CWA 36hr forecast proxy."""
    import urllib.request as urllib_req
    import ssl
    cwa_key = os.environ.get("CWA_API_KEY", "")
    if not cwa_key:
        return json.dumps({"error": "no key"}), 500
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={cwa_key}&format=JSON"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib_req.Request(url)
        with urllib_req.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read())
        locations = data.get("records", {}).get("location", [])
        result = {}
        for loc in locations:
            name = loc["locationName"]
            we = loc["weatherElement"]
            wx = we[0]["time"][0]["parameter"]["parameterName"]
            wx_code = we[0]["time"][0]["parameter"]["parameterValue"]
            rain = we[1]["time"][0]["parameter"]["parameterName"]
            temp_min = we[2]["time"][0]["parameter"]["parameterName"]
            temp_max = we[4]["time"][0]["parameter"]["parameterName"]
            result[name] = {"wx": wx, "code": wx_code, "rain": rain, "min": temp_min, "max": temp_max}
        return json.dumps(result, ensure_ascii=False), 200, {"Content-Type": "application/json", "Cache-Control": "public, max-age=1800"}
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


MESSENGER_VERIFY_TOKEN = "taiwanartnow2026"
MESSENGER_PAGE_TOKEN = os.environ.get("MESSENGER_PAGE_TOKEN", "")


@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """Meta Webhook verification (GET request)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == MESSENGER_VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


SUBSCRIBERS_FILE = os.path.join(os.path.dirname(__file__), "subscribers.json")


def _load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"users": {}}


def _save_subscribers(data):
    content = json.dumps(data, ensure_ascii=False, indent=2)
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    # Persist to GitHub repo (survives Render redeploys)
    _save_to_github("subscribers.json", content)


def _save_to_github(filename, content):
    """Save file to GitHub repository via API."""
    import urllib.request as urllib_req
    import base64
    gh_token = os.environ.get("GH_TOKEN", "")
    if not gh_token:
        return
    repo = "taiwan-chodofu/taiwan-art-now"
    api_url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    # Get current file SHA (needed for update)
    sha = ""
    try:
        req = urllib_req.Request(api_url, headers={
            "Authorization": f"token {gh_token}",
            "Accept": "application/vnd.github.v3+json",
        })
        resp = urllib_req.urlopen(req, timeout=10)
        sha = json.loads(resp.read()).get("sha", "")
    except Exception:
        pass
    # Create or update
    payload = json.dumps({
        "message": f"Auto-update {filename}",
        "content": encoded,
        "sha": sha,
    }).encode()
    try:
        req = urllib_req.Request(api_url, data=payload, headers={
            "Authorization": f"token {gh_token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json",
        }, method="PUT")
        urllib_req.urlopen(req, timeout=15)
    except Exception:
        pass


ADMIN_SENDER_ID = "27481470654840665"


def _add_subscriber(sender_id, ref_code=None):
    from datetime import datetime, timezone, timedelta
    subs = _load_subscribers()
    is_new = False
    if sender_id not in subs["users"]:
        subs["users"][sender_id] = {
            "subscribed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "weekly_digest": True,
            "fav_alerts": True,
        }
        is_new = True
    # Always update ref if provided (handles existing users connecting from new device)
    if ref_code:
        subs["users"][sender_id]["ref"] = ref_code
        if "refs" not in subs:
            subs["refs"] = {}
        subs["refs"][ref_code] = sender_id
    if is_new or ref_code:
        _save_subscribers(subs)
    if is_new and sender_id != ADMIN_SENDER_ID:
        _notify_admin_new_subscriber(sender_id)
    return is_new


def _notify_admin_new_subscriber(new_sender_id):
    page_token = os.environ.get("MESSENGER_PAGE_TOKEN", "")
    if not page_token:
        return
    subs = _load_subscribers()
    count = len(subs["users"])
    _send_messenger_reply(ADMIN_SENDER_ID,
        f"📢 新規登録！ (合計{count}人)\nsender_id: {new_sender_id}")


def _send_messenger_reply(sender_id, text):
    import urllib.request as urllib_req
    page_token = os.environ.get("MESSENGER_PAGE_TOKEN", "")
    if not page_token:
        return
    payload = json.dumps({
        "recipient": {"id": sender_id},
        "message": {"text": text},
    }).encode()
    req = urllib_req.Request(
        f"https://graph.facebook.com/v18.0/me/messages?access_token={page_token}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib_req.urlopen(req, timeout=10)
    except Exception:
        pass


@app.route("/webhook", methods=["POST"])
def webhook_receive():
    """Receive messages from Messenger and create GitHub issues."""
    import urllib.request as urllib_req
    from datetime import datetime, timezone, timedelta

    body = request.get_json(silent=True) or {}
    entries = body.get("entry", [])
    for entry in entries:
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id", "")

            # Handle standalone referral (existing user clicks m.me?ref=xxx)
            referral = event.get("referral", {})
            if referral and not event.get("postback") and not event.get("message"):
                ref_code = referral.get("ref", "")
                if ref_code:
                    _add_subscriber(sender_id, ref_code=ref_code)
                    _send_messenger_reply(sender_id,
                        "✓ 已連結 / Connected\n\n"
                        "🌐 https://taiwan-art-now.onrender.com/")
                continue

            # Handle postback (Get Started / Ice Breakers)
            postback = event.get("postback", {})
            referral_from_postback = event.get("referral", {}) or postback.get("referral", {})
            ref_code = referral_from_postback.get("ref", "") if referral_from_postback else ""
            if postback:
                payload = postback.get("payload", "")
                if payload == "SUBSCRIBE_NOTIFICATIONS":
                    is_new = _add_subscriber(sender_id, ref_code=ref_code)
                    if is_new:
                        _send_messenger_reply(sender_id,
                            "🎨 歡迎！你已訂閱每週展覽通知。\n\n"
                            "也歡迎隨時傳送：\n"
                            "📌 想掲載的展覽名稱或URL\n"
                            "📍 想知道附近有什麼展覽\n\n"
                            "🌐 taiwan-art-now.onrender.com\n\n"
                            "─────\n"
                            "Welcome! You're subscribed to weekly exhibition updates.\n\n"
                            "Feel free to send:\n"
                            "📌 Exhibition info you'd like listed\n"
                            "📍 Ask what's nearby\n\n"
                            "━━━━━\n"
                            "取消: 輸入「取消」/ Unsubscribe: type \"stop\"")
                    else:
                        _send_messenger_reply(sender_id,
                            "✓ 已訂閱\n\n"
                            "歡迎傳送展覽資訊或詢問附近展覽 📌📍\n\n"
                            "━━━━━\n"
                            "取消: 輸入「取消」")
                    continue

            message = event.get("message", {})
            text = message.get("text", "")
            attachments = message.get("attachments", [])

            image_urls = [a["payload"]["url"] for a in attachments if a.get("type") == "image" and a.get("payload", {}).get("url")]

            if not text and not image_urls:
                continue

            # Handle unsubscribe keywords
            text_lower = text.strip().lower()
            if text_lower in ("取消", "unsubscribe", "解除", "退訂", "stop", "登録解除"):
                subs = _load_subscribers()
                if sender_id in subs["users"]:
                    del subs["users"][sender_id]
                    _save_subscribers(subs)
                    _send_messenger_reply(sender_id,
                        "✓ 已取消訂閱，不會再收到通知。\n\n"
                        "如需重新訂閱: 輸入「訂閱」\n\n"
                        "─────────────────\n\n"
                        "✓ Unsubscribed. You won't receive further notifications.\n\n"
                        "To re-subscribe: type \"subscribe\"")
                else:
                    _send_messenger_reply(sender_id,
                        "目前尚未訂閱。\n\nNot currently subscribed.")
                continue

            # Handle re-subscribe keywords
            if text_lower in ("訂閱", "subscribe", "登録", "開始"):
                _add_subscriber(sender_id)
                _send_messenger_reply(sender_id,
                    "🎨 已訂閱！每週三將收到展覽結束提醒。\n\n"
                    "🌐 https://taiwan-art-now.onrender.com/\n\n"
                    "─────────────────\n\n"
                    "🎨 Subscribed! Weekly updates on exhibitions ending soon.\n\n"
                    "🌐 https://taiwan-art-now.onrender.com/?lang=en\n\n"
                    "━━━━━━━━━━\n"
                    "取消訂閱 Unsubscribe: 輸入「取消」或「unsubscribe」")
                continue

            # Auto-subscribe anyone who messages the page
            _add_subscriber(sender_id)

            body_parts = [f"**From Messenger:** sender_id={sender_id}"]
            if text:
                body_parts.append(f"**Message:** {text}")
            for img in image_urls:
                body_parts.append(f"**Image:** ![photo]({img})")
            tw_now = datetime.now(timezone(timedelta(hours=8)))
            body_parts.append(f"**Received:** {tw_now.isoformat()}")

            issue_body = "\n\n".join(body_parts)
            issue_data = json.dumps({
                "title": f"[Messenger] {text[:50] or 'Image submission'}",
                "body": issue_body,
                "labels": ["user-request"],
            }).encode()

            gh_token = os.environ.get("GH_TOKEN", "")
            if gh_token:
                req = urllib_req.Request(
                    "https://api.github.com/repos/taiwan-chodofu/taiwan-art-now/issues",
                    data=issue_data,
                    headers={
                        "Authorization": f"token {gh_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    method="POST",
                )
                try:
                    urllib_req.urlopen(req, timeout=10)
                except Exception:
                    pass

    return "OK", 200


@app.route("/health")
def health():
    """ヘルスチェック用（cron ping向け軽量エンドポイント）。
    バックグラウンドで1アーティストのARTouch記事を更新する。"""
    import threading
    t = threading.Thread(target=_update_one_artist_activity, daemon=True)
    t.start()
    return "ok", 200


def _update_one_artist_activity():
    """1アーティストのARTouch記事を更新する（ローテーション）。"""
    import urllib.parse
    try:
        from curl_cffi import requests as cffi_requests
        from bs4 import BeautifulSoup
    except ImportError:
        return

    activities_path = os.path.join(os.path.dirname(__file__), "artist_activities.json")
    try:
        with open(activities_path, "r", encoding="utf-8") as f:
            activities = json.load(f)
    except Exception:
        return

    artists = list(activities.get("artists", {}).keys())
    if not artists:
        return

    # ローテーション: generated timestamp のハッシュで決定
    import hashlib
    gen = activities.get("generated", "")
    idx = int(hashlib.md5(gen.encode()).hexdigest(), 16) % len(artists)
    # 次のアーティスト
    target_en = artists[(idx + 1) % len(artists)]
    artist_data = activities["artists"].get(target_en, {})
    zh = artist_data.get("artist_zh", "")
    if not zh:
        return

    try:
        import re
        query = urllib.parse.quote(zh)
        url = f"https://artouch.com/?s={query}"
        resp = cffi_requests.get(url, impersonate="chrome", timeout=15)
        if resp.status_code != 200:
            return
        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.find_all("a", href=re.compile(r"content-\d+\.html"))
        seen = set()
        articles = []
        for a in links:
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if href not in seen and title and len(title) > 10:
                seen.add(href)
                articles.append({"title": title[:100], "url": href, "source": "ARTouch"})
        if articles:
            activities["artists"][target_en]["articles"] = articles[:10]
            activities["generated"] = __import__("datetime").datetime.now().isoformat()
            text = json.dumps(activities, ensure_ascii=False, indent=2)
            text = re.sub(r"[\ud800-\udfff]", "", text)
            with open(activities_path, "w", encoding="utf-8") as f:
                f.write(text)
    except Exception:
        pass


@app.route("/api/submit", methods=["POST"])
def submit_request():
    """ユーザー投稿を受け付け、GitHub Issues に作成する。"""
    import urllib.request as urllib_req

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    lat = data.get("lat")
    lng = data.get("lng")
    image_url = data.get("image_url", "")

    if not text and not lat and not image_url:
        return json.dumps({"error": "empty"}), 400

    body_parts = []
    if text:
        body_parts.append(f"**Message:** {text}")
    if lat and lng:
        body_parts.append(f"**Location:** [{lat}, {lng}](https://www.google.com/maps?q={lat},{lng})")
    if image_url:
        body_parts.append(f"**Image:** ![photo]({image_url})")
    from datetime import datetime, timezone, timedelta
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    body_parts.append(f"**Submitted:** {tw_now.isoformat()}")

    issue_body = "\n\n".join(body_parts)
    issue_data = json.dumps({
        "title": f"[User Request] {text[:50] or 'Location submission'}",
        "body": issue_body,
        "labels": ["user-request"],
    }).encode()

    gh_token = os.environ.get("GH_TOKEN", "")
    if gh_token:
        req = urllib_req.Request(
            "https://api.github.com/repos/taiwan-chodofu/taiwan-art-now/issues",
            data=issue_data,
            headers={
                "Authorization": f"token {gh_token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github.v3+json",
            },
            method="POST",
        )
        try:
            urllib_req.urlopen(req, timeout=10)
        except Exception:
            pass

    return json.dumps({"ok": True}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5050)
