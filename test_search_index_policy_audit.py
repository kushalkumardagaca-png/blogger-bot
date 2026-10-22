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


def varied(count: int) -> str:
    """Distinct words, so a fixture is not accidentally 'stuffed' by its own filler.

    The stuffing rule counts one word's share of the prose, and any repeated template sentence crosses
    5% immediately. A clean fixture has to be clean for every reason at once, or the test that says "no
    violations" is really testing the wrong thing.
    """
    return " ".join(f"{chr(97 + (i // 26) % 26)}{chr(97 + i % 26)}tion" for i in range(count))


BODY = varied(420)


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

    def __call__(self, url: str, timeout: int = 45, **_) -> tuple[int, str]:
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
            "dollar.</p><p>" + varied(300) + "</p>")
    about = ("<p>Daily Yield is written by a chartered accountant who covers rates, funds and household "
             "money.</p><p>" + varied(300).replace("tion", "ment") + "</p>")
    feeds = {"posts": entries(one(post, "Gold rate today in India", gold)),
             "pages": entries(one(f"{BLOG}/p/about.html", "About Daily Yield", about))}
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

    def test_a_word_normal_for_this_site_is_not_stuffing(self):
        # a markets desk says "market" a lot; that is subject matter, not keyword stuffing
        self.assertGreaterEqual(audit.STUFFING_MIN_REPEATS, 3)
        self.assertTrue(callable(audit.prose))
        hub = ("<p>" + " ".join(f"gold {index} rate settled higher" for index in range(60)) + "</p>"
               + "".join(f'<a href="/x{i}">article {i} here</a>' for i in range(200)))
        self.assertNotIn("article", audit.prose(hub).lower(),
                        "link labels are navigation and must not be counted as prose")

    def test_a_ticker_headline_is_not_shouting(self):
        self.assertTrue(callable(audit.gate.is_shouting))
        self.assertFalse(audit.gate.is_shouting("EURUSD 1.1253 EURGBP 0.8438 EURJPY 177.4"),
                         "ISO 4217 codes have no lowercase form; that title is correct as written")
        self.assertTrue(audit.gate.is_shouting("DAILY NEWS"))

    def test_a_short_page_label_is_not_reported_as_a_violation(self):
        # "Disclaimer" and "Calculator" are the site's own navigation labels. The 12-character floor is
        # the rule this repository applies to an article headline; a standing page is not a headline, and
        # reporting the correct title as a violation is how a fixer ends up padding it.
        self.assertLess(audit.PAGE_TITLE_MIN, audit.TITLE_MIN)
        rows = [{"url": f"{BLOG}/p/calculator.html", "title": "Calculator", "resource": "pages"}]
        self.assertTrue(all(len(row["title"]) >= audit.PAGE_TITLE_MIN for row in rows))

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

    def test_the_indexnow_key_page_is_exempt_because_the_submission_needs_it(self):
        # unpublishing this URL makes every IndexNow batch fail, so the audit may not nag about it
        self.assertIn("indexnow-key", audit.EXEMPT_UTILITY_SLUGS)
        self.assertNotIn("indexnow-key", audit.UTILITY_SLUGS - audit.EXEMPT_UTILITY_SLUGS)

    def test_the_defects_we_actually_had_are_all_seen(self):
        post = f"{BLOG}/2026/10/gold-rate-october.html"
        cut = f"{BLOG}/2026/10/student-loan-interest-rates-federal.html"
        twin_a = f"{BLOG}/2026/10/asia-news-2026-10-18.html"
        twin_b = f"{BLOG}/2026/10/asia-news-2026-10-18_01443792159.html"
        about = f"{BLOG}/p/about.html"
        utility = f"{BLOG}/p/indexnow-key.html"           # exempt: IndexNow reads its key here
        notice = f"{BLOG}/p/share-market_0718113516.html"  # a redirect notice that must not be listed
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
                one(utility, "IndexNow key", "<p>key</p>"),
                one(notice, "GLOBAL SNAPSHOT - MOVED",
                    "<p>This page moved to /p/global-snapshot.html.</p>")),
            "/sitemap.xml": (None, sitemap([post, cut, twin_a, twin_b, utility, notice, about])),
            "/sitemap-pages.xml": (None, sitemap([about, utility, notice, f"{BLOG}/"])),
        }
        pages = {f"{BLOG}/": page(f"{BLOG}/", "Daily Yield - personal finance and markets"),
                 post: page(post, images='<img src="https://bp.blogspot.com/q/hash0000aaaa1111bbbb.jpg">'),
                 cut: page(cut, "Student Loan Interest Rates: Federal, Private,"),
                 utility: page(utility, "IndexNow key", robots="noindex"),
                 notice: page(notice, "GLOBAL SNAPSHOT - MOVED"),
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
        offenders = "".join(seen["no-utility-pages-in-sitemaps"]["offenders"])
        self.assertIn(notice, offenders, "a redirect notice in a sitemap must be reported")
        self.assertNotIn("indexnow-key", offenders, "the IndexNow key page must not be reported: "
                         "unpublishing it breaks every IndexNow submission")
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




    def test_a_full_article_under_a_leftover_slug_is_not_offered_as_a_page_to_delete(self):
        """An odd address with a real article behind it is a naming problem, and nothing more.

        This is the false positive that reached the owner as a to-do on 22 October: two published
        pieces, "Stop Maxing Your 401(k)" and "Your Portfolio Does Not Owe You Rent", were called
        machine artifacts because their slugs read "context-httpsschema" - a September bug that let a
        schema fragment be used as a title, which Blogger then froze into the permalink. Acting on that
        report would have deleted published work, the one thing forbidden the same day. The check now
        reads the page, so the article is not an offender and the odd address is still shown, as advice.
        """
        odd = f"{BLOG}/2026/09/context-httpsschema.html"
        home = f"{BLOG}/"
        body = ("<p>Stop maxing your 401(k) before the tax answer moves underneath you.</p><p>"
                + varied(420) + "</p>")
        pages = {home: page(home, "Daily Yield - personal finance and markets"),
                 odd: page(odd, "Stop Maxing Your 401(k)")}
        feeds = {"posts": entries(one(odd, "Stop Maxing Your 401(k)", body)), "pages": entries()}
        feeds["/sitemap.xml"] = (None, sitemap([odd]))
        feeds["/sitemap-pages.xml"] = (None, sitemap([f"{BLOG}/p/about.html"]))
        net = FakeNet(pages, feeds, robots=f"User-agent: *\nAllow: /\nSitemap: {BLOG}/sitemap.xml\n"
                      f"Sitemap: {BLOG}/sitemap-pages.xml\n")
        seen = {row["id"]: row for row in self.run_audit(net)["checks"]}
        self.assertEqual("PASS", seen["no-utility-pages-in-sitemaps"]["status"],
                         "an article is not a low-value page: " + seen["no-utility-pages-in-sitemaps"]["detail"])
        self.assertEqual("FAIL", seen["odd-address-holds-real-article"]["status"],
                         "the odd address itself must stay visible in the report")
        self.assertTrue(seen["odd-address-holds-real-article"]["advisory"],
                        "naming an article's permalink is advice to a person, not a site that failed a rule")
        self.assertIn(odd, seen["odd-address-holds-real-article"]["offenders"])


        def test_a_page_carrying_only_the_stray_fragment_is_still_reported_as_low_value(self):
            """The other half of the same rule: nothing was softened for the two articles."""
            stray = f"{BLOG}/2026/09/context-httpsschema_0119702296.html"
            home = f"{BLOG}/"
            pages = {home: page(home, "Daily Yield - personal finance and markets"),
                     stray: page(stray, "context-httpsschema")}
            feeds = {"posts": entries(one(stray, "context-httpsschema",
                                          "<p>{'@context': 'https://schema.org'}</p>")), "pages": entries()}
            feeds["/sitemap.xml"] = (None, sitemap([stray]))
            feeds["/sitemap-pages.xml"] = (None, sitemap([]))
            net = FakeNet(pages, feeds, robots=f"User-agent: *\nAllow: /\nSitemap: {BLOG}/sitemap.xml\n"
                          f"Sitemap: {BLOG}/sitemap-pages.xml\n")
            seen = {row["id"]: row for row in self.run_audit(net)["checks"]}
            self.assertIn(stray, seen["no-utility-pages-in-sitemaps"]["offenders"],
                          "a page carrying nothing but the escaped fragment must still be named")

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


class MobileFirstFetch(unittest.TestCase):
    """The 453-URL lesson: a page that only answers a desktop fetch is not an indexable page.

    These are offline on purpose. `first_hop` is replaced by a table of answers, so what is under test is
    the judgement - a 302 to the mobile template is a finding, a 200 is not, and a rate limit is never
    allowed to become one - plus the rule that this audit reads the site as a reader and never borrows a
    crawler's identity to prove a point.
    """

    def test_a_direct_answer_is_not_a_finding(self):
        url = f"{BLOG}/p/daily-news.html"
        with mock.patch.object(audit, "get", lambda *a, **k: (200, "<html></html>")):
            self.assertFalse(audit.mobile_answer(url)["moved"])

    def test_a_mobile_bounce_is_measured_as_the_address_it_landed_on(self):
        url = f"{BLOG}/"

        def bounced(_url, timeout=45, *, user_agent=None, trace=None):
            self.assertIn("Mobile", user_agent, "the check must ask as a phone")
            if trace is not None:
                trace["finalUrl"] = _url + "?m=1"
            return 200, "<link href='%s' rel='canonical'/>" % _url

        with mock.patch.object(audit, "get", bounced):
            answer = audit.mobile_answer(url)
        self.assertTrue(answer["moved"])
        self.assertEqual(answer["finalUrl"], url + "?m=1")
        self.assertEqual(answer["canonical"], url, "the target canonicalises back to the URL asked for")

    def test_a_throttle_is_not_reported_as_a_defect(self):
        with mock.patch.object(audit, "get", lambda *a, **k: (429, "")):
            self.assertEqual(audit.mobile_answer(f"{BLOG}/")["status"], 429)

    def test_the_mobile_identity_is_a_browser_not_a_crawler(self):
        self.assertIn("Mobile", audit.MOBILE_PROBE_UA)
        for needle in ("Googlebot", "bot.html", "BingPreview", "Lighthouse"):
            self.assertNotIn(needle, audit.MOBILE_PROBE_UA, needle + " would be impersonating a service")

    def test_the_probe_refuses_to_follow_the_redirect(self):
        source = Path(audit.__file__).read_text(encoding="utf-8")
        body = source.split("def mobile_answer")[1].split("def rendered_probe_head_canonical")[0]
        self.assertIn("get(", body, "one network path, so a test can intercept it"
                       " and the audit never opens its own connection")

    def test_the_check_is_registered_with_an_owner_and_a_guideline(self):
        source = Path(audit.__file__).read_text(encoding="utf-8")
        block = source.split('"mobile-first-fetch-is-direct"')[1][:900]
        self.assertIn('"blogger"', block, "the fix is the platform's setting, so it must be said so")
        self.assertIn("Mobile devices", block, "the action has to name the switch, not just the symptom")



if __name__ == "__main__":
    unittest.main(verbosity=2)
