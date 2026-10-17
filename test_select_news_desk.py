#!/usr/bin/env python3
"""The News desk selector must never choose a desk whose slot has expired.

Written after the Banking edition of 16 October (18:45 slot) never reached the
blog and the China run published 62 minutes after its own slot.
"""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

import select_news_desk as snd

IST = ZoneInfo("Asia/Kolkata")


def tracker(rows, path: Path):
    path.write_text(json.dumps({"desks": rows}), encoding="utf-8")
    return path


class DeskSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tracker_path = Path(self.temp.name) / "news_tracker.json"
        tracker({}, self.tracker_path)

    def now(self, hour, minute):
        return dt.datetime(2026, 10, 16, hour, minute, tzinfo=IST)

    def test_scheduled_desk_keeps_the_run_while_its_window_is_open(self):
        desk, reason = snd.choose("markets", self.now(12, 5),
                                  snd.load_published(self.now(12, 5), self.tracker_path))
        self.assertEqual(desk, "markets")
        self.assertIn("window", reason)

    def test_a_slot_inside_the_grace_window_still_publishes(self):
        desk, _ = snd.choose("banking", self.now(19, 30),
                             snd.load_published(self.now(19, 30), self.tracker_path))
        self.assertEqual(desk, "banking")

    def test_a_slot_past_its_range_is_still_published(self):
        # The Banking slot of 16 October was missing at 22:30, long after 18:45.
        # It is still produced — the edition matters more than the clock — and the
        # selector says plainly how late it is.
        now = self.now(22, 30)
        desk, reason = snd.choose("banking", now, snd.load_published(now, self.tracker_path))
        self.assertEqual(desk, "banking")
        self.assertIn("publishing it now", reason)

    def test_a_delayed_china_run_still_publishes_china(self):
        # GitHub started the China run after its 05:15 slot. The edition is still
        # produced, and the run log records how late it started.
        now = self.now(6, 55)
        desk, reason = snd.choose("china", now, snd.load_published(now, self.tracker_path))
        self.assertEqual(desk, "china")
        self.assertIn("late", reason)

    def test_a_desk_already_live_is_not_repeated(self):
        now = self.now(12, 20)
        rows = {"markets": {"edition": "2026-10-16"}}
        desk, reason = snd.choose("markets", now, snd.load_published(now, tracker(rows, self.tracker_path)))
        self.assertNotEqual(desk, "markets")
        self.assertIn("already live", reason)

    def test_the_most_overdue_desk_is_caught_up_first(self):
        # Every desk already live except banking: the run still publishes it rather
        # than doing nothing, and the reason names the lateness.
        now = self.now(23, 50)
        published = {"asia-pacific", "china", "india", "russia", "markets", "europe",
                     "economy", "americas", "companies", "global"}
        desk, reason = snd.choose("global", now, published)
        self.assertEqual(desk, "banking")
        self.assertIn("overdue", reason)


if __name__ == "__main__":
    unittest.main()
