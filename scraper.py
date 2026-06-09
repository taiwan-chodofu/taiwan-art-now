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
                     "座談", "講座", "放映", "工作坊"]
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
    try:
        payload = {"JJMethod": "GetEx", "Type": "1"}
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
            dates = f"{begin} - {end}" if begin and end else begin
            link = f"{base}/Exhibition/Exhibition_page.aspx?id={ex_id}"
            if name:
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
    """鳳甲美術館の公式サイトから展覧会情報を取得する。"""
    exhibitions = []
    today = _now_tw()
    url = "https://hong-gah.org.tw/en/exhibitions"
    try:
        soup = _fetch_cffi(url)
        article = soup.find("article")
        if not article:
            raise ValueError("No article element found")
        text = article.get_text(separator="|", strip=True)
        parts = [p.strip() for p in text.split("|") if p.strip()]
        i = 0
        while i < len(parts):
            title = parts[i]
            dates = ""
            if i + 1 < len(parts):
                dm = re.search(r"(\d{4}\.\d{1,2}\.\d{1,2})\s*[-–]\s*(\d{1,2}\.\d{1,2})", parts[i + 1])
                if dm:
                    dates = parts[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1
            if not title or len(title) < 3 or re.match(r"^\d{4}\.", title):
                continue
            date_full = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\s*[-–]\s*(\d{1,2})\.(\d{1,2})", dates)
            normalized_dates = ""
            if date_full:
                y = int(date_full.group(1))
                sm, sd = int(date_full.group(2)), int(date_full.group(3))
                em, ed = int(date_full.group(4)), int(date_full.group(5))
                normalized_dates = f"{y}.{sm:02d}.{sd:02d} – {y}.{em:02d}.{ed:02d}"
                try:
                    if datetime(y, em, ed) < today:
                        continue
                except ValueError:
                    pass
            link_el = soup.find("a", href=re.compile(re.escape(title[:15])), recursive=True)
            href = ""
            if not link_el:
                links = article.find_all("a", href=True)
                for a in links:
                    if title[:10] in a.get_text():
                        href = a.get("href", "")
                        break
            else:
                href = link_el.get("href", "")
            exhibitions.append({
                "museum": "honggah",
                "title_en": title, "title_ja": "", "title_zh": "",
                "dates": normalized_dates or dates,
                "location": "Hong-Gah Museum",
                "link": href,
            })
    except Exception as exc:
        logger.warning("Hong-Gah scrape failed: %s", exc)
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
            exhibitions.append({
                "museum": "tcma",
                "title_en": title, "title_ja": "", "title_zh": "",
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
    """C-LAB（臺灣當代文化實驗場）から当期展覧会情報を取得する。"""
    exhibitions = []
    base = MUSEUMS["clab"]["url"]
    url = f"{base}/en/events/"
    today = _now_tw()
    try:
        soup = _fetch(url)
        for card in soup.select("div.a-base-card.-event"):
            cat_el = card.select_one(".a-base-card__category-wrapper")
            cat = cat_el.get_text(strip=True) if cat_el else ""
            if cat != "Exhibition":
                continue
            link_el = card.select_one("a[href]")
            href = link_el.get("href", "") if link_el else ""
            title_el = card.select_one("p.a-base-card__title, h2, h3, strong")
            title = title_el.get_text(strip=True) if title_el else ""
            time_el = card.select_one(".a-base-card__time")
            time_text = time_el.get_text(separator=" ", strip=True) if time_el else ""
            dates = _parse_clab_dates(time_text)
            end_match = re.findall(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", dates)
            if len(end_match) >= 2:
                try:
                    ey, em, ed = int(end_match[1][0]), int(end_match[1][1]), int(end_match[1][2])
                    if datetime(ey, em, ed) < today:
                        continue
                except ValueError:
                    pass
            if not href.startswith("http"):
                href = base + href
            if title and len(title) > 3:
                exhibitions.append({
                    "museum": "clab",
                    "title_en": title,
                    "title_ja": "",
                    "title_zh": "",
                    "dates": dates,
                    "location": "C-LAB",
                    "link": href,
                })
    except Exception as exc:
        logger.warning("C-LAB scrape failed: %s", exc)
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
                    exhibitions.append({
                        "museum": "kdmofa",
                        "title_en": title,
                        "title_ja": "", "title_zh": "",
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
                exhibitions.append({
                    "museum": museum_id,
                    "title_en": title,
                    "title_ja": "", "title_zh": "",
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

        return {
            "artists": artists[:15],
            "curator": curator,
            "description": description,
            "fetched_at": _now_tw().isoformat(),
        }
    except Exception as exc:
        logger.warning("Detail extraction failed for %s: %s", url, exc)
        return None


def _enrich_exhibitions(exhibitions, max_to_fetch=5):
    """既存キャッシュを参照しつつ、未取得展覧会の詳細を最大max_to_fetch件取得。"""
    details_cache = _load_details_cache()
    today = _now_tw()
    targets = []
    for ex in exhibitions:
        link = ex.get("link", "")
        if not link or "facebook.com" in link:
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

    if targets:
        _save_details_cache(details_cache)


def _load_fb_json(museum_id):
    """家PCが生成したfb_exhibitions.jsonから該当施設のデータを読む。"""
    fb_path = os.path.join(os.path.dirname(__file__), "fb_exhibitions.json")
    if not os.path.exists(fb_path):
        return []
    try:
        with open(fb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ex for ex in data.get("exhibitions", []) if ex.get("museum") == museum_id]
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
        "honggah": lambda: _with_fallback("honggah", _scrape_honggah),
        "ntcart": lambda: _with_fallback("ntcart", _scrape_ntcart),
        "tcma": lambda: _with_fallback("tcma", _scrape_tcma),
        "clab": lambda: _with_fallback("clab", _scrape_clab),
        "thecube": _scrape_thecube,
        "chiayi": _scrape_chiayi,
        "kdmofa": lambda: _with_fallback("kdmofa", _scrape_kdmofa),
        "goodug": lambda: _with_fallback("goodug", _scrape_goodug),
        "tav": lambda: _with_fallback("tav", _scrape_tav),
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
    for key in ["tfam", "honggah", "ntcart", "tcma", "clab",
                "thecube", "chiayi", "kdmofa", "goodug", "tav"]:
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
                museum_url = m.get("url", "")
                if "facebook.com" in museum_url:
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
                existing_titles = {
                    (e.get("title_en", "") or e.get("title_zh", ""))
                    for e in all_exhibitions if e["museum"] == mid
                }
                new_title = ex.get("title_en", "") or ex.get("title_zh", "")
                if new_title and new_title not in existing_titles:
                    all_exhibitions.append(ex)

    except Exception as exc:
        logger.warning("Master data load failed: %s", exc)

    all_exhibitions = _dedup_exhibitions(all_exhibitions)
    all_exhibitions = _remove_expired(all_exhibitions)
    all_exhibitions = _filter_known_museums(all_exhibitions)
    _enrich_exhibitions(all_exhibitions, max_to_fetch=8)
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


def _dedup_exhibitions(exhibitions):
    """同一museum内のタイトル重複（完全一致・包含関係）を除去する。"""
    from collections import defaultdict
    by_museum = defaultdict(list)
    for ex in exhibitions:
        by_museum[ex.get("museum", "")].append(ex)

    result = []
    for mid, items in by_museum.items():
        if len(items) < 2:
            result.extend(items)
            continue
        keep = []
        seen_keys = set()
        for item in items:
            title = item.get("title_en", "") or item.get("title_zh", "") or ""
            dates_norm = _normalize_date_str(item.get("dates", ""))
            # 完全一致（タイトル+日付）
            exact_key = (title.strip().lower(), dates_norm)
            if exact_key in seen_keys:
                continue
            # タイトル包含 + 日付一致
            is_subset = False
            for other in items:
                if other is item:
                    continue
                other_title = other.get("title_en", "") or other.get("title_zh", "") or ""
                other_dates_norm = _normalize_date_str(other.get("dates", ""))
                if not title or not other_title:
                    continue
                if title in other_title and title != other_title and dates_norm == other_dates_norm:
                    is_subset = True
                    break
            if not is_subset:
                seen_keys.add(exact_key)
                keep.append(item)
        result.extend(keep)
    return result


def _normalize_date_str(s):
    """日付文字列から数字だけ抽出して比較用文字列にする。"""
    if not s:
        return ""
    return re.sub(r"[^\d]", "", s)


ARCHIVE_FILE = os.path.join(os.path.dirname(__file__), "archive.json")
ARCHIVE_RETENTION_DAYS = 365


def _remove_expired(exhibitions):
    """終了日が過去の展覧会を除去する。終了済みは archive.json に蓄積。"""
    today = _now_tw()
    result = []
    expired = []
    for ex in exhibitions:
        dates = ex.get("dates", "")
        date_matches = re.findall(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", dates)
        is_expired = False
        if len(date_matches) >= 2:
            y, m, d = int(date_matches[1][0]), int(date_matches[1][1]), int(date_matches[1][2])
            try:
                end_dt = datetime(y, m, d)
                if end_dt < today:
                    is_expired = True
            except ValueError:
                pass
        if is_expired:
            expired.append(ex)
        else:
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
