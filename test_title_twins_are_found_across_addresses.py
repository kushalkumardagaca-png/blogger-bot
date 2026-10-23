#!/usr/bin/env python3
"""A duplicate the auditor cannot see is a duplicate the owner finds instead.

On 23 October 2026 the blog carried "Americas Finance News — 22 October 2026" twice, one copy at
`americas-finance-news-2026-10-23.html` and one at `americas-finance-news-2026-10-23_0361840868.html`.
The whole-site audit reported `duplicate_groups_found: []`, because it grouped duplicates by URL and a
double publication never shares a URL — Blogger makes room for the second copy by renaming it. The
owner saw it on the post list before any report did.

These cases pin the two halves of the fix: a pair is found by title as well as by address, and the
title pass only ever applies to a *fresh* pair, so the same-title pages the blog has accumulated for
months stay where they are for the owner to decide about.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
os.environ.setdefault("BLOGGER_BLOG_ID", "0")
sys.path.insert(0, str(ROOT))

import harden_live_corpus as corpus  # noqa: E402

TITLE = "Americas Finance News \u2014 22 October 2026"
BODY = "<p>" + " ".join(f"sentence {i} about markets and rates" for i in range(90)) + "</p>"


def post(pid, title, slug, when=None, body=BODY):
    when = when or dt.datetime.now(dt.timezone.utc)
    return {"id": pid, "title": title, "content": body, "labels": ["News"],
            "url": f"https://dailyyield.blogspot.com/2026/10/{slug}.html",
            "published": when.isoformat().replace("+00:00", "Z")}


class TwinDetection(unittest.TestCase):
    def test_the_same_edition_at_two_addresses_is_found(self):
        rows = [post("1", TITLE, "americas-finance-news-2026-10-23"),
                post("2", TITLE, "americas-finance-news-2026-10-23_0361840868")]
        groups = [g for g in corpus.twin_groups(rows, {}) if g["kind"] == "title"]
        self.assertEqual(len(groups), 1, groups)
        group = groups[0]
        self.assertTrue(group["recent"], "a pair published today must be treated as an accident to repair")
        self.assertEqual(group["remove_ids"], ["2"], "the copy Blogger had to rename is the newer one")
        self.assertEqual(group["keep_url"], rows[0]["url"], "the first address is the one a reader was sent to")

    def test_an_old_same_title_pair_is_reported_but_never_touched(self):
        months = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=40)
        rows = [post("1", "Quarterly Banking Commentary On Deposit Rates", "banking-a", months),
                post("2", "Quarterly Banking Commentary On Deposit Rates", "banking-b", months)]
        groups = [g for g in corpus.twin_groups(rows, {}) if g["kind"] == "title"]
        self.assertEqual(len(groups), 1)
        self.assertFalse(groups[0]["recent"],
                         "40 days old is history, not a double publication; bulk removal is the owner's act")

    def test_two_editions_of_the_same_desk_are_not_a_twin(self):
        rows = [post("1", "India Finance News \u2014 22 October 2026", "india-a"),
                post("2", "India Finance News \u2014 23 October 2026", "india-b")]
        self.assertEqual([g for g in corpus.twin_groups(rows, {}) if g["kind"] == "title"], [],
                         "a desk reuses its headline every day; the prose decides, not the title")

    def test_similar_title_and_different_prose_is_not_a_twin(self):
        rows = [post("1", TITLE, "americas-a", body=BODY),
                post("2", TITLE, "americas-b", body="<p>" + " ".join(f"other text {i}" for i in range(90)) + "</p>")]
        self.assertEqual([g for g in corpus.twin_groups(rows, {}) if g["kind"] == "title"], [])

    def test_identical_addresses_still_group_as_before(self):
        rows = [post("1", TITLE, "americas-finance-news-2026-10-23"),
                post("2", TITLE, "americas-finance-news-2026-10-23")]
        class Resp:
            def json(self):
                return {"id": "1"}
        original = corpus.call
        corpus.call = lambda *a, **k: Resp()
        try:
            groups = [g for g in corpus.twin_groups(rows, {}) if g["kind"] == "url"]
        finally:
            corpus.call = original
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["keep_id"], "1", "Blogger's own canonical answer decides which copy survives")

    def test_the_green_gate_definition_was_not_widened(self):
        # `exact_duplicate_groups` is what the publication gate reads. If the title pass leaked into
        # it, every desk in the country would be held behind a cosmetic backlog - which is the
        # mistake of 23 October morning, repeated at a larger scale.
        rows = [post("1", TITLE, "americas-a"), post("2", TITLE, "americas-b")]
        self.assertEqual(corpus.exact_duplicate_groups(rows, {}), [])


class PolicyRelease(unittest.TestCase):
    def test_the_release_exists_and_refuses_deletion(self):
        import json
        policy = json.loads((ROOT / "SITE_CHANGE_POLICY.json").read_text(encoding="utf-8"))
        entry = [e for e in policy.get("releasedCorrections", []) if e.get("action") == "duplicate_twin_retirement"]
        self.assertEqual(len(entry), 1)
        scope = entry[0]["scope"].casefold()
        for must in ("never a delete", "48 hours", "draft", "before-image"):
            self.assertIn(must, scope, f"the released scope must say '{must}'")
        self.assertTrue(policy.get("frozen"), "releasing this write must not lift the freeze itself")


if __name__ == "__main__":
    unittest.main()
