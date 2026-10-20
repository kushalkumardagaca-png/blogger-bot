#!/usr/bin/env python3
"""The News checker must report the defects the site really has, and never claim zero from a failure."""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import google_news_readiness as news

FEED = """<rss><channel>
<item><title>Payoneer: How Stablecoin is Scaling in Cross-B</title>
<link>https://dailyyield.blogspot.com/2026/10/payoneer-how-stablecoin-is-scaling-in.html</link>
<guid>x</guid><pubDate>Tue, 20 Oct 2026 10:45:09 +0000</pubDate>
<description>Stablecoins are being used to settle cross-border invoices faster than correspondent banks.</description>
<category>Banking Payments &amp; Fintech</category><category>Master Article</category>
<author>noreply@blogger.com (Kushal K. Daga)</author></item>
<item><title>Short</title><link>https://dailyyield.blogspot.com/?m=1</link>
<description>tiny</description></item>
</channel></rss>"""

PAGE = """<html><head><title>Payoneer: How Stablecoin is Scaling in Cross-B</title></head>
<body><h1>Payoneer: How Stablecoin is Scaling in Cross-B</h1><p>body</p></body></html>"""


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.evidence = pathlib.Path(tempfile.mkdtemp())
        (self.tmp / "feed.xml").write_text(FEED, encoding="utf-8")
        (self.tmp / "page-1.html").write_text(PAGE, encoding="utf-8")
        self.saved = (news.OUT, news.MD)
        news.OUT, news.MD = self.evidence / "r.json", self.evidence / "r.md"

    def tearDown(self):
        news.OUT, news.MD = self.saved

    def run_check(self):
        with mock.patch("sys.argv", ["google_news_readiness.py", "--fixture-dir", str(self.tmp)]):
            self.assertEqual(news.main(), 0)
        return json.loads(news.OUT.read_text(encoding="utf-8"))

    def test_a_cut_headline_is_found_in_the_feed_and_counted(self):
        report = self.run_check()
        self.assertEqual(report["status"], "MEASURED")
        self.assertEqual(report["feed"]["feedItems"], 2)
        self.assertEqual(report["feed"]["issueCounts"]["truncatedHeadline"], 1)
        self.assertEqual(report["feed"]["issueCounts"]["headlineTooShort"], 1)
        self.assertEqual(report["feed"]["issueCounts"]["nonCanonicalLink"], 1)

    def test_a_page_without_a_picture_or_a_head_description_is_reported(self):
        report = self.run_check()
        self.assertIn("noOpenGraphImage", report["pages"][0]["issues"])
        self.assertIn("noHeadDescription", report["pages"][0]["issues"])
        self.assertEqual(report["pageIssueCounts"]["noOpenGraphImage"], 1)
        gaps = {row["gap"] for row in report["blockersForPublisherCenter"]}
        self.assertIn("truncatedHeadline", gaps)

    def test_an_unreadable_feed_is_not_reported_as_a_clean_bill(self):
        empty = pathlib.Path(tempfile.mkdtemp())
        with mock.patch("sys.argv", ["google_news_readiness.py", "--fixture-dir", str(empty)]):
            self.assertEqual(news.main(), 0)
        report = json.loads(news.OUT.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "FEED_UNREADABLE")
        self.assertNotIn("issueCounts", report["feed"])
        self.assertIn("nothing is assumed", news.MD.read_text(encoding="utf-8"))

    def test_the_checker_is_read_only(self):
        source = pathlib.Path(news.__file__).read_text(encoding="utf-8")
        self.assertNotIn("googleapis.com/blogger", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("PATCH", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
