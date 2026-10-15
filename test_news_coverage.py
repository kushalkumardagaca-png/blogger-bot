#!/usr/bin/env python3
"""Coverage and reader-priority rules for every News edition.

These tests protect the editorial instruction of 15 October 2026: a country
edition must carry at least two stories from every sub-section, a sub-section
edition must carry at least two from every country, neither may exceed ten from a
single bucket, the Global edition stays an editor's pick, and every edition is
ordered by search demand, story size and audience appetite.
"""
from __future__ import annotations

import unittest

import news_coverage as nc

DEMAND = {"date": "2026-10-15", "source": "test", "terms": ["sensex today", "oil price"],
          "lexicon": list(nc.DEMAND_LEXICON)}


def item(title, topic, country, prio=2, **extra):
    row = {"title": title, "topic": topic, "country": country, "region": country,
           "agency": extra.pop("agency", "agency-" + country), "prio": prio,
           "date": extra.pop("date", None), "url": extra.pop("url", "https://example.com/" + title.replace(" ", "-"))}
    row.update(extra)
    return row


def country_desk_pool(padding=9):
    rows = []
    for topic in nc.DESK_TOPICS:
        for index in range(padding):
            rows.append(item(f"India {topic} story {index}", topic, "india", prio=1 if index == 0 else 3))
    return rows


def topic_desk_pool(padding=3):
    rows = []
    for country in nc.COUNTRIES:
        for index in range(padding):
            rows.append(item(f"{country} markets story {index}", "markets", country, prio=2 if index == 0 else 4))
    return rows


class CountryDeskTests(unittest.TestCase):
    def test_every_subsection_gets_at_least_two_stories(self):
        chosen, report = nc.apply_quotas(country_desk_pool(), "india", DEMAND)
        for topic in nc.DESK_TOPICS:
            self.assertGreaterEqual(report["counts"].get(topic, 0), nc.MIN_PER_BUCKET, topic)
        self.assertEqual(report["buckets_short_of_minimum"], {})

    def test_no_subsection_exceeds_ten(self):
        chosen, report = nc.apply_quotas(country_desk_pool(padding=25), "india", DEMAND)
        for topic, count in report["counts"].items():
            self.assertLessEqual(count, nc.MAX_PER_BUCKET, topic)

    def test_thin_pool_still_publishes_what_exists(self):
        rows = [item("Only markets story", "markets", "india"), item("Second markets story", "markets", "india")]
        chosen, report = nc.apply_quotas(rows, "india", DEMAND)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(report["buckets_short_of_minimum"], {})
        self.assertIn("economy", report["buckets_never_covered"])

    def test_shortfall_is_recorded_when_a_bucket_has_only_one(self):
        rows = [row for row in country_desk_pool(padding=2) if row["topic"] != "banking"]
        rows.append(item("A single banking story", "banking", "india"))
        chosen, report = nc.apply_quotas(rows, "india", DEMAND)
        self.assertEqual(report["buckets_short_of_minimum"].get("banking"), 1)


class TopicDeskTests(unittest.TestCase):
    def test_every_country_gets_at_least_two_stories(self):
        chosen, report = nc.apply_quotas(topic_desk_pool(), "markets", DEMAND)
        for country in nc.COUNTRIES:
            self.assertGreaterEqual(report["counts"].get(country, 0), nc.MIN_PER_BUCKET, country)

    def test_no_country_exceeds_ten(self):
        chosen, report = nc.apply_quotas(topic_desk_pool(padding=14), "markets", DEMAND)
        for country, count in report["counts"].items():
            self.assertLessEqual(count, nc.MAX_PER_BUCKET, country)

    def test_edition_never_exceeds_the_pipeline_cap(self):
        chosen, _ = nc.apply_quotas(topic_desk_pool(padding=20), "markets", DEMAND)
        self.assertLessEqual(len(chosen), nc.EDITION_CAP)


class GlobalDeskTests(unittest.TestCase):
    def test_global_is_an_editor_pick_without_country_quotas(self):
        rows = [item(f"Big global story {i}", "economy", "us" if i % 2 else "germany") for i in range(30)]
        chosen, report = nc.apply_quotas(rows, "global", DEMAND)
        self.assertEqual(report["mode"], "editor-pick")
        self.assertLessEqual(len(chosen), nc.EDITION_CAP)
        self.assertNotIn("minimum_per_bucket", report)

    def test_global_can_skip_a_country_entirely(self):
        rows = [item(f"United States story {i}", "markets", "us") for i in range(12)]
        chosen, _ = nc.apply_quotas(rows, "global", DEMAND)
        self.assertTrue(chosen)
        self.assertTrue(all(row["country"] == "us" for row in chosen))


class OrderingTests(unittest.TestCase):
    def test_demand_terms_lift_a_story(self):
        quiet = item("Regional output report published", "economy", "germany")
        demanded = item("Sensex today: oil price surge lifts Indian shares", "economy", "india")
        ordered = nc.rank([quiet, demanded], DEMAND)
        self.assertEqual(ordered[0]["title"], demanded["title"])

    def test_bigger_story_ranks_above_a_routine_one(self):
        routine = item("Bank publishes quarterly circular", "banking", "india")
        big = item("Central bank cuts rates by 50 bps as inflation plunges to a record low", "banking", "india")
        ordered = nc.rank([routine, big], DEMAND)
        self.assertEqual(ordered[0]["title"], big["title"])

    def test_country_desk_sections_run_strongest_first(self):
        rows = [item("Routine markets note", "markets", "india", prio=4),
                item("Sensex today plunges 2% after record oil price surge", "markets", "india", prio=1),
                item("Government publishes annual jobs bulletin", "economy", "india", prio=3)]
        ordered = nc.order_for_reader(rows, "india", DEMAND)
        topics = [row["topic"] for row in ordered]
        self.assertEqual(topics[0], "markets")
        self.assertEqual(ordered[0]["title"][:5], "Sense")

    def test_enforce_returns_order_and_report(self):
        ordered, report = nc.enforce(country_desk_pool(), "india", DEMAND)
        self.assertTrue(ordered)
        self.assertEqual(report["desk"], "india")
        self.assertEqual(report["demand_source"], "test")
        self.assertTrue(report["lead_headline"])

    def test_demand_falls_back_to_the_lexicon_when_the_feed_is_missing(self):
        original = nc.fetch_trends
        nc.fetch_trends = lambda *a, **k: []
        try:
            document = nc.search_demand(refresh=True)
            self.assertEqual(document["source"], "finance-demand-lexicon")
            score = nc.demand_score(item("Oil price rises as inflation cools", "markets", "us"), document)
            self.assertGreater(score, 0)
        finally:
            nc.fetch_trends = original


if __name__ == "__main__":
    unittest.main()
