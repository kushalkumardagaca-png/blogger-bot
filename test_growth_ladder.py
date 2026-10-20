#!/usr/bin/env python3
"""A target without a measured series beside it is a wish, so the ladder is tested like an instrument.

The rules these cases protect: a rung whose date has not arrived may not claim a verdict, a
missing measurement must read as UNKNOWN, and a projection needs three real points before it is
allowed to name a date.
"""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import growth_ladder as ladder


def point(day: str, indexed: int, views) -> dict:
    return {"date": day, "indexedPages": indexed, "viewsPerDay": views, "impressions28d": 2,
            "clicks28d": 1, "submittedPages": 551, "measurableFollowers": 12, "evidenceComplete": True}


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = (ladder.ROOT, ladder.OUT, ladder.MD, ladder.HISTORY)
        ladder.ROOT, ladder.OUT, ladder.MD = self.tmp, self.tmp / "l.json", self.tmp / "l.md"
        ladder.HISTORY = self.tmp / "GROWTH_LADDER_HISTORY.json"

    def tearDown(self):
        ladder.ROOT, ladder.OUT, ladder.MD, ladder.HISTORY = self.saved

    def seed(self, points):
        ladder.HISTORY.write_text(json.dumps({"updated": points[-1]["date"], "points": points}),
                                  encoding="utf-8")

    def run_with(self, today, *extra):
        fixture = self.tmp / "today.json"
        fixture.write_text(json.dumps(today), encoding="utf-8")
        with mock.patch("sys.argv", ["growth_ladder.py", "--fixture", str(fixture), *extra]):
            self.assertEqual(ladder.main(), 0)
        return json.loads(ladder.OUT.read_text(encoding="utf-8"))


class Rungs(Harness):
    def test_a_rung_that_has_not_arrived_yet_cannot_claim_a_verdict(self):
        report = self.run_with({"asOf": "2026-10-19", "indexedPages": 1, "submittedPages": 551,
                                "impressions28d": 2, "clicks28d": 1, "viewsPerDay": 0.036,
                                "measurableFollowers": None, "gateVerdict": "CONTRACT",
                                "evidenceComplete": True})
        verdicts = {rung["verdict"] for rung in report["ladder"]}
        self.assertEqual(verdicts, {"FUTURE"}, "no rung may be judged before its date")
        self.assertIsNone(report["ladder"][0]["measuredIndexedPages"])

    def test_a_past_rung_is_judged_against_the_measurement_it_has(self):
        self.seed([point("2026-10-13", 2, 0.1), point("2026-10-19", 2, 0.1)])
        report = self.run_with({"asOf": "2026-10-19", "indexedPages": 2, "submittedPages": 551,
                                "impressions28d": 2, "clicks28d": 1, "viewsPerDay": 0.1,
                                "measurableFollowers": 12, "gateVerdict": "CONTRACT",
                                "evidenceComplete": True})
        first = report["ladder"][0]
        self.assertEqual(first["measuredIndexedPages"], 2)
        self.assertEqual(first["verdict"], "BEHIND", "2 indexed pages is not the first rung")
        # a past rung that was actually cleared reads ON TRACK; the ladder is interpolated from
        # the measured starting point, so clearing it means the growth happened on time
        self.seed([point("2026-10-13", 200, 40), point("2026-10-19", 200, 40)])
        report = self.run_with({"asOf": "2026-10-19", "indexedPages": 200, "submittedPages": 551,
                                "impressions28d": 400, "clicks28d": 20, "viewsPerDay": 40,
                                "measurableFollowers": 12, "gateVerdict": "EXPAND",
                                "evidenceComplete": True})
        self.assertEqual(report["ladder"][0]["verdict"], "ON TRACK")

    def test_the_last_rung_lands_on_the_deadline_and_not_past_it(self):
        report = self.run_with({"asOf": "2026-10-19", "indexedPages": 1, "submittedPages": 551,
                                "impressions28d": 2, "clicks28d": 1, "viewsPerDay": 0.036,
                                "measurableFollowers": None, "gateVerdict": "CONTRACT",
                                "evidenceComplete": True})
        self.assertEqual(report["ladder"][-1]["by"], ladder.DEADLINE.isoformat())
        self.assertEqual(report["ladder"][-1]["indexedPages"], [150, 400])
        self.assertEqual(report["commitment"]["viewsPerDay"], [150, 1500])


class Arithmetic(Harness):
    def test_the_50k_question_is_answered_with_division_not_adjectives(self):
        report = self.run_with({"asOf": "2026-10-19", "indexedPages": 1, "submittedPages": 551,
                                "impressions28d": 28, "clicks28d": 1, "viewsPerDay": 0.036,
                                "measurableFollowers": 12, "gateVerdict": "CONTRACT",
                                "declaredTarget": 10_000_000, "declaredDeadline": "2027-09-30",
                                "evidenceComplete": True})
        numbers = report["ownerAsk"]["arithmetic"]
        self.assertEqual(numbers["yieldPerIndexedPagePerDay"], 1.0, "28 impressions / 28 days / 1 page")
        self.assertEqual(numbers["impressionsNeededPerDayForAsk"]["range"], [1_666_667, 2_500_000])
        self.assertEqual(numbers["indexedPagesNeededForAskAtTodayYield"], 1_666_667)
        self.assertEqual(numbers["yieldMultipleNeededAtTopOfSubTarget"], 4167.0)
        self.assertGreater(numbers["askVsDeclaredPlanMultiple"], 1.0,
                           "the ask has to be compared with the plan the repo already declared")
        self.assertIs(report["ownerAsk"]["reachable"], False)

    def test_a_missing_measurement_is_left_missing(self):
        report = self.run_with({"asOf": "", "indexedPages": None, "submittedPages": None,
                                "impressions28d": None, "clicks28d": None, "viewsPerDay": None,
                                "measurableFollowers": None, "gateVerdict": None,
                                "evidenceComplete": False})
        self.assertIsNone(report["ownerAsk"]["reachable"], "no evidence, no verdict")
        self.assertIsNone(report["ownerAsk"]["arithmetic"]["yieldPerIndexedPagePerDay"])
        self.assertIn("not measured", ladder.MD.read_text(encoding="utf-8"))


class Projection(Harness):
    def test_a_date_is_only_named_once_three_points_exist(self):
        self.seed([point("2026-10-13", 5, 10), point("2026-10-16", 20, 20)])
        report = self.run_with({"asOf": "2026-10-16", "indexedPages": 5, "submittedPages": 551,
                                "impressions28d": 280, "clicks28d": 10, "viewsPerDay": 10,
                                "measurableFollowers": 12, "gateVerdict": "CONTRACT",
                                "evidenceComplete": True})
        self.assertEqual(report["projection"]["status"], "NOT_ENOUGH_MEASUREMENT")
        self.assertGreaterEqual(report["projection"]["needsMoreDays"], 1)
        self.assertIsNone(report["projection"]["date50k"])

    def test_the_measured_rate_is_used_for_the_projection_once_there_are_three_points(self):
        self.seed([point("2026-10-13", 5, 10), point("2026-10-16", 20, 30), point("2026-10-19", 40, 50)])
        report = self.run_with({"asOf": "2026-10-19", "indexedPages": 40, "submittedPages": 551,
                                "impressions28d": 1400, "clicks28d": 50, "viewsPerDay": 50,
                                "measurableFollowers": 12, "gateVerdict": "EXPAND",
                                "evidenceComplete": True})
        self.assertEqual(report["projection"]["impressionsPerDayGain"], 6.667)
        self.assertEqual(report["projection"]["status"], "PROJECTED")
        self.assertTrue(report["projection"]["date50k"], "the projection must produce a date")
        self.assertEqual(report["projection"]["date50k"], "2047-04-25",
                         "at 6.7 extra views a day of gain the 50,000th visit is two decades out, "
                         "not in December - which is the point of doing the division")

    def test_a_flat_line_is_reported_as_flat(self):
        self.seed([point("2026-10-13", 5, 10), point("2026-10-16", 5, 10), point("2026-10-19", 5, 10)])
        report = self.run_with({"asOf": "2026-10-19", "indexedPages": 5, "submittedPages": 551,
                                "impressions28d": 280, "clicks28d": 10, "viewsPerDay": 10,
                                "measurableFollowers": 12, "gateVerdict": "CONTRACT",
                                "evidenceComplete": True})
        self.assertEqual(report["projection"]["status"], "FLAT_OR_FALLING")
        self.assertIsNone(report["projection"]["date50k"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
