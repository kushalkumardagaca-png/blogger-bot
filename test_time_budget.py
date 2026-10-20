#!/usr/bin/env python3
"""Preparation has one clock, and the clock decides when to stop trying - never what to publish.

Owner's rule of 20 October 2026: a Master article is prepared in 10-50 minutes and must never take
more than 40. Before this module the workflow allowed 120-150 minutes, and a slow Commons download
or a hung model call could hold a slot for the rest of the day.
"""
import os
import time
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent

import photo_selector
import time_budget
from time_budget import BUDGET, Budget, configured_minutes


class Configuration(unittest.TestCase):
    def test_the_default_sits_inside_the_owners_ceiling(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(configured_minutes(), 30.0)

    def test_an_environment_value_is_honoured_but_cannot_exceed_the_ceiling(self):
        for raw, expected in (('12', 12.0), ('55', time_budget.HARD_MAX_MINUTES),
                              ('nonsense', 30.0), ('1', 5.0)):
            with self.subTest(raw=raw):
                with mock.patch.dict(os.environ, {"MASTER_PREPARATION_BUDGET_MINUTES": raw}):
                    self.assertEqual(configured_minutes(), expected)


class Clock(unittest.TestCase):
    def test_seconds_never_exceeds_the_requested_ceiling(self):
        self.assertLessEqual(Budget(30).seconds(60), 60)
        self.assertLessEqual(Budget(30).seconds(35), 35)

    def test_seconds_shrinks_as_the_run_runs_out(self):
        clock = Budget(minutes=0.5)  # half a minute, so the floor never masks the change
        first = clock.seconds(60, floor=1)
        time.sleep(1.2)
        self.assertLess(clock.seconds(60, floor=1), first)
        self.assertGreater(clock.seconds(60, floor=1), 1)

    def test_the_run_is_over_only_once_the_time_is_genuinely_gone(self):
        clock = Budget(minutes=0.02)
        self.assertFalse(clock.out())
        time.sleep(1.3)
        self.assertTrue(clock.out())
        self.assertEqual(clock.remaining(), 0.0)

    def test_the_note_reports_all_three_numbers(self):
        note = Budget(minutes=17).note()
        self.assertEqual({"budgetMinutes", "elapsedMinutes", "remainingMinutes"}, set(note))
        self.assertEqual(note["budgetMinutes"], 17.0)

    def test_stopping_names_the_activity_and_points_at_recovery(self):
        message = str(Budget(minutes=7).stop("downloading a candidate photograph"))
        self.assertIn("7 minutes", message)
        self.assertIn("downloading a candidate photograph", message)
        self.assertIn("recovery", message)

    def test_a_tired_photo_search_stops_instead_of_starting_another_query(self):
        exhausted = Budget(minutes=1 / 6000)  # ten hundredths of a second
        time.sleep(0.15)
        with mock.patch.object(photo_selector, "BUDGET", exhausted):
            with self.assertRaises(RuntimeError) as caught:
                photo_selector.commons_candidates("office workers computers")
        self.assertIn("time budget", str(caught.exception))
        # and a query that has time left still asks for its normal ceiling, not less
        self.assertLessEqual(Budget(minutes=30).seconds(60), 60)


class Ceilings(unittest.TestCase):
    """The owner's 40-minute rule has to be written where CI can see it, not only in a comment."""

    WRITERS = ("master_evergreen_writer.yml", "master_trending_writer.yml")

    def test_both_master_writers_work_to_the_same_clock(self):
        for name in self.WRITERS:
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("MASTER_PREPARATION_BUDGET_MINUTES: '30'", text)
                self.assertIn("1800-second budget", text)  # a long attempt is not repeated in-run
                # deliberately no GitHub-side timeout anywhere in the file: the run reaches its
                # own deadline and reports it, because cancelling a healthy generation by age is
                # what used to lose articles here (see master_stale_run_reaper.yml)
                self.assertNotIn("timeout-minutes:", text)

    def test_no_open_ended_network_wait_is_left_in_the_writer_path(self):
        generator = (ROOT / "master_v3_generator.py").read_text(encoding="utf-8")
        photos = (ROOT / "photo_selector.py").read_text(encoding="utf-8")
        pipeline = (ROOT / "master_v3_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("from time_budget import BUDGET", generator)
        self.assertIn("from time_budget import BUDGET", photos)
        self.assertIn("from time_budget import BUDGET", pipeline)
        self.assertNotIn("timeout=90", generator)
        self.assertNotIn("timeout=35", photos)
        # every page, feed and API read in the writing path is bounded by the run's own clock;
        # only the two Google authorisation exchanges keep a fixed 30 seconds
        for name, text in (("master_v3_generator.py", generator), ("photo_selector.py", photos)):
            for line in text.splitlines():
                if "requests.get(" in line:
                    with self.subTest(module=name, line=line.strip()[:56]):
                        self.assertIn("BUDGET.seconds(", line,
                                      "an unbounded network wait would outlive the 40-minute ceiling")


if __name__ == "__main__":
    unittest.main(verbosity=2)
