# Taiwan Art Now 🎨

A multilingual web app that aggregates current exhibition information from contemporary art museums across Taiwan.

## Museums Covered (9)

| Museum | Location | Data Source |
|--------|----------|-------------|
| Hong-Gah Museum (鳳甲美術館) | Taipei, Beitou | Manual JSON |
| MOCA Taipei (台北當代藝術館) | Taipei, Datong | HTML scraping + detail pages |
| TFAM (臺北市立美術館) | Taipei, Zhongshan | Ajax API |
| C-LAB (臺灣當代文化實驗場) | Taipei, Da'an | HTML scraping |
| TheCube Project Space (立方計劃空間) | Taipei, Da'an | HTML scraping + Playwright |
| KdMoFA (關渡美術館) | Taipei, Beitou | HTML scraping |
| New Taipei City Art Museum (新北市美術館) | New Taipei, Yingge | Manual JSON |
| Chiayi Art Museum (嘉義市立美術館) | Chiayi | HTML scraping |
| Taichung Art Museum (臺中市立美術館) | Taichung | Manual JSON |

## Features

- 4 languages: English, 日本語, 中文, Polski
- Current exhibitions only (past exhibitions filtered out)
- Unified date format (YYYY.MM.DD)
- "X days left" badge for exhibitions ending within 14 days
- 6-hour data cache for fast loading
- One-click refresh button

## Quick Start

### Prerequisites

- Python 3.10+
- Playwright (for some museum sites)

### Install

```bash
cd taiwan_art
pip install -r requirements.txt
playwright install chromium
```

### Run

Double-click `start.bat` (Windows), or:

```bash
cd taiwan_art
python app.py
```

Open http://127.0.0.1:5050 in your browser.

## Updating Manual Exhibition Data

Some museums use SPA frameworks or Cloudflare protection, making automated scraping impossible. Their data is managed via JSON files:

| File | Museum |
|------|--------|
| `honggah_manual.json` | Hong-Gah Museum |
| `ntcart_manual.json` | New Taipei City Art Museum |
| `tcma_manual.json` | Taichung Art Museum |
| `kdmofa_manual.json` | KdMoFA (fallback only) |

Edit these files when exhibitions change. Format:

```json
[
  {
    "title_en": "Exhibition Title",
    "title_ja": "展覧会タイトル",
    "title_zh": "展覽標題",
    "dates": "2026.03.07 – 2026.05.31",
    "location": "Museum Name",
    "link": "https://..."
  }
]
```

## Project Structure

```
taiwan_art/
├── app.py                 # Flask app (routing, i18n, date normalization)
├── scraper.py             # Scrapers for 9 museums
├── templates/
│   └── index.html         # ART iT-inspired minimal UI
├── honggah_manual.json    # Hong-Gah Museum exhibitions
├── ntcart_manual.json     # New Taipei City Art Museum exhibitions
├── tcma_manual.json       # Taichung Art Museum exhibitions
├── kdmofa_manual.json     # KdMoFA exhibitions (fallback)
├── requirements.txt
├── start.bat              # Windows launcher
├── LICENSE
└── .gitignore
```

## License

MIT
