"""台湾現代アート美術館の展覧会情報スクレイパー"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import logging
import re

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache.json")
CACHE_TTL_HOURS = 6

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
        "url": "https://www.mocataipei.org.tw",
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
    """キャッシュファイルを読み込む。"""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        age_hours = (datetime.now() - cached_at).total_seconds() / 3600
        if age_hours < CACHE_TTL_HOURS:
            return data.get("exhibitions", [])
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _save_cache(exhibitions):
    """展覧会データをキャッシュに保存する。"""
    data = {
        "cached_at": datetime.now().isoformat(),
        "exhibitions": exhibitions,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
    prefix = "/en" if lang == "en" else "/zh-tw"
    url = f"{base}{prefix}/ExhibitionAndEvent/Exhibitions/Current%20Exhibition"
    title_key = f"title_{lang}"
    today = datetime.now()
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
        today = datetime.now()
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


def _scrape_honggah():
    """鳳甲美術館の公式サイトから展覧会情報を取得する。"""
    exhibitions = []
    today = datetime.now()
    url = "https://hong-gah.org.tw/en/exhibitions"
    try:
        soup = _fetch(url)
        for h4 in soup.find_all("h4"):
            link = h4.find("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://hong-gah.org.tw" + href
            parent = h4.parent
            text = parent.get_text(separator="\n", strip=True) if parent else ""
            dm = re.search(
                r"(\d{4}\.\d{2}\.\d{2})\s*[-–]\s*(\d{4}\.\d{2}\.\d{2})", text
            )
            dates = f"{dm.group(1)} – {dm.group(2)}" if dm else ""
            if dates and not _is_current_exhibition(dates, today):
                continue
            if not dates:
                sm = re.search(r"(\d{4}\.\d{2}\.\d{2})", text)
                dates = sm.group(1) if sm else ""
            exhibitions.append({
                "museum": "honggah",
                "title_en": title, "title_ja": "", "title_zh": "",
                "dates": dates, "location": "Hong-Gah Museum",
                "link": href,
            })
    except Exception as exc:
        logger.warning("Hong-Gah scrape failed: %s", exc)
    if not exhibitions:
        manual_path = os.path.join(os.path.dirname(__file__), "honggah_manual.json")
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                return [{"museum": "honggah", **i} for i in json.load(f)]
        except Exception:
            pass
    return exhibitions


def _scrape_ntcart():
    """新北市美術館の公式サイトから展覧会情報を取得する。"""
    exhibitions = []
    today = datetime.now()
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
    today = datetime.now()
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
    """C-LAB（臺灣當代文化實驗場）から当期・近日開始の展覧会情報を取得する。"""
    exhibitions = []
    base = MUSEUMS["clab"]["url"]
    url = f"{base}/en/events/"
    today = datetime.now()
    try:
        soup = _fetch(url)
        seen = set()
        for link_tag in soup.select("a[href*='/events/']"):
            href = link_tag.get("href", "")
            if href in seen or href.rstrip("/").endswith("/events"):
                continue
            seen.add(href)
            text = link_tag.get_text(separator="|", strip=True)
            # Exhibitionカテゴリのみ対象
            if "Exhibition" not in text:
                continue
            parts = [p.strip() for p in text.split("|") if p.strip()]
            parts = [p for p in parts if p not in ("Exhibition", "+ MORE")]
            title = parts[0] if parts else ""
            dates = ""
            date_match = re.search(
                r"(\d{2}\.\d{2}.*?\d{4}.*?\d{2}\.\d{2}.*?\d{4})", text
            )
            if date_match:
                dates = date_match.group(1).strip()
            # 終了日で当期判定（C-LAB形式: MM.DD ... YYYY）
            end_years = re.findall(r"(\d{4})\s*\.", dates)
            date_pairs = re.findall(r"(\d{2})\.(\d{2})", dates)
            if end_years and len(date_pairs) >= 2:
                try:
                    ey = int(end_years[-1])
                    em, ed = int(date_pairs[-1][0]), int(date_pairs[-1][1])
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
    today = datetime.now()
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
    today = datetime.now()
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
    today = datetime.now()
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
    today = datetime.now()
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


def _scrape_generic(museum_id, exhibition_url):
    """汎用スクレイパー: 展覧会ページからタイトルと日付を自動抽出する。"""
    exhibitions = []
    today = datetime.now()
    try:
        soup = _fetch(exhibition_url)
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # 日付パターンを含む行とその前の行をペアで抽出
        for i, line in enumerate(lines):
            date_match = re.search(
                r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})"
                r".*?[–—~\-]\s*"
                r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})",
                line,
            )
            if date_match:
                dates = (
                    f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}"
                    f" - {date_match.group(4)}/{date_match.group(5)}/{date_match.group(6)}"
                )
                if not _is_current_exhibition(dates, today):
                    continue
                title = lines[i - 1] if i > 0 else line
                # タイトルが短すぎるか日付のみの場合はスキップ
                if len(title) < 3 or re.match(r"^\d{4}", title):
                    title = line.split(date_match.group(0))[0].strip()
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


def fetch_all_exhibitions():
    """全美術館の展覧会情報を取得する（キャッシュ付き）。"""
    cached = _load_cache()
    if cached is not None:
        return cached

    all_exhibitions = []

    # 既存の専用スクレイパー
    moca_en = _scrape_moca(lang="en")
    moca_zh = _scrape_moca(lang="zh")
    all_exhibitions.extend(_merge_exhibitions(moca_en, moca_zh))
    all_exhibitions.extend(_scrape_tfam_api())
    all_exhibitions.extend(_scrape_honggah())
    all_exhibitions.extend(_scrape_ntcart())
    all_exhibitions.extend(_scrape_tcma())
    all_exhibitions.extend(_scrape_clab())
    all_exhibitions.extend(_scrape_thecube())
    all_exhibitions.extend(_scrape_chiayi())
    all_exhibitions.extend(_scrape_kdmofa())
    all_exhibitions.extend(_scrape_goodug())
    all_exhibitions.extend(_scrape_tav())

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

        # artemperor.tw アグリゲーターで未取得館を補完
        existing_ids = {e["museum"] for e in all_exhibitions}
        artemperor_data = _scrape_artemperor(pages=5)
        for ex in artemperor_data:
            mid = ex["museum"]
            if mid not in existing_ids:
                # 新規館: そのまま追加
                all_exhibitions.append(ex)
                existing_ids.add(mid)
            else:
                # 既存館: 同一タイトルがなければ追加
                existing_titles = {
                    (e.get("title_en", "") or e.get("title_zh", ""))
                    for e in all_exhibitions if e["museum"] == mid
                }
                new_title = ex.get("title_en", "") or ex.get("title_zh", "")
                if new_title and new_title not in existing_titles:
                    all_exhibitions.append(ex)

    except Exception as exc:
        logger.warning("Master data load failed: %s", exc)

    _save_cache(all_exhibitions)
    return all_exhibitions
