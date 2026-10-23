#!/usr/bin/env python3
"""When two runs publish one desk, the blog must end up with one article.

At 04:45 IST on 23 October 2026 two news-desk runs were alive at once. Each read the tracker at
checkout, and both saw "americas: not yet published today"; the duplicate-safe scan in front of
draft creation reads only *live* posts, so neither run could see the other mid-flight. Both inserted,
Blogger renamed the second permalink, and the edition was published twice.

`reconcile_same_edition_twins` is the last line: after the final update the run re-reads the live
corpus for its own edition and, when a copy already exists, keeps the one that went live first and
reverts **its own** copy to a draft. A run is only ever allowed to undo what that same run created.
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
os.environ.setdefault("BLOGGER_BLOG_ID", "0")
sys.path.insert(0, str(ROOT))

import news_pipeline as pipeline  # noqa: E402

TITLE = "Americas Finance News \u2014 22 October 2026"
CANON = "https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-23.html"
TWIN = "https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-23_0361840868.html"


class FakeBlogger:
    """Answers the three calls the reconciliation makes, and remembers every write."""

    def __init__(self, live, mine_published):
        self.live = live
        self.mine_published = mine_published
        self.calls = []

    def __call__(self, path, token, method="GET", body=None, **kwargs):
        self.calls.append((method, path))
        if path.startswith("/posts?"):
            return {"items": self.live}
        if path.startswith("/posts/900"):          # this run's own post
            return {"id": "900", "published": self.mine_published, "url": TWIN}
        return {"id": "900"}


def art():
    return {"title": TITLE, "html": "<article>markets</article>", "slug": "americas-finance-news-2026-10-23"}


class Reconciliation(unittest.TestCase):
    def setUp(self):
        self._edition = pipeline.stored_is_this_edition
        pipeline.stored_is_this_edition = lambda stored, a: True
        self._call = pipeline.blogger_call

    def tearDown(self):
        pipeline.stored_is_this_edition = self._edition
        pipeline.blogger_call = self._call

    def test_a_second_copy_of_the_same_edition_is_found(self):
        fake = FakeBlogger([{"id": "100", "title": TITLE, "url": CANON,
                             "published": "2026-10-22T23:15:02Z"}], "2026-10-22T23:15:40Z")
        pipeline.blogger_call = fake
        copies = pipeline.live_copies_of_this_edition(art(), "t", "900")
        self.assertEqual([c["id"] for c in copies], ["100"])

    def test_the_later_copy_is_the_one_this_run_gives_up(self):
        fake = FakeBlogger([{"id": "100", "title": TITLE, "url": CANON,
                             "published": "2026-10-22T23:15:02Z"}], "2026-10-22T23:15:40Z")
        pipeline.blogger_call = fake
        url, event = pipeline.reconcile_same_edition_twins(art(), "t", "900", TWIN)
        self.assertEqual(url, CANON, "the reader-facing address stays the copy that published first")
        self.assertIn(("POST", "/posts/900/revert"), fake.calls, "this run reverts its own copy")
        self.assertEqual(event["action"].split(" ")[0:4], ["this", "run's", "duplicate", "copy"])
        self.assertNotIn("DELETE", [m for m, _ in fake.calls], "a twin is retired, never erased")

    def test_the_first_copy_keeps_what_it_published(self):
        fake = FakeBlogger([{"id": "100", "title": TITLE, "url": CANON,
                             "published": "2026-10-22T23:19:02Z"}], "2026-10-22T23:15:40Z")
        pipeline.blogger_call = fake
        url, event = pipeline.reconcile_same_edition_twins(art(), "t", "900", TWIN)
        self.assertEqual(url, TWIN, "this run published first; the other run gives its copy up")
        self.assertNotIn("POST", [m for m, _ in fake.calls], "a run never reverts a post it did not create")
        self.assertIn("earlier copy", event["action"])

    def test_a_solitary_edition_changes_nothing(self):
        fake = FakeBlogger([], "2026-10-22T23:15:40Z")
        pipeline.blogger_call = fake
        url, event = pipeline.reconcile_same_edition_twins(art(), "t", "900", CANON)
        self.assertEqual((url, event), (CANON, None))
        self.assertEqual([m for m, _ in fake.calls if m != "GET"], [])

    def test_an_edition_is_never_lost_to_a_failing_check(self):
        def boom(*a, **k):
            raise RuntimeError("Blogger is not answering")
        pipeline.blogger_call = boom
        with self.assertRaises(RuntimeError):
            pipeline.reconcile_same_edition_twins(art(), "t", "900", CANON)
        # The publish path is allowed to swallow exactly this: a live article is not
        # unpublished because a repair call failed.
        source = (ROOT / "news_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("twin reconciliation unavailable", source)
        self.assertIn("the corpus audit will resolve it", source)


class RunsCannotOverlap(unittest.TestCase):
    """The group key, not the check, is what let two runs start. These are load-bearing lines."""

    def read(self, name):
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_dispatch_runs_queue_instead_of_racing(self):
        wires = self.read("daily_news_wires.yml")
        self.assertNotIn("|| github.run_id", wires,
                         "a concurrency group that contains the run id is unique per run, so it is not a lock")
        self.assertIn("daily-yield-news-dispatch", wires)

    def test_recovery_routes_have_a_lock_at_all(self):
        for name in ("news_desk_recovery.yml", "master_slot_recovery.yml"):
            text = self.read(name)
            self.assertIn("\nconcurrency:\n", text, f"{name} can dispatch a second run of the same work")
            self.assertIn("cancel-in-progress: false", text, "a cancelled recovery is a missing edition")


if __name__ == "__main__":
    unittest.main()
