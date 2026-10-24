#!/usr/bin/env python3
"""The audience count has to survive a dead endpoint, and it may never use a secret.

A follower counter that reports 0 when the network did not answer would turn "unknown" into a
fake measurement - the exact mistake these jobs exist to stop.
"""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import audience_channels as channels


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = (channels.ROOT, channels.OUT, channels.MD)
        channels.ROOT, channels.OUT, channels.MD = self.tmp, self.tmp / "c.json", self.tmp / "c.md"

    def tearDown(self):
        channels.ROOT, channels.OUT, channels.MD = self.saved

    def run_with(self, payload):
        fixture = self.tmp / "payload.json"
        fixture.write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch("sys.argv", ["audience_channels.py", "--fixture", str(fixture)]):
            self.assertEqual(channels.main(), 0)
        return json.loads(channels.OUT.read_text(encoding="utf-8"))


class ViewCounters(Harness):
    def test_the_reconciled_view_ledger_is_carried_into_the_audience_report(self):
        (self.tmp / "BLOGGER_VIEWS_LEDGER.json").write_text(json.dumps({
            "bloggerCounter": {"status": "MEASURED", "last7Days": 2200, "perDayFrom7DayWindow": 314.3},
            "humanCount": {"viewsPerDay": 16.4, "basis": "GA4_PAGEVIEWS_7_DAY_AVERAGE"}}), encoding="utf-8")
        report = self.run_with({"bluesky": {"ok": True, "handle": "@x", "followers": 1, "posts": 1,
                                          "accountAgeDays": 1, "followersPerPost": 1.0}})
        views = report["blogPageviews"]
        self.assertTrue(views["measurable"], "Blogger's own counter was read, so it must be reported")
        self.assertEqual(314.3, views["bloggerPerDay"])
        self.assertEqual(16.4, views["humanViewsPerDay"], "the human number stays beside Blogger's")
        self.assertIn("requests, not readers", views["warning"])

    def test_a_ledger_that_could_not_read_blogger_stays_an_honest_gap(self):
        (self.tmp / "BLOGGER_VIEWS_LEDGER.json").write_text(json.dumps(
            {"bloggerCounter": {"status": "NOT_MEASURED", "reason": "Blogger credentials unavailable"}}),
            encoding="utf-8")
        report = self.run_with({"bluesky": {"ok": True, "handle": "@x", "followers": 1, "posts": 1,
                                          "accountAgeDays": 1, "followersPerPost": 1.0}})
        self.assertFalse(report["blogPageviews"]["measurable"])
        self.assertIn("credentials", report["blogPageviews"]["why"])


class Counting(Harness):
    def test_two_public_channels_are_added_up(self):
        report = self.run_with({
            "bluesky": {"ok": True, "handle": "@dailyyield.bsky.social", "followers": 10,
                        "following": 3, "posts": 193, "created": "2026-09-26", "accountAgeDays": 24,
                        "followersPerPost": 0.0518, "source": "public.api.bsky.app"},
            "mastodon": {"ok": True, "handle": "@dailyyield", "followers": 2, "following": 0,
                         "posts": 176, "created": "2026-09-26", "accountAgeDays": 24,
                         "followersPerPost": 0.0114, "source": "mastodon.social"}})
        self.assertEqual(report["totals"]["followers"], 12)
        self.assertEqual(report["totals"]["channelsMeasured"], 2)
        self.assertEqual(report["channels"]["Bluesky"]["followers"], 10)
        self.assertFalse(report["credentialsUsed"])
        # Blogger does publish a page-view counter and the nightly view ledger reads it. Until that
        # ledger exists, the honest answer here is "not measured", with the job that fills it named.
        self.assertFalse(report["blogPageviews"]["measurable"])
        self.assertIn("BLOGGER_VIEWS_LEDGER.json", report["blogPageviews"]["why"])
        self.assertIn("0.0114", (channels.MD.read_text(encoding="utf-8")))

    def test_an_endpoint_that_did_not_answer_is_never_reported_as_zero_followers(self):
        report = self.run_with({"mastodon": {"ok": False, "error": "timed out"},
                               "bluesky": {"ok": False, "error": "timed out"}})
        self.assertIsNone(report["totals"]["followers"], "unknown must not become a measured 0")
        self.assertEqual(report["totals"]["channelsMeasured"], 0)
        self.assertIn("not measured", channels.MD.read_text(encoding="utf-8"))

    def test_unmeasured_channels_are_listed_rather_than_guessed(self):
        report = self.run_with({"bluesky": {"ok": True, "handle": "@x", "followers": 1, "posts": 1,
                                            "accountAgeDays": 1, "followersPerPost": 1.0}})
        # Facebook and Mastodon have no public follower endpoint; a channel that is not measured is
        # listed as unknown rather than guessed at, which is what this test guards.
        # Facebook has no public follower endpoint. Tumblr was dropped from automation on 21 October
        # 2026, so it must not appear as a channel at all rather than as an unmeasured one.
        self.assertNotIn("Tumblr", report["channels"])
        for name in ("Facebook",):
            self.assertFalse(report["channels"][name]["ok"])
            self.assertIn(name, report["totals"]["channelsNotMeasured"])
            self.assertNotIn("followers", report["channels"][name])


class Boundaries(unittest.TestCase):
    def test_the_reader_never_touches_a_credential(self):
        source = pathlib.Path(channels.__file__).read_text(encoding="utf-8")
        self.assertNotIn("os.environ", source, "public counts only - no token, no app secret")
        self.assertNotIn("secrets.", source)
        self.assertTrue(all("token" not in str(v).lower() or "not allowed to touch" in str(v)
                            for v in channels.NOT_MEASURED.values()))

    def test_age_of_an_account_comes_from_its_own_creation_date(self):
        self.assertGreaterEqual(channels.days_since("2026-09-26T16:35:55.056Z"), 1)
        self.assertIsNone(channels.days_since(""))
        self.assertIsNone(channels.days_since("not a date"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
