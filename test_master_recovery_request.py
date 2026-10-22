"""The recovery route must not depend on the wording of a commit message.

`.github/master-recovery-request` is how a Master slot that today's schedule missed gets recovered, and it
fires on a push to that path. On 22 October two requests were pushed and GitHub ignored both, because the
commits that wrote them carried a skip marker in their messages - so the fix in `master_recovery_request.py`
is to ask the same question on a timer too, and to answer from the site's own records so that a timer
cannot start a second article for a slot that is already written or already being written.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import master_recovery_request as rec

TODAY = dt.date(2026, 10, 22)


class ReadTheRequest(unittest.TestCase):
    def write_file(self, text):
        tmp = pathlib.Path(tempfile.mkdtemp()) / "master-recovery-request"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        return tmp

    def test_a_missing_file_is_reported_and_not_dispatched(self):
        kind, slot = rec.read_request(self.write_file("x") .parent / "absent")
        self.assertIsNone(kind)
        self.assertIn("no request file", slot)

    def test_whitespace_including_a_skip_marker_cannot_change_the_request(self):
        """The push that GitHub ignores is a message problem; the *content* is still a valid request."""
        self.assertEqual(rec.read_request(self.write_file(" trending:4 \n")), ("trending", 4))
        self.assertEqual(rec.read_request(self.write_file("evergreen:4")), ("evergreen", 4))

    def test_an_unusable_request_says_what_to_write(self):
        kind, reason = rec.read_request(self.write_file("slot 3 please"))
        self.assertIsNone(kind)
        self.assertIn("evergreen:0-4", reason)


class Decide(unittest.TestCase):
    plan = {"date": str(TODAY), "blockedTopics": {}}

    def test_no_live_article_no_active_run_and_a_young_request_means_dispatch(self):
        got = rec.decide("trending", 4, self.plan, {}, today=TODAY, requested_min_ago=6, writer_active=False)
        self.assertTrue(got["dispatch"])
        self.assertEqual(got["file"], "master_trending_writer.yml")
        self.assertEqual(got["slot"], 4)

    def test_a_slot_that_is_already_live_is_left_alone(self):
        published = [{"kind": "trending", "slot": 4, "url": "https://dailyyield.blogspot.com/2026/10/x.html"}]
        with mock.patch.dict("sys.modules", {"master_slot_state": FakeSlotState(published)}):
            got = rec.decide("trending", 4, self.plan, {"published": published}, today=TODAY,
                             requested_min_ago=6, writer_active=False)
        self.assertFalse(got["dispatch"])
        self.assertIn("confirmed live article", got["note"])

    def test_an_active_writer_run_is_never_doubled_up(self):
        got = rec.decide("evergreen", 4, self.plan, {}, today=TODAY, requested_min_ago=3, writer_active=True)
        self.assertFalse(got["dispatch"])
        self.assertIn("already working", got["note"])

    def test_an_old_request_expires_instead_of_retrying_forever(self):
        got = rec.decide("trending", 4, self.plan, {}, today=TODAY, requested_min_ago=rec.DEFAULT_TTL_MINUTES + 40,
                         writer_active=False)
        self.assertFalse(got["dispatch"])
        self.assertIn("expired", got["note"])

    def test_a_plan_from_yesterday_vouches_for_nothing(self):
        stale = {"date": str(TODAY - dt.timedelta(days=1))}
        self.assertFalse(rec.slot_is_live("trending", 4, stale, {}, TODAY),
                         "an old plan cannot claim today's slot is filled")

    def test_a_keeper_that_cannot_be_read_still_gets_its_attempt(self):
        """Deliberate: the writer re-checks for a live article before publishing, so a wasted run is cheap
        and an abandoned slot is not."""
        with mock.patch.dict("sys.modules", {"master_slot_state": None}):
            self.assertFalse(rec.slot_is_live("trending", 4, self.plan, {}, TODAY))


class FakeSlotState:
    def __init__(self, records):
        self.records = records

    def keeper_for_slot(self, plan, records, kind, slot):
        for row in (records or []):
            if row.get("kind") == kind and row.get("slot") == slot:
                return row
        return None


if __name__ == "__main__":
    unittest.main(verbosity=2)
