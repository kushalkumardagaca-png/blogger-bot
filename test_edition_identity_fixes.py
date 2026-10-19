#!/usr/bin/env python3
"""Tests for the two 18 October publication defects and their reporting.

Defect 1: an undated desk title made today's edition overwrite yesterday's post, so
the slot reported an article published 24 hours early at the wrong address.
Defect 2: two dispatches for one desk each created a post, because the recovery
check only knew the canonical address and not the collision-suffixed one.
"""
import datetime as dt
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import news_pipeline as np
import seo_hygiene
from slot_guard import is_wrong_day

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
BANK_ART = {"title": "Banking & Personal Money — 18 October 2026",
            "slug": "banking-fintech-personal-money-2026-10-18", "html": "<h1>18 October 2026</h1>",
            "labels": ["News", "Category Edition", "Banking & Payments", "Daily Yield", "Kushal Daga"],
            "canonical": "https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10-18.html"}


class TitleKeepsItsEditionDate(unittest.TestCase):
    def test_long_desk_name_is_shortened_instead_of_the_date(self):
        title = seo_hygiene.compact_title("Banking & Personal Money News — 18 October 2026")
        self.assertIn("18 October 2026", title)
        self.assertLessEqual(len(title), seo_hygiene.MAX_TITLE_CHARS)
        self.assertNotIn("…", title)

    def test_desks_that_already_fit_are_untouched(self):
        self.assertEqual(seo_hygiene.compact_title("Economy, Trade & Jobs News — 18 October 2026"),
                         "Economy, Trade & Jobs News — 18 October 2026")

    def test_two_days_of_one_desk_never_share_a_title(self):
        a = seo_hygiene.compact_title(f"Banking & Personal Money News — 17 October 2026")
        b = seo_hygiene.compact_title("Banking & Personal Money News — 18 October 2026")
        self.assertNotEqual(a, b)
        import editorial_integrity
        self.assertNotEqual(editorial_integrity.normalized_title(a),
                            editorial_integrity.normalized_title(b))
        self.assertTrue(a.endswith("17 October 2026") and b.endswith("18 October 2026"))


class PreviousEditionIsNeverOverwritten(unittest.TestCase):
    def test_different_title_dates_prove_a_previous_edition(self):
        stored = {"title": "Banking & Personal Money — 17 October 2026",
                  "published": "2026-10-17T13:15:04Z"}
        self.assertTrue(np.is_previous_edition(stored, BANK_ART))

    def test_bloggers_own_publish_day_proves_it_when_titles_are_undated(self):
        stored = {"title": "Banking & Personal Money News", "published": "2026-10-17T13:15:04Z"}
        self.assertTrue(np.is_previous_edition(stored, BANK_ART))

    def test_same_day_post_is_still_repaired_not_duplicated(self):
        stored = {"title": "Banking & Personal Money News", "published": "2026-10-18T13:15:04Z"}
        self.assertFalse(np.is_previous_edition(stored, BANK_ART))

    def test_unreadable_publish_time_falls_back_to_repair(self):
        self.assertFalse(np.is_previous_edition({"title": "Banking & Personal Money News"}, BANK_ART))

    def test_america_market_date_in_the_title_is_not_called_previous(self):
        art = {"title": "Americas Finance News — 17 October 2026",
               "slug": "americas-finance-news-2026-10-18"}
        stored = {"title": "Americas Finance News — 17 October 2026",
                  "published": "2026-10-18T01:05:00Z"}
        self.assertFalse(np.is_previous_edition(stored, art))

    def test_publish_call_never_puts_to_an_earlier_days_post(self):
        earlier = {"id": "777", "title": "Banking & Personal Money News",
                   "url": "https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01450325346.html",
                   "content": "<h1>Banking & Personal Money News</h1>", "published": "2026-10-17T13:15:04Z"}
        calls = []

        def fake_call(path, token, method="GET", body=None, _auth_retry=True):
            calls.append((method, path.split("?")[0]))
            if path.startswith("/posts?") and method == "GET":
                return {"items": [earlier]}
            if method == "POST" and path.startswith("/posts?isDraft"):
                return {"id": "999", "url": "https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10-18.html"}
            if path.startswith("/posts/999/publish"):
                return {"url": "https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10-18.html",
                        "status": "LIVE"}
            if path.startswith("/posts/999") and method == "PUT":
                return {"url": BANK_ART["slug"]}
            return {"id": "999", "status": "LIVE", "url": "", "content": "", "title": ""}

        with patch.object(np, "assert_green_operating_state", lambda: True), \
             patch.object(np, "blogger_call", fake_call), \
             patch.object(np, "stamp", lambda html, title, profile: html), \
             patch.object(np, "automation_disclosure", lambda *a, **k: ""), \
             patch.object(np, "assert_saved_green", lambda post: True), \
             patch.object(np, "assert_edition_identity", lambda stored, art: True), \
             patch.object(np, "find_incomplete_live_post", lambda art, token: None), \
             patch.object(np, "headline_of", lambda content, fallback="": fallback):
            np.publish_post(dict(BANK_ART, html="<h1>Banking & Personal Money — 18 October 2026</h1>"), "tok")
        self.assertNotIn(("PUT", "/posts/777"), calls,
                         "an earlier day's edition must not be rewritten")
        self.assertIn(("POST", "/posts"), calls,
                      "today's edition must become its own post")


class SameDayEditionIsAdopted(unittest.TestCase):
    def setUp(self):
        self.day = dt.date(2026, 10, 18)
        self.rows = [
            {"url": "https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18_01443792159.html",
             "published": "2026-10-17T22:45:34Z"},
            {"url": "https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18.html",
             "published": "2026-10-17T22:45:02Z"},
            {"url": "https://dailyyield.blogspot.com/2026/10/india-finance-news-2026-10-18.html",
             "published": "2026-10-17T22:00:00Z"},
        ]

    def test_either_address_form_is_found_and_the_earliest_is_the_keeper(self):
        with patch.object(np, "blogger_call", lambda path, token, method="GET", body=None, **k: {"items": self.rows}):
            found = np.find_same_day_desk_post("asia-pacific-finance-news", self.day, "tok")
        self.assertEqual(found, "https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18.html")

    def test_an_unrelated_desk_and_a_failed_read_never_invent_an_edition(self):
        with patch.object(np, "blogger_call", lambda path, token, method="GET", body=None, **k: {"items": self.rows}):
            self.assertIsNone(np.find_same_day_desk_post("economy-trade-jobs", self.day, "tok"))
        with patch.object(np, "blogger_call", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("api down"))):
            self.assertIsNone(np.find_same_day_desk_post("asia-pacific-finance-news", self.day, "tok"))

    def test_run_desk_adopts_the_sibling_instead_of_publishing_again(self):
        tracker = {"desks": {"asia-pacific": {"edition": "2026-10-17", "window_end": "2026-10-17T13:45:00+05:30",
                                             "url": "https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-17.html"}}}
        events, built = [], []
        sibling = "https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18_01443792159.html"
        fake_now = dt.datetime(2026, 10, 18, 13, 50, tzinfo=IST)
        with patch.object(np.dt, "datetime") as clock, \
             patch.object(np, "find_same_day_desk_post", return_value=sibling), \
             patch.object(np, "live_current_edition", return_value=True), \
             patch.object(np, "save_tracker", lambda t: built.append(t)), \
             patch.object(np, "append_social_event", lambda desk, url: events.append((desk, url))), \
             patch.object(np, "fetch_desk_items", lambda desk: built.append("FETCHED") or ([], 0, 0)):
            clock.now.return_value = fake_now
            self.assertTrue(np.run_desk("asia-pacific", tracker, token="tok"))
        self.assertEqual(events, [("asia-pacific", sibling)])
        self.assertEqual(tracker["desks"]["asia-pacific"]["edition"], "2026-10-18")
        self.assertEqual(tracker["desks"]["asia-pacific"]["url"], sibling)
        self.assertNotIn("FETCHED", built, "no second edition may be researched or built")


class ReportingNamesTheDefect(unittest.TestCase):
    def test_yesterdays_timestamp_is_not_reported_as_early(self):
        day = dt.date(2026, 10, 18)
        published = dt.datetime(2026, 10, 17, 18, 45, tzinfo=IST)
        self.assertTrue(is_wrong_day(published, day))
        self.assertFalse(is_wrong_day(dt.datetime(2026, 10, 18, 18, 50, tzinfo=IST), day))

    def test_naive_timestamps_are_judged_in_india_time(self):
        self.assertFalse(is_wrong_day(dt.datetime(2026, 10, 18, 23, 30), dt.date(2026, 10, 18)))


class MasterDayIdentity(unittest.TestCase):
    def test_published_records_are_read_whichever_key_they_use(self):
        from master_topic_discovery import used_topic_ids
        history = {"items": [{"topic_id": "aaa"}, {"id": "bbb"}, {"url": "no-id"}]}
        tracker = {"published": [{"topic_id": "ccc"}, {"topic_id": "aaa"}]}
        self.assertEqual(used_topic_ids(history, tracker), {"aaa", "bbb", "ccc"})

    def test_blogger_timestamps_are_judged_in_india_time(self):
        import master_v3_pipeline as m
        self.assertEqual(m.ist_day("2026-10-15T19:45:08-07:00"), dt.date(2026, 10, 16))
        self.assertEqual(m.ist_day("2026-10-19T04:15:00Z"), dt.date(2026, 10, 19))
        self.assertIsNone(m.ist_day(""))
        self.assertIsNone(m.ist_day("not a date"))

    def test_an_older_article_cannot_answer_for_todays_slot(self):
        import master_v3_pipeline as m
        plan = {"date": "2026-10-19", "status": "READY",
                "trending": [], "evergreen": [{"id": "ecdac34f3a084a15", "title": "Best Financial Habits For Gen Z",
                                               "category": "Money Hacks & Financial Habits"}]}
        written = {}
        with patch.dict("os.environ", {"MASTER_PUBLICATION_ENABLED": "true"}), \
             patch.object(m, "selected", lambda kind, slot: (plan, plan["evergreen"][0])), \
             patch.object(m, "blocked_topics", lambda p: set()), \
             patch.object(m, "reuse_completed_slot", lambda *a, **k: False), \
             patch.object(m, "_package_or_build", lambda kind, slot, item: Path("package.json")), \
             patch.object(m, "read", lambda path, default: {"id": "x", "policy_version": m.POLICY_VERSION}), \
             patch.object(m, "validate", lambda package: True), \
             patch.object(m, "build_html", lambda kind, item, package: ("t", "s", "m", ["Master Article"], "<p>b</p>")), \
             patch.object(m, "publish_to_blogger", lambda *a, **k: {"url": "https://dailyyield.blogspot.com/2026/10/best-financial-habits-for-gen-z.html",
                                                                     "published": "2026-10-15T19:45:08-07:00"}), \
             patch.object(m, "wait_for_release", lambda *a, **k: None), \
             patch.object(m, "write", lambda path, value: written.update({path.name: value})):
            with self.assertRaises(RuntimeError) as caught:
                m.publish("evergreen", 0)
        self.assertIn("MASTER EDITION IDENTITY FAILED", str(caught.exception))
        self.assertIn("ecdac34f3a084a15", written["MASTER_DAILY_PLAN.json"]["blockedTopics"])

    def test_a_substituted_topic_gets_a_package_before_publishing(self):
        import master_v3_pipeline as m
        calls = []
        with patch.object(m, "package_path", lambda kind, item: Path("missing.json")), \
             patch.object(m, "Path") as path_cls:
            path_cls.return_value.exists.return_value = False
            with patch.object(m, "prepare", lambda kind, slot: calls.append(("prepare", kind, slot))):
                try:
                    m._package_or_build("evergreen", 0, {"id": "new"})
                except RuntimeError:
                    pass
        self.assertEqual(calls, [("prepare", "evergreen", 0)])


class RouteAttemptCap(unittest.TestCase):
    def test_a_repeatedly_failing_route_is_paused_not_spammed(self):
        import social_guard as g
        now = dt.datetime(2026, 10, 19, 13, 0, tzinfo=IST)
        waiting, paused, attempts = g.route_state({"at": (now - dt.timedelta(hours=3)).isoformat(), "n": 4}, now)
        self.assertEqual((waiting, paused, attempts), (False, True, 4))

    def test_a_recent_dispatch_is_simply_still_waiting(self):
        import social_guard as g
        now = dt.datetime(2026, 10, 19, 13, 0, tzinfo=IST)
        waiting, paused, attempts = g.route_state({"at": (now - dt.timedelta(minutes=4)).isoformat(), "n": 4}, now)
        self.assertEqual((waiting, paused, attempts), (True, False, 4))

    def test_an_older_plain_timestamp_entry_still_works(self):
        import social_guard as g
        now = dt.datetime(2026, 10, 19, 13, 0, tzinfo=IST)
        waiting, paused, attempts = g.route_state((now - dt.timedelta(hours=2)).isoformat(), now)
        self.assertEqual((waiting, paused, attempts), (False, False, 1))

    def test_no_entry_means_a_clean_start(self):
        import social_guard as g
        now = dt.datetime(2026, 10, 19, 13, 0, tzinfo=IST)
        self.assertEqual(g.route_state(None, now), (False, False, 0))


class CredentialHealthIsVisible(unittest.TestCase):
    def test_a_dead_network_is_reported_and_a_healthy_one_is_ignored(self):
        import tempfile
        import social_guard as g
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(g.blocked_platforms(root), {})
            (root / "SOCIAL_CREDENTIAL_HEALTH.json").write_text(json.dumps(
                {"tumblr": {"ok": False, "reason": "RuntimeError: invalid_grant"},
                 "mastodon": {"ok": True, "reason": ""}}), encoding="utf-8")
            blocked = g.blocked_platforms(root)
        self.assertEqual(list(blocked), ["tumblr"])
        self.assertIn("invalid_grant", blocked["tumblr"])

    def test_broken_json_cannot_make_the_guard_think_a_network_is_down(self):
        import tempfile
        import social_guard as g
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SOCIAL_CREDENTIAL_HEALTH.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(g.blocked_platforms(root), {})

    def test_the_publisher_writes_health_without_leaving_a_token_behind(self):
        import tempfile
        import tumblr_publisher as t
        with tempfile.TemporaryDirectory() as tmp:
            health = Path(tmp) / "SOCIAL_CREDENTIAL_HEALTH.json"
            original = t.HEALTH_FILE
            t.HEALTH_FILE = health
            try:
                t.record_health(False, "401 Client Error: unauthorized url=" + "A" * 60)
                row = json.loads(health.read_text())["tumblr"]
                self.assertFalse(row["ok"])
                self.assertNotIn("A" * 60, health.read_text())
                self.assertIn("re-authorise", row["action"])
                t.record_health(True)
                self.assertTrue(json.loads(health.read_text())["tumblr"]["ok"])
            finally:
                t.HEALTH_FILE = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
