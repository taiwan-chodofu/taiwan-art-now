"""台湾現代アート美術館の展覧会情報スクレイパー"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import logging
import re
import threading

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache.json")
CACHE_TTL_HOURS = 6

_bg_lock = threading.Lock()
_bg_running = False

# 台湾タイムゾーン (UTC+8)
_TW_TZ = None

def _now_tw():
    """台湾時間(UTC+8)の現在時刻をnaive datetimeで返す。"""
    global _TW_TZ
    if _TW_TZ is None:
        from datetime import timezone, timedelta
        _TW_TZ = timezone(timedelta(hours=8))
    return datetime.now(_TW_TZ).replace(tzinfo=None)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8,ja;q=0.7",
}

# --- 美術館定義 ---
MUSEUMS = {
    "moca": {
        "name": {
            "en": "Museum of Contemporary Art, Taipei (MOCA)",
            "ja": "台北當代藝術館（MOCA Taipei）",
            "zh": "台北當代藝術館（MOCA Taipei）",
        },
        "url": "https://www.moca.taipei",
        "hours": {
            "en": "Tue–Sun 10:00–18:00 | Closed Mon",
            "ja": "火〜日 10:00–18:00 ｜ 月曜休館",
            "zh": "週二至週日 10:00–18:00 ｜ 週一休館",
        },
        "address": {
            "en": "No.39, Chang-An W. Rd., Datong Dist., Taipei",
            "ja": "台北市大同區長安西路39號",
            "zh": "台北市大同區長安西路39號",
        },
    },
    "tfam": {
        "name": {
            "en": "Taipei Fine Arts Museum (TFAM)",
            "ja": "台北市立美術館（TFAM）",
            "zh": "臺北市立美術館（TFAM）",
        },
        "url": "https://www.tfam.museum",
        "hours": {
            "en": "Tue–Sun 09:30–17:30 | Sat until 20:30 | Closed Mon",
            "ja": "火〜日 9:30–17:30 ｜ 土 20:30まで ｜ 月曜休館",
            "zh": "週二至週日 9:30–17:30 ｜ 週六延長至20:30 ｜ 週一休館",
        },
        "address": {
            "en": "No.181, Sec.3, Zhongshan N. Rd., Zhongshan Dist., Taipei",
            "ja": "台北市中山區中山北路三段181號",
            "zh": "臺北市中山區中山北路三段181號",
        },
    },
    "honggah": {
        "name": {
            "en": "Hong-Gah Museum",
            "ja": "鳳甲美術館（Hong-Gah Museum）",
            "zh": "鳳甲美術館",
        },
        "url": "https://hong-gah.org.tw",
        "hours": {
            "en": "Tue–Sun 10:30–17:30 | Closed Mon",
            "ja": "火〜日 10:30–17:30 ｜ 月曜休館",
            "zh": "週二至週日 10:30–17:30 ｜ 週一休館",
        },
        "address": {
            "en": "11F., No.166, Daye Rd., Beitou Dist., Taipei",
            "ja": "台北市北投區大業路166號11樓",
            "zh": "台北市北投區大業路166號11樓",
        },
    },
    "ntcart": {
        "name": {
            "en": "New Taipei City Art Museum",
            "ja": "新北市美術館",
            "zh": "新北市美術館",
        },
        "url": "https://ntcart.museum",
        "hours": {
            "en": "Tue–Sun 10:00–18:00 | Closed Mon",
            "ja": "火〜日 10:00–18:00 ｜ 月曜休館",
            "zh": "週二至週日 10:00–18:00 ｜ 週一休館",
        },
        "address": {
            "en": "No.2, Guanqian Rd., Yingge Dist., New Taipei City",
            "ja": "新北市鶯歌區館前路2號",
            "zh": "新北市鶯歌區館前路2號",
        },
    },
    "tcma": {
        "name": {
            "en": "Taichung City Museum of Art (TCMA)",
            "ja": "臺中市立美術館（TCMA）",
            "zh": "臺中市立美術館",
        },
        "url": "https://www.tcam.museum",
        "hours": {
            "en": "Tue–Fri, Sun 09:00–17:00 | Sat 09:00–20:00 | Closed Mon",
            "ja": "火〜金・日 9:00–17:00 ｜ 土 9:00–20:00 ｜ 月曜休館",
            "zh": "週二至週五、週日 09:00–17:00 ｜ 週六 09:00–20:00 ｜ 週一休館",
        },
        "address": {
            "en": "Taichung Green Museumbrary, Xitun Dist., Taichung",
            "ja": "台中市西屯区（台中グリーンミュージアムブラリー内）",
            "zh": "臺中市西屯區（臺中綠美圖）",
        },
    },
    "clab": {
        "name": {
            "en": "C-LAB (Taiwan Contemporary Culture Lab)",
            "ja": "C-LAB（臺灣當代文化實驗場）",
            "zh": "C-LAB 臺灣當代文化實驗場",
        },
        "url": "https://clab.org.tw",
        "hours": {
            "en": "Tue–Sun 11:00–18:00 | Closed Mon",
            "ja": "火〜日 11:00–18:00 ｜ 月曜休館",
            "zh": "週二至週日 11:00–18:00 ｜ 週一休館",
        },
        "address": {
            "en": "No.177, Sec.1, Jianguo S. Rd., Da'an Dist., Taipei",
            "ja": "台北市大安區建國南路一段177號",
            "zh": "臺北市大安區建國南路一段177號",
        },
    },
    "thecube": {
        "name": {
            "en": "TheCube Project Space",
            "ja": "立方計劃空間（TheCube）",
            "zh": "立方計劃空間",
        },
        "url": "https://thecubespace.com",
        "hours": {
            "en": "Wed–Sun 13:00–19:00 | Closed Mon–Tue",
            "ja": "水〜日 13:00–19:00 ｜ 月火休館",
            "zh": "週三至週日 13:00–19:00 ｜ 週一二休館",
        },
        "address": {
            "en": "2F, No.13, Ln.136, Sec.4, Roosevelt Rd., Da'an Dist., Taipei",
            "ja": "台北市大安區羅斯福路四段136巷13號2樓",
            "zh": "臺北市大安區羅斯福路四段136巷13號2樓",
        },
    },
    "chiayi": {
        "name": {
            "en": "Chiayi Art Museum",
            "ja": "嘉義市立美術館",
            "zh": "嘉義市立美術館",
        },
        "url": "https://chiayiartmuseum.chiayi.gov.tw",
        "hours": {
            "en": "Tue–Sun 09:00–17:00 | Closed Mon",
            "ja": "火〜日 9:00–17:00 ｜ 月曜休館",
            "zh": "週二至週日 09:00–17:00 ｜ 週一休館",
        },
        "address": {
            "en": "No.101, Guangning St., West Dist., Chiayi City",
            "ja": "嘉義市西區廣寧街101號",
            "zh": "嘉義市西區廣寧街101號",
        },
    },
    "kdmofa": {
        "name": {
            "en": "Kuandu Museum of Fine Arts (KdMoFA)",
            "ja": "關渡美術館（KdMoFA）",
            "zh": "關渡美術館",
        },
        "url": "https://kdmofa.tnua.edu.tw",
        "hours": {
            "en": "Tue–Sun 10:00–17:00 | Closed Mon",
            "ja": "火〜日 10:00–17:00 ｜ 月曜休館",
            "zh": "週二至週日 10:00–17:00 ｜ 週一休館",
        },
        "address": {
            "en": "No.1, Xueyuan Rd., Beitou Dist., Taipei (TNUA campus)",
            "ja": "台北市北投區學園路1號（國立臺北藝術大學内）",
            "zh": "臺北市北投區學園路1號（國立臺北藝術大學內）",
        },
    },
}


def _load_cache():
    """キャッシュファイルを読み込む。TTL内ならデータを返す。超過ならNone。"""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        age_hours = (_now_tw() - cached_at).total_seconds() / 3600
        if age_hours < CACHE_TTL_HOURS:
            return data.get("exhibitions", [])
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _load_cache_stale():
    """キャッシュファイルからデータを返す（TTL無視、古くてもOK）。"""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        exhibitions = data.get("exhibitions", [])
        if exhibitions:
            return exhibitions
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _save_cache(exhibitions):
    """展覧会データをキャッシュに保存する。"""
    data = {
        "cached_at": _now_tw().isoformat(),
        "exhibitions": exhibitions,
    }
    text = json.dumps(data, ensure_ascii=False, indent=2)
    text = re.sub(r"[\ud800-\udfff]", "", text)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def _fetch(url, timeout=8):
    """URLからHTMLを取得してBeautifulSoupオブジェクトを返す。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
    except requests.exceptions.SSLError:
        # 一部の台湾政府系サイトはSubject Key Identifierが欠落している
        logger.warning("SSL検証失敗、verify=Falseでリトライ: %s", url)
        resp = requests.get(
            url, headers=HEADERS, timeout=timeout, verify=False
        )
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def _fetch_rendered(url, wait_selector=None, timeout=60000):
    """PlaywrightでJSレンダリング後のHTMLを取得する（stealth対応）。"""
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            Stealth().apply_stealth_sync(ctx)
            page = ctx.new_page()
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout)
            else:
                page.wait_for_timeout(10000)
            html = page.content()
            browser.close()
            return BeautifulSoup(html, "lxml")
    except Exception as exc:
        logger.warning("Playwright fetch failed for %s: %s", url, exc)
        return None


def _scrape_moca(lang="en"):
    """MOCA Taipei から当期展覧会情報を取得する（詳細ページから日付取得）。"""
    exhibitions = []
    base = MUSEUMS["moca"]["url"]
    prefix = "/en" if lang == "en" else "/tw"
    url = f"{base}{prefix}/ExhibitionAndEvent/Exhibitions/Current%20Exhibition"
    title_key = f"title_{lang}"
    today = _now_tw()
    skip_keywords = ["Artist Talk", "Screening", "Lecture", "Workshop",
                     "Guided Tour", "Curator Talk", "Artist Meet",
                     "座談", "講座", "放映", "工作坊", "導覽",
                     "面對面", "小光點", "上誼"]
    try:
        soup = _fetch(url)
        seen = set()
        for link_tag in soup.select("a[href*='ExhibitionAndEvent/Info']"):
            href = link_tag.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            text = link_tag.get_text(separator="|", strip=True)
            parts = [p for p in text.split("|") if p and p != "+ MORE"]
            title = parts[0] if parts else ""
            if any(kw.lower() in title.lower() for kw in skip_keywords):
                continue
            if not href.startswith("http"):
                href = base + href
            # 詳細ページから日付を取得してフィルタ
            dates = _fetch_moca_dates(href)
            if not _is_current_exhibition(dates, today):
                continue
            location = "MOCA Taipei"
            for p in parts[1:]:
                if "MoCA" in p or "MOCA" in p:
                    location = p
                    break
            if title:
                exhibitions.append({
                    "museum": "moca",
                    title_key: title,
                    "dates": dates,
                    "location": location,
                    "link": href,
                })
    except Exception as exc:
        logger.warning("MOCA %s scrape failed: %s", lang, exc)
    return exhibitions


def _fetch_moca_dates(detail_url):
    """MOCAの詳細ページから展示期間を取得する。"""
    try:
        soup = _fetch(detail_url)
        text = soup.get_text()
        dates = re.findall(r"(\d{4})\s*/\s*(\d{2})\s*/\s*(\d{2})", text)
        if len(dates) >= 2:
            s = f"{dates[-2][0]}/{dates[-2][1]}/{dates[-2][2]}"
            e = f"{dates[-1][0]}/{dates[-1][1]}/{dates[-1][2]}"
            return f"{s} - {e}"
    except Exception:
        pass
    return ""


def _scrape_tfam_api():
    """TFAM Ajax APIから展覧会情報を取得する。"""
    exhibitions = []
    base = MUSEUMS["tfam"]["url"]
    api_url = f"{base}/ashx/Exhibition.ashx"
    api_headers = {
        **HEADERS,
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{base}/Exhibition/Exhibition.aspx",
    }
    today = _now_tw()
    horizon = today + timedelta(days=90)
    try:
        # Type=3 で全件取得し、開催中・近日開始のみフィルタする
        payload = {"JJMethod": "GetEx", "Type": "3"}
        try:
            resp = requests.post(
                api_url, json=payload, headers=api_headers, timeout=15
            )
        except requests.exceptions.SSLError:
            resp = requests.post(
                api_url, json=payload, headers=api_headers,
                timeout=15, verify=False,
            )
        resp.raise_for_status()
        result = resp.json()
        items = result.get("Data", [])
        for item in items:
            name = (item.get("ExName") or "").strip()
            begin = item.get("BeginDate", "")
            end = item.get("EndDate", "")
            area = item.get("Area", "")
            ex_id = item.get("ExID", "")
            if not name:
                continue
            # 海外開催の展示を除外（ヴェネチア・ビエンナーレ等）
            if any(kw in name for kw in ("威尼斯", "Venice", "Biennale")):
                continue
            # 開催中 or 90日以内に開始するもののみ
            try:
                if end:
                    end_dt = datetime.strptime(end, "%Y/%m/%d")
                    if end_dt < today:
                        continue
                if begin:
                    begin_dt = datetime.strptime(begin, "%Y/%m/%d")
                    if begin_dt > horizon:
                        continue
            except ValueError:
                pass
            dates = f"{begin} - {end}" if begin and end else begin
            link = f"{base}/Exhibition/Exhibition_page.aspx?id={ex_id}"
            exhibitions.append({
                "museum": "tfam",
                "title_en": "",
                "title_ja": "",
                "title_zh": name,
                "dates": dates,
                "location": area or "TFAM",
                "link": link,
            })
    except Exception as exc:
        logger.warning("TFAM API scrape failed: %s", exc)
    return exhibitions


def _is_current_exhibition(dates_str, today=None):
    """日付文字列から展覧会が現在開催中かどうか判定する。"""
    if not dates_str:
        return True  # 日付なしは当期とみなす
    if today is None:
        from datetime import timezone, timedelta
        tw_tz = timezone(timedelta(hours=8))
        today = datetime.now(tw_tz).replace(tzinfo=None)
    # 全角スラッシュを半角に正規化
    s = dates_str.replace("／", "/")
    # 全日付を抽出（YYYY.MM.DD, YYYY/MM/DD, YYYY-MM-DD 対応）
    all_dates = re.findall(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", s)
    if len(all_dates) >= 2:
        # 2つ目が終了日
        y, m, d = int(all_dates[1][0]), int(all_dates[1][1]), int(all_dates[1][2])
        try:
            return datetime(y, m, d) >= today
        except ValueError:
            return True
    if len(all_dates) == 1:
        # 年なし短縮終了日を探す（例: 2026.3.21 – 5.17）
        short_end = re.search(r"[–—~\-]\s*(\d{1,2})[-./](\d{1,2})\s*$", s)
        if short_end:
            y = int(all_dates[0][0])
            m, d = int(short_end.group(1)), int(short_end.group(2))
            try:
                return datetime(y, m, d) >= today
            except ValueError:
                pass
        # 開始日のみ: 開始日から90日以内なら当期
        y, m, d = int(all_dates[0][0]), int(all_dates[0][1]), int(all_dates[0][2])
        try:
            return (today - datetime(y, m, d)).days <= 90
        except ValueError:
            pass
    return True


def _fetch_cffi(url):
    """curl_cffiでCloudflare保護サイトにアクセスする。"""
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, impersonate="chrome", timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except ImportError:
        logger.warning("curl_cffi not installed, falling back to requests")
        return _fetch(url)


def _scrape_honggah():
    """鳳甲美術館の公式サイトから展覧会情報を取得する。
    中文版ページを正として取得し、英語版で英語タイトルを補完。"""
    exhibitions = []
    today = _now_tw()
    horizon = today + timedelta(days=90)

    # 中文版ページから正式タイトルと日付を取得
    zh_data = []
    try:
        soup_zh = _fetch_cffi("https://hong-gah.org.tw/exhibitions-zh")
        text = soup_zh.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        date_re = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})$")
        for i, line in enumerate(lines):
            m = date_re.match(line)
            if m and i > 0:
                title_zh = lines[i - 1]
                y, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
                em, ed = int(m.group(4)), int(m.group(5))
                try:
                    end_dt = datetime(y, em, ed)
                    start_dt = datetime(y, sm, sd)
                    if end_dt < today:
                        continue
                    if start_dt > horizon:
                        continue
                except ValueError:
                    continue
                if title_zh and len(title_zh) > 2:
                    zh_data.append({
                        "title_zh": title_zh,
                        "dates": f"{y}.{sm:02d}.{sd:02d} – {y}.{em:02d}.{ed:02d}",
                    })
    except Exception as exc:
        logger.warning("Hong-Gah ZH scrape failed: %s", exc)

    # 英語版ページから英語タイトルを取得
    en_titles = []
    try:
        soup_en = _fetch_cffi("https://hong-gah.org.tw/en/exhibitions")
        text = soup_en.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        date_re = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})$")
        for i, line in enumerate(lines):
            m = date_re.match(line)
            if m and i > 0:
                en_titles.append(lines[i - 1])
    except Exception:
        pass

    # 統合: 中文を正とし、英語を日付マッチで補完
    for idx, zh_item in enumerate(zh_data):
        title_en = en_titles[idx] if idx < len(en_titles) else ""
        exhibitions.append({
            "museum": "honggah",
            "title_en": title_en,
            "title_ja": "",
            "title_zh": zh_item["title_zh"],
            "dates": zh_item["dates"],
            "location": "Hong-Gah Museum",
            "link": "https://hong-gah.org.tw/exhibitions-zh",
        })

    return exhibitions


def _scrape_ntcart():
    """新北市美術館の公式サイトから展覧会情報を取得する。"""
    exhibitions = []
    today = _now_tw()
    url = "https://ntcart.museum"
    try:
        soup = _fetch(url)
        for link in soup.find_all("a", href=re.compile(r"exhibition_content")):
            text = link.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if len(lines) < 2:
                continue
            title = lines[0]
            dm = re.search(r"(\d{4}-\d{2}-\d{2})\s*[—–]\s*(\d{4}-\d{2}-\d{2})", text)
            if not dm:
                continue
            dates = f"{dm.group(1)} - {dm.group(2)}"
            if not _is_current_exhibition(dates, today):
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://ntcart.museum/" + href
            exhibitions.append({
                "museum": "ntcart",
                "title_en": "", "title_ja": "", "title_zh": title,
                "dates": dates, "location": "新北市美術館",
                "link": href,
            })
    except Exception as exc:
        logger.warning("NTCArt scrape failed: %s", exc)
    if not exhibitions:
        manual_path = os.path.join(os.path.dirname(__file__), "ntcart_manual.json")
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                return [{"museum": "ntcart", **i} for i in json.load(f)]
        except Exception:
            pass
    return exhibitions


def _scrape_tcma():
    """臺中市立美術館の公式サイトから展覧会情報を取得する。"""
    exhibitions = []
    today = _now_tw()
    url = "https://www.tcam.museum/en/exhibition"
    try:
        soup = _fetch(url)
        for link in soup.find_all("a", href=re.compile(r"/exhibition/")):
            title = link.get_text(strip=True)
            if not title or len(title) < 3 or title.lower() in ("more", "exhibition"):
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://www.tcam.museum" + href
            # 詳細ページから日付を取得
            dates = _fetch_tcma_dates(href)
            if dates and not _is_current_exhibition(dates, today):
                continue
            has_cjk = bool(re.search(r"[一-鿿]", title))
            exhibitions.append({
                "museum": "tcma",
                "title_en": "" if has_cjk else title,
                "title_ja": "",
                "title_zh": title if has_cjk else "",
                "dates": dates, "location": "TCMA",
                "link": href,
            })
    except Exception as exc:
        logger.warning("TCMA scrape failed: %s", exc)
    if not exhibitions:
        manual_path = os.path.join(os.path.dirname(__file__), "tcma_manual.json")
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                return [{"museum": "tcma", **i} for i in json.load(f)]
        except Exception:
            pass
    return exhibitions


def _fetch_tcma_dates(detail_url):
    """臺中市立美術館の詳細ページから展示期間を取得する。"""
    try:
        soup = _fetch(detail_url)
        text = soup.get_text(separator="\n")
        match = re.search(
            r"(\d{4}/\d{2}/\d{2})\s*-\s*(\d{4}/\d{2}/\d{2})", text
        )
        if match:
            return f"{match.group(1)} - {match.group(2)}"
    except Exception:
        pass
    return ""


def _scrape_clab():
    """C-LAB（臺灣當代文化實驗場）から当期展覧会情報を取得する。
    中文版を正として取得し、英語版で英語タイトルを補完。"""
    exhibitions = []
    base = MUSEUMS["clab"]["url"]
    today = _now_tw()

    # 中文版と英語版の両方を取得
    zh_titles = []
    en_titles = []
    for lang_path, cat_keyword, title_list in [
        ("/events/", "展覽", zh_titles),
        ("/en/events/", "Exhibition", en_titles),
    ]:
        url = f"{base}{lang_path}"
        try:
            soup = _fetch(url)
            for card in soup.select("div.a-base-card.-event"):
                cat_el = card.select_one(".a-base-card__category-wrapper")
                cat = cat_el.get_text(strip=True) if cat_el else ""
                if cat != cat_keyword:
                    continue
                title_el = card.select_one("p.a-base-card__title, h2, h3, strong")
                title = title_el.get_text(strip=True) if title_el else ""
                time_el = card.select_one(".a-base-card__time")
                time_text = time_el.get_text(separator=" ", strip=True) if time_el else ""
                link_el = card.select_one("a[href]")
                href = link_el.get("href", "") if link_el else ""
                title_list.append({"title": title, "time_text": time_text, "href": href})
        except Exception:
            pass

    # 中文版を正として使い、英語版をマッチ
    for idx, zh_item in enumerate(zh_titles):
        title_zh = zh_item["title"]
        dates = _parse_clab_dates(zh_item["time_text"])
        href = zh_item["href"]
        if not href.startswith("http"):
            href = base + href
        title_en = en_titles[idx]["title"] if idx < len(en_titles) else ""

        # 日付フィルタ
        end_match = re.findall(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", dates)
        if len(end_match) >= 2:
            try:
                ey, em, ed = int(end_match[1][0]), int(end_match[1][1]), int(end_match[1][2])
                if datetime(ey, em, ed) < today:
                    continue
            except ValueError:
                pass

        if title_zh and len(title_zh) > 3:
            exhibitions.append({
                "museum": "clab",
                "title_en": title_en,
                "title_ja": "",
                "title_zh": title_zh,
                "dates": dates,
                "location": "C-LAB",
                "link": href,
            })

    return exhibitions


def _parse_clab_dates(time_text):
    """C-LABの日付形式 'MM.DD (DAY) YYYY . MM.DD (DAY) YYYY .' をYYYY/MM/DD形式に変換。"""
    matches = re.findall(r"(\d{2})\.(\d{2})\s*\(\w+\)\s*(\d{4})", time_text)
    if len(matches) >= 2:
        start = f"{matches[0][2]}/{int(matches[0][0]):02d}/{int(matches[0][1]):02d}"
        end = f"{matches[1][2]}/{int(matches[1][0]):02d}/{int(matches[1][1]):02d}"
        return f"{start} - {end}"
    if len(matches) == 1:
        return f"{matches[0][2]}/{int(matches[0][0]):02d}/{int(matches[0][1]):02d} –"
    return time_text


def _scrape_thecube():
    """TheCube Project Space から当期展覧会情報を取得する（詳細ページから日付取得）。"""
    exhibitions = []
    base = MUSEUMS["thecube"]["url"]
    url = f"{base}/en/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        html = resp.text
        # カルーセル部分の当期展覧会リンクを抽出
        pattern = re.compile(
            r'carousel-caption[^>]*>.*?'
            r'href=["\']([^"\']*?/project/[^"\']+)["\']>'
            r'([^<]+)<',
            re.DOTALL,
        )
        seen = set()
        for m in pattern.finditer(html):
            href = m.group(1).strip()
            title = m.group(2).strip()
            if not title or href in seen:
                continue
            seen.add(href)
            if not href.startswith("http"):
                href = base + href
            # 詳細ページから日付を取得
            dates = _fetch_thecube_dates(href)
            exhibitions.append({
                "museum": "thecube",
                "title_en": title,
                "title_ja": "",
                "title_zh": "",
                "dates": dates,
                "location": "TheCube Project Space",
                "link": href,
            })
    except Exception as exc:
        logger.warning("TheCube scrape failed: %s", exc)
    return exhibitions


def _fetch_thecube_dates(detail_url):
    """TheCubeの詳細ページから展示期間を取得する（Playwright使用）。"""
    soup = _fetch_rendered(detail_url)
    if not soup:
        return ""
    text = soup.get_text()
    match = re.search(
        r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*[–—\-]\s*(\d{1,2}[./]\d{1,2})",
        text,
    )
    if match:
        return f"{match.group(1)} – {match.group(2)}"
    return ""


def _scrape_chiayi():
    """嘉義市立美術館から展覧会情報を取得する。"""
    exhibitions = []
    base = MUSEUMS["chiayi"]["url"]
    url = f"{base}/ExhibitionsListC003100.aspx?appname=Exhibition3110"
    try:
        soup = _fetch(url)
        for link_tag in soup.select("a[href*='ExhibitionsDetail']"):
            text = link_tag.get_text(separator="|", strip=True)
            # 日付を抽出（全角スラッシュ対応）
            date_match = re.search(
                r"(\d{4}[／/]\d{2}[／/]\d{2})\s*\|?\s*[-–—]\s*\|?\s*(\d{4}[／/]\d{2}[／/]\d{2})",
                text,
            )
            dates = ""
            if date_match:
                dates = f"{date_match.group(1)} - {date_match.group(2)}"
            # タイトルは日付より前の部分
            title_text = text.split("|")[0].strip() if "|" in text else text
            title_match = re.split(r"\d{4}[／/]", title_text)
            title = title_match[0].strip() if title_match else title_text
            href = link_tag.get("href", "")
            if not href.startswith("http"):
                href = base + "/" + href
            if title and len(title) > 2:
                if not any(e["title_zh"] == title for e in exhibitions):
                    exhibitions.append({
                        "museum": "chiayi",
                        "title_en": "", "title_ja": "",
                        "title_zh": title,
                        "dates": dates,
                        "location": "嘉義市立美術館",
                        "link": href,
                    })
    except Exception as exc:
        logger.warning("Chiayi scrape failed: %s", exc)
    return exhibitions


def _scrape_kdmofa():
    """關渡美術館から当期展覧会情報を取得する。"""
    exhibitions = []
    base = MUSEUMS["kdmofa"]["url"]
    url = f"{base}/en/mod/exhibition/index.php"
    today = _now_tw()
    try:
        soup = _fetch(url)
        text = soup.get_text(separator="\n", strip=True)
        # パターン: タイトル\n日付\n場所
        date_pattern = re.compile(
            r"(\d{4}\.\d{2}\.\d{2})\s*[～~\-–]\s*(\d{4}\.\d{2}\.\d{2})"
        )
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            m = date_pattern.search(line)
            if m and i > 0:
                title = lines[i - 1]
                dates = f"{m.group(1)} – {m.group(2)}"
                if not _is_current_exhibition(dates, today):
                    continue
                if title and len(title) > 3:
                    has_cjk = bool(re.search(r"[一-鿿]", title))
                    exhibitions.append({
                        "museum": "kdmofa",
                        "title_en": "" if has_cjk else title,
                        "title_ja": "",
                        "title_zh": title if has_cjk else "",
                        "dates": dates,
                        "location": "KdMoFA",
                        "link": url,
                    })
    except Exception as exc:
        logger.warning("KdMoFA scrape failed: %s", exc)
        # フォールバック: JSONファイル
        manual_path = os.path.join(os.path.dirname(__file__), "kdmofa_manual.json")
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                items = json.load(f)
            return [{"museum": "kdmofa", **item} for item in items]
        except Exception:
            pass
    return exhibitions


def _scrape_artlogic_gallery(museum_id, exhibition_url, location_filter=None):
    """Artlogic CMS（Tina Keng, Asia Art Center 等）から展覧会情報を取得する。
    日付パターン (例: '23 May - 11 Jul 2026') を持つ行を中心に、
    その前にあるタイトル + 後にある場所を抽出する。"""
    exhibitions = []
    today = _now_tw()
    horizon = today + timedelta(days=90)
    date_re = re.compile(
        r"^(\d{1,2})\s+(\w{3,9})\s*[–-]\s*(\d{1,2})\s+(\w{3,9})\s+(\d{4})$"
    )
    try:
        soup = _fetch(exhibition_url)
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # 「Past」セクションの開始位置を検出
        past_start = len(lines)
        for idx, l in enumerate(lines):
            if l in ("Past", "Archive", "Past Exhibition", "Past Exhibitions"):
                # ヘッダーがコンテンツの前後どちらにあるか判定
                # コンテンツ前: 後にもう一度「Current」が出る
                later = lines[idx + 1: idx + 30]
                if any(x in ("Current", "Current Exhibition") for x in later):
                    continue  # ナビゲーション、無視
                past_start = idx
                break

        i = 0
        while i < min(past_start, len(lines)):
            line = lines[i]
            # 日付行を見つける
            m = date_re.match(line)
            if m and i > 0:
                pass  # 後段で処理
            else:
                i += 1
                continue
            i += 1  # 日付行を進める前に
            i -= 1  # 元に戻す（下のロジックで処理）
            break
        # 日付行を全部探す
        for idx in range(past_start):
            line = lines[idx]
            m = date_re.match(line)
            if not m:
                continue
            # 前の行: タイトル（または subtitle、その前が title）
            prev1 = lines[idx - 1] if idx >= 1 else ""
            prev2 = lines[idx - 2] if idx >= 2 else ""
            # タイトル候補: prev2が短く意味あり且つprev1がサブタイトル
            if prev2 and 3 < len(prev2) < 100 and not date_re.match(prev2) and prev2 not in (
                "Current", "Past", "Forthcoming", "Current Exhibition", "Past Exhibition"
            ):
                title = prev2
                subtitle = prev1
            else:
                title = prev1
                subtitle = ""
            # 後の行: location
            loc_line = lines[idx + 1] if idx + 1 < past_start else ""
            # 日付パース
            months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                      "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
            try:
                sd = int(m.group(1))
                sm = months.get(m.group(2)[:3].title(), 0)
                ed = int(m.group(3))
                em = months.get(m.group(4)[:3].title(), 0)
                ey = int(m.group(5))
                sy = ey if (sm, sd) <= (em, ed) else ey - 1
                if not sm or not em:
                    continue
                start_dt = datetime(sy, sm, sd)
                end_dt = datetime(ey, em, ed)
                if end_dt < today or start_dt > horizon:
                    continue
                if location_filter and location_filter.lower() not in loc_line.lower():
                    continue
                if not title or len(title) < 3:
                    continue
                dates = f"{sy}/{sm:02d}/{sd:02d} - {ey}/{em:02d}/{ed:02d}"
                full_title = f"{title} — {subtitle}" if subtitle and subtitle != title else title
                exhibitions.append({
                    "museum": museum_id,
                    "title_en": full_title,
                    "title_ja": "", "title_zh": "",
                    "dates": dates,
                    "location": loc_line,
                    "link": exhibition_url,
                })
            except (ValueError, KeyError):
                continue
    except Exception as exc:
        logger.warning("Artlogic scrape failed for %s: %s", museum_id, exc)
    return exhibitions


def _scrape_fubon():
    """富邦美術館 (Fubon Art Museum) から展覧会情報を取得する。
    構造: 中文タイトル / 英文タイトル / YYYY.MM.DD - YYYY.MM.DD / 会場
    の4行ブロックが繰り返し現れる。"""
    exhibitions = []
    today = _now_tw()
    horizon = today + timedelta(days=90)
    url = "https://www.fubonartmuseum.org/"
    date_re = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})\s*-\s*(\d{4})\.(\d{1,2})\.(\d{1,2})$")
    try:
        soup = _fetch(url)
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        i = 0
        while i < len(lines) - 3:
            m = date_re.match(lines[i + 2]) if i + 2 < len(lines) else None
            if m:
                title_zh = lines[i]
                title_en = lines[i + 1]
                venue = lines[i + 3] if i + 3 < len(lines) else ""
                # 「美術館」が会場文字列に含まれているもののみ展覧会と判定
                if "美術館" not in venue and "Museum" not in venue:
                    i += 1
                    continue
                try:
                    sy, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    ey, em, ed = int(m.group(4)), int(m.group(5)), int(m.group(6))
                    start_dt = datetime(sy, sm, sd)
                    end_dt = datetime(ey, em, ed)
                    if end_dt < today or start_dt > horizon:
                        i += 4
                        continue
                except ValueError:
                    i += 1
                    continue
                if title_zh and 3 < len(title_zh) < 200:
                    dates = f"{sy}/{sm:02d}/{sd:02d} - {ey}/{em:02d}/{ed:02d}"
                    exhibitions.append({
                        "museum": "fubon",
                        "title_en": title_en or title_zh,
                        "title_ja": "", "title_zh": title_zh,
                        "dates": dates,
                        "location": venue,
                        "link": url,
                    })
                    i += 4
                    continue
            i += 1
    except Exception as exc:
        logger.warning("Fubon scrape failed: %s", exc)
    return exhibitions


def _scrape_jut():
    """JUT Art Museum (忠泰美術館) から展覧会情報を取得する。"""
    exhibitions = []
    today = _now_tw()
    horizon = today + timedelta(days=90)
    base = "https://jam.jutfoundation.org.tw"
    try:
        for path in ["/en/online-exhibition", "/en/coming-exhibition"]:
            url = base + path
            try:
                soup = _fetch(url)
            except Exception:
                continue
            text = soup.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            section_keywords = ("Current", "Forthcoming", "Upcoming", "Coming")
            i = 0
            while i < len(lines) - 4:
                if lines[i] in section_keywords:
                    title = lines[i + 1]
                    start_str = lines[i + 2]
                    sep = lines[i + 3]
                    end_str = lines[i + 4]
                    if (re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", start_str) and
                        sep in ("-", "–", "—") and
                        re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", end_str)):
                        try:
                            sy, sm, sd = [int(x) for x in start_str.split("/")]
                            ey, em, ed = [int(x) for x in end_str.split("/")]
                            start_dt = datetime(sy, sm, sd)
                            end_dt = datetime(ey, em, ed)
                            if end_dt < today or start_dt > horizon:
                                i += 5
                                continue
                            if title and 3 < len(title) < 200:
                                exhibitions.append({
                                    "museum": "jut",
                                    "title_en": title,
                                    "title_ja": "", "title_zh": "",
                                    "dates": f"{start_str} - {end_str}",
                                    "location": "JUT Art Museum",
                                    "link": url,
                                })
                                i += 5
                                continue
                        except ValueError:
                            pass
                i += 1
    except Exception as exc:
        logger.warning("JUT scrape failed: %s", exc)
    return exhibitions


def _scrape_soka():
    """索卡藝術 (Soka Art) 台北・台南支店の展覧会情報を取得する。
    詳細ページから location を確認して Taipei/Tainan のみ抽出。"""
    exhibitions = []
    today = _now_tw()
    horizon = today + timedelta(days=90)
    base = "https://www.soka-art.com"
    list_url = f"{base}/en/exhibition"
    months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
              "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    date_re = re.compile(
        r"(\w{3,9})\s+(\d{1,2})\s*[-–]\s*(\w{3,9})?\s*(\d{1,2}),?\s+(\d{4})"
    )
    try:
        soup = _fetch(list_url)
        items = soup.select(".exhibition-list-wrapper .item")
        seen_links = set()
        for item in items:
            a = item.find("a", href=True)
            if not a:
                continue
            href = a.get("href", "")
            if not href.startswith("http"):
                href = base + href
            if href in seen_links:
                continue
            seen_links.add(href)
            text = item.get_text(separator=" | ", strip=True)
            # タイトル: h3 か itemの最初のテキスト断片
            h3 = item.find("h3")
            title = h3.get_text(strip=True) if h3 else ""
            # 日付パターン
            m = date_re.search(text)
            if not m:
                continue
            try:
                sm_str = m.group(1)[:3].title()
                sm = months.get(sm_str, 0)
                sd = int(m.group(2))
                em_str = (m.group(3) or sm_str)[:3].title()
                em = months.get(em_str, 0)
                ed = int(m.group(4))
                ey = int(m.group(5))
                if not sm or not em:
                    continue
                sy = ey if (sm, sd) <= (em, ed) else ey - 1
                start_dt = datetime(sy, sm, sd)
                end_dt = datetime(ey, em, ed)
                if end_dt < today or start_dt > horizon:
                    continue
            except (ValueError, KeyError):
                continue
            # location を確認するために詳細ページを取得
            try:
                detail = _fetch(href, timeout=8)
                detail_text = detail.get_text(separator="\n", strip=True)
                # 'Taipei' or 'Tainan' のロケーションを含むか
                if not any(loc in detail_text for loc in ["Taipei", "Tainan"]):
                    continue
                location = "Soka Art Taipei" if "Taipei" in detail_text else "Soka Art Tainan"
            except Exception:
                location = "Soka Art"
            if not title:
                # itemから title らしきものを抽出
                for line in text.split(" | "):
                    line = line.strip()
                    if line and len(line) > 5 and not date_re.search(line) and "View" not in line:
                        title = line
                        break
            if title and len(title) > 3:
                dates = f"{sy}/{sm:02d}/{sd:02d} - {ey}/{em:02d}/{ed:02d}"
                exhibitions.append({
                    "museum": "soka",
                    "title_en": title,
                    "title_ja": "", "title_zh": "",
                    "dates": dates,
                    "location": location,
                    "link": href,
                })
    except Exception as exc:
        logger.warning("Soka scrape failed: %s", exc)
    return exhibitions


def _scrape_tnam():
    """臺南市美術館（TNAM）から展覧会情報を取得する。
    構造: 開始日/開始時刻/終了日/終了時刻/タイトル/場所 の6行ブロック。"""
    exhibitions = []
    today = _now_tw()
    horizon = today + timedelta(days=90)
    base = "https://www.tnam.museum"
    try:
        for page_url in [f"{base}/exhibition/current", f"{base}/exhibition/upcoming"]:
            try:
                soup = _fetch(page_url)
            except Exception:
                continue
            text = soup.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            date_re = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")
            i = 0
            while i < len(lines) - 5:
                # パターン: YYYY/MM/DD / HH:MM / YYYY/MM/DD / HH:MM / Title / Venue
                if (date_re.match(lines[i]) and
                    re.match(r"^\d{1,2}:\d{2}$", lines[i + 1]) and
                    date_re.match(lines[i + 2]) and
                    re.match(r"^\d{1,2}:\d{2}$", lines[i + 3])):
                    start = lines[i]
                    end = lines[i + 2]
                    title = lines[i + 4]
                    venue = lines[i + 5] if i + 5 < len(lines) else ""
                    try:
                        sy, sm, sd = [int(x) for x in start.split("/")]
                        ey, em, ed = [int(x) for x in end.split("/")]
                        start_dt = datetime(sy, sm, sd)
                        end_dt = datetime(ey, em, ed)
                        if end_dt < today or start_dt > horizon:
                            i += 1
                            continue
                    except ValueError:
                        i += 1
                        continue
                    if title and 3 < len(title) < 200:
                        dates = f"{start} - {end}"
                        exhibitions.append({
                            "museum": "tnam",
                            "title_en": title,
                            "title_ja": "", "title_zh": title,
                            "dates": dates,
                            "location": venue,
                            "link": page_url,
                        })
                        i += 6
                        continue
                i += 1
    except Exception as exc:
        logger.warning("TNAM scrape failed: %s", exc)
    return exhibitions


def _scrape_pingtung():
    """屏東縣立美術館から展覧会情報を取得する。"""
    exhibitions = []
    today = _now_tw()
    horizon = today + timedelta(days=90)
    url = "https://www.cultural.pthg.gov.tw/pt1936/Default.aspx"
    try:
        soup = _fetch(url)
        text = soup.get_text(separator="\n", strip=True)
        # パターン: タイトル(YYYY.MM.DD-YYYY.MM.DD)
        matches = re.findall(
            r"([^\n\(\)]{3,100}?)\s*\((\d{4}\.\d{1,2}\.\d{1,2})-(\d{4}\.\d{1,2}\.\d{1,2})\)",
            text,
        )
        seen = set()
        for title, start, end in matches:
            title = title.strip()
            key = (title, start, end)
            if key in seen:
                continue
            seen.add(key)
            try:
                start_parts = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", start)
                end_parts = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", end)
                if not start_parts or not end_parts:
                    continue
                start_dt = datetime(*[int(g) for g in start_parts.groups()])
                end_dt = datetime(*[int(g) for g in end_parts.groups()])
                if end_dt < today:
                    continue
                if start_dt > horizon:
                    continue
            except (ValueError, AttributeError):
                continue
            dates = f"{start} – {end}"
            exhibitions.append({
                "museum": "pingtung",
                "title_en": title,
                "title_ja": "", "title_zh": title,
                "dates": dates,
                "location": "Pingtung Art Museum",
                "link": url,
            })
    except Exception as exc:
        logger.warning("Pingtung scrape failed: %s", exc)
    return exhibitions


def _scrape_montue():
    """北師美術館（MoNTUE）から展覧会情報を取得する。
    一覧ページから個別展覧会のリンクを取得し、各ページのh2/og:titleから情報抽出。"""
    exhibitions = []
    base = "https://montue.ntue.edu.tw"
    today = _now_tw()
    horizon = today + timedelta(days=90)
    try:
        # 展覧会一覧ページから個別リンクを抽出
        for page_url in [f"{base}/exhibitions/", f"{base}/exhibitions-upcoming/"]:
            try:
                soup = _fetch(page_url)
            except Exception:
                continue
            # スキップすべきナビゲーションスラッグ
            skip_slugs = {
                "exhibitions", "exhibitions-upcoming", "exhibitions-past",
                "dreamin-montue", "learning", "opm", "news", "about-montue",
                "home", "visit", "site-map", "cookies", "cookies-policy",
                "archive", "archive-gallery", "wp-content", "wp-admin",
            }
            seen_slugs = set()
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if not href.startswith(base):
                    continue
                # /スラッグ/ 形式の個別ページのみ
                path = href.replace(base, "").strip("/")
                if "/" in path:
                    continue
                if not path or path in skip_slugs:
                    continue
                if path in seen_slugs:
                    continue
                seen_slugs.add(path)
                # 詳細ページから情報取得
                try:
                    detail = _fetch(f"{base}/{path}/")
                except Exception:
                    continue
                # h2 から「日付 タイトル」抽出
                h2 = detail.find("h2")
                title = ""
                dates = ""
                if h2:
                    h2_text = h2.get_text(strip=True)
                    m = re.search(r"(\d{4}\.\d{1,2}\.\d{1,2})\s*[\-~–]\s*(\d{4}\.\d{1,2}\.\d{1,2})\s*(.+)", h2_text)
                    if m:
                        dates = f"{m.group(1)} – {m.group(2)}"
                        title = m.group(3).strip()
                # og:title からタイトルを補完
                if not title:
                    og = detail.find("meta", property="og:title")
                    if og:
                        title = og.get("content", "").strip()
                if not title or not dates:
                    continue
                # 90日horizonチェック
                end_match = re.search(r"\d{4}\.\d{1,2}\.\d{1,2}", dates.split("–")[-1])
                if end_match:
                    try:
                        end_dt = datetime.strptime(end_match.group(0), "%Y.%m.%d")
                        if end_dt < today:
                            continue
                    except ValueError:
                        pass
                start_match = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", dates)
                if start_match:
                    try:
                        start_dt = datetime(
                            int(start_match.group(1)),
                            int(start_match.group(2)),
                            int(start_match.group(3)),
                        )
                        if start_dt > horizon:
                            continue
                    except ValueError:
                        pass
                exhibitions.append({
                    "museum": "montue",
                    "title_en": title,
                    "title_ja": "", "title_zh": title,
                    "dates": dates,
                    "location": "MoNTUE",
                    "link": f"{base}/{path}/",
                })
    except Exception as exc:
        logger.warning("MoNTUE scrape failed: %s", exc)
    return exhibitions


def _scrape_goodug():
    """好地下藝術空間（Good Underground）のweeblyサイトから展覧会情報を取得する。"""
    exhibitions = []
    today = _now_tw()
    year = today.year
    # 当年と前年のページを確認
    for y in [year, year - 1]:
        url = f"https://goodunderground.weebly.com/{y}.html"
        try:
            soup = _fetch(url)
            text = soup.get_text(separator="\n", strip=True)
            # パターン: YYYY.MM.DD - YYYY.MM.DD タイトル
            for m in re.finditer(
                r"(\d{4}\.\d{1,2}\.\d{1,2})\s*-\s*(\d{4}\.\d{1,2}\.\d{1,2})"
                r"\s*(.+?)(?=\d{4}\.\d{1,2}\.\d{1,2}|\Z)",
                text, re.DOTALL,
            ):
                dates = f"{m.group(1)} - {m.group(2)}"
                if not _is_current_exhibition(dates, today):
                    continue
                title = m.group(3).strip().split("\n")[0].strip()
                if title and len(title) > 2:
                    exhibitions.append({
                        "museum": "goodug",
                        "title_en": title,
                        "title_zh": title,
                        "title_ja": "",
                        "dates": dates,
                        "location": "好地下藝術空間",
                        "link": url,
                    })
        except Exception as exc:
            logger.warning("Good Underground scrape failed for %d: %s", y, exc)
    if not exhibitions:
        # フォールバック: JSONファイル
        manual_path = os.path.join(os.path.dirname(__file__), "goodug_manual.json")
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                items = json.load(f)
            return [{"museum": "goodug", **item} for item in items]
        except Exception:
            pass
    return exhibitions


def _scrape_tav():
    """台北國際藝術村（寶藏巖）の公式サイトから展覧会情報を取得する。"""
    exhibitions = []
    today = _now_tw()
    url = "https://www.artistvillage.org/event.php"
    try:
        soup = _fetch(url)
        # 各イベントリンクから日付とタイトルを抽出
        for link in soup.find_all("a", href=re.compile(r"event-detail")):
            text = link.get_text(separator="\n", strip=True)
            # 日付パターン: YYYY-MM-DD ~ YYYY-MM-DD
            dm = re.search(
                r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", text
            )
            if not dm:
                continue
            dates = f"{dm.group(1)} - {dm.group(2)}"
            if not _is_current_exhibition(dates, today):
                continue
            # タイトルは日付より前の行
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = ""
            for line in lines:
                if re.search(r"\d{4}-\d{2}-\d{2}", line):
                    break
                if len(line) > 3:
                    title = line
                    break
            if not title:
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://www.artistvillage.org/" + href
            exhibitions.append({
                "museum": "tav",
                "title_en": title,
                "title_zh": title,
                "title_ja": "",
                "dates": dates,
                "location": "寶藏巖國際藝術村",
                "link": href,
            })
    except Exception as exc:
        logger.warning("TAV scrape failed: %s", exc)
    if not exhibitions:
        manual_path = os.path.join(os.path.dirname(__file__), "tav_manual.json")
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                items = json.load(f)
            return [{"museum": "tav", **item} for item in items]
        except Exception:
            pass
    return exhibitions


def _merge_exhibitions(list_a, list_b):
    """2つの展覧会リストをマージする（同一美術館の同一順序で結合）。"""
    merged = []
    for item in list_a:
        entry = {
            "museum": item.get("museum", ""),
            "title_en": item.get("title_en", ""),
            "title_ja": item.get("title_ja", ""),
            "title_zh": item.get("title_zh", ""),
            "dates": item.get("dates", ""),
            "location": item.get("location", ""),
            "link": item.get("link", ""),
        }
        merged.append(entry)
    # list_bの情報で空フィールドを補完する
    for i, item_b in enumerate(list_b):
        if i < len(merged) and merged[i]["museum"] == item_b.get("museum"):
            for key in ["title_en", "title_ja", "title_zh", "dates"]:
                if not merged[i].get(key) and item_b.get(key):
                    merged[i][key] = item_b[key]
        else:
            merged.append({
                "museum": item_b.get("museum", ""),
                "title_en": item_b.get("title_en", ""),
                "title_ja": item_b.get("title_ja", ""),
                "title_zh": item_b.get("title_zh", ""),
                "dates": item_b.get("dates", ""),
                "location": item_b.get("location", ""),
                "link": item_b.get("link", ""),
            })
    return merged


# --- artemperor.tw アグリゲーター名 → museum ID マッピング ---
# マスターデータの中国語名やartemperor上の表記ゆれに対応
ARTEMPEROR_NAME_MAP = {
    "台北當代藝術館": "moca",
    "臺北市立美術館": "tfam",
    "洪建全基金會": "honggah",  # Hong-Gah
    "新北市美術館": "ntcart",
    "臺中市立美術館": "tcma",
    "空總臺灣當代文化實驗場": "clab",
    "C-LAB": "clab",
    "立方計劃空間": "thecube",
    "TheCube": "thecube",
    "嘉義市立美術館": "chiayi",
    "關渡美術館": "kdmofa",
    "國家攝影文化中心": "ncpi",
    "國立臺灣美術館": "ntmofa",
    "臺南市美術館": "tnam",
    "高雄市立美術館": "kmfa",
    "桃園市立美術館": "tmofa",
    "蘭陽博物館": "lym",
    "伊通公園": "itpark",
    "IT Park": "itpark",
    "非常廟": "vt",
    "VT Artsalon": "vt",
    "絕對空間": "absolute",
    "Lightbox": "lightbox",
    "朋丁": "ponding",
    "Pon Ding": "ponding",
    "耿畫廊": "tinakeng",
    "Tina Keng Gallery": "tinakeng",
    "TKG+": "tkgplus",
    "大未來林舍畫廊": "linlin",
    "Lin & Lin Gallery": "linlin",
    "亞洲藝術中心": "asiaart",
    "Asia Art Center": "asiaart",
    "尊彩藝術中心": "liang",
    "Liang Gallery": "liang",
    "誠品畫廊": "eslite",
    "Eslite Gallery": "eslite",
    "亞紀畫廊": "eachmodern",
    "Each Modern": "eachmodern",
    "TAO ART": "taoart",
    "谷公館": "michaelku",
    "Michael Ku Gallery": "michaelku",
    "也趣畫廊": "aki",
    "AKI Gallery": "aki",
    "双方藝廊": "doublesq",
    "Double Square Gallery": "doublesq",
    "索卡藝術": "soka",
    "Soka Art": "soka",
    "白石畫廊": "whitestone",
    "Whitestone Gallery": "whitestone",
    "333 Gallery": "g333",
    "Bluerider ART": "bluerider",
    "忠泰美術館": "jut",
    "Jut Art Museum": "jut",
    "富邦美術館": "fubon",
    "朱銘美術館": "juming",
    "毓繡美術館": "yuhsiu",
    "永添藝術": "alien",
    "ALIEN Art Centre": "alien",
    "華山1914": "huashan",
    "華山1914文化創意產業園區": "huashan",
    "松山文創園區": "songshan",
    "駁二藝術特區": "pier2",
    "The Pier-2 Art Center": "pier2",
    "福利社": "frees",
    "FreeS Art Space": "frees",
    "台北國際藝術村": "tav",
    "新浜碼頭藝術空間": "sinpin",
    "其玟畫廊": "chiwen",
    "Chi-Wen Gallery": "chiwen",
    "紅野畫廊": "powen",
    "亦安畫廊": "yiyun",
    "大得畫廊": "date",
    "月臨畫廊": "moon",
    "加力畫廊": "inart",
    "花蓮文化創意產業園區": "hualiencp",
    "府中15": "fuzhong15",
    "多納藝術": "donnaart",
    "Donna Art": "donnaart",
    "大象藝術空間館": "daxiangart",
    "Da Xiang Art Space": "daxiangart",
    "1839當代藝廊": "1839cg",
    "1839 Contemporary Gallery": "1839cg",
    "采泥藝術": "chinigallery",
    "Chini Gallery": "chinigallery",
    "MAISON ACME": "maisonacme",
    "圓山別邸": "maisonacme",
    "蕭壠文化園區": "soulangh",
    "Soulangh": "soulangh",
    "師大美術館": "ntnuart",
    "MoNTUE": "montue",
    "北師美術館": "montue",
    "宛儒畫廊": "yuanru",
    "Yuan Ru Gallery": "yuanru",
    "異雲書屋": "yiyun",
    "就在藝術空間": "projectfulfill",
    "Project Fulfill": "projectfulfill",
    "德鴻畫廊": "derhorng",
    "Der-Horng": "derhorng",
    "屏東縣立美術館": "pingtung",
    "臺東美術館": "ttam",
    "新竹市美術館": "hcfam",
    "鳳甲美術館": "honggah",
    "ss space space": "sssart",
    "國立臺灣文學館": "nmtl",
    "國立臺灣歷史博物館": "nmth",
    "伊日藝術計劃": "yiriarts",
    "YIRI ARTS": "yiriarts",
    "赤粒藝術": "redgold",
    "Red Gold Fine Art": "redgold",
    "安卓藝術": "mindset",
    "Mind Set Art Center": "mindset",
    "朝代畫廊": "dynasty",
    "Dynasty Gallery": "dynasty",
    "純Object": "simpleobject",
    "Simple Object": "simpleobject",
    "Neverland Gallery": "neverland",
}


def _match_artemperor_name(gallery_name):
    """artemperor.twのギャラリー名からmuseum IDを返す。"""
    # 完全一致
    if gallery_name in ARTEMPEROR_NAME_MAP:
        return ARTEMPEROR_NAME_MAP[gallery_name]
    # 部分一致（マップのキーがギャラリー名に含まれるか）
    for key, mid in ARTEMPEROR_NAME_MAP.items():
        if key in gallery_name or gallery_name in key:
            return mid
    return None


def _scrape_artemperor(pages=3):
    """artemperor.tw（非池中藝術網）から展覧会情報を取得する。

    Args:
        pages: 取得するページ数（1ページ約30件）
    Returns:
        list: 展覧会情報のリスト
    """
    exhibitions = []
    today = _now_tw()
    seen = set()

    for page in range(1, pages + 1):
        url = f"https://artemperor.tw/tidbits?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8, verify=False)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # div.list_text が各展覧会カード
            for card in soup.find_all("div", class_="list_text"):
                # ギャラリー名: <figure class="tag">
                fig = card.find("figure", class_="tag")
                gallery_name = fig.get_text(strip=True) if fig else ""

                # 展覧会タイトル: <h2>
                h2 = card.find("h2")
                title = h2.get_text(strip=True) if h2 else ""
                # 【】括弧を除去
                if title.startswith("【") and "】" in title:
                    title = title[1:].replace("】", " ", 1).strip()

                # 日付: <p> に「日期：YYYY-MM-DD ~ YYYY-MM-DD」
                p_tag = card.find("p")
                dates_str = ""
                if p_tag:
                    dm = re.search(
                        r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})",
                        p_tag.get_text(),
                    )
                    if dm:
                        dates_str = f"{dm.group(1)} - {dm.group(2)}"

                # リンク: <a> の href
                link_tag = card.find("a", href=re.compile(r"/tidbits/\d+"))
                detail_url = ""
                if link_tag:
                    href = link_tag.get("href", "")
                    if href.startswith("//"):
                        href = "https:" + href
                    elif not href.startswith("http"):
                        href = "https://artemperor.tw" + href
                    detail_url = href

                if not gallery_name or not title or not dates_str:
                    continue
                if not _is_current_exhibition(dates_str, today):
                    continue

                museum_id = _match_artemperor_name(gallery_name)
                if not museum_id:
                    continue

                key = (museum_id, title)
                if key in seen:
                    continue
                seen.add(key)

                exhibitions.append({
                    "museum": museum_id,
                    "title_en": title,
                    "title_zh": title,
                    "title_ja": "",
                    "dates": dates_str,
                    "location": "",
                    "link": detail_url,
                })
        except Exception as exc:
            logger.warning("Artemperor page %d failed: %s", page, exc)

    logger.info("Artemperor: %d exhibitions from %d pages", len(exhibitions), pages)
    return exhibitions


def _extract_generic_dates(line):
    """様々な形式の日付ペアを抽出して統一形式で返す。"""
    # パターン1: YYYY/MM/DD - YYYY/MM/DD 等
    m = re.search(
        r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})"
        r".*?[–—~\-]\s*"
        r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})",
        line,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)} - {m.group(4)}/{m.group(5)}/{m.group(6)}"
    # パターン2: 2026年5月21日 - 7月4日（中国語）
    m = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*[–—~\-]\s*(\d{1,2})月(\d{1,2})日",
        line,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)} - {m.group(1)}/{m.group(4)}/{m.group(5)}"
    # パターン3: 2026年5月21日 - 2026年7月4日
    m = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*[–—~\-]\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
        line,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)} - {m.group(4)}/{m.group(5)}/{m.group(6)}"
    return ""


def _scrape_generic(museum_id, exhibition_url):
    """汎用スクレイパー: 展覧会ページからタイトルと日付を自動抽出する。"""
    exhibitions = []
    today = _now_tw()
    try:
        soup = _fetch(exhibition_url)
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # 日付パターンを含む行とその前の行をペアで抽出
        for i, line in enumerate(lines):
            dates = _extract_generic_dates(line)
            if not dates:
                continue
            if not _is_current_exhibition(dates, today):
                continue
            title = lines[i - 1] if i > 0 else line
            if len(title) < 3 or re.match(r"^\d{4}", title):
                title = line.split(dates)[0].strip() if dates in line else line
            # タイトル内に日付パターンが含まれる場合は除去
            title = re.sub(
                r"\s*\d{4}[./\-]\d{1,2}[./\-]\d{1,2}\s*[–—~\-]\s*\d{4}[./\-]\d{1,2}[./\-]\d{1,2}\s*$",
                "", title,
            ).strip()
            title = re.sub(
                r"\s*\d{4}[./\-]\d{1,2}[./\-]\d{1,2}\s*$", "", title,
            ).strip()
            # タイトルは100文字以内、長すぎる場合は最初の文だけ取る
            if len(title) > 100:
                first_segment = re.split(r"[。、，,\.!?！？]", title)[0]
                if 5 < len(first_segment) <= 100:
                    title = first_segment
                else:
                    continue
            # 「Solo Exhibition」「Group Exhibition」のような汎用タイトルは前行を見る
            if title.lower().strip() in ("solo exhibition", "group exhibition", "exhibition", "duo exhibition") and i >= 2:
                better = lines[i - 2]
                if 3 < len(better) < 80 and not re.match(r"^\d", better):
                    title = better + " — " + title
            if title and len(title) > 2:
                # CJK文字が含まれていればtitle_zh、なければtitle_en
                has_cjk = bool(re.search(r"[一-鿿]", title))
                exhibitions.append({
                    "museum": museum_id,
                    "title_en": "" if has_cjk else title,
                    "title_ja": "",
                    "title_zh": title if has_cjk else "",
                    "dates": dates,
                    "location": "",
                    "link": exhibition_url,
                })
    except Exception as exc:
        logger.warning("Generic scrape failed for %s: %s", museum_id, exc)
    return exhibitions


DETAILS_FILE = os.path.join(os.path.dirname(__file__), "exhibition_details.json")
DETAILS_TTL_DAYS = 14


def _load_details_cache():
    """既存の詳細キャッシュを読み込む。"""
    if not os.path.exists(DETAILS_FILE):
        return {}
    try:
        with open(DETAILS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_details_cache(details):
    """詳細キャッシュを保存する。"""
    text = json.dumps(details, ensure_ascii=False, indent=2)
    text = re.sub(r"[\ud800-\udfff]", "", text)
    with open(DETAILS_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def _extract_exhibition_details(url):
    """展覧会詳細ページからアーティスト・キュレーター・概要を抽出する。"""
    try:
        soup = _fetch(url, timeout=12)
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        artists = []
        curator = ""
        artist_keywords = ("Artists", "Artist", "藝術家", "參展藝術家", "アーティスト")
        curator_keywords = ("Curator", "策展人", "キュレーター")
        stop_keywords = (
            "Supervisor", "Curator", "Organizer", "Sponsor", "Director",
            "Producer", "Venue", "Address", "Schedule", "Hours", "Date",
            "策展人", "主辦", "指導", "協辦", "贊助", "場地", "地點", "時間",
        )

        i = 0
        while i < len(lines):
            line = lines[i]
            if line in artist_keywords:
                j = i + 1
                while j < len(lines) and j - i < 30:
                    next_line = lines[j]
                    if next_line in stop_keywords:
                        break
                    if len(next_line) < 60 and not next_line.startswith("http") and "•" not in next_line:
                        if _is_valid_artist_name(next_line):
                            artists.append(next_line)
                    else:
                        break
                    j += 1
                i = j
                continue
            if line in curator_keywords:
                if i + 1 < len(lines) and len(lines[i + 1]) < 60:
                    curator = lines[i + 1]
            i += 1

        ps = soup.find_all("p")
        long_ps = [p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 80]
        description = long_ps[0][:800] if long_ps else ""

        if artists and len(artists) > 2:
            unique_chars = set("".join(artists))
            if len(unique_chars) < 10:
                artists = []

        return {
            "artists": artists[:15],
            "curator": curator,
            "description": description,
            "fetched_at": _now_tw().isoformat(),
        }
    except Exception as exc:
        logger.warning("Detail extraction failed for %s: %s", url, exc)
        return None


def _run_validation(exhibitions):
    """エンリッチ後のデータ品質チェック。問題検出時にログ出力。"""
    from collections import Counter, defaultdict

    issues = []

    # Check 1: 同一美術館で複数展示が完全に同じアーティストセットを持つ
    by_museum = defaultdict(list)
    for ex in exhibitions:
        artists = ex.get('artists', [])
        if artists and len(artists) > 2:
            by_museum[ex.get('museum', '')].append({
                'title': ex.get('title_zh', '') or ex.get('title_en', ''),
                'artists': tuple(sorted(artists)),
            })
    for mid, exs in by_museum.items():
        if len(exs) < 2:
            continue
        for i in range(len(exs)):
            for j in range(i + 1, len(exs)):
                if exs[i]['artists'] == exs[j]['artists']:
                    issues.append(
                        f"[DUPLICATE ARTISTS] {mid}: '{exs[i]['title'][:30]}' and "
                        f"'{exs[j]['title'][:30]}' share identical {len(exs[i]['artists'])} artists"
                    )

    # Check 2: UI/ナビゲーション文字列がアーティスト名に混入
    junk_indicators = ['線上藝廊', '登入', '購物', '服務條款', '展覽回顧', '當期展覽',
                       '購物須知', '展覽資訊', '參觀資訊']
    for ex in exhibitions:
        for artist in ex.get('artists', []):
            if any(junk in artist for junk in junk_indicators):
                issues.append(
                    f"[JUNK ARTIST] {ex.get('museum','')}: "
                    f"'{ex.get('title_zh','')[:20]}' has junk: '{artist}'"
                )

    # Check 3: 共有リンク（同じURLが複数展示で使われている）
    links = [ex.get('link', '') for ex in exhibitions if ex.get('link')]
    shared = {link: count for link, count in Counter(links).items() if count > 1}
    for link, count in shared.items():
        issues.append(f"[SHARED LINK] {count} exhibitions share: {link[:80]}")

    # Check 4: 必須フィールド欠落（展示名・日付・施設・リンク）
    for ex in exhibitions:
        title = ex.get('title_zh', '') or ex.get('title_en', '') or '(no title)'
        museum = ex.get('museum', '?')
        if not ex.get('dates'):
            issues.append(f"[MISSING DATES] {museum}: '{title[:30]}'")
        if not (ex.get('title_zh') or ex.get('title_en')):
            issues.append(f"[MISSING TITLE] {museum}: '{title[:30]}'")

    # Check 5: スクレイプ結果と手動データの差異検出
    manual_path = os.path.join(os.path.dirname(__file__), "manual_exhibitions.json")
    if os.path.exists(manual_path):
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
            manual_exs = manual_data.get("exhibitions", [])
            manual_by_key = {}
            for mex in manual_exs:
                key = (mex.get("museum", ""), mex.get("title_en", "") or mex.get("title_zh", ""))
                manual_by_key[key] = mex

            for ex in exhibitions:
                museum = ex.get("museum", "")
                title = ex.get("title_en", "") or ex.get("title_zh", "")
                key = (museum, title)
                if key not in manual_by_key:
                    continue
                mex = manual_by_key[key]
                # Compare dates
                scraped_dates = ex.get("dates", "")
                manual_dates = mex.get("dates", "")
                if scraped_dates and manual_dates and scraped_dates != manual_dates:
                    issues.append(
                        f"[DATA MISMATCH] {museum} '{title[:25]}': "
                        f"dates differ — scraped='{scraped_dates}' vs manual='{manual_dates}'"
                    )
                # Compare title_en
                s_title = ex.get("title_en", "")
                m_title = mex.get("title_en", "")
                if s_title and m_title and s_title != m_title:
                    issues.append(
                        f"[DATA MISMATCH] {museum}: "
                        f"title_en differs — scraped='{s_title[:40]}' vs manual='{m_title[:40]}'"
                    )
                # Compare link
                s_link = ex.get("link", "")
                m_link = mex.get("link", "")
                if s_link and m_link and s_link != m_link:
                    issues.append(
                        f"[DATA MISMATCH] {museum} '{title[:25]}': "
                        f"link differs — scraped='{s_link[:50]}' vs manual='{m_link[:50]}'"
                    )
        except Exception:
            pass

    if issues:
        from datetime import datetime, timezone, timedelta
        tw_now = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')
        log_path = os.path.join(os.path.dirname(__file__), 'validation_log.txt')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n--- Validation {tw_now} ---\n")
            for issue in issues:
                f.write(issue + '\n')
        logger.warning("Validation found %d issues. See validation_log.txt", len(issues))
    else:
        logger.info("Validation passed: no issues found.")


def _enrich_exhibitions(exhibitions, max_to_fetch=5):
    """既存キャッシュを参照しつつ、未取得展覧会の詳細を最大max_to_fetch件取得。"""
    details_cache = _load_details_cache()
    today = _now_tw()

    from collections import Counter
    link_counts = Counter(ex.get("link", "") for ex in exhibitions if ex.get("link"))
    shared_links = {link for link, count in link_counts.items() if count > 1}

    targets = []
    for ex in exhibitions:
        link = ex.get("link", "")
        if not link or "facebook.com" in link:
            continue
        if link in shared_links:
            continue
        # トップページのみのリンクは除外（クエリパラメータ付きやパス深いURLは詳細とみなす）
        is_trunk = (
            link.count("/") < 4
            and "?" not in link
            and "=" not in link
        )
        if is_trunk:
            continue
        cached = details_cache.get(link)
        if cached:
            ex["artists"] = cached.get("artists", [])
            ex["curator"] = cached.get("curator", "")
            ex["description"] = cached.get("description", "")
            if cached.get("description_en"):
                ex["description_en"] = cached["description_en"]
            if cached.get("description_ja"):
                ex["description_ja"] = cached["description_ja"]
            # 手動で3言語入力済みのエントリは再スクレイプしない
            if cached.get("description_ja") or cached.get("description_en"):
                continue
            try:
                fetched_at = datetime.fromisoformat(cached.get("fetched_at", "2000-01-01"))
                age_days = (today - fetched_at).total_seconds() / 86400
                if age_days < DETAILS_TTL_DAYS:
                    continue
            except (ValueError, TypeError):
                pass
        targets.append((ex, link))

    if targets:
        logger.info("Enriching %d exhibitions (max %d this round)", len(targets), max_to_fetch)

    for ex, link in targets[:max_to_fetch]:
        details = _extract_exhibition_details(link)
        if details:
            details_cache[link] = details
            ex["artists"] = details.get("artists", [])
            ex["curator"] = details.get("curator", "")
            ex["description"] = details.get("description", "")
            if details.get("description_en"):
                ex["description_en"] = details["description_en"]
            if details.get("description_ja"):
                ex["description_ja"] = details["description_ja"]

    if targets:
        _save_details_cache(details_cache)


def _load_fb_json(museum_id):
    """manual_exhibitions.jsonから該当施設のデータを読む。date_start/date_endをdates文字列に変換。"""
    fb_path = os.path.join(os.path.dirname(__file__), "manual_exhibitions.json")
    if not os.path.exists(fb_path):
        return []
    try:
        with open(fb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = []
        for ex in data.get("exhibitions", []):
            if ex.get("museum") != museum_id:
                continue
            if not ex.get("dates") and ex.get("date_start"):
                start = ex["date_start"].replace("-", ".")
                end = ex.get("date_end", "").replace("-", ".")
                ex["dates"] = f"{start} – {end}" if end else start
            results.append(ex)
        return results
    except Exception:
        return []


def _scrape_facebook(museum_id, fb_url):
    """Facebookページから展覧会情報を抽出する（Googlebot UA + curl_cffi）。"""
    exhibitions = []
    today = _now_tw()
    try:
        from curl_cffi import requests as cffi_requests
        googlebot_ua = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        resp = cffi_requests.get(
            fb_url, headers={"User-Agent": googlebot_ua},
            impersonate="chrome", timeout=30,
        )
        if resp.status_code != 200:
            return []
        # 投稿テキストを抽出
        raw_messages = re.findall(r'"message":\{"text":"([^"]+)"', resp.text)
        unique_messages = list(dict.fromkeys(raw_messages))
        seen_titles = set()
        for msg_raw in unique_messages:
            try:
                text = msg_raw.encode("raw_unicode_escape").decode("unicode_escape", errors="ignore")
            except Exception:
                text = msg_raw.replace("\\n", "\n")
            if not any(kw in text for kw in ["展", "Exhibition", "exhibition", "個展", "聯展", "Opening", "開幕"]):
                continue
            title, dates = _extract_fb_exhibition(text)
            if not title or title in seen_titles:
                continue
            if dates:
                end_match = re.findall(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", dates)
                if len(end_match) >= 2:
                    try:
                        ey, em, ed = int(end_match[1][0]), int(end_match[1][1]), int(end_match[1][2])
                        if datetime(ey, em, ed) < today:
                            continue
                    except ValueError:
                        continue
            seen_titles.add(title)
            exhibitions.append({
                "museum": museum_id,
                "title_en": title, "title_ja": "", "title_zh": title,
                "dates": dates,
                "location": "",
                "link": fb_url,
            })
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("Facebook scrape failed for %s: %s", museum_id, exc)
    return exhibitions


def _extract_fb_exhibition(text):
    """Facebook投稿テキストから展覧会タイトルと日付を抽出する。"""
    # 日付パターン（広め）
    date_patterns = [
        (r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*[（(]\w+[）)]\s*[－\-–~]\s*(\d{4}[./]\d{1,2}[./]\d{1,2})", "full_paren"),
        (r"(\d{4}[./]\d{1,2}[./]\d{1,2})\s*\w*\.?\s*[－\-–~]\s*(\d{4}[./]\d{1,2}[./]\d{1,2})", "full"),
        (r"展期[：:]*\s*(\d{4}[./]\d{1,2}[./]\d{1,2})\s*[－\-–~]\s*(\d{4}[./]\d{1,2}[./]\d{1,2})", "zhanqi_full"),
        (r"展期[：:]*\s*(\d{1,2}[./]\d{1,2})\s*[－\-–~]\s*(\d{1,2}[./]\d{1,2})", "zhanqi_short"),
    ]
    dates = ""
    for pattern, ptype in date_patterns:
        m = re.search(pattern, text)
        if m:
            if ptype in ("full", "full_paren", "zhanqi_full"):
                dates = f"{m.group(1)} – {m.group(2)}"
            elif ptype == "zhanqi_short":
                year = str(_now_tw().year)
                dates = f"{year}/{m.group(1)} – {year}/{m.group(2)}"
            break
    # タイトル: 最初の意味のある行
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = ""
    for line in lines:
        if re.match(r"^[\d./\-–（）() ]+$", line):
            continue
        if any(skip in line for skip in ["展期", "Exhibition Dates", "Venue", "http", "地點", "時間"]):
            continue
        if len(line) > 3:
            title = re.sub(r"[#＃]", "", line).strip()
            break
    return title, dates


def _with_fallback(museum_id, scrape_fn):
    """スクレイパーを実行し、0件なら手動JSONにフォールバックする。"""
    result = scrape_fn()
    if result:
        return result
    manual_path = os.path.join(os.path.dirname(__file__), f"{museum_id}_manual.json")
    if os.path.exists(manual_path):
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                items = json.load(f)
            if items:
                logger.info("Fallback to manual JSON for %s (%d items)", museum_id, len(items))
                return [{"museum": museum_id, **item} for item in items]
        except Exception:
            pass
    return []


def _do_scrape_all():
    """実際のスクレイピング処理（重い部分）。結果をキャッシュに保存して返す。"""
    all_exhibitions = []

    # 既存の専用スクレイパー（並列実行）
    from concurrent.futures import ThreadPoolExecutor, as_completed
    tasks = {
        "moca_en": lambda: _scrape_moca(lang="en"),
        "moca_zh": lambda: _scrape_moca(lang="zh"),
        "tfam": _scrape_tfam_api,
        # honggah: manual-only (site returns 403, scraper produces junk data)
        "ntcart": lambda: _with_fallback("ntcart", _scrape_ntcart),
        "tcma": lambda: _with_fallback("tcma", _scrape_tcma),
        "clab": lambda: _with_fallback("clab", _scrape_clab),
        "thecube": _scrape_thecube,
        "chiayi": _scrape_chiayi,
        "kdmofa": lambda: _with_fallback("kdmofa", _scrape_kdmofa),
        "goodug": lambda: _with_fallback("goodug", _scrape_goodug),
        "tav": lambda: _with_fallback("tav", _scrape_tav),
        "montue": lambda: _with_fallback("montue", _scrape_montue),
        "pingtung": lambda: _with_fallback("pingtung", _scrape_pingtung),
        "tinakeng": lambda: _with_fallback("tinakeng", lambda: _scrape_artlogic_gallery(
            "tinakeng", "https://www.tinakenggallery.com/en/exhibitions", "Taipei")),
        "asiaart": lambda: _with_fallback("asiaart", lambda: _scrape_artlogic_gallery(
            "asiaart", "https://www.asiaartcenter.org/en/exhibitions", "Taipei")),
        "tnam": lambda: _with_fallback("tnam", _scrape_tnam),
        "soka": lambda: _with_fallback("soka", _scrape_soka),
        "jut": lambda: _with_fallback("jut", _scrape_jut),
        "fubon": lambda: _with_fallback("fubon", _scrape_fubon),
    }
    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                logger.warning("Parallel scrape failed for %s: %s", name, exc)
                results[name] = []

    all_exhibitions.extend(_merge_exhibitions(
        results.get("moca_en", []), results.get("moca_zh", [])
    ))
    for key in ["tfam", "ntcart", "tcma", "clab",
                "thecube", "chiayi", "kdmofa", "goodug", "tav",
                "montue", "pingtung", "tinakeng", "asiaart", "tnam", "soka", "jut", "fubon"]:
        all_exhibitions.extend(results.get(key, []))

    # マスターデータから汎用スクレイパー対象を取得
    master_path = os.path.join(os.path.dirname(__file__), "museums_master.json")
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            master = json.load(f)
        existing_ids = {e["museum"] for e in all_exhibitions}
        for m in master["museums"]:
            mid = m["id"]
            if mid in existing_ids:
                continue
            scraper_type = m.get("scraper")
            ex_url = m.get("exhibition_url")
            if scraper_type == "generic" and ex_url:
                all_exhibitions.extend(_scrape_generic(mid, ex_url))
            elif scraper_type and scraper_type.endswith("_manual"):
                manual_path = os.path.join(
                    os.path.dirname(__file__), f"{mid}_manual.json"
                )
                try:
                    with open(manual_path, "r", encoding="utf-8") as f2:
                        items = json.load(f2)
                    all_exhibitions.extend(
                        [{"museum": mid, **item} for item in items]
                    )
                except Exception:
                    pass
            elif not scraper_type:
                fb_data = _load_fb_json(mid)
                if fb_data:
                    all_exhibitions.extend(fb_data)

        # artemperor.tw アグリゲーターで未取得館を補完
        existing_ids = {e["museum"] for e in all_exhibitions}
        artemperor_data = _scrape_artemperor(pages=5)
        for ex in artemperor_data:
            mid = ex["museum"]
            if mid not in existing_ids:
                all_exhibitions.append(ex)
                existing_ids.add(mid)
            else:
                existing_norm_titles = set()
                for e in all_exhibitions:
                    if e["museum"] == mid:
                        for t in (e.get("title_en", ""), e.get("title_zh", "")):
                            if t:
                                existing_norm_titles.add(_normalize_title_for_compare(t))
                new_title = ex.get("title_en", "") or ex.get("title_zh", "")
                new_norm = _normalize_title_for_compare(new_title)
                is_dup = False
                if new_norm:
                    for existing_norm in existing_norm_titles:
                        if new_norm in existing_norm or existing_norm in new_norm:
                            is_dup = True
                            break
                if not is_dup and new_title:
                    all_exhibitions.append(ex)

    except Exception as exc:
        logger.warning("Master data load failed: %s", exc)

    all_exhibitions = _dedup_exhibitions(all_exhibitions)
    all_exhibitions = _filter_noise(all_exhibitions)
    all_exhibitions = _remove_expired(all_exhibitions)
    all_exhibitions = _filter_known_museums(all_exhibitions)
    _enrich_exhibitions(all_exhibitions, max_to_fetch=8)
    _run_validation(all_exhibitions)
    _save_cache(all_exhibitions)
    return all_exhibitions


def get_artist_index():
    """全展覧会から アーティスト→展覧会リスト のインデックスを生成。"""
    cached = _load_cache_stale() or []
    details = _load_details_cache()
    index = {}

    # link → 展覧会データのマップ
    link_to_ex = {ex.get("link", ""): ex for ex in cached if ex.get("link")}

    # 1. キャッシュ済み詳細データから（リッチ情報あり）
    for link, detail in details.items():
        ex = link_to_ex.get(link)
        if not ex:
            continue
        for artist in detail.get("artists", []):
            if not _is_valid_artist_name(artist):
                continue
            normalized = _normalize_artist_name(artist)
            if not normalized:
                continue
            if normalized not in index:
                index[normalized] = {"name": artist, "exhibitions": []}
            index[normalized]["exhibitions"].append({
                "title": ex.get("title_en") or ex.get("title_zh") or "",
                "museum": ex.get("museum", ""),
                "dates": ex.get("dates", ""),
                "link": ex.get("link", ""),
            })

    # 2. 既にex内にartistsフィールドがある場合（家PCのfb_exhibitions等）
    for ex in cached:
        for artist in ex.get("artists", []):
            if not _is_valid_artist_name(artist):
                continue
            normalized = _normalize_artist_name(artist)
            if not normalized:
                continue
            if normalized not in index:
                index[normalized] = {"name": artist, "exhibitions": []}
            # 重複チェック
            already = any(
                e.get("link") == ex.get("link", "") and e.get("title") == (ex.get("title_en") or ex.get("title_zh") or "")
                for e in index[normalized]["exhibitions"]
            )
            if not already:
                index[normalized]["exhibitions"].append({
                    "title": ex.get("title_en") or ex.get("title_zh") or "",
                    "museum": ex.get("museum", ""),
                    "dates": ex.get("dates", ""),
                    "link": ex.get("link", ""),
                })
    return index


def _normalize_artist_name(name):
    """アーティスト名のURLキーを生成する。"""
    if not name:
        return ""
    n = name.strip().replace("　", " ")
    n = re.sub(r"\s+", " ", n)
    # URL safe key: スペースを-に、その他特殊文字を除去
    key = re.sub(r"[^\w一-鿿぀-ゟ゠-ヿ -]", "", n.lower())
    key = re.sub(r"\s+", "-", key)
    key = re.sub(r"-+", "-", key).strip("-")
    return key


def _is_valid_artist_name(name):
    """アーティスト名として妥当か判定する。"""
    if not name or len(name) < 2 or len(name) > 60:
        return False
    # ノートや注記の典型パターンを除外
    junk_patterns = [
        r"按.*排序", r"^\*", r"^/", r"^[\d\s\-:./]+$",
        r"^與談", r"^主辦", r"^協辦", r"^指導",
        r"^Director", r"^Producer", r"^Organizer", r"^Sponsor",
        r"基金會藝術總監", r"基金會董事", r"執行長",
    ]
    # UI/navigation items that get mistaken for artist names
    ui_junk = [
        "線上藝廊", "登入", "購物須知", "服務條款", "廣告方案", "電子報",
        "藝術新聞", "展覽活動", "專題報導", "藝文影音", "藝術聚點",
        "免費展訊", "隱私權", "常見問題", "會員中心", "藝術品",
        "More", "VIEW", "CLOSE", "Search", "GO", "TOP",
        "展覽回顧", "展覽預告", "當期展覽", "歷年展覽",
        "參觀資訊", "交通資訊", "導覽服務", "時間票價",
        "Participating Artists", "Year",
    ]
    if name in ui_junk or any(junk in name for junk in ui_junk):
        return False
    for pat in junk_patterns:
        if re.search(pat, name):
            return False
    return True


def _filter_known_museums(exhibitions):
    """master.jsonに登録されている施設の展覧会のみ残す。"""
    master_path = os.path.join(os.path.dirname(__file__), "museums_master.json")
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            master = json.load(f)
        known_ids = {m["id"] for m in master.get("museums", [])}
    except Exception:
        return exhibitions
    return [ex for ex in exhibitions if ex.get("museum") in known_ids]


def _normalize_title_for_compare(title):
    """タイトル比較用の正規化（括弧・記号・空白を除去して小文字化）。"""
    if not title:
        return ""
    # 括弧類とよく使われる装飾記号を除去
    t = re.sub(r"[【】《》「」『』\[\]()（）\s\.,，。\-－—–:：;；!！\?？]+", "", title.lower())
    return t


def _dates_overlap(dates_a, dates_b):
    """2つの日付正規化文字列が重なっているか判定（数字のみ）。"""
    if not dates_a or not dates_b:
        return True
    nums_a = re.findall(r"\d{8}", dates_a)
    nums_b = re.findall(r"\d{8}", dates_b)
    if len(nums_a) >= 2 and len(nums_b) >= 2:
        return not (nums_a[1] < nums_b[0] or nums_b[1] < nums_a[0])
    return dates_a == dates_b


def _titles_similar(norm_a, norm_b, min_common=5):
    """2つの正規化タイトルが類似しているか（包含関係 or 共通部分5文字以上）。"""
    if not norm_a or not norm_b:
        return False
    if norm_a in norm_b or norm_b in norm_a:
        return True
    shorter = norm_a if len(norm_a) <= len(norm_b) else norm_b
    longer = norm_b if len(norm_a) <= len(norm_b) else norm_a
    for i in range(len(shorter) - min_common + 1):
        if shorter[i:i+min_common] in longer:
            return True
    return False


def _dedup_exhibitions(exhibitions):
    """同一museum内のタイトル重複を除去する。
    artemperor.tw 由来は優先的に除外する（公式ソース優先）。
    除外したものはログに記録する。"""
    from collections import defaultdict
    by_museum = defaultdict(list)
    for ex in exhibitions:
        by_museum[ex.get("museum", "")].append(ex)

    result = []
    dedup_log = []
    for mid, items in by_museum.items():
        if len(items) < 2:
            result.extend(items)
            continue
        items_sorted = sorted(items, key=lambda x: 1 if "artemperor" in x.get("link", "") else 0)
        keep = []
        seen_entries = []
        for item in items_sorted:
            title_zh = item.get("title_zh", "")
            title_en = item.get("title_en", "")
            title = title_en or title_zh or ""
            dates_norm = _normalize_date_str(item.get("dates", ""))
            norm_title = _normalize_title_for_compare(title)
            norm_title_zh = _normalize_title_for_compare(title_zh)
            exact_key = (norm_title, dates_norm)
            is_dup = False
            for kept_norm, kept_norm_zh, kept_dates, kept_title in seen_entries:
                if exact_key == (kept_norm, kept_dates):
                    is_dup = True
                    break
                if _dates_overlap(dates_norm, kept_dates):
                    if _titles_similar(norm_title, kept_norm) or _titles_similar(norm_title_zh, kept_norm_zh):
                        is_dup = True
                        break
            if is_dup:
                dedup_log.append(f"[DEDUP] {mid}: removed '{title[:40]}' (dup of '{kept_title[:40]}')")
            else:
                seen_entries.append((norm_title, norm_title_zh, dates_norm, title))
                keep.append(item)
        result.extend(keep)

    if dedup_log:
        log_path = os.path.join(os.path.dirname(__file__), "dedup_log.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                from datetime import datetime, timezone, timedelta
                ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
                f.write(f"\n--- {ts} ---\n")
                for line in dedup_log:
                    f.write(line + "\n")
        except Exception:
            pass
        for line in dedup_log:
            logger.info(line)

    return result


def _normalize_date_str(s):
    """日付文字列から数字だけ抽出して比較用文字列にする。"""
    if not s:
        return ""
    return re.sub(r"[^\d]", "", s)


ARCHIVE_FILE = os.path.join(os.path.dirname(__file__), "archive.json")
ARCHIVE_RETENTION_DAYS = 365


UPCOMING_HORIZON_DAYS = 90  # 3ヶ月先までを「近日開始」として扱う


def _parse_date_range(dates_str):
    """日付文字列から (start_dt, end_dt) を返す。取得失敗時は (None, None)。"""
    if not dates_str:
        return None, None
    # 全角スラッシュを半角に
    s = dates_str.replace("／", "/")
    full_dates = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", s)
    start_dt = None
    end_dt = None
    if len(full_dates) >= 1:
        try:
            start_dt = datetime(int(full_dates[0][0]), int(full_dates[0][1]), int(full_dates[0][2]))
        except ValueError:
            pass
    if len(full_dates) >= 2:
        try:
            end_dt = datetime(int(full_dates[1][0]), int(full_dates[1][1]), int(full_dates[1][2]))
        except ValueError:
            pass
    elif len(full_dates) == 1:
        # 短縮終了日: "YYYY.MM.DD – MM.DD" or "YYYY.MM.DD - M/D"
        short_end = re.search(r"[–—\-~]\s*(\d{1,2})[./\-](\d{1,2})\s*$", s)
        if short_end:
            try:
                year = int(full_dates[0][0])
                m, d = int(short_end.group(1)), int(short_end.group(2))
                # 開始日より前の月日なら翌年
                if start_dt and (m, d) < (start_dt.month, start_dt.day):
                    year += 1
                end_dt = datetime(year, m, d)
            except ValueError:
                pass
    return start_dt, end_dt


NOISE_TITLE_KEYWORDS = ["票券", "互惠", "志工", "招募", "徵才", "休館", "停車", "專家導覽", "藝術家面對面"]


def _filter_noise(exhibitions):
    """展示ではないノイズタイトルを除去する。"""
    return [
        ex for ex in exhibitions
        if not any(kw in (ex.get("title_zh", "") or ex.get("title_en", "") or "") for kw in NOISE_TITLE_KEYWORDS)
    ]


def _remove_expired(exhibitions):
    """終了日が過去の展覧会を除去 + 開始日が遠すぎる展覧会も除外。
    残った展覧会には status フィールドを付与する。"""
    today = _now_tw()
    horizon = today + timedelta(days=UPCOMING_HORIZON_DAYS)
    result = []
    expired = []
    for ex in exhibitions:
        dates = ex.get("dates", "")
        start_dt, end_dt = _parse_date_range(dates)
        status = "unknown"
        is_expired = False
        skip_far_future = False
        if end_dt and end_dt < today:
            is_expired = True
        elif start_dt and start_dt > today:
            if start_dt > horizon:
                skip_far_future = True
            else:
                status = "upcoming"
        elif start_dt and start_dt <= today:
            status = "current"
        if is_expired:
            expired.append(ex)
            continue
        if skip_far_future:
            continue
        ex["status"] = status
        result.append(ex)
    if expired:
        _archive_exhibitions(expired)
    return result


def _archive_exhibitions(expired):
    """終了済み展覧会をアーカイブに追加する（重複なし）。"""
    archive = []
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f).get("exhibitions", [])
        except Exception:
            archive = []
    seen_keys = {(ex.get("museum"), ex.get("title_zh") or ex.get("title_en"), ex.get("dates")) for ex in archive}
    for ex in expired:
        key = (ex.get("museum"), ex.get("title_zh") or ex.get("title_en"), ex.get("dates"))
        if key not in seen_keys:
            archive.append(ex)
            seen_keys.add(key)
    # 古すぎるものは削除（1年以上前）
    cutoff = _now_tw() - timedelta(days=ARCHIVE_RETENTION_DAYS)
    keep = []
    for ex in archive:
        end_match = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", ex.get("dates", ""))
        if len(end_match) >= 2:
            try:
                end_dt = datetime(int(end_match[1][0]), int(end_match[1][1]), int(end_match[1][2]))
                if end_dt < cutoff:
                    continue
            except ValueError:
                pass
        keep.append(ex)
    text = json.dumps({"exhibitions": keep}, ensure_ascii=False, indent=2)
    text = re.sub(r"[\ud800-\udfff]", "", text)
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def load_archive():
    """アーカイブされた終了済み展覧会を返す。"""
    if not os.path.exists(ARCHIVE_FILE):
        return []
    try:
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("exhibitions", [])
    except Exception:
        return []


def _bg_refresh():
    """バックグラウンドでスクレイピングを実行する。"""
    global _bg_running
    try:
        logger.info("Background refresh started")
        _do_scrape_all()
        logger.info("Background refresh completed")
    except Exception as exc:
        logger.error("Background refresh failed: %s", exc)
    finally:
        with _bg_lock:
            _bg_running = False


def fetch_all_exhibitions():
    """全美術館の展覧会情報を取得する（stale-while-revalidateキャッシュ）。"""
    global _bg_running

    # 1. TTL内のキャッシュがあれば即返す
    cached = _load_cache()
    if cached is not None:
        return cached

    # 2. TTL切れだが古いキャッシュが存在する場合:
    #    古いデータを即返し、裏で更新を開始
    stale = _load_cache_stale()
    if stale is not None:
        with _bg_lock:
            if not _bg_running:
                _bg_running = True
                t = threading.Thread(target=_bg_refresh, daemon=True)
                t.start()
        return stale

    # 3. キャッシュが完全に存在しない場合（初回デプロイ直後等）:
    #    同期でスクレイピングして返す（これだけは待ちが発生する）
    return _do_scrape_all()
