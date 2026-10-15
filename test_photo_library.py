#!/usr/bin/env python3
"""Rules for the prepared photo pools.

The pools exist so a publication never stops because a photograph could not be
found in time, while keeping every rule the site already had: only clearly
licensed photographs, no children, no charts or logos, landscape frames, and no
photograph ever used twice. These tests run offline with fixture candidates.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import photo_library as pl


def candidate(source_id="commons:1", licence="CC BY 4.0", title="Central bank building in the city centre",
              width=2400, height=1350, url="https://example.com/a.jpg"):
    return {
        "source_id": source_id, "provider": "Wikimedia Commons", "title": title, "description": "",
        "creator": "A Photographer", "licence": licence,
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_page": "https://commons.wikimedia.org/wiki/File:x", "download_url": url,
        "original_url": url, "width": width, "height": height, "query": "test",
    }


class LicenceTests(unittest.TestCase):
    def test_free_licences_pass(self):
        for licence in ("CC BY 4.0", "CC BY 2.0", "CC0", "Public domain", "cc by 3.0"):
            self.assertTrue(pl.licence_ok(candidate(licence=licence)), licence)

    def test_restricted_licences_fail(self):
        for licence in ("CC BY-NC 4.0", "CC BY-ND 2.0", "CC BY-SA 4.0", "GFDL", "All rights reserved", "Unknown"):
            self.assertFalse(pl.licence_ok(candidate(licence=licence)), licence)

    def test_subject_filters(self):
        self.assertFalse(pl.subject_ok(candidate(title="School children at a desk")))
        self.assertFalse(pl.subject_ok(candidate(title="Stock market chart and diagram")))
        self.assertFalse(pl.subject_ok(candidate(title="Company logo on a wall")))
        self.assertFalse(pl.subject_ok(candidate(width=800, height=500)))
        self.assertFalse(pl.subject_ok(candidate(width=1200, height=1600)))
        self.assertTrue(pl.subject_ok(candidate()))

    def test_match_score_needs_relevance(self):
        wanted = pl.terms("central bank interest rate decision")
        self.assertGreater(pl.match_score(wanted, candidate()), 0)
        unrelated = candidate(title="Mountain lake at sunrise")
        self.assertEqual(pl.match_score(wanted, unrelated), 0)


class PoolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._master, self._news = pl.MASTER_DIR, pl.NEWS_DIR
        pl.MASTER_DIR = base / "master"
        pl.NEWS_DIR = base / "news"
        pl.MASTER_DIR.mkdir(parents=True)
        pl.NEWS_DIR.mkdir(parents=True)
        # fixture source replaces the network entirely
        self._gather = pl.gather
        pool = [candidate(f"commons:{i}", title=f"Business meeting office table number {i}",
                          url=f"https://example.com/{i}.jpg") for i in range(12)]
        self.calls = {"n": 0}

        def fake_gather(queries, wanted, want, exclude):
            if want <= 0:
                return []          # mirrors the real gather() guard
            start = self.calls["n"] * max(1, want)
            self.calls["n"] += 1
            rows = [dict(x) for x in pool if str(x["source_id"]) not in {str(e) for e in exclude}]
            return rows[start:start + max(1, want)]

        pl.gather = fake_gather

    def tearDown(self):
        pl.MASTER_DIR, pl.NEWS_DIR = self._master, self._news
        pl.gather = self._gather
        self._tmp.cleanup()

    def test_master_pool_is_built_to_target(self):
        pool = pl.ensure_master_pool("topic-1", "How to read inflation signals", ["office workers computers"])
        self.assertEqual(len(pool["entries"]), pl.MASTER_TARGET)

    def test_reserved_photographs_are_unique_and_marked_taken(self):
        first = pl.reserve_master_entry("topic-1", "How to read inflation signals", None, 1)
        second = pl.reserve_master_entry("topic-1", "How to read inflation signals", None, 2)
        third = pl.reserve_master_entry("topic-1", "How to read inflation signals", None, 3)
        self.assertNotEqual(first["source_id"], second["source_id"])
        self.assertNotEqual(second["source_id"], third["source_id"])
        path = pl.MASTER_DIR / "topic-1.json"
        pool = json.loads(path.read_text())
        self.assertEqual(len(pool["taken"]), 3)
        self.assertEqual(pool["taken"][0]["placement"], 1)

    def test_pool_runs_out_cleanly(self):
        pool = pl.ensure_master_pool("topic-2", "Small business cash flow", None)
        size = len(pool["entries"])
        self.assertGreaterEqual(size, pl.MASTER_TARGET)
        taken = 0
        while pl.reserve_master_entry("topic-2", "Small business cash flow", None, taken + 1) is not None:
            taken += 1
            self.assertLessEqual(taken, size)
        self.assertEqual(taken, size)
        self.assertIsNone(pl.reserve_master_entry("topic-2", "Small business cash flow", None, 99))

    def test_news_rotation_advances_and_avoids_recent_urls(self):
        pool = pl.build_news_pool("india", target=4)
        self.assertTrue(pool["entries"])
        first = pl.next_news_photo("india")
        second = pl.next_news_photo("india", avoid={first["download_url"]})
        self.assertNotEqual(first["source_id"], second["source_id"])
        third = pl.next_news_photo("india", avoid={first["download_url"], second["download_url"]})
        self.assertNotIn(third["source_id"], {first["source_id"], second["source_id"]})

    def test_every_entry_carries_its_licence_record(self):
        pool = pl.build_news_pool("markets", target=3)
        for entry in pool["entries"]:
            self.assertTrue(entry["licence"])
            self.assertTrue(entry["licence_url"] or "public domain" in entry["licence"].casefold())
            self.assertTrue(entry["source_page"])
            self.assertTrue(entry["creator"])

    def test_desk_focus_queries_exist_for_every_news_desk(self):
        desks = ("global", "americas", "china", "asia-pacific", "india", "russia", "europe",
                 "markets", "economy", "banking", "companies")
        for desk in desks:
            self.assertTrue(pl.DESK_FOCUS.get(desk) or desk in ("global",), desk)

    def test_status_reports_both_pools(self):
        pl.ensure_master_pool("topic-3", "Credit without interest", None)
        pl.build_news_pool("europe", target=3)
        document = pl.status()
        self.assertGreaterEqual(document["master_pools"], 1)
        self.assertGreaterEqual(document["news_pools"], 1)
        self.assertGreater(document["master_photos"], 0)


if __name__ == "__main__":
    unittest.main()
