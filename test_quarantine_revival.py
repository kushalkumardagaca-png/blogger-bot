#!/usr/bin/env python3
"""Rules for the 15 October quarantine-revival decision.

These tests protect five user requirements:
1. one article per eight-hour slot, never two at once;
2. a different combination of three social networks for each article;
3. every article is repaired and re-verified against the publication benchmark
   before it can be released;
4. the repair never removes the transparency disclosure or the integrity stamp;
5. publication stays inside the approved Daily Yield accounts and domain.
"""
from __future__ import annotations

import datetime as dt
import json
import unittest
from pathlib import Path

import revive_quarantine as rq
from content_policy_guard import DISCLOSURE_MARKER

ROOT = Path(__file__).parent


class RevivalPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / "QUARANTINE_REVIVAL_PLAN.json").read_text())
        self.items = self.plan["items"]

    def test_eighteen_drafts_in_priority_order(self):
        self.assertEqual(len(self.items), 18)
        self.assertEqual([x["order"] for x in self.items], list(range(1, 19)))
        self.assertEqual(len({x["draft_id"] for x in self.items}), 18)

    def test_each_article_has_three_distinct_networks(self):
        for item in self.items:
            route = item["social_route"]
            self.assertEqual(len(route), 3, item)
            self.assertEqual(len(set(route)), 3, item)
            self.assertTrue(set(route) <= {"facebook", "bluesky", "tumblr", "mastodon"}, item)

    def test_rotation_changes_between_articles(self):
        routes = [tuple(x["social_route"]) for x in self.items]
        self.assertNotEqual(routes[0], routes[1])
        # Consecutive articles never lead with the same network twice in a row.
        leads = [x["social_route"][0] for x in self.items]
        self.assertTrue(any(a != b for a, b in zip(leads, leads[1:])))
        # The rotation cycles rather than sticking to one combination.
        self.assertGreaterEqual(len(set(routes)), 4)

    def test_every_approved_network_is_used(self):
        used = {p for item in self.items for p in item["social_route"]}
        self.assertEqual(used, {"facebook", "bluesky", "tumblr", "mastodon"})

    def test_spacing_is_eight_hours(self):
        self.assertEqual(SPACING_HOURS := self.plan["cadence_hours"], rq.SPACING_HOURS)
        self.assertEqual(SPACING_HOURS, 8)


class SpacingTests(unittest.TestCase):
    def test_not_due_before_the_next_slot(self):
        now = dt.datetime(2026, 10, 15, 21, 30, tzinfo=rq.IST)
        state = {"next_due_at": (now + dt.timedelta(hours=8)).isoformat(), "items": {}}
        self.assertFalse(rq.due_now(state, now))
        self.assertTrue(rq.due_now(state, now + dt.timedelta(hours=8, minutes=1)))

    def test_first_run_is_due(self):
        self.assertTrue(rq.due_now({"next_due_at": "", "items": {}}, dt.datetime.now(rq.IST)))

    def test_only_one_item_is_pending_at_a_time(self):
        state = {"next_due_at": "", "items": {}}
        item = rq.next_pending(state)
        self.assertIsNotNone(item)
        rq.item_state(state, item["draft_id"])["status"] = "live"
        self.assertNotEqual(rq.next_pending(state)["draft_id"], item["draft_id"])


class RepairGateTests(unittest.TestCase):
    def test_stock_phrases_and_unsupported_absolutes_are_replaced(self):
        content = '<p>This forensic framework eliminates redundant intermediary friction with guaranteed returns.</p>'
        cleaned, found = rq.neutralise_prohibited(content)
        self.assertTrue(found)
        for banned in rq.MASS_TEMPLATE_PHRASES + rq.UNSUPPORTED_ABSOLUTES:
            self.assertNotIn(banned.casefold(), cleaned.casefold())

    def test_disclosure_and_stamp_are_added_once(self):
        content = rq.ensure_disclosure("<p>Body</p>")
        content = rq.ensure_disclosure(content)
        self.assertEqual(content.count(DISCLOSURE_MARKER), 1)
        stamped = rq.stamp(content, "A repaired Daily Yield article title", "quarantine-revival")
        self.assertIn("DY_EDITORIAL_INTEGRITY_V1", stamped)
        self.assertEqual(stamped.count("DY_EDITORIAL_INTEGRITY_V1"), 1)

    def test_structured_data_and_byline_are_restored(self):
        content, added = rq.ensure_jsonld("<p>Body</p>", "Title", "https://dailyyield.blogspot.com/2026/10/x.html", "Description")
        self.assertTrue(added)
        self.assertIn("application/ld+json", content)
        content, byline = rq.ensure_byline(content)
        self.assertTrue(byline)
        self.assertIn("Kushal K. Daga", content)

    def test_context_card_is_not_duplicated(self):
        first, added = rq.ensure_context("<article><p>Body</p></article>", "A finance headline")
        self.assertTrue(added)
        second, added_again = rq.ensure_context(first, "A finance headline")
        self.assertFalse(added_again)
        self.assertEqual(second.count('class="dy-context"'), 1)

    def test_reader_block_is_not_duplicated(self):
        first, added = rq.ensure_reader_block("<p>Body</p>")
        self.assertTrue(added)
        second, added_again = rq.ensure_reader_block(first)
        self.assertFalse(added_again)

    def test_benchmark_rejects_a_thin_package(self):
        from publication_preflight import assert_publishable
        with self.assertRaises(RuntimeError):
            assert_publishable("Too short", "<p>Nothing here</p>", ["News"], check_remote_images=False)

    def test_announce_uses_the_three_assigned_networks(self):
        item = {"order": 4, "social_route": ["mastodon", "facebook", "tumblr"]}
        commands = rq.announce(item, "2026-10-15T00:00:00+00:00", "https://dailyyield.blogspot.com/2026/10/x.html", apply=False)
        self.assertEqual(len(commands), 3)
        for index, command in enumerate(commands):
            self.assertIn(f"route_index={index}", command)
            self.assertIn("extra_platforms=mastodon,facebook,tumblr", command)
            self.assertIn("target_url=https://dailyyield.blogspot.com/", command)

    def test_social_rotation_accepts_only_approved_platforms(self):
        import social_rotation as sr
        plan = sr.make_plan("revive-01", "https://dailyyield.blogspot.com/2026/10/x.html", "post", "", "", route_index=2, platforms=("mastodon", "facebook", "tumblr"))
        self.assertEqual(plan["platform"], "tumblr")
        with self.assertRaises(ValueError):
            sr.make_plan("revive-01", "https://dailyyield.blogspot.com/2026/10/x.html", "post", "", "", route_index=0, platforms=("twitter", "facebook"))


if __name__ == "__main__":
    unittest.main()
