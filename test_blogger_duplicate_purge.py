#!/usr/bin/env python3
"""Deleting live posts needs proof, a cap, an archive, and a reason to keep its hands off.

These cases run against a fixture, so no request is ever made to Blogger or to the blog.
"""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import blogger_duplicate_purge as purge


def post(pid: str, title: str, slug: str, body: str = "word " * 120) -> dict:
    return {"id": pid, "title": title, "url": f"https://dailyyield.blogspot.com/2026/10/{slug}.html",
            "body": f"<p>{body}</p>", "published": "2026-10-14T05:00:00.000+05:30"}


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = (purge.ROOT, purge.OUT, purge.MD, purge.ARCHIVE, purge.EVIDENCE_FILES)
        purge.ROOT = self.tmp
        purge.OUT, purge.MD, purge.ARCHIVE = (self.tmp / "audit.json", self.tmp / "audit.md",
                                              self.tmp / "deleted_posts")
        (self.tmp / "evidence.json").write_text(json.dumps(
            {"rows": [{"url": "https://dailyyield.blogspot.com/2026/10/keep-me.html"}]}), encoding="utf-8")
        purge.EVIDENCE_FILES = ("evidence.json",)

    def tearDown(self):
        purge.ROOT, purge.OUT, purge.MD, purge.ARCHIVE, purge.EVIDENCE_FILES = self.saved

    def run_with(self, posts, *extra):
        fixture = self.tmp / "posts.json"
        fixture.write_text(json.dumps(posts), encoding="utf-8")
        with mock.patch("sys.argv", ["purge.py", "--fixture", str(fixture), *extra]):
            self.assertEqual(purge.main(), 0)
        return json.loads(purge.OUT.read_text(encoding="utf-8"))


class Detection(Harness):
    def test_two_posts_with_the_same_exact_title_are_one_group(self):
        report = self.run_with([
            post("a", "Sold property eight different ways to", "sold-property-eight-different-ways-to"),
            post("b", "Sold property eight different ways to", "sold-property-eight-different-ways-to_0586614503",
                 body="word " * 40)])
        self.assertEqual(report["titleGroups"], 1)
        self.assertEqual(report["duplicateUrls"], 1)
        self.assertEqual(report["removable"], 1)

    def test_titles_that_only_look_alike_are_left_alone(self):
        report = self.run_with([post("a", "Gold price today", "gold-price-today"),
                                post("b", "Gold price today in India", "gold-price-today-in-india")])
        self.assertEqual(report["titleGroups"], 0)
        self.assertEqual(report["removable"], 0)

    def test_a_duplicate_the_operation_already_points_at_is_held_back(self):
        # the evidence file names the _duplicate_ URL, so the purger may not touch it
        (self.tmp / "evidence.json").write_text(json.dumps({"rows": [{
            "url": "https://dailyyield.blogspot.com/2026/10/keep-me_123456.html"}]}), encoding="utf-8")
        report = self.run_with([post("a", "Keep me", "keep-me"),
                                post("b", "Keep me", "keep-me_123456", body="word " * 40)])
        self.assertEqual(report["removable"], 0, "nothing may be deleted when only protected copies exist")
        self.assertEqual(report["protectedByEvidence"], 1)
        group = report["groups"][0]
        self.assertEqual(group["deletable"], [])
        self.assertEqual([row["url"] for row in group["protected"]],
                         ["https://dailyyield.blogspot.com/2026/10/keep-me_123456.html"])
        self.assertTrue((purge.ROOT / "audit.md").exists())

class Restraint(Harness):
    def test_the_default_run_deletes_nothing(self):
        calls = []
        with mock.patch.object(purge, "api", lambda *a, **k: calls.append((a, k)) or {"kind": "unused"}):
            report = self.run_with([post("a", "Same title", "same-title"),
                                    post("b", "Same title", "same-title_777777", body="word " * 30)])
        self.assertEqual(report["mode"], "AUDIT_ONLY")
        self.assertEqual(report["removed"], [])
        self.assertEqual(calls, [], "an audit must not call the API at all")
        self.assertFalse(purge.ARCHIVE.exists())

    def test_the_batch_cap_is_honoured(self):
        posts = []
        for index in range(9):
            posts.append(post(f"keep{index}", f"Title {index}", f"title-{index}"))
            posts.append(post(f"dup{index}", f"Title {index}", f"title-{index}_99900{index}", body="word " * 20))
        report = self.run_with(posts, "--max", "3")
        self.assertEqual(report["removable"], 9)
        self.assertEqual(report["selectedThisRun"], 3, "one run must not be allowed to empty the blog")


if __name__ == "__main__":
    unittest.main(verbosity=2)
