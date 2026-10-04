import unittest
from datetime import date
from unittest.mock import patch

import audience_growth_baseline as baseline


def row(key, clicks, impressions, position):
    return {"keys": [key], "clicks": clicks, "impressions": impressions, "ctr": clicks / impressions if impressions else 0, "position": position}


class AudienceGrowthBaselineTests(unittest.TestCase):
    def test_aggregate_uses_impression_weighted_position(self):
        result = baseline.aggregate([row("a", 2, 10, 2), row("b", 3, 30, 6)])
        self.assertEqual(result, {"clicks": 5, "impressions": 40, "ctr": 0.125, "averagePosition": 5.0})

    def test_report_never_invents_readers_from_search_clicks(self):
        daily = [row("2026-10-01", 4, 100, 8), row("2026-10-02", 6, 150, 7)]
        pages = [row("https://dailyyield.blogspot.com/example", 10, 250, 7.4)]
        countries = [row("ind", 7, 170, 7)]
        devices = [row("MOBILE", 8, 200, 7.2)]
        with patch.object(baseline, "query", side_effect=[daily, pages, countries, devices]):
            report = baseline.build_report("token", date(2026, 10, 4))
        self.assertEqual(report["syntheticViews"], 0)
        self.assertEqual(report["availableThrough"], "2026-10-02")
        self.assertEqual(report["searchAcquisition"]["last28Days"]["clicks"], 10)
        self.assertIsNone(report["readerMeasurement"]["dau"])
        self.assertEqual(report["readerMeasurement"]["status"], "NOT_AVAILABLE_FROM_SEARCH_CONSOLE")

    def test_ranked_rows_are_sorted_by_real_clicks_then_impressions(self):
        rows = [row("b", 1, 500, 5), row("a", 3, 20, 2), row("c", 1, 700, 6)]
        self.assertEqual([item["page"] for item in baseline.ranked(rows, "page")], ["a", "c", "b"])


if __name__ == "__main__":
    unittest.main()
