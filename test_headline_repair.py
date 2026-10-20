#!/usr/bin/env python3
"""Proof for every headline this job wants to touch: it must be the article's own words.

Runs on a fixture. Nothing here talks to Blogger or to the blog.
"""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import headline_repair as repair


def post(pid: str, title: str, headings=(), slug: str = "a-post", extra: str = "") -> dict:
    body = extra + "".join(f"<h2>{head}</h2><p>word word word word word word.</p>" for head in headings)
    return {"id": pid, "title": title, "url": f"https://dailyyield.blogspot.com/2026/10/{slug}.html",
            "body": body, "content": body, "published": "2026-10-20T10:45:09.000+00:00"}


CUT = "Payoneer: How Stablecoin is Scaling in Cross-B"           # 46 characters, ends mid-word
FULL = "Payoneer: How Stablecoin is Scaling in Cross-Border Payments"


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = (repair.ROOT, repair.OUT, repair.MD, repair.BACKUP)
        repair.ROOT, repair.OUT, repair.MD = self.tmp, self.tmp / "repair.json", self.tmp / "repair.md"
        repair.BACKUP = self.tmp / "backup.json.gz"

    def tearDown(self):
        repair.ROOT, repair.OUT, repair.MD, repair.BACKUP = self.saved

    def run_with(self, posts, *extra):
        fixture = self.tmp / "posts.json"
        fixture.write_text(json.dumps(posts), encoding="utf-8")
        with mock.patch("sys.argv", ["headline_repair.py", "--fixture", str(fixture), *extra]):
            self.assertEqual(repair.main(), 0)
        return json.loads(repair.OUT.read_text(encoding="utf-8"))


class Warrant(Harness):
    def test_a_cut_title_is_recovered_from_the_headings_the_article_already_shows(self):
        report = self.run_with([post("a", CUT, [FULL, "Global Business Account for Cross-Border Payments"])])
        self.assertEqual(report["repairable"], 1)
        self.assertEqual(report["examples"][0]["after"], FULL)
        self.assertEqual(report["examples"][0]["before"], CUT)
        self.assertEqual(report["mode"], "AUDIT_ONLY")
        self.assertEqual(report["repaired"], [], "an audit writes nothing")

    def test_a_headline_written_short_on_purpose_is_left_alone(self):
        report = self.run_with([post("b", "Gold price today in India",
                                    ["Gold price today in India and why it moved on Tuesday"])])
        self.assertEqual(report["repairable"], 0)

    def test_an_unrelated_heading_is_never_promoted_to_a_title(self):
        report = self.run_with([post("c", CUT, ["Menu Pages", "Evidence route map", "Frequently asked questions"])])
        self.assertEqual(report["repairable"], 0)

    def test_a_recovery_that_would_create_a_duplicate_title_is_held_back(self):
        report = self.run_with([post("d", FULL, [FULL]),
                                post("e", CUT, [FULL])])
        self.assertEqual(report["repairable"], 0, "the fix must not manufacture a new duplicate")
        self.assertEqual(report["heldBackCollisions"], 1)


    def test_a_heading_that_is_itself_cut_short_cannot_repair_a_title(self):
        # the wire fed us an already-truncated headline; promoting it would just move the bug
        cut = "SpaceX, Tesla earnings to test Musk's AI spend"
        report = self.run_with([post("g", cut, ["SpaceX, Tesla earnings to test Musk\u2019s AI spending ambitions as"])])
        self.assertEqual(report["repairable"], 0)
        self.assertEqual(report["clippedTitles"], 0)

class Restraint(Harness):
    def test_the_default_run_never_calls_the_api(self):
        calls = []
        with mock.patch.object(repair, "api", lambda *a, **k: calls.append((a, k)) or {"kind": "unused"}):
            report = self.run_with([post("f", CUT, [FULL])])
        self.assertEqual(report["selectedThisRun"], 1)
        self.assertEqual(report["repaired"], [])
        self.assertEqual(calls, [], "an audit must not touch Blogger")
        self.assertFalse(repair.BACKUP.exists())

    def test_the_batch_cap_is_honoured(self):
        names = ("Alpha", "Beta", "Gamma", "Delta")
        posts = [post(str(index), f"{names[index % 4]} desk report shows the quarterly numbers",
                      [f"{names[index % 4]} desk report shows the quarterly numbers in detail"])
                 for index in range(4)]
        with mock.patch.object(repair, "api", lambda *a, **k: {}):
            report = self.run_with(posts, "--apply", "--max", "2")
        self.assertEqual(report["repairable"], 4)
        self.assertEqual(report["selectedThisRun"], 2, "one run must not rewrite the whole blog")
        self.assertTrue(repair.BACKUP.exists(), "posts must be backed up before a title is written")


class Clip(unittest.TestCase):
    def test_headline_clipping_breaks_on_words_not_at_the_limit(self):
        import master_v3_generator as gen
        source = FULL + " and Treasury Float for Clients"
        clipped = gen.head_clip(source)
        self.assertLessEqual(len(clipped), 72)
        self.assertTrue(source.startswith(clipped), "clipping may only shorten, never rewrite")
        self.assertTrue(source[len(clipped)].isspace(), "a headline may not end inside a word")
        self.assertEqual(gen.head_clip("Short enough to stay"), "Short enough to stay")


if __name__ == "__main__":
    unittest.main(verbosity=2)
