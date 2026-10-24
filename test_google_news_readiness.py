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


class CutnessIsReadFromTheSentence(unittest.TestCase):
    """A listing report that guesses at defects by length cannot decide anything for a reviewer.

    The old test called every 43-to-47-character headline cut, which flagged a complete dated headline
    and passed over "Cost of living protests hit Belgium, Italy," at 43. Both questions are separate
    now: does the sentence stop where a sentence cannot stop, and is it sitting exactly on this blog's
    own 46-character title limit (the thing that shortens them in the first place)?
    """

    def test_a_complete_headline_of_ordinary_length_is_not_called_cut(self):
        for title in ("Economy, Trade & Jobs News — 21 October 2026",
                      "What a rate cut does to an FD renewal",
                      "A modest increase in bank taxes is not the end"):
            self.assertFalse(news.headline_is_cut(title), title)

    def test_the_four_ways_a_headline_readsunfinished(self):
        for title in ("Cost of living protests hit Belgium, Italy,",   # trailing comma
                      "Billionaire Mukesh Ambani launches India’s",      # dangling possessive
                      "4 Different Types of Life Insurance & How",  # function word last
                      "Markets open lower and …"):                     # ellipsis
            self.assertTrue(news.headline_is_cut(title), title)

    def test_the_length_cap_is_reported_as_our_own_limit_not_a_google_decision(self):
        at_cap = "Rowan-Cabarrus Community College to Facilitate"
        self.assertEqual(len(at_cap), news.CAP)
        self.assertTrue(news.clipped_by_our_own_cap(at_cap))
        self.assertFalse(news.clipped_by_our_own_cap("A headline of forty-five characters exactly"))

    def test_the_two_signals_are_counted_apart(self):
        rows, summary = news.check_feed(
            '<rss><channel>'
            '<item><title>Cost of living protests hit Belgium, Italy,</title>'
            '<link>https://dailyyield.blogspot.com/2026/10/a.html</link>'
            '<pubDate>Wed, 21 Oct 2026 05:00:00 +0000</pubDate>'
            '<description>long enough to be shown in a listing</description>'
            '<category>News</category><author>blob (Kushal K. Daga)</author></item>'
            '<item><title>' + "x" * (news.CAP - 4) + ' end</title>'
            '<link>https://dailyyield.blogspot.com/2026/10/b.html</link>'
            '<pubDate>Wed, 21 Oct 2026 05:00:00 +0000</pubDate>'
            '<description>long enough to be shown in a listing</description>'
            '<category>News</category><author>blob (Kushal K. Daga)</author></item>'
            '</channel></rss>')
        self.assertEqual(summary["issueCounts"].get("truncatedHeadline"), 1)
        self.assertEqual(summary["issueCounts"].get("clippedByOurTitleCap"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class MetaLinesAreReadInEitherOrder(unittest.TestCase):
    """A page whose picture line reads `content=` first is not a page without a picture.

    On 24 October 2026 this job reported six pages as carrying no share picture and no description. The
    pages carried both: Blogger writes `content=` before `property=`, and the two searches here demanded
    the other order. These cases lock the reading to the fact rather than to the spelling.
    """

    HEAD_CONTENT_FIRST = ("<head><meta content='https://lh3.googleusercontent.com/a/photo=w544' property='og:image'/>"
                          "<meta content='A real summary of the page, long enough to be worth showing' name='description'/>"
                          "</head><body>x</body>")
    HEAD_PROPERTY_FIRST = ("<head><meta property='og:image' content='https://lh3.googleusercontent.com/a/photo=w544'/>"
                           "<meta name='description' content='A real summary of the page, long enough to be worth showing'/>"
                           "</head><body>x</body>")
    HEAD_WITH_NOTHING = "<head><title>nothing here</title></head><body>x</body>"

    def _issues(self, head):
        rows = news.check_pages(["https://dailyyield.blogspot.com/p/a.html"],
                                     lambda key, url: head)
        return rows[0]["issues"]

    def test_a_picture_written_the_way_blogger_writes_it_is_seen(self):
        self.assertEqual(self._issues(self.HEAD_CONTENT_FIRST), [])
        self.assertEqual(self._issues(self.HEAD_PROPERTY_FIRST), [])

    def test_a_page_that_really_has_no_picture_is_still_reported(self):
        issues = self._issues(self.HEAD_WITH_NOTHING)
        self.assertIn("noOpenGraphImage", issues)
        self.assertIn("noHeadDescription", issues)

    def test_a_short_description_is_not_counted_as_a_description(self):
        head = self.HEAD_CONTENT_FIRST.replace(
            "A real summary of the page, long enough to be worth showing", "Too short")
        self.assertIn("noHeadDescription", self._issues(head))

    def test_the_reader_returns_the_value_not_the_position(self):
        for head in (self.HEAD_CONTENT_FIRST, self.HEAD_PROPERTY_FIRST):
            self.assertEqual(news.meta_value(head, "og:image"),
                             "https://lh3.googleusercontent.com/a/photo=w544")
        self.assertEqual(news.meta_value(self.HEAD_WITH_NOTHING, "og:image"), "")
