import datetime as dt
import re
import unittest
from unittest.mock import patch

import news_pipeline as news


HERO = {
    "url": "https://example.com/hero.jpg",
    "alt": "Financial district",
    "credit": "Test photograph",
    "source": "test",
}


class NewsArticleExpansionTests(unittest.TestCase):
    def setUp(self):
        self.day = dt.date(2026, 10, 9)
        self.end = dt.datetime(2026, 10, 9, 12, tzinfo=news.IST)
        self.start = self.end - dt.timedelta(days=1)

    def items(self, count=15):
        subjects = [
            "inflation", "growth", "jobs", "rates", "trade", "budget",
            "housing", "savings", "earnings", "enforcement", "regulation",
            "IPO", "crypto", "pension", "market",
        ]
        description = (
            "The publisher reports expectations and possible market consequences "
            "for investors, companies and policy makers today."
        )
        return [
            {
                "title": f"{subjects[i % len(subjects)].title()} outlook, expected consequences and investor response analysis update {i}",
                "url": f"https://example.com/source-{i}",
                "desc": description,
                "date": self.day,
                "agency": f"Credible Source {i}",
                "prio": 2,
                "media": True,
            }
            for i in range(count)
        ]

    def build(self, count=15):
        with patch.object(news, "daily_hero", return_value=HERO):
            article = news.build_article(
                "global", self.items(count), [], self.day, self.start,
                self.end, {}, [], context_target=175,
            )
        related = [
            {
                "id": f"related-{i}",
                "title": f"Practical finance guide {i}",
                "content": "",
                "labels": ["Articles"],
                "published": f"2026-10-0{i + 1}T00:00:00Z",
                "url": f"https://dailyyield.blogspot.com/2026/10/guide-{i}.html",
            }
            for i in range(4)
        ]
        current = {"id": "pending", "title": article["title"], "labels": article["labels"], "content": article["html"]}
        article["html"] = news.ensure_related_articles(article["html"], current, related)
        article["html"] = news.ensure_family(article["html"])
        article["html"] = news.ensure_continuous_motion(article["html"])
        article["html"], _ = news.repair_image_alts(article["html"], article["title"])
        return article

    def test_rich_article_is_inside_strict_editorial_range(self):
        article = self.build()
        count = news.assert_news_editorial_length(article["html"])
        self.assertGreaterEqual(count, 3800)
        self.assertLessEqual(count, 4100)

    def test_every_headline_has_immediate_source_description(self):
        html = self.build()["html"]
        blocks = re.findall(r'<div class="fbk-item[^>]*>(.*?)</div>', html, re.S)
        self.assertEqual(len(blocks), 15)
        for block in blocks:
            self.assertRegex(
                block,
                r"<h3>.*?</h3>\s*<p class=\"fbk-description\"><strong>.*?</strong>.+?</p>",
            )

    def test_forecasts_are_labelled_and_not_asserted_as_fact(self):
        html = news.compose_item(self.items(1)[0], self.end)
        self.assertIn("Reported outlook", html)
        self.assertIn("not an observed future result", html)
        self.assertIn("Credible Source 0", html)

    def test_redundant_opening_lede_is_removed_and_method_is_a_guidance_box(self):
        html = self.build()["html"]
        self.assertNotIn('class="fbk-lede"', html)
        self.assertNotIn("current, verified finance items from", html)
        self.assertIn('class="fbk-method"', html)
        self.assertIn("Reader guidance · not a news headline", html)
        self.assertIn('aria-labelledby="fbkMethodTitle"', html)

    def test_thin_article_is_blocked(self):
        article = self.build(14)
        with self.assertRaisesRegex(ValueError, "outside 3800-4100"):
            news.assert_news_editorial_length(article["html"])

    def test_source_integrity_gate_rejects_headline_only_items(self):
        item = self.items(1)[0]
        self.assertTrue(news.item_source_is_usable(item))
        item["desc"] = "headline only"
        self.assertFalse(news.item_source_is_usable(item))

    def test_discovery_includes_forecasts_and_expert_expectations(self):
        names = [source[0] for source in news.discovery_sources("india")]
        self.assertTrue(any("Forecast" in name for name in names))
        self.assertTrue(any("Analyst Expectations" in name for name in names))

    def test_adaptive_polish_adds_a_sourced_headline_when_short(self):
        description = (
            "Publisher reports an outlook with possible consequences for markets, "
            "policy, companies and households today."
        )
        candidates = [
            {
                "title": f"Outlook update {i}", "url": f"https://example.com/adaptive-{i}",
                "desc": description, "date": self.day, "agency": f"Source {i}",
                "prio": 2, "media": True,
            }
            for i in range(20)
        ]
        related = [
            {"id": f"r{i}", "title": f"Guide {i}", "content": "", "labels": ["Articles"],
             "published": "2026-10-01T00:00:00Z",
             "url": f"https://dailyyield.blogspot.com/2026/10/guide-{i}.html"}
            for i in range(4)
        ]
        article, selected, count, mode = news.build_fitted_news_article(
            "global", candidates, [], self.day, self.start, self.end,
            {}, [], related, HERO,
        )
        self.assertGreater(len(selected), 15)
        self.assertIn(f"{len(selected)} headlines", mode)
        self.assertGreaterEqual(count, 3800)
        self.assertLessEqual(count, 4100)
        self.assertEqual(article["html"].count('class="fbk-description"'), len(selected))

    def test_oversized_draft_is_sentence_polished_without_touching_source_summary(self):
        items = self.items(20)
        with patch.object(news, "daily_hero", return_value=HERO):
            article = news.build_article(
                "global", items, [], self.day, self.start, self.end,
                {}, [], hero_override=HERO, context_target=233,
            )
        article = news.finish_news_article(article, [])
        protected = news.source_summary(items[0])
        self.assertGreater(news.editorial_word_count(article["html"]), 4100)
        polished, count = news.reduce_news_context(article["html"])
        self.assertGreaterEqual(count, 3800)
        self.assertLessEqual(count, 4100)
        self.assertIn(protected, polished)
        self.assertIn("not an observed future result", polished)


if __name__ == "__main__":
    unittest.main()
