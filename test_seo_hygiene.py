import unittest
from pathlib import Path

from seo_hygiene import (
    MAX_TITLE_CHARS, compact_title, description_from_content,
    image_alt_failures, repair_image_alts, unique_title,
)


class SeoHygieneTests(unittest.TestCase):
    def test_long_news_title_keeps_desk_and_date(self):
        title = compact_title("Canada Finance News · 1 October 2026 · Coverage September 30 to October 1 — Markets rally")
        self.assertEqual(title, "Canada Finance News — 1 October 2026")
        self.assertLessEqual(len(title), MAX_TITLE_CHARS)

    def test_long_evergreen_title_is_word_clipped(self):
        title = compact_title("The Complete Beginner Guide to Building Wealth Through Low-Cost Index Funds and Tax-Advantaged Accounts")
        self.assertLessEqual(len(title), MAX_TITLE_CHARS)
        self.assertFalse(title.endswith(" "))

    def test_duplicate_suffix_stays_inside_budget(self):
        title = unique_title("A very long financial analysis title that consumes the complete title allowance", 12)
        self.assertLessEqual(len(title), MAX_TITLE_CHARS)
        self.assertTrue(title.endswith("(12)"))

    def test_missing_empty_and_unquoted_alts_are_repaired(self):
        content = '<img src="a"><img src="b" alt=""><img src="c" alt=><img src="d" alt="Existing">'
        repaired, count = repair_image_alts(content, "Market guide")
        self.assertEqual(count, 3)
        self.assertEqual(image_alt_failures(repaired), 0)
        self.assertIn('alt="Existing"', repaired)

    def test_description_is_factual_and_bounded(self):
        content = "<p>This sourced guide explains diversified investment costs, tax structure and practical risk controls for long-term readers.</p>"
        description = description_from_content("Guide", content)
        self.assertIn("sourced guide", description)
        self.assertLessEqual(len(description), 155)

    def test_theme_has_server_description_fallback_and_single_item_page_name(self):
        theme = Path("theme/Daily-Yield-Theme-v4-2026-10-01.xml").read_text(encoding="utf-8")
        self.assertIn("Bing-safe server-rendered fallback", theme)
        self.assertIn("<title><data:blog.pageName/></title>", theme)
        self.assertNotIn("<title><data:blog.pageName/> | Daily Yield Finance</title>", theme)
        self.assertIn("img:not([alt]),img[alt=\"\"]", theme)


if __name__ == "__main__":
    unittest.main()
