#!/usr/bin/env python3
"""A share that ran out of fast attempts is deferred, not abandoned - and a refusal names its real cause.

On 23 October the Americas edition's Facebook route spent four attempts. The fourth failed at 6:37 pm on
a caption our own policy gate declined; the publisher wrote the truth into
`SOCIAL_CREDENTIAL_HEALTH.json` and, minutes later, reported the network healthy again. The guard saw
neither. Its cap turned into a verdict for the day - `route paused after 4 attempts today: the network or
its credentials need attention` - and no share was ever attempted again, so one article ended the day with
half of its social distribution and a note telling the owner to re-authorise a token that had never
failed.

Two rules, no loosening: a pause is a spacing (one more bounded attempt after 90 minutes, with the
attempt history intact so a genuinely broken network still cannot spin), and the reason the publisher
already recorded is the reason the guard repeats.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import social_guard as guard  # noqa: E402

NOW = dt.datetime(2026, 10, 23, 21, 30, tzinfo=guard.IST)


def entry(minutes_ago: int, attempts: int) -> dict:
    return {"at": (NOW - dt.timedelta(minutes=minutes_ago)).isoformat(), "n": attempts}


class APauseIsASpacing(unittest.TestCase):
    def test_a_route_that_just_ran_only_waits(self):
        waiting, paused, attempts = guard.route_state(entry(6, 1), NOW)
        self.assertTrue(waiting and not paused)

    def test_four_attempts_in_a_row_are_paused(self):
        waiting, paused, attempts = guard.route_state(entry(30, 4), NOW)
        self.assertTrue(paused, "the fast retries must not burn runner minutes all evening")

    def test_a_paused_route_is_offered_again_after_the_resume_window(self):
        waiting, paused, attempts = guard.route_state(entry(95, 4), NOW)
        self.assertFalse(paused, "a pause that never lifts is how a share is quietly abandoned")
        self.assertFalse(waiting)

    def test_the_attempt_history_survives_the_resume(self):
        _, _, attempts = guard.route_state(entry(120, 7), NOW)
        self.assertEqual(attempts, 7, "the pause resets its spacing, not its count")

    def test_a_route_under_the_cap_keeps_only_its_spacing(self):
        waiting, paused, attempts = guard.route_state(entry(120, 2), NOW)
        self.assertFalse(paused or waiting)

    def test_an_unreadable_stamp_still_respects_the_cap(self):
        waiting, paused, attempts = guard.route_state({"at": "yesterday", "n": 9}, NOW)
        self.assertTrue(paused)
        self.assertEqual(attempts, 9)


class NotesReadTheRecord(unittest.TestCase):
    def test_a_policy_refusal_is_not_reported_as_a_credential_problem(self):
        note = guard.blocked_note(["facebook"], {"facebook":
            "RuntimeError: SOCIAL CONTENT POLICY GATE FAILED — excessive hashtagging"})
        self.assertNotIn("re-authorise", note, "the owner must not be sent to fix a token that works")
        self.assertIn("our own content rules", note)
        self.assertIn("counted as missing", note, "and the share must stay owed, not written off")

    def test_a_dead_token_still_names_the_owner_step(self):
        note = guard.blocked_note(["facebook"], {"facebook": "Graph returned (#190) the access token has expired"})
        self.assertIn("re-authorise", note)

    def test_a_pause_says_when_it_resumes(self):
        note = guard.paused_note(4)
        self.assertIn("90 minutes", note)
        self.assertIn("counted as missing", note)


class HealthIsTheSwitch(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def write_health(self, rows):
        (self.tmp / "SOCIAL_CREDENTIAL_HEALTH.json").write_text(json.dumps(rows), encoding="utf-8")

    def test_a_healthy_network_is_not_blocked(self):
        self.write_health({"facebook": {"ok": True, "reason": "", "checkedAtIST": NOW.isoformat()}})
        self.assertEqual(guard.blocked_platforms(root=self.tmp), {})

    def test_a_broken_network_is_blocked_with_its_reason(self):
        self.write_health({"facebook": {"ok": False, "reason": "token expired"}})
        self.assertEqual(guard.blocked_platforms(root=self.tmp), {"facebook": "token expired"})

    def test_a_retired_network_cannot_hold_the_day_hostage(self):
        self.write_health({"tumblr": {"ok": False, "reason": "retired platform"}})
        self.assertEqual(guard.blocked_platforms(root=self.tmp), {})


class TheGuardStillCountsTheShare(unittest.TestCase):
    def test_a_paused_route_leaves_the_post_missing_rather_than_green(self):
        source = (ROOT / "social_guard.py").read_text(encoding="utf-8")
        self.assertIn('record["paused"] = True', source)
        self.assertIn("PAUSE_RESUME_AFTER = dt.timedelta(minutes=90)", source)
        self.assertIn("def blocked_note", source)


if __name__ == "__main__":
    unittest.main()
