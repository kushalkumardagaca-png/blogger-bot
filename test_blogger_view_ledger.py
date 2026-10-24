#!/usr/bin/env python3
"""The two counters must be reported together, honestly, and neither one may be silenced."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import blogger_view_ledger as ledger

BLOGGER_REPLY = {"kind": "blogger#page_views", "counts": [
    {"timeRange": "ALL_TIME", "count": "20966"},
    {"timeRange": "THIRTY_DAYS", "count": "17546"},
    {"timeRange": "SEVEN_DAYS", "count": "2200"},
]}
LADDER = {"measured": {"asOf": "2026-10-23", "viewsPerDay": 16.4,
                       "viewsBasis": "GA4_PAGEVIEWS_7_DAY_AVERAGE", "ga4Status": "MEASURED",
                       "dailyReaders": 12}}
BASELINE = {"syntheticViews": 0, "mode": "AUTHENTICATED_SEARCH_CONSOLE_ZERO_PUBLIC_VIEWS"}


def report_with(tmp: Path, read=lambda path: BLOGGER_REPLY):
    (tmp / "GROWTH_LADDER.json").write_text(json.dumps(LADDER))
    (tmp / "AUDIENCE_GROWTH_BASELINE.json").write_text(json.dumps(BASELINE))
    old_ladder, old_base = ledger.LADDER, ledger.BASELINE
    ledger.LADDER, ledger.BASELINE = tmp / "GROWTH_LADDER.json", tmp / "AUDIENCE_GROWTH_BASELINE.json"
    try:
        return ledger.build(read=read, today=datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc))
    finally:
        ledger.LADDER, ledger.BASELINE = old_ladder, old_base


class BloggerCounter(unittest.TestCase):
    def test_blogger_ranges_are_read_in_bloggers_own_words(self):
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d))
        b = report["bloggerCounter"]
        self.assertEqual("MEASURED", b["status"])
        self.assertEqual(20966, b["allTime"])
        self.assertEqual(17546, b["last30Days"])
        self.assertEqual(314.3, b["perDayFrom7DayWindow"])

    def test_a_failed_read_stays_an_honest_gap(self):
        def broken(path):
            raise RuntimeError("Blogger GET /pageviews returned HTTP 403")
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d), read=broken)
        b = report["bloggerCounter"]
        self.assertEqual("NOT_MEASURED", b["status"])
        self.assertIsNone(b.get("allTime"))
        self.assertIn("403", b["reason"])
        self.assertIsNone(report["verdict"]["bloggerToHumanRatio"])
        self.assertIn("cannot be compared", report["verdict"]["plainEnglish"])

    def test_missing_credentials_are_reported_not_raised(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            for name in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN"):
                os.environ.pop(name, None)
            result = ledger.blogger_pageviews(read=None)
        self.assertEqual("NOT_MEASURED", result["status"])
        self.assertIn("credentials", result["reason"])

class TwoInstruments(unittest.TestCase):
    def test_the_human_number_is_carried_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d))
        h = report["humanCount"]
        self.assertEqual(16.4, h["viewsPerDay"])
        self.assertEqual("GA4_PAGEVIEWS_7_DAY_AVERAGE", h["basis"])
        self.assertEqual(12, h["dailyReaders"])

    def test_bloggers_bigger_number_never_becomes_the_projection_basis(self):
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d))
        self.assertIs(False, report["verdict"]["usedForGrowthProjection"])
        self.assertIn("never replaces the first", report["verdict"]["guard"])
        self.assertNotEqual(314.3, report["humanCount"]["viewsPerDay"])

    def test_a_ratio_of_this_size_is_named_as_machines(self):
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d))
        v = report["verdict"]
        self.assertEqual(19.2, v["bloggerToHumanRatio"])
        self.assertTrue("5 to 10 times" in v["plainEnglish"] or "machines" in v["plainEnglish"])
        self.assertIn("runs no JavaScript", v["revenueEffect"])

    def test_an_ordinary_ratio_is_not_called_out_as_a_problem(self):
        reply = {"counts": [{"timeRange": "SEVEN_DAYS", "count": "800"}]}
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d), read=lambda path: reply)
        self.assertEqual(7.0, report["verdict"]["bloggerToHumanRatio"])  # 800/7 = 114.3, 114.3/16.4
        self.assertIn("ordinary range", report["verdict"]["plainEnglish"])

    def test_our_own_tooling_is_recorded_as_measured_not_assumed(self):
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d))
        self.assertEqual(0, report["automationSelfRequests"]["syntheticViews"])
        self.assertIn("AUDIENCE_GROWTH_BASELINE.json", report["automationSelfRequests"]["source"])


class NoSyntheticViews(unittest.TestCase):
    def test_the_ledger_never_requests_a_public_page(self):
        source = Path("blogger_view_ledger.py").read_text()
        for forbidden in ("urlopen", "requests.get", "httpx", "dailyyield.blogspot.com"):
            self.assertNotIn(forbidden, source, f"a view-counting script must not contain {forbidden}")

    def test_both_counters_appear_in_the_owner_readable_page(self):
        with tempfile.TemporaryDirectory() as d:
            report = report_with(Path(d))
        md = ledger.markdown(report)
        for needle in ("Blogger's own Stats", "Google Analytics", "Which one is real", "Money:",
                       "Our own tooling added", "20,966", "16.4"):
            self.assertIn(needle, md)


if __name__ == "__main__":
    unittest.main()
