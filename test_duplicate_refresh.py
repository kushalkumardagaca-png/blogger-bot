#!/usr/bin/env python3
"""Duplicates are answered with fresh material, not with deletions.

Owner rule, 20 October 2026: 21 articles a day are maintained, so the nightly job may not shrink
the site. These cases prove the four things that make that safe - nothing is deleted, both posts
are archived before either is written, the new wording comes out of the post's own sentences, and
the replacement title cannot collide with another live headline.
"""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import duplicate_refresh as refresh

SHARED = "This article walks through the same eight ways to sell a property in India."
TWIN_ONLY = "Only this later edition records the registrar deadline of 21 October and the revised stamp duty note."


def post(pid: str, slug: str, content: str, title: str = "Sold property eight different ways to",
         published: str = "2026-10-14T05:00:00.000+05:30") -> dict:
    return {"id": pid, "title": title, "published": published,
            "url": f"https://dailyyield.blogspot.com/2026/10/{slug}.html", "content": content}


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = (refresh.ROOT, refresh.OUT, refresh.MD, refresh.ARCHIVE)
        refresh.ROOT, refresh.OUT, refresh.MD = self.tmp, self.tmp / "r.json", self.tmp / "r.md"
        refresh.ARCHIVE = self.tmp / "archive"
        # the survivor is the plain republication; the twin is the copy that carries one extra
        # paragraph, and that paragraph is the only fresh material this job is allowed to use
        self.original = post("1", "sold-property-eight-different-ways-to", f"<p>{SHARED}</p>")
        self.twin = post("2", "sold-property-eight-different-ways-to_0586614503",
                         f"<p>{SHARED}</p><p>{TWIN_ONLY}</p>", published="2026-10-15T09:30:00.000+05:30")

    def tearDown(self):
        refresh.ROOT, refresh.OUT, refresh.MD, refresh.ARCHIVE = self.saved

    def run_with(self, posts, *extra):
        fixture = self.tmp / "fixture.json"
        fixture.write_text(json.dumps({"posts": posts, "bodies": {}}), encoding="utf-8")
        with mock.patch("sys.argv", ["refresh.py", "--fixture", str(fixture), *extra]):
            self.assertEqual(refresh.main(), 0)
        return json.loads(refresh.OUT.read_text(encoding="utf-8"))


class Differentiation(Harness):
    def test_the_twin_gets_its_own_headline_and_a_note_built_from_its_own_words(self):
        report = self.run_with([self.original, self.twin])
        row = report["examples"][0]
        self.assertEqual(row["afterTitle"], "Sold property eight different ways to — 15 October 2026 edition")
        self.assertIn("registrar deadline", row["block"])
        self.assertNotIn("Earlier edition", row["block"])

    def test_a_verbatim_copy_is_marked_as_an_earlier_edition_and_links_forward(self):
        copy = post("2", "sold-property-eight-different-ways-to_0586614503", f"<p>{SHARED}</p>",
                    published="2026-10-15T09:30:00.000+05:30")
        report = self.run_with([self.original, copy])
        row = report["examples"][0]
        self.assertEqual(row["uniqueSentences"], 0)
        self.assertIn("Earlier edition", row["block"])
        self.assertIn("sold-property-eight-different-ways-to.html", row["block"],
                      "the reader is sent to the live version, not left on a stale page")

    def test_a_replacement_title_never_collides_with_another_live_headline(self):
        taken = {"sold property eight different ways to — 15 october 2026 edition"}
        title = refresh.new_title("Sold property eight different ways to",
                                  {"published": "2026-10-15T09:30:00.000+05:30"}, taken)
        self.assertNotIn(title.lower(), taken)
        self.assertTrue(title.endswith("(2)"))


class Restraint(Harness):
    def test_nothing_is_deleted_by_this_job_at_all(self):
        source = pathlib.Path(refresh.__file__).read_text(encoding="utf-8")
        self.assertNotIn("DELETE", source, "the owner asked for a refresh, not a smaller website")
        self.assertIn('method="PATCH"', source, "the only write is the twin itself")
        self.assertTrue((pathlib.Path(__file__).with_name("test_duplicate_refresh.py")).exists())

    def test_the_default_run_writes_nothing(self):
        calls = []
        with mock.patch.object(refresh, "api_call", lambda *a, **k: calls.append((a, k)) or {}):
            report = self.run_with([self.original, self.twin])
        self.assertEqual(report["mode"], "AUDIT_ONLY")
        self.assertEqual(report["refreshed"], [])
        self.assertEqual(report["deletions"], 0)
        self.assertEqual(calls, [], "an audit must not call Blogger")
        self.assertFalse(refresh.ARCHIVE.exists())

    def test_the_archive_comes_first_and_a_failed_archive_stops_the_run(self):
        calls = []

        def fake_api(token, url, method="GET", body=None):
            calls.append((method, url))
            if "view=RAW" in url:
                raise RuntimeError("blogger is refusing reads")
            return {}

        with mock.patch.object(refresh, "api_call", fake_api):
            report = self.run_with([self.original, self.twin], "--apply")
        self.assertEqual(report["refreshed"], [], "no write may happen without a backup")
        self.assertTrue(all(method != "PATCH" for method, _ in calls), "and no PATCH was attempted")
        self.assertIn("archiving failed", report["failed"][0]["error"])
        self.assertIn("archived before it is rewritten", report["stopped"])

    def test_a_successful_run_backs_up_then_writes_title_and_content(self):
        calls = []

        def fake_api(token, url, method="GET", body=None):
            calls.append((method, url, body))
            return {"id": "2", "title": "Sold property eight different ways to",
                    "content": f"<p>{SHARED}</p><p>{TWIN_ONLY}</p>", "labels": []}

        with mock.patch.object(refresh, "api_call", fake_api):
            report = self.run_with([self.original, self.twin], "--apply")
        self.assertEqual(len(report["refreshed"]), 1)
        self.assertTrue((refresh.ARCHIVE / "2.json").exists())
        patch = [entry for entry in calls if entry[0] == "PATCH"]
        self.assertEqual(len(patch), 1, "one write for the twin, none for the survivor")
        self.assertIn("What only this edition carries", patch[0][2]["content"])
        self.assertTrue(patch[0][2]["content"].endswith(f"<p>{TWIN_ONLY}</p>"),
                        "the original text is kept, not replaced")
        self.assertEqual(report["deletions"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
