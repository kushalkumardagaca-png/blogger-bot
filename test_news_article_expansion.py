import datetime as dt
import re
import unittest

import news_pipeline as news

HERO = {"url": "https://example.com/hero.jpg", "alt": "Financial district",
        "credit": "Test photograph", "source": "test"}
RELATED = [
    {"id": f"r{i}", "title": f"Practical finance guide {i}", "content": "",
     "labels": ["Articles"], "published": "2026-10-01T00:00:00Z",
     "url": f"https://dailyyield.blogspot.com/2026/10/guide-{i}.html"}
    for i in range(4)
]

class NewsArticleExpansionTests(unittest.TestCase):
    def setUp(self):
        self.day = dt.date(2026, 10, 9)
        self.end = dt.datetime(2026, 10, 9, 12, tzinfo=news.IST)
        self.start = self.end - dt.timedelta(days=1)

    def items(self, count=34, topic=None):
        topics = [key for key, _ in news.SECTION_ORDER]
        countries = ["us", "canada", "mexico", "brazil", "india", "china", "russia",
                     "uk", "germany", "france", "italy", "spain", "japan", "south-korea", "australia"]
        subjects = ["market", "inflation", "banking", "earnings", "crypto", "trade",
                    "mortgage", "IPO", "gold", "jobs", "fintech", "merger"]
        description = ("The publisher reports current evidence, expectations, principal risks and "
                       "possible consequences for markets, companies, policy and households today.")
        out = []
        for i in range(count):
            country = countries[i % len(countries)]
            chosen_topic = topic or topics[i % len(topics)]
            out.append({
                "title": f"{subjects[i % len(subjects)].title()} outlook and financial consequences update {i}",
                "url": f"https://example.com/source-{i}", "desc": description,
                "date": self.day, "agency": f"Credible Source {i}", "prio": 2,
                "media": True, "topic": chosen_topic, "country": country,
                "region": news.COUNTRY_TO_REGION[country],
            })
        return out

    def fitted(self, desk="global", count=34, topic=None):
        return news.build_fitted_news_article(
            desk, self.items(count, topic), [], self.day, self.start, self.end,
            {}, [], RELATED, HERO,
        )

    def test_geographic_article_uses_24_to_28_headlines_and_strict_range(self):
        article, selected, count, mode = self.fitted("global", 28)
        self.assertGreaterEqual(len(selected), 24)
        self.assertLessEqual(len(selected), 28)
        self.assertGreaterEqual(count, 3800)
        self.assertLessEqual(count, 4100)
        self.assertIn(f"{len(selected)} headlines", mode)
        self.assertEqual(article["html"].count('class="fbk-description"'), len(selected))

    def test_geographic_article_contains_all_four_subject_sections(self):
        article, _, _, _ = self.fitted("india", 28)
        for _key, label in news.SECTION_ORDER:
            self.assertIn(label, article["html"])
        self.assertEqual(article["labels"][0:3], ["News", "Geographic Edition", "India Finance News"])
        for label in news.TOPIC_LABELS.values():
            self.assertIn(label, article["labels"])
        self.assertIn("Country · India", article["labels"])

    def test_regional_article_carries_each_constituent_country_label(self):
        article, _, _, _ = self.fitted("americas", 28)
        for country in ("United States", "Canada", "Mexico", "Brazil"):
            self.assertIn("Country · " + country, article["labels"])

    def test_category_article_uses_geographic_sections_and_canonical_labels(self):
        article, selected, count, _ = self.fitted("markets", 34, "markets")
        self.assertGreaterEqual(len(selected), 30)
        self.assertLessEqual(len(selected), 34)
        self.assertGreaterEqual(count, 3800)
        self.assertLessEqual(count, 4100)
        self.assertEqual(article["labels"][0:3], ["News", "Category Edition", "Markets, Crypto & Commodities"])
        for label in news.COUNTRY_LABELS.values():
            self.assertIn(label, article["labels"])
        for place in ("India", "China", "Russia", "Americas", "Europe", "Asia-Pacific"):
            self.assertIn(place, article["html"])

    def test_every_headline_has_immediate_concise_source_description(self):
        article, selected, _, _ = self.fitted("global", 28)
        blocks = re.findall(r'<div class="fbk-item[^>]*>(.*?)</div>', article["html"], re.S)
        self.assertEqual(len(blocks), len(selected))
        for block in blocks:
            self.assertRegex(block, r'<h3>.*?</h3>\s*<p class="fbk-description"><strong>.*?</strong>.+?</p>')

    def test_forecasts_are_labelled_and_not_asserted_as_fact(self):
        html = news.compose_item(self.items(1)[0], self.end)
        self.assertIn("Reported outlook", html)
        self.assertIn("not an observed future result", html)
        self.assertIn("Credible Source 0", html)

    def test_opening_lede_removed_and_method_is_guidance_box(self):
        article, _, _, _ = self.fitted("global", 28)
        html = article["html"]
        self.assertNotIn('class="fbk-lede"', html)
        self.assertIn('class="fbk-method"', html)
        self.assertIn("Reader guidance · not a news headline", html)

    def test_source_integrity_gate_rejects_headline_only_items(self):
        item = self.items(1)[0]
        self.assertTrue(news.item_source_is_usable(item))
        item["desc"] = "headline only"
        self.assertFalse(news.item_source_is_usable(item))

    def test_discovery_includes_forecasts_and_expert_expectations(self):
        names = [source[0] for source in news.discovery_sources("india")]
        self.assertTrue(any("Forecast" in name for name in names))
        self.assertTrue(any("Analyst Expectations" in name for name in names))

    def test_oversized_draft_is_sentence_polished_without_touching_source_summary(self):
        items = self.items(28)
        article = news.build_article("global", items, [], self.day, self.start, self.end,
                                     {}, [], hero_override=HERO, context_target=180,
                                     summary_target=60)
        article = news.finish_news_article(article, RELATED)
        protected = news.source_summary(items[0], maximum=60)
        self.assertGreater(news.editorial_word_count(article["html"]), 4100)
        polished, count = news.reduce_news_context(article["html"])
        self.assertGreaterEqual(count, 3800)
        self.assertLessEqual(count, 4100)
        self.assertIn(protected, polished)
        self.assertIn("not an observed future result", polished)

if __name__ == "__main__":
    unittest.main()
