#!/usr/bin/env python3
"""The capacity gate has to be able to say "stop", and it has to say it from evidence.

These cases exist because the property's real numbers are uncomfortable: one indexed URL out
of five hundred and fifty one submitted. The automation that reacts to that must not be able
to invent growth, must not punish the site when a measurement is simply missing, and must not
keep announcing duplicate-title and utility pages that spend the crawl budget articles need.
"""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import indexing_capacity_gate as gate


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.paths = {}
        for name in ("STATUS", "BASELINE", "INDEXNOW", "DEMAND", "OUT", "MD", "PRIORITY"):
            self.paths[name] = getattr(gate, name)
            setattr(gate, name, self.tmp / self.paths[name].name)
        (self.tmp / "SEARCH_DEMAND_TRENDS.json").write_text(json.dumps(
            {"lexicon": ["inflation", "rate cut", "gold price"]}))

    def tearDown(self):
        for name, value in self.paths.items():
            setattr(gate, name, value)

    def write(self, name, payload):
        (self.tmp / name).write_text(json.dumps(payload))

    def run_gate(self, today="2026-10-20"):
        with mock.patch("sys.argv", ["indexing_capacity_gate.py", "--today", today, "--quiet"]):
            self.assertEqual(gate.main(), 0)
        return json.loads((self.tmp / "INDEXING_CAPACITY.json").read_text())


class Decisions(Harness):
    def test_no_measurement_is_reported_as_unknown_and_changes_nothing(self):
        report = self.run_gate()
        self.assertEqual(report["decision"], "UNKNOWN")
        self.assertIsNone(report["masterArticlesPerDay"])
        self.assertIn("no Search Console index measurement", " ".join(report["why"]))

    def test_a_stuck_index_contracts_and_names_the_real_reason(self):
        self.write("INDEX_STATUS_REPORT.json", {"indexed": 1, "urls": 551,
                                                "byCoverageState": [["Discovered - currently not indexed", 360]]})
        self.write("AUDIENCE_GROWTH_BASELINE.json",
                   {"searchAcquisition": {"last28Days": {"clicks": 1, "impressions": 2}}})
        report = self.run_gate()
        self.assertEqual(report["decision"], "CONTRACT")
        self.assertEqual(report["measured"]["indexed"], 1)
        self.assertEqual(report["measured"]["submitted"], 551)
        self.assertEqual(report["masterArticlesPerDay"], 2)
        self.assertEqual(report["newsWiresPerDay"], 1)
        self.assertIn("not being trusted", " ".join(report["why"]))

    def test_a_growing_index_is_allowed_to_expand(self):
        self.write("INDEX_STATUS_REPORT.json", {"indexed": 340, "urls": 600})
        (self.tmp / "INDEXING_CAPACITY.json").write_text(json.dumps(
            {"history": [{"day": (dt.date(2026, 10, 20) - dt.timedelta(days=d)).isoformat(),
                          "indexed": 300 + d * 8} for d in range(1, 8)]}))
        report = self.run_gate()
        self.assertEqual(report["decision"], "EXPAND")
        self.assertGreater(report["masterArticlesPerDay"], 5)

    def test_a_moving_but_small_index_holds_instead_of_expanding(self):
        self.write("INDEX_STATUS_REPORT.json", {"indexed": 40, "urls": 560})
        report = self.run_gate()
        self.assertEqual(report["decision"], "HOLD")


class AnnouncementPriority(Harness):
    def setUp(self):
        super().setUp()
        self.write("INDEX_STATUS_REPORT.json", {"indexed": 1, "urls": 551})
        pending = [
            "https://dailyyield.blogspot.com/2026/10/india-finance-news-2026-10-20.html",
            "https://dailyyield.blogspot.com/2026/10/how-rate-cuts-move-gold-price.html",
            "https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01450325346.html",
            "https://dailyyield.blogspot.com/p/terms-and-conditions.html",
            "https://dailyyield.blogspot.com/?m=1",
        ]
        self.write("INDEXNOW_STATE.json", {"submitted": {}, "pending": pending})

    def test_duplicate_and_utility_urls_are_held_back_not_announced(self):
        self.run_gate()
        priority = json.loads((self.tmp / "INDEX_PRIORITY.json").read_text())
        announced = " ".join(priority["announce"])
        self.assertNotIn("terms-and-conditions", announced)
        self.assertNotIn("_01450325346", announced)
        self.assertNotIn("?m=1", announced)
        self.assertEqual(priority["suppressCount"], 3)

    def test_fresh_news_and_a_demand_matching_guide_lead_the_list(self):
        self.run_gate()
        priority = json.loads((self.tmp / "INDEX_PRIORITY.json").read_text())
        self.assertEqual(len(priority["announce"]), 2, "only the two URLs worth the budget")
        self.assertIn("india-finance-news", priority["announce"][0])
        self.assertIn("how-rate-cuts-move-gold-price", priority["announce"][1])

    def test_a_queue_that_has_never_been_submitted_is_called_out(self):
        report = self.run_gate()
        self.assertTrue(report["announcementQueue"]["indexnowLooksBlocked"],
                        "URLs queued with nothing ever accepted is a broken key, not a full queue")
        report2 = self.run_gate()
        self.assertIn("submittedEver", report2["announcementQueue"])


    def test_a_daily_template_is_not_announced_more_than_twice(self):
        pending = [f"https://dailyyield.blogspot.com/2026/10/companies-ipos-deals-2026-10-{day:02d}.html"
                   for day in range(1, 13)]
        self.write("INDEXNOW_STATE.json", {"submitted": {}, "pending": pending})
        self.run_gate()
        priority = json.loads((self.tmp / "INDEX_PRIORITY.json").read_text())
        self.assertEqual(len(priority["announce"]), 2, "twelve copies of one template must not take twelve slots")
        self.assertEqual(priority["suppressCount"], 10)


class Evidence(Harness):
    def test_missing_evidence_files_are_listed_as_missing(self):
        report = self.run_gate()
        self.assertIs(report["evidenceFiles"]["INDEX_STATUS_REPORT.json"], False)
        self.assertIs(report["evidenceFiles"]["SEARCH_DEMAND_TRENDS.json"], True)

    def test_the_human_report_is_written_beside_the_machine_one(self):
        self.write("INDEX_STATUS_REPORT.json", {"indexed": 1, "urls": 551})
        self.run_gate()
        text = (self.tmp / "INDEXING_CAPACITY.md").read_text()
        self.assertIn("CONTRACT", text)
        self.assertIn("1 of 551", text.replace("**", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
