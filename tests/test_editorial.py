import unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from app import app

class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_full_manuscript(self):
        response = self.client.get("/essays/001?utm_source=instagram")
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.data, "html.parser")
        manuscript = (Path(app.root_path) / "editorial/001.txt").read_text(encoding="utf-8").strip()
        body, appendix, sources, footer = manuscript.split("\n\n⸻\n\n")
        title, *paragraphs = body.split("\n\n")
        self.assertEqual(soup.h1.get_text(), title)
        self.assertEqual([p.get_text() for p in soup.select("#essay-body p")], paragraphs)
        self.assertEqual([a["href"] for a in soup.select("details a")], [line for line in sources.splitlines() if line.startswith("https://")])
        self.assertEqual(soup.select_one('link[rel="canonical"]')["href"], "https://taiwan-art-now.onrender.com/essays/001")
        self.assertTrue(soup.select_one('a[href="/?open=mylist&lang=zh"]'))

    def test_index(self):
        response = self.client.get("/essays")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/essays/001"', response.data)

    def test_editorial_navigation_templates(self):
        with app.test_request_context("/"):
            from flask import render_template
            for lang in ("zh", "ja", "en"):
                soup = BeautifulSoup(render_template("editorial_card.html", current_lang=lang), "html.parser")
                self.assertEqual(soup.a["href"], "/essays/001")
                self.assertIn("既是一，又不只是一", soup.a.get_text())
        for path in ("discover", "search", "artists", "archive"):
            template = (Path(app.root_path) / "templates" / (path + ".html")).read_text(encoding="utf-8")
            self.assertIn('href="/essays"', template)
            app.jinja_env.get_template(path + ".html")
        for path in ("index", "artist_detail", "exhibition_detail_page"):
            template = (Path(app.root_path) / "templates" / (path + ".html")).read_text(encoding="utf-8")
            self.assertIn("include 'editorial_card.html'", template)
            app.jinja_env.get_template(path + ".html")

    def test_og(self):
        response = self.client.get("/og-image/essays/001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(Image.open(BytesIO(response.data)).size, (1200, 630))

    def test_exhibition_resolution(self):
        records = [{"museum":"other"}, {"museum":"fotoaura","link":"other"}, {"museum":"fotoaura","link":"https://www.facebook.com/events/1464742292528914/"}]
        with patch("scraper.fetch_all_exhibitions", return_value=records):
            self.assertEqual(self.client.get("/essays/001/exhibition").location, "/exhibition/fotoaura/1?lang=zh")
        with patch("scraper.fetch_all_exhibitions", return_value=[]):
            self.assertIn("/search?", self.client.get("/essays/001/exhibition").location)


    def test_second_edition_full_text_and_navigation(self):
        import re
        from urllib.parse import parse_qs, urlparse
        response = self.client.get("/essays/001/second?utm_source=instagram")
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.data, "html.parser")
        manuscript = (Path(app.root_path) / "editorial/001-second.txt").read_text(encoding="utf-8").strip()
        body, _, backmatter = manuscript.partition("\n---\n")
        blocks = re.split(r"\n\s*\n", body.strip())
        expected = [b for b in blocks if not b.startswith("#") and b not in ("Taiwan Art Now", "第二稿｜投票之後")]
        self.assertEqual([p.get_text() for p in soup.select("#essay-body p")], expected)
        headings = [b[3:] for b in blocks if re.match(r"^## [ⅠⅡⅢⅣⅤⅥⅦⅧ]", b)]
        self.assertEqual(len(headings), 8)
        self.assertEqual([h.get_text() for h in soup.select("#essay-body h2")], headings)
        toc = soup.select('nav[aria-label="目錄"] a')
        self.assertEqual(len(toc), 8)
        for a in toc:
            self.assertIsNotNone(soup.find(id=a["href"][1:]))
        canonical = "https://taiwan-art-now.onrender.com/essays/001/second"
        self.assertEqual(soup.select_one('link[rel="canonical"]')["href"], canonical)
        self.assertEqual(soup.select_one("#share-url")["value"], canonical)
        self.assertEqual(soup.select_one('meta[property="og:url"]')["content"], canonical)
        self.assertTrue(soup.select_one('meta[property="og:image"]')["content"].endswith("/001/second"))
        for name, key in (("LINE", "url"), ("Facebook", "u")):
            a = next(a for a in soup.select("#share a") if name in a.get_text())
            self.assertEqual(parse_qs(urlparse(a["href"]).query)[key], [canonical])
        sources = backmatter.split("### 參考資料｜References", 1)[1]
        self.assertEqual([a["href"] for a in soup.select("details a")], [l.strip() for l in sources.splitlines() if l.strip().startswith("https://")])
        self.assertIn("Paul Celan", soup.get_text())
        self.assertIn("尚未觀看", soup.get_text())
        self.assertTrue(soup.select_one('nav[aria-label="文章版本"] a[href="/essays/001"]'))
        first = BeautifulSoup(self.client.get("/essays/001").data, "html.parser")
        self.assertTrue(first.select_one('nav[aria-label="文章版本"] a[href="/essays/001/second"]'))
        index = BeautifulSoup(self.client.get("/essays").data, "html.parser")
        self.assertEqual([a["href"] for a in index.select(".essay-card")], ["/essays/001/second", "/essays/001"])

    def test_second_edition_og(self):
        first = self.client.get("/og-image/essays/001")
        second = self.client.get("/og-image/essays/001/second")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.mimetype, "image/png")
        self.assertEqual(Image.open(BytesIO(second.data)).size, (1200, 630))
        self.assertNotEqual(first.data, second.data)

if __name__ == "__main__":
    unittest.main()
