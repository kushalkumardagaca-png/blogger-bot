#!/usr/bin/env python3
"""The 21 slots must be delivered inside the owner's 30-minute tolerance."""
from __future__ import annotations

import datetime as dt
import unittest

import slot_guard as sg

IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
DAY = dt.date(2026, 10, 17)


def at(hour, minute):
    return dt.datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=IST)


class SlotListTests(unittest.TestCase):
    def test_there_are_exactly_twenty_one_slots(self):
        slots = sg.todays_slots(DAY)
        self.assertEqual(len(slots), 21)
        self.assertEqual(sum(1 for s in slots if s["kind"] == "news"), 11)
        self.assertEqual(sum(1 for s in slots if s["kind"] == "trending"), 5)
        self.assertEqual(sum(1 for s in slots if s["kind"] == "evergreen"), 5)

    def test_the_slots_are_in_time_order(self):
        slots = sg.todays_slots(DAY)
        self.assertEqual([s["due"] for s in slots], sorted(s["due"] for s in slots))

    def test_the_first_and_last_slots_of_the_day(self):
        slots = sg.todays_slots(DAY)
        self.assertEqual(slots[0]["slot"], "04:15")
        self.assertEqual(slots[-1]["slot"], "22:15")


class ToleranceTests(unittest.TestCase):
    def test_anything_inside_thirty_minutes_is_on_time(self):
        due = at(18, 45)
        self.assertEqual(sg.classify(due, at(19, 10), at(19, 10)), "on time")
        self.assertEqual(sg.classify(due, at(18, 20), at(18, 20)), "on time")

    def test_forty_minutes_after_the_slot_is_late(self):
        self.assertEqual(sg.classify(at(18, 45), at(19, 30), at(19, 30)), "late")

    def test_a_slot_that_is_due_and_open_is_pending(self):
        self.assertEqual(sg.classify(at(18, 45), at(19, 5), None), "pending")

    def test_a_slot_whose_range_passed_is_overdue_and_still_published(self):
        # The owner's rule: missing the range never cancels that day's article.
        self.assertEqual(sg.classify(at(18, 45), at(19, 40), None), "overdue")

    def test_a_slot_not_yet_due_is_upcoming(self):
        self.assertEqual(sg.classify(at(18, 45), at(17, 0), None), "upcoming")
