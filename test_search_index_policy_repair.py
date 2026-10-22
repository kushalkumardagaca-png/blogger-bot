#!/usr/bin/env python3
"""Proof for the one-time policy repair: what it may touch, what it must refuse, and what it never does.

The repair edits live Blogger content, so these tests are written to fail if a future change widens its
hands: a title nobody asked to change, a body that was not missing alt text, an original URL instead of
its duplicate copy, a URL other automation links to, or a single public Daily Yield pageview.

No network. The inventory is a fixture and the Blogger client is never imported by a test.
"""
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest import mock

import search_index_policy_repair as repair

SENTENCES = " ".join(f"desk note {index} settled higher before the bell today" for index in range(60))
BODY = f"<p>{SENTENCES}</p>"


def item(pid: str, title: str, url: str, *, resource: str = "posts", content: str = BODY,
         published: str = "2026-10-20T01:00:00Z") -> dict:
    return {"id": pid, "title": title, "url": url, "resource": resource, "content": content,
            "published": published, "labels": ["Markets"], "status": "LIVE"}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = (repair.OUT, repair.MD, repair.BACKUP)
        repair.OUT, repair.MD = self.tmp / "repair.json", self.tmp / "repair.md"
        repair.BACKUP = self.tmp / "backup.json.gz"

    def tearDown(self):
        repair.OUT, repair.MD, repair.BACKUP = self.saved

    def test_the_plan_fixes_the_three_defects_and_invents_nothing(self):
        items = [
            item("1", "TERMS AND CONDITIONS", "https://x/p/terms.html", resource="pages",
                 content='<h2>Terms and conditions for Daily Yield</h2>' + BODY),
            item("2", "Student Loan Interest Rates: Federal, Private,",
                 "https://x/2026/10/loans.html"),
            item("3", "Gold rate today in India", "https://x/2026/10/gold.html",
                 content=BODY + '<p><img src="https://bp.blogspot.com/a/photo-1.jpg"></p>'),
        ]
        planned = {row["url"]: row for row in repair.plan(items)}
        self.assertIn("https://x/p/terms.html", planned, "an ALL-CAPS page title must be repaired")
        self.assertEqual(planned["https://x/p/terms.html"]["toTitle"],
                         "Terms and conditions for Daily Yield")
        self.assertIn("https://x/2026/10/loans.html", planned, "a headline ending on a comma must be re-cut")
        self.assertFalse(planned["https://x/2026/10/loans.html"]["toTitle"].endswith(","))
        self.assertIn("https://x/2026/10/gold.html", planned, "an image with no alt text must be repaired")
        self.assertIn("alt text", " ".join(planned["https://x/2026/10/gold.html"]["reasons"]))
        # the body keeps every sentence it had: only the img tag changed
        self.assertIn(SENTENCES[:60], planned["https://x/2026/10/gold.html"]["content"])
        self.assertIn('alt="', planned["https://x/2026/10/gold.html"]["content"])

    def test_a_compliant_url_is_left_alone_entirely(self):
        items = [item("9", "Gold rate today in India", "https://x/2026/10/gold.html")]
        self.assertEqual(repair.plan(items), [],
                         "a needless write changes nothing a reader needs and freshens the crawl date")

    def test_two_urls_cannot_keep_one_title_after_the_repair(self):
        items = [item("1", "BANKING & PERSONAL MONEY NEWS", "https://x/a.html"),
                 item("2", "BANKING & PERSONAL MONEY NEWS", "https://x/b.html")]
        planned = repair.plan(items)
        titles = {row["toTitle"] for row in planned}
        self.assertEqual(len(titles), len(planned), f"the repair must not create a new collision: {titles}")
        self.assertTrue(all(gate_key != "" for gate_key in (row["toTitle"] for row in planned)))

    def test_an_exact_numbered_twin_is_taken_down_and_its_original_kept(self):
        # the copy carries the numeric suffix Blogger added, and its timestamp is EARLIER than the
        # original's on purpose: choosing which URL to keep by date is how a repair takes down the right
        # address and leaves the ugly one live
        items = [item("10", "Asia News — 18 October 2026", "https://x/2026/10/asia.html",
                      published="2026-10-20T01:00:00Z"),
                 item("11", "Asia News — 18 October 2026", "https://x/2026/10/asia_01443792159.html",
                      published="2026-10-18T05:00:00Z")]
        outcomes = repair.takedowns(items, protected=set())
        self.assertEqual([row["url"] for row in outcomes["unpublish"]],
                         ["https://x/2026/10/asia_01443792159.html"])
        self.assertFalse(outcomes["heldBack"])

    def test_an_edition_that_has_diverged_from_its_twin_is_not_touched(self):
        items = [item("10", "Asia News — 18 October 2026", "https://x/2026/10/asia.html"),
                 item("11", "Asia News — 18 October 2026", "https://x/2026/10/asia_01443792159.html",
                      content="<p>" + " ".join(f"reserve policy note {index} after the meeting ended"
                                               for index in range(70)) + "</p>")]
        outcomes = repair.takedowns(items, protected=set())
        self.assertEqual(outcomes["unpublish"], [])
        self.assertIn("edition rather than a duplicate", outcomes["heldBack"][0]["why"])

    def test_a_url_the_operation_links_to_is_never_taken_down(self):
        items = [item("10", "Asia News — 18 October 2026", "https://x/2026/10/asia.html"),
                 item("11", "Asia News — 18 October 2026", "https://x/2026/10/asia_01443792159.html",
                      published="2026-10-18T05:00:00Z")]
        outcomes = repair.takedowns(items, protected={"https://x/2026/10/asia_01443792159.html"})
        self.assertEqual(outcomes["unpublish"], [])
        self.assertIn("held back", outcomes["heldBack"][0]["why"])

    def test_machine_artifacts_leave_the_sitemap(self):
        items = [item("12", "http://schema.org", "https://x/2026/09/context-httpsschema.html"),
                 item("13", "GLOBAL SNAPSHOT — MOVED", "https://x/p/share-market_0718113516.html",
                      resource="pages")]
        outcomes = repair.takedowns(items, protected=set())
        self.assertEqual(len(outcomes["unpublish"]), 2)

    def test_the_indexnow_key_page_is_never_a_takedown(self):
        # taking that URL down would stop every IndexNow submission working
        items = [item("14", "indexnow-key", "https://x/p/indexnow-key.html", resource="pages")]
        self.assertEqual(repair.takedowns(items, protected=set())["unpublish"], [])


class RunModes(Fixture):
    """Audit mode must redirect every artefact it writes: a test that scribbles in the repo is a bug."""
    def test_audit_mode_writes_nothing_to_the_site(self):
        items = [item("2", "Student Loan Interest Rates: Federal, Private,", "https://x/loans.html")]
        fixture = self.tmp_of(items)
        with mock.patch("sys.argv", ["search_index_policy_repair.py", "--fixture", str(fixture)]):
            self.assertEqual(repair.main(), 0)
        self.assertTrue(str(repair.OUT).startswith(str(self.tmp)),
                        "an offline test must not write into the repository working tree")
        payload = json.loads(repair.OUT.read_text(encoding="utf-8"))
        self.assertEqual(payload["mode"], "AUDIT_ONLY")
        self.assertEqual(payload["planned"]["patches"], 1)
        self.assertEqual(payload.get("written", 0), 0)
        self.assertEqual(payload["backup"], "", "a run that wrote nothing must claim no backup")
        self.assertIn("Student Loan", payload["preview"][0]["reasons"][0])
        self.assertFalse(repair.BACKUP.exists())

    def tmp_of(self, items) -> pathlib.Path:
        path = pathlib.Path(tempfile.mkdtemp()) / "inventory.json"
        path.write_text(json.dumps(items), encoding="utf-8")
        return path


class Boundaries(unittest.TestCase):
    def test_the_client_is_the_shared_zero_view_one_and_no_public_page_is_ever_fetched(self):
        src = pathlib.Path(repair.__file__).read_text(encoding="utf-8")
        self.assertIn("from bing_seo_repair import", src)
        self.assertNotIn("import urllib.request", src,
                         "only bing_seo_repair.request_json may open a connection: it is the one that "
                         "refuses a public Daily Yield URL")
        self.assertIn("from site_change_control import stop_if_frozen", src)
        self.assertNotIn("theme", src.split('"""')[2], "this job may not touch the theme")

    def test_apply_mode_requires_the_plan_to_be_non_empty_and_is_the_only_writer(self):
        src = pathlib.Path(repair.__file__).read_text(encoding="utf-8")
        self.assertIn('if arguments.apply and (patches or unpublished):', src)
        self.assertIn("BACKUP.write_bytes", src)
        self.assertIn("PATCH_SPACING_SECONDS", src)
        self.assertIn("def self_test", src)
        self.assertEqual(repair.self_test()["status"], "OK",
                         "the module's own offline proof must stay green")


if __name__ == "__main__":
    unittest.main(verbosity=2)
