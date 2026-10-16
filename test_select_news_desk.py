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

    def test_an_expired_slot_never_publishes_and_says_so(self):
        # The Banking slot of 16 October was still missing at 22:30, long after
        # its 18:45 window. Nothing is published for it; the selector reports the
        # expiry so the run log shows why, and the News engine's own grace rule
        # then records the slot as expired rather than filling it late.
        now = self.now(22, 30)
        desk, reason = snd.choose("banking", now, snd.load_published(now, self.tracker_path))
        self.assertIn("past its window", reason)
        self.assertIn("no desk can still publish on time", reason)
        self.assertTrue(snd.choose("banking", now, {"banking"})[0])

    def test_a_delayed_china_run_does_not_publish_china_late(self):
        # GitHub started the China run after its 05:15 slot and the edition went
        # live at 06:17. Once its window has closed the desk is left alone and the
        # run prepares the next edition that can still be on time.
        now = self.now(6, 55)
        desk, reason = snd.choose("china", now, snd.load_published(now, self.tracker_path))
        self.assertNotEqual(desk, "china")
        self.assertEqual(desk, "india")
        self.assertIn("on time", reason)

    def test_a_desk_already_live_is_not_repeated(self):
        now = self.now(12, 20)
        rows = {"markets": {"edition": "2026-10-16"}}
        desk, reason = snd.choose("markets", now, snd.load_published(now, tracker(rows, self.tracker_path)))
        self.assertNotEqual(desk, "markets")
        self.assertIn("already live", reason)

    def test_nothing_available_returns_the_scheduled_desk_for_a_visible_failure(self):
        now = self.now(23, 50)
        desk, reason = snd.choose("banking", now, snd.load_published(now, self.tracker_path))
        self.assertIn(reason, ("no desk can still publish on time", reason))
        self.assertTrue(desk)


if __name__ == "__main__":
    unittest.main()
