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

if __name__ == "__main__":
    unittest.main()
