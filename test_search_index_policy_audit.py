#!/usr/bin/env python3
"""Proof for the search index policy audit: what it must see, and what it must never do.

Nothing here touches the network. Every corpus, sitemap, robots.txt and rendered page the audit reads
in production is handed to it as a string by `FakeNet` below, so a regression in a detector shows up as
a failed test rather than as a quiet PASS on the live site.

The fixtures are deliberately small copies of real defects found on Daily Yield on 22 October 2026:
a utility page inside a sitemap, a headline clipped onto a comma, a possessive cut in half, the same
article published at two numbered slugs, an image with no alt text, and two country editions whose text
is the same document twice.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from unittest import mock

import search_index_policy_audit as audit

BLOG = audit.BLOG
BODY = " ".join(f"settlement figure {index} moved on the desk before the bell" for index in range(90))


def entries(*items: dict) -> dict:
    """Wrap bare entries the way Blogger's JSON feed does."""
    return {"feed": {"entry": list(items)}}


def one(url: str, title: str, body: str | None = None) -> dict:
    """One published entry, as the feed hands it over.

    The default body carries the headline's own words, because the audit also measures whether the
    opening pays off the title - a fixture that fails that rule would make the clean case unclean.
    """
    return {"title": {"$t": title},
            "link": [{"rel": "alternate", "href": url}],
            "content": {"$t": body if body is not None
                        else f"<p>{title} moved across the desk, and here is the evidence: {BODY}</p>" * 2},
            "published": {"$t": "2026-10-21T09:00:00.000-07:00"},
            "updated": {"$t": "2026-10-21T09:00:00.000-07:00"},
            "category": [{"term": "Markets"}]}


def entry(url: str, title: str, body: str | None = None, *, kind: str = "posts") -> dict:
    return {"feed": {"entry": [{
        "title": {"$t": title},
        "link": [{"rel": "alternate", "href": url}],
        "content": {"$t": body if body is not None else f"<p>{BODY}</p>" * 4},
        "published": {"$t": "2026-10-21T09:00:00.000-07:00"},
        "updated": {"$t": "2026-10-21T09:00:00.000-07:00"},
        "category": [{"term": "Markets"}],
    }]}}


def sitemap(urls: list[str]) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/'
            'sitemap/0.9">' + "".join(f"<url><loc>{u}</loc><lastmod>2026-10-21</lastmod></url>" for u in urls)
            + "</urlset>")


def page(url: str, title: str = "Gold rate today in India", *, canonical: str | None = "",
         robots: str = "", images: str = "", extra: str = "") -> str:
    return (f"<html><head><title>{title}</title>"
            f'<meta name="description" content="Gold rate today in India, checked against MCX and LBMA.">'
            + (f'<link rel="canonical" href="{canonical}">' if canonical is not None else "")
            + (f'<meta name="robots" content="{robots}">' if robots else "")
            + f"</head><body><h1>{title}</h1><p>{BODY}</p>{images}{extra}</body></html>")


class FakeNet:
    """Stand in for the whole crawl surface, and remember every request the audit made."""

    def __init__(self, pages: dict[str, str], feeds: dict[str, dict], *, robots: str = "") -> None:
        self.pages = pages
        self.feeds = feeds
        self.robots = robots
        self.seen: list[str] = []

    def __call__(self, url: str, timeout: int = 45) -> tuple[int, str]:
        self.seen.append(url)
        if url.endswith("/robots.txt"):
            return 200, self.robots or "User-agent: *\nAllow: /\n"
        for kind, payload in self.feeds.items():
            if f"/feeds/{kind}/default" in url:
                start = int(re.search(r"start-index=(\d+)", url).group(1))
                return (200, json.dumps(payload)) if start == 1 else (200, json.dumps({"feed": {"entry": []}}))
        for path in ("/sitemap.xml", "/sitemap-pages.xml"):
            if url.endswith(path):
                if path in self.feeds:
                    return 200, self.feeds[path][1]
                return 200, sitemap(sorted(self.pages))
        if url in self.pages:
            return 200, self.pages[url]
        return 404, ""


def clean_setup() -> tuple[FakeNet, dict]:
    post = f"{BLOG}/2026/10/gold-rate-october.html"
    home = f"{BLOG}/"
    pages = {home: page(home, "Daily Yield - personal finance and markets"),
             post: page(post, "Gold rate today in India")}
    # long enough to clear the thin line on purpose: a clean fixture has to be clean, or the test for
    # "no violations" proves nothing
    gold = ("<p>Gold rate today in India rose with bullion in London and the rupee eased against the "
            "dollar, so the MCX contract settled higher while the premium over spot narrowed to a "
            "dollar and a half per ten grams, and jewellers reported the wedding order book filling "
            "faster than the previous month.</p>")
    about = ("<p>Daily Yield is written by a chartered accountant who covers rates, funds and household "
             "money, every claim is tied to a named source, the desk publishes no sponsored posts, and "
             "the correction policy sits on this page so a reader can see what was wrong and when it was "
             "fixed rather than trusting an unmarked rewrite.</p>")
    feeds = {"posts": entries(one(post, "Gold rate today in India", gold * 10)),
             "pages": entries(one(f"{BLOG}/p/about.html", "About Daily Yield", about * 10))}
    feeds["/sitemap.xml"] = (None, sitemap([post]))
    # the pages sitemap lists only the page: Blogger never offers the homepage in a sitemap, and a
    # URL listed but not published is itself a violation the audit has to catch
    feeds["/sitemap-pages.xml"] = (None, sitemap([f"{BLOG}/p/about.html"]))
    net = FakeNet(pages, feeds, robots="User-agent: *\nAllow: /\nSitemap: "
                  + f"{BLOG}/sitemap.xml\nSitemap: {BLOG}/sitemap-pages.xml\n")
    return net, pages


class Detectors(unittest.TestCase):
    """Each rule must fire on its defect and stay quiet on sound input."""

    def test_cut_titles_are_caught_in_both_shapes_we_actually_shipped(self):
        # a comma left behind by the clip, and a headline that stops inside a possessive
        self.assertTrue(audit.title_is_cut("Student Loan Interest Rates: Federal, Private,"))
        self.assertTrue(audit.title_is_cut("Billionaire Mukesh Ambani launches India’s"))
        for honest in ("Gold rate today in India", "What a 30-year loan really costs",
                       "Markets today: Asia opens higher"):
            self.assertFalse(audit.title_is_cut(honest), honest)

    def test_a_numbered_rerun_is_one_article_at_two_urls(self):
        rows = [{"slug": "india-news-2026-10-18.html", "url": f"{BLOG}/2026/10/india-news-2026-10-18.html"},
                {"slug": "india-news-2026-10-18_01443792159.html",
                 "url": f"{BLOG}/2026/10/india-news-2026-10-18_01443792159.html"},
                {"slug": "brazil-2026-10-18.html", "url": f"{BLOG}/2026/10/brazil-2026-10-18.html"}]
        found = audit.rerun_twins(rows)
        self.assertEqual(len(found), 1, found)
        self.assertIn("india-news-2026-10-18", found[0])
        self.assertNotIn("brazil", found[0])
        self.assertEqual(audit.rerun_twins(rows[:1]), [])

    def test_similarity_is_jaccard_so_boilerplate_cannot_fake_a_duplicate(self):
        shared = " ".join(f"shared clause {index}" for index in range(40))
        short = f"{shared} end"
        long = shared + " " + " ".join(f"distinct finding {index}" for index in range(400))
        small, big = audit.shingles(short.lower()), audit.shingles(long.lower())
        containment = len(small & big) / max(1, min(len(small), len(big)))
        jaccard = len(small & big) / max(1, len(small | big))
        self.assertGreater(containment, 0.9, "the old formula would have called this a duplicate")
        self.assertLess(jaccard, audit.SHINGLE_DUPLICATE_RATIO, "the shipped formula does not")

    def test_a_page_shorter_than_a_ruling_is_never_judged(self):
        self.assertGreaterEqual(audit.SHINGLE_MIN_SHARDS, 20)
        self.assertLess(len(audit.shingles("one two three")), audit.SHINGLE_MIN_SHARDS)

    def test_image_alt_text_rules(self):
        markup = ('<img src="/a.jpg" alt="Traders watch a screen on the BSE floor">'
                  '<img src="/b.jpg" alt=""><img src="/c.jpg">')
        self.assertEqual(len(audit.image_tags(markup)), 3)
        self.assertEqual(len(audit.images_without_alt(markup)), 2)

    def test_opaque_file_names_are_named_not_assumed(self):
        self.assertTrue(audit.opaque_file_name("https://bp.blogspot.com/abcd1234ef567890.jpg"))
        self.assertFalse(audit.opaque_file_name("https://cdn.example.com/gold-rate-october-2026.png"))

    def test_sitemap_entries_are_read_as_urls(self):
        raw = sitemap([f"{BLOG}/a.html", f"{BLOG}/b.html"])
        self.assertEqual(audit.sitemap_locations(raw), [f"{BLOG}/a.html", f"{BLOG}/b.html"])
        self.assertEqual(audit.sitemap_locations("<html>nope</html>"), [])


class Register(unittest.TestCase):
    def test_an_advisory_is_printed_but_never_counted_as_a_violation(self):
        rows: list[dict] = []
        audit.register(rows, "host-renames-images", "Bing §12", False, "detail", ["u"], "platform",
                       advisory=True)
        audit.register(rows, "thin-url", "Bing §11", False, "detail", ["u2"], "repo")
        self.assertTrue(rows[0]["advisory"])
        self.assertFalse(rows[1]["advisory"])
        self.assertEqual([row for row in rows if row["status"] == "FAIL" and not row["advisory"]],
                         [rows[1]])

    def test_a_passing_advisory_is_not_marked(self):
        rows: list[dict] = []
        audit.register(rows, "ok", "Bing §12", True, "detail", [], "platform", advisory=True)
        self.assertEqual(rows[0]["status"], "PASS")
        self.assertFalse(rows[0]["advisory"])

    def test_offenders_are_capped_but_the_count_is_not(self):
        rows: list[dict] = []
        audit.register(rows, "many", "Bing §6", False, "detail", [f"u{index}" for index in range(60)],
                       "repo", cap=12)
        self.assertEqual(len(rows[0]["offenders"]), 12)
        self.assertEqual(rows[0]["offenderCount"], 60)


class WholeAudit(unittest.TestCase):
    """Run the real audit() over a fake web, both clean and dirty."""

    def run_audit(self, net: FakeNet) -> dict:
        """Drive the shipped audit() end to end against the fake web, with no sleeping and no socket."""
        with mock.patch.object(audit, "get", net), \
                mock.patch.object(audit.time, "sleep", lambda *_: None):
            return audit.audit()

    def test_a_conforming_site_reports_no_violations(self):
        net, _ = clean_setup()
        report = self.run_audit(net)
        failing = [row for row in report["checks"] if row["status"] == "FAIL" and not row["advisory"]]
        self.assertEqual([row["id"] for row in failing], [],
                         json.dumps({row["id"]: row["detail"] for row in failing}, indent=1))
        self.assertEqual(report["summary"]["fail"], 0)
        self.assertIn("every-url-carries-a-date", [row["id"] for row in report["checks"]])

    def test_the_defects_we_actually_had_are_all_seen(self):
        post = f"{BLOG}/2026/10/gold-rate-october.html"
        cut = f"{BLOG}/2026/10/student-loan-interest-rates-federal.html"
        twin_a = f"{BLOG}/2026/10/asia-news-2026-10-18.html"
        twin_b = f"{BLOG}/2026/10/asia-news-2026-10-18_01443792159.html"
        about = f"{BLOG}/p/about.html"
        utility = f"{BLOG}/p/indexnow-key.html"
        filler = "<p>" + BODY + "</p>"
        photo = {**one(post, "Gold rate today in India"),
                 "content": {"$t": filler + '<p><img src="https://bp.blogspot.com/x/photo-1.jpg"></p>'}}
        feeds = {
            "posts": entries(
                photo,
                one(cut, "Student Loan Interest Rates: Federal, Private,"),
                one(twin_a, "Asia Pacific Finance News — 18 October 2026"),
                one(twin_b, "Asia Pacific Finance News — 18 October 2026")),
            "pages": entries(
                one(about, "ABOUT US", "<p>one two three</p>"),
                one(utility, "IndexNow key", "<p>key</p>")),
            "/sitemap.xml": (None, sitemap([post, cut, twin_a, twin_b, utility, about])),
            "/sitemap-pages.xml": (None, sitemap([about, utility, f"{BLOG}/"])),
        }
        pages = {f"{BLOG}/": page(f"{BLOG}/", "Daily Yield - personal finance and markets"),
                 post: page(post, images='<img src="https://bp.blogspot.com/q/hash0000aaaa1111bbbb.jpg">'),
                 cut: page(cut, "Student Loan Interest Rates: Federal, Private,"),
                 utility: page(utility, "IndexNow key", robots="noindex"),
                 about: page(about, "ABOUT US")}
        net = FakeNet(pages, feeds, robots=f"User-agent: *\nAllow: /\nSitemap: {BLOG}/sitemap.xml\n"
                      f"Sitemap: {BLOG}/sitemap-pages.xml\n")
        report = self.run_audit(net)
        seen = {row["id"]: row for row in report["checks"]}
        for check_id in ("no-utility-pages-in-sitemaps", "titles-descriptive-and-complete",
                         "titles-not-shouted-in-caps", "no-duplicate-titles-across-urls",
                         "content-not-thin", "no-double-published-urls",
                         "images-described-not-decorated", "no-blocking-robots-meta"):
            self.assertEqual(seen[check_id]["status"], "FAIL",
                             f"{check_id} missed the defect it exists to find: {seen[check_id]['detail']}")
        self.assertIn(utility, "".join(seen["no-utility-pages-in-sitemaps"]["offenders"]))
        self.assertIn(cut, "".join(seen["titles-descriptive-and-complete"]["offenders"]))
        # an advisory is shown without pretending the site failed a rule it cannot change
        self.assertEqual(seen["sitemap-freshness-signals"]["fixableBy"], "platform")
        self.assertIn("URLs that must change", audit.render_markdown(report))

    def test_the_audit_reads_and_never_writes_anywhere(self):
        net, _ = clean_setup()
        self.run_audit(net)
        self.assertTrue(net.seen, "the audit must actually have read something")
        src = Path(audit.__file__).read_text(encoding="utf-8")
        self.assertIn("Request(url, headers=", src)   # one GET helper, no other client
        self.assertEqual(len(re.findall(r"urllib\.request\.Request\(", src)), 1,
                         "only the shared GET helper may open a connection")
        # a request that is not a GET, or a token in the source, would put the audit inside the site
        self.assertNotIn("method=", src.replace('method="GET"', ""))
        self.assertNotIn("blogger.googleapis.com", src)
        self.assertNotIn("access_token", src)
        self.assertNotIn("serviceaccount", src)
        self.assertEqual(audit.SITEMAPS, tuple(f"{BLOG}{path}" for path in
                                               ("/sitemap.xml", "/sitemap-pages.xml")))
        for url in net.seen:
            self.assertTrue(url.startswith(BLOG), url)


class Mapping(unittest.TestCase):
    """The guideline numbers have to stay attached to the rules, or the report stops meaning anything."""

    def test_every_numbered_duty_the_site_can_answer_is_cited(self):
        src = Path(audit.__file__).read_text(encoding="utf-8")
        for section in ("§2", "§3", "§5", "§6", "§8", "§9", "§10", "§11", "§12", "§13", "§14",
                        "§15", "§17", "§18", "§19", "§20", "§21"):
            self.assertIn(section, src, f"Bing {section} is no longer cited by any check")
        self.assertIn("support.google.com/webmasters/answer/9012289", src)

    def test_the_report_names_what_a_feed_cannot_answer(self):
        gaps = Path(audit.__file__).read_text(encoding="utf-8")
        for topic in ("Cloaking", "Core Web Vitals", "Ad density", "advisory", "notAnswerableHere"):
            self.assertIn(topic, gaps, f"{topic} must stay declared as out of reach, not silently skipped")

    def test_the_offline_self_test_still_guards_the_detectors(self):
        self.assertEqual(audit.run_check(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
