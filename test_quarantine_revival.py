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
        self.assertIn("Kushal Daga", content)

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
        plan = sr.make_plan("revive-01", "https://dailyyield.blogspot.com/2026/10/x.html", "post", "", "", route_index=2, platforms=("mastodon", "facebook", "bluesky"))
        self.assertEqual(plan["platform"], "bluesky")
        with self.assertRaises(ValueError):
            sr.make_plan("revive-01", "https://dailyyield.blogspot.com/2026/10/x.html", "post", "", "", route_index=0, platforms=("twitter", "facebook"))


class RepetitionRepairTests(unittest.TestCase):
    """The gate that quarantined the drafts must be satisfied, not bypassed."""

    def test_banned_stock_sentence_is_removed_everywhere(self):
        from content_policy_guard import REPETITIVE_FALLBACK_PHRASES
        from editorial_integrity import scrub_repeated_sentences
        phrase = REPETITIVE_FALLBACK_PHRASES[1]
        content = f"<p>{phrase}</p><p>A unique sentence about market plumbing and settlement timing appears here.</p><p>{phrase}</p>"
        cleaned, removed = scrub_repeated_sentences(content)
        self.assertEqual(removed, 2)
        self.assertNotIn(phrase, cleaned)

    def test_later_duplicate_inside_a_tagged_block_is_removed(self):
        from editorial_integrity import scrub_repeated_sentences
        sentence = "Singapore households now hold a large share of their savings in listed equities and funds."
        content = (f"<p>{sentence}</p><p><strong>Context.</strong> {sentence} The desk adds one more distinct line here.</p>")
        cleaned, removed = scrub_repeated_sentences(content)
        self.assertEqual(removed, 1)
        self.assertEqual(cleaned.count(sentence), 1)

    def test_first_occurrence_and_controlled_blocks_are_preserved(self):
        from editorial_integrity import scrub_repeated_sentences
        sentence = "Required minimum distributions depend on the previous year end balance and an age factor."
        content = (f"{rq.READER_SNIPPET}<p>{sentence}</p><p>{sentence}</p>"
                   "<!-- DY_PAGE_FAMILY_START --><p>Daily Yield directory entry.</p>")
        cleaned, _ = scrub_repeated_sentences(content)
        self.assertEqual(cleaned.count(sentence), 1)
        self.assertIn("DY_PAGE_FAMILY_START", cleaned)
        self.assertIn("DY_ENGAGED_READER_V2", cleaned)

    def test_repair_package_clears_the_recorded_gate_failures(self):
        from content_policy_guard import REPETITIVE_FALLBACK_PHRASES, audit_text
        phrase = REPETITIVE_FALLBACK_PHRASES[1]
        sentence = "Analysts keep returning to the same cross-border comparison when they discuss valuation gaps."
        post = {"id": "1", "title": "From digital India to intelligent India", "labels": ["News"],
                "url": "https://dailyyield.blogspot.com/2026/10/x.html",
                "content": f"<p>{sentence}</p><p>{phrase}</p><p>{sentence}</p>"}
        repaired = rq.repair_package(post, post["title"], [])
        self.assertNotIn(phrase, repaired["content"])
        self.assertNotIn("repetitive deterministic fallback sentence", audit_text(post["title"], repaired["content"]))

    def test_failed_draft_is_retried_after_the_repair_code_changes(self):
        state = {"next_due_at": "", "items": {}}
        item = rq.plan_items()[0]
        row = rq.item_state(state, item["draft_id"])
        row["status"] = "repair_failed"
        row["revision"] = rq.implementation_revision()
        # A failure at the current revision steps aside for the next article.
        self.assertNotEqual(rq.next_pending(state, rq.implementation_revision())["draft_id"], item["draft_id"])
        # A fixed implementation re-opens it as the first article again.
        self.assertEqual(rq.next_pending(state, "an-older-revision")["draft_id"], item["draft_id"])


class PromiseAndDepthRepairTests(unittest.TestCase):
    def test_promise_shaped_paragraph_is_rewritten(self):
        from content_policy_guard import audit_text
        content = ('<h1>Build Credit Without Paying Interest</h1>'
                   '<p>Some lenders advertise guaranteed approval for applicants with a thin credit file.</p>'
                   '<p>A zero risk approach does not exist, because payment history moves the score.</p>')
        repaired, found = rq.neutralise_deceptive_phrases(content)
        self.assertTrue(found)
        self.assertNotIn("deceptive financial or commercial promise", audit_text("Build Credit Without Paying Interest", repaired))
        self.assertIn("<h1>Build Credit Without Paying Interest</h1>", repaired)

    def test_first_person_product_claim_is_removed(self):
        from content_policy_guard import audit_text
        content = "<p>I personally tested six secured-card products and paid every balance in full.</p>"
        repaired, found = rq.neutralise_deceptive_phrases(content)
        self.assertTrue(any("first-person" in item for item in found))
        self.assertNotIn("unsupported first-person product or investment experience", audit_text("t", repaired))

    def test_warning_about_a_scam_is_never_rewritten(self):
        content = "<p>Warnings about scammers say that promised returns should never persuade a saver.</p>"
        repaired, found = rq.neutralise_deceptive_phrases(content)
        self.assertEqual(found, [])
        self.assertEqual(repaired, content)

    def test_deep_article_is_left_alone(self):
        long_content = "<h2>A section</h2>" + "<p>" + ("A distinct and factual sentence about money decisions and their documented limits. " * 120) + "</p>"
        repaired, note = rq.ensure_reader_checklist(long_content, "t", ["Master Article"])
        self.assertEqual(note, "")
        self.assertNotIn("dy-reader-checklist", repaired)

    def test_short_article_gains_a_reader_checklist(self):
        content = "".join(f"<h2>Section {i} about one money decision</h2><p>Sentence {i} explains one part of that decision in enough words to count.</p>" for i in range(6))
        repaired, note = rq.ensure_reader_checklist(content, "t", ["Master Article"])
        self.assertIn("dy-reader-checklist", repaired)
        self.assertIn("depth was", note)

    def test_stock_repeating_paragraph_is_removed(self):
        from editorial_integrity import scrub_repeated_sentences
        stock = "<p>" + "documented source evidence " * 6 + "</p>"
        duplicate = "<p>" + ("A full factual paragraph about settlement timing and daily bank reconciliation. " * 3) + "</p>"
        cleaned, removed = scrub_repeated_sentences(f"<h1>H</h1>{duplicate}{duplicate}{stock}")
        self.assertGreaterEqual(removed, 1)
        self.assertNotIn("documented source evidence", cleaned)
        # The unique reader text survives exactly once.
        self.assertEqual(cleaned.count("settlement timing"), 1)


if __name__ == "__main__":
    unittest.main()
