"""Unit tests for the *actual* _stable_key/_normalize_dates helpers in app.py.

The full application imports scrapers and external services; isolate only the
real function AST so these tests run with no network, database, Flask app or
subscriber JSON involved. See docs/ai-handoff/DECISIONS.md 2026-11-26
("stable_key is not yet safe...") for the collision this closes and the
deliberate choice of start-date-only disambiguation.
"""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
wanted = {"_normalize_dates", "_stable_key"}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
assert len(nodes) == len(wanted), "app.py helper(s) renamed or removed"
code = compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec")
scope = {}
exec(code, scope)
_stable_key = scope["_stable_key"]


class StableKeyTests(unittest.TestCase):
    def test_different_launch_dates_get_different_keys(self):
        # A title reused across different real occurrences at the same venue
        # (e.g. an undated annual series name) must not collide.
        a = _stable_key("m", {"title_zh": "年度展", "dates": "2025.01.10 – 2025.02.10"})
        b = _stable_key("m", {"title_zh": "年度展", "dates": "2026.01.10 – 2026.02.10"})
        self.assertNotEqual(a, b)

    def test_same_start_date_with_corrected_end_date_keeps_the_same_key(self):
        # Real case from archive.json: museum 99dac, "維度游移Ⅱ-張可昱創作個展",
        # same start date, end date corrected by a later re-scrape. Must stay
        # one key so a user's favs/visited registration is not orphaned by a
        # routine end-date correction.
        original = _stable_key("99dac", {"title_zh": "維度游移Ⅱ-張可昱創作個展",
                                          "dates": "2026.08.08 – 2026.08.29"})
        corrected = _stable_key("99dac", {"title_zh": "維度游移Ⅱ-張可昱創作個展",
                                           "dates": "2026.08.08 – 2026.10.31"})
        self.assertEqual(original, corrected)

    def test_missing_date_falls_back_to_title_only_rather_than_fabricating_one(self):
        key = _stable_key("m", {"title_zh": "", "title_en": "Untitled Show", "dates": ""})
        self.assertEqual(key, "m__Untitled Show")

    def test_title_en_used_only_when_title_zh_is_absent(self):
        key = _stable_key("m", {"title_zh": "中文標題", "title_en": "English Title",
                                 "dates": "2026.05.01 – 2026.05.31"})
        self.assertTrue(key.startswith("m__中文標題__"))

    def test_different_museums_with_identical_title_and_date_still_differ(self):
        a = _stable_key("museum_a", {"title_zh": "同名展", "dates": "2026.03.01 – 2026.03.31"})
        b = _stable_key("museum_b", {"title_zh": "同名展", "dates": "2026.03.01 – 2026.03.31"})
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
