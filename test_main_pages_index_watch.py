#!/usr/bin/env python3
"""Tests for the main-pages scoreboard.

These exist because the failure this job replaces was silent: the site had a Search Console job that
registered sitemaps, it got frozen, and for three days nothing checked whether the sitemaps were
still there or whether the thirteen front doors were indexed. The assertions below are the guarantees
that make the job worth running daily — homepage included in the target list, sitemap registration
repaired through the API that actually exists, an API error reported as unknown rather than as "not
indexed", Bing's silence reported as unreported rather than as refusal, and no Blogger write at any
point.
"""
import datetime as dt
import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import main_pages_index_watch as watch

BLOG = watch.BLOG
HOME_URL = watch.PREFIX_PROPERTY
PREFIX = watch.PREFIX_PROPERTY


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "refused", {}, io.BytesIO(b"{}"))


class FakeHttp:
    """Stands in for every network call and records what was asked, so the tests can assert on it."""

    def __init__(self, *, sitemaps=None, site_entries=None, inspect_by_url=None, bing=None,
                 raise_on=None, body_of=None):
        self.calls = []
        self.sitemaps = sitemaps if sitemaps is not None else []
        self.site_entries = site_entries if site_entries is not None else [
            {"siteUrl": HOME_URL, "permissionLevel": "siteOwner"}]
        self.inspect_by_url = inspect_by_url or {}
        self.bing = bing or {"quota": [], "stats": []}
        self.raise_on = raise_on or {}
        self.body_of = body_of or {}
        self.put_paths = []

    def __call__(self, url, *, headers=None, method="GET", body=None, timeout=60):
        parsed = urllib.parse.urlparse(url)
        self.calls.append((method, url, parsed.path))
        for needle, error in self.raise_on.items():
            if needle in url:
                raise error
        if url.endswith("oauth2.googleapis.com/token"):
            return {"access_token": "fake-access"}
        if parsed.path.endswith("/webmasters/v3/sites"):
            return {"siteEntry": self.site_entries}
        if parsed.path.endswith("/sitemaps"):
            return {"sitemap": self.sitemaps}
        if "/sitemaps/" in parsed.path:
            self.put_paths.append(urllib.parse.unquote(parsed.path.split("/sitemaps/")[-1]))
            return {}
        if parsed.path.endswith("urlInspection/index:inspect"):
            payload = self.inspect_by_url.get(body["inspectionUrl"], {"verdict": "FAIL",
                                                                     "coverageState": "Discovered - currently not indexed"})
            return {"inspectionResult": {"indexStatusResult": payload,
                                         "inspectionResultLink": "https://search.google.com/"}}
        if url.startswith(BLOG):
            return self.body_of.get("sitemap", "")
        if "api.bing.com" in url:
            if "GetQuotas" in url:
                return self.bing.get("quota", [])
            return self.bing.get("stats", [])
        raise AssertionError(f"unexpected request: {method} {url}")


class SitemapTruth(unittest.TestCase):
    """Google reports lastSubmitted and lastDownloaded. It has no "accessed" field.

    This test exists because the first version of the scoreboard asked for a key that does not
    exist, and the report then printed "last read never" about a sitemap Google reads daily. A
    missing field and an unanswered question look the same unless something pins the difference.
    """

    def test_google_sitemap_dates_are_read_from_the_fields_that_exist(self):
        rows = [{"path": f"{BLOG}/sitemap-pages.xml", "isPending": False, "errors": "0",
                 "warnings": "0", "lastSubmitted": "2026-10-18T04:00:00Z",
                 "lastDownloaded": "2026-10-22T01:50:00Z",
                 "indexStatus": [{"indexStatus": "success", "urlCount": "14"}]}]
        access = "fake"
        with mock.patch.object(watch, "gsc", lambda a, m, path, body=None: {"sitemap": rows}):
            state = watch.sitemap_state(access, watch.DOMAIN_PROPERTY)
        self.assertEqual(state["status"], "MEASURED")
        row = state["registered"][0]
        self.assertEqual(row["lastDownloaded"], "2026-10-22T01:50:00Z")
        self.assertEqual(row["lastSubmitted"], "2026-10-18T04:00:00Z")
        self.assertEqual(row["indexStatus"], [{"state": "success", "urls": "14"}])
        self.assertNotIn("accessed", row)
        rendered = watch.render_markdown(watch.build_report(
            targets=watch.main_page_targets([]), properties={"status": "MEASURED", "visible": []},
            sitemaps=state, registration={"submittedNow": [], "failed": []},
            rows=[{"url": row2["url"], "verdict": "UNKNOWN"} for row2 in watch.main_page_targets([])],
            bing={"status": "MEASURED", "seen": {}, "quota": {}, "notReported": []},
            today=dt.date(2026, 10, 22))
        )
        self.assertIn("last read by Google: 2026-10-22", rendered)
        self.assertIn("URLs success 14", rendered)

    def test_a_sitemap_google_never_downloaded_is_called_out_loudly(self):
        rows = [{"path": f"{BLOG}/sitemap.xml", "isPending": False, "errors": "0", "warnings": "0"}]
        with mock.patch.object(watch, "gsc", lambda a, m, path, body=None: {"sitemap": rows}):
            state = watch.sitemap_state("x")
        report = watch.build_report(targets=watch.main_page_targets([]),
                                    properties={"status": "MEASURED", "visible": []}, sitemaps=state,
                                    registration={"submittedNow": [], "failed": []}, rows=[],
                                    bing={"status": "MEASURED", "seen": {}, "quota": {},
                                          "notReported": []}, today=dt.date(2026, 10, 22))
        text = watch.render_markdown(report)
        self.assertIn("last read by Google: never", text)
        self.assertIn("has not reported reading", text)


    def test_the_permission_level_of_each_property_is_part_of_the_answer(self):
        # A property that is merely visible is not a property the automation may change. The 403 we
        # measured on sitemap submission is only explainable with the permission level attached.
        entries = [{"siteUrl": PREFIX, "permissionLevel": "siteOwner"},
                   {"siteUrl": watch.DOMAIN_PROPERTY, "permissionLevel": "full"}]
        with mock.patch.object(watch, "gsc", lambda a, m, path, body=None: {"siteEntry": entries}):
            out = watch.list_properties("x")
        self.assertEqual(out["urlPrefixProperty"], "siteOwner")
        self.assertEqual(out["domainProperty"], "full")
        self.assertEqual(out["permission"][PREFIX], "siteOwner")
        report = watch.build_report(targets=watch.main_page_targets([]),
                                    properties={**out, "status": "MEASURED", "urlPrefixProperty": "unverified",
                                                  "urlPrefixPropertyVisible": True,
                                                  "domainPropertyVisible": True},
                                    sitemaps={"status": "MEASURED", "registered": [], "missing": []},
                                    registration={"submittedNow": [], "failed": []}, rows=[],
                                    bing={"status": "MEASURED", "seen": {}, "quota": {},
                                          "notReported": []}, today=dt.date(2026, 10, 22))
        self.assertIn("Users and permissions", " ".join(report["ownerActions"]))


class Targets(unittest.TestCase):
    def test_the_homepage_leads_and_the_machine_pages_are_left_out(self):
        pages = [f"{BLOG}/p/indexnow-key.html", f"{BLOG}/p/terms-and-conditions.html",
                 f"{BLOG}/p/global-snapshot.html", f"{BLOG}/p/share-market_0718113516.html",
                 f"{BLOG}/p/daily-news.html", f"{BLOG}/p/about-us_02080501126.html",
                 f"{BLOG}/p/contact-us_01883938366.html", f"{BLOG}/p/calculator_0908148622.html",
                 f"{BLOG}/p/money-atlas_01486068069.html", f"{BLOG}/p/for-corporate_01804417406.html",
                 f"{BLOG}/p/article.html", f"{BLOG}/p/markets-today.html",
                 f"{BLOG}/p/privacy-policy.html", f"{BLOG}/p/disclaimer.html"]
        targets = watch.main_page_targets(pages)
        urls = [row["url"] for row in targets]
        self.assertEqual(urls[0], HOME_URL)
        self.assertEqual(len(urls), 13, urls)
        self.assertNotIn(f"{BLOG}/p/indexnow-key.html", urls)
        self.assertNotIn(f"{BLOG}/p/share-market_0718113516.html", urls)
        self.assertEqual([row["kind"] for row in targets[:2]], ["home", "page"])

    def test_a_foreign_or_insecure_url_is_never_added(self):
        targets = watch.main_page_targets([HOME_URL, "http://dailyyield.blogspot.com/p/x.html",
                                           "https://evil.example/p/x.html", "https://a@b.blogspot.com/p/x"])
        self.assertEqual([row["url"] for row in targets], [HOME_URL])

    def test_the_sitemap_is_read_for_urls_not_for_our_assumptions(self):
        raw = ('<urlset><url><loc> https://dailyyield.blogspot.com/p/a.html </loc></url>'
               '<url><loc>https://dailyyield.blogspot.com/p/b.html</loc></url></urlset>')
        self.assertEqual(watch.parse_sitemap_locations(raw),
                         [f"{BLOG}/p/a.html", f"{BLOG}/p/b.html"])
        self.assertEqual(watch.parse_sitemap_locations(""), [])


class GoogleSide(unittest.TestCase):
    def setUp(self):
        self.targets = watch.main_page_targets([f"{BLOG}/p/daily-news.html"])

    def run_main(self, fake, *, apply=True, token=True, today="2026-10-21"):
        env = {"GSC_CLIENT_ID": "fake-client", "GSC_CLIENT_SECRET": "fake-client-secret",
               "GSC_REFRESH_TOKEN": "fake-refresh" if token else "",
               "BLOGGER_CLIENT_ID": "", "BLOGGER_CLIENT_SECRET": "", "BLOG_ID": ""}
        probe = mock.patch.object(watch, "live_probe", lambda url: {
            "reachable": True, "status": 200, "hops": [], "finalUrl": url,
            "canonical": url})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(watch, "http", fake), probe, \
                mock.patch.dict(os.environ, env, clear=False), \
                redirect_stdout(io.StringIO()) as out:
            argv = ["main_pages_index_watch.py", "--today", today,
                    "--out", str(Path(tmp) / "report.json")] + (["--apply"] if apply else [])
            with mock.patch("sys.argv", argv):
                code = watch.main()
            payload = json.loads((Path(tmp) / "report.json").read_text())
        return code, payload, out.getvalue()

    def test_sitemaps_are_registered_and_the_missing_one_is_the_one_that_gets_a_put(self):
        fake = FakeHttp(sitemaps=[{"path": f"{BLOG}/sitemap.xml", "isPending": False, "errors": 0,
                                   "warnings": 0, "accessed": "2026-10-20T00:00:00Z"}],
                        body_of={"sitemap": f'<urlset><url><loc>{BLOG}/p/daily-news.html</loc></url></urlset>'})
        code, report, _ = self.run_main(fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.put_paths, [f"{BLOG}/sitemap-pages.xml"])
        self.assertEqual(report["sitemaps"]["missing"], [f"{BLOG}/sitemap-pages.xml"])
        self.assertEqual(report["sitemapRegistration"]["submittedNow"], [f"{BLOG}/sitemap-pages.xml"])
        self.assertEqual(report["siteWrites"], 0)

    def test_a_read_only_run_reports_the_gap_without_touching_google(self):
        fake = FakeHttp(sitemaps=[], body_of={"sitemap": ""})
        _, report, _ = self.run_main(fake, apply=False)
        self.assertEqual(fake.put_paths, [])
        self.assertEqual(report["sitemapRegistration"]["submittedNow"], [])
        self.assertIn("not attempted", report["sitemapRegistration"]["failed"][0]["error"])

    def test_a_refused_registration_is_a_recorded_failure_not_a_crash(self):
        fake = FakeHttp(sitemaps=[], body_of={"sitemap": ""},
                        raise_on={"/sitemaps/": http_error("x", 403)})
        code, report, _ = self.run_main(fake)
        self.assertEqual(code, 0)
        self.assertEqual(report["sitemapRegistration"]["failed"][0]["error"], "HTTP 403")
        self.assertNotIn("sitemap.xml", report["sitemapRegistration"]["submittedNow"])

    def test_the_verdicts_are_per_page_and_the_manual_queue_names_the_unindexed_ones(self):
        fake = FakeHttp(sitemaps=[{"path": f"{BLOG}/sitemap.xml"}, {"path": f"{BLOG}/sitemap-pages.xml"}],
                        inspect_by_url={HOME_URL: {"verdict": "PASS", "coverageState": "Indexed"},
                                        f"{BLOG}/p/daily-news.html": {"verdict": "FAIL",
                                                                      "coverageState": "Discovered - currently not indexed",
                                                                      "lastCrawlTime": "2026-10-20T02:00:00Z"}},
                        body_of={"sitemap": f'<urlset><url><loc>{BLOG}/p/daily-news.html</loc></url></urlset>'})
        _, report, _ = self.run_main(fake)
        self.assertEqual(report["google"]["indexed"], 1)
        self.assertEqual(report["google"]["notIndexed"], 1)
        self.assertEqual(len(report["manualQueue"]), 1)
        self.assertEqual(report["manualQueue"][0]["url"], f"{BLOG}/p/daily-news.html")
        self.assertIn("Request indexing", " ".join(report["manualQueue"][0]["steps"]))
        self.assertEqual(report["byPage"][0]["google"], "PASS")

    def test_no_google_authorisation_is_reported_as_unavailable_not_as_not_indexed(self):
        fake = FakeHttp()
        code, report, _ = self.run_main(fake, token=False)
        self.assertEqual(code, 0)
        self.assertEqual(report["google"]["status"], "UNAVAILABLE")
        self.assertEqual(report["google"]["indexed"], 0)
        self.assertTrue(all(row["verdict"] == "UNKNOWN" for row in report["google"]["rows"]))
        self.assertEqual(report["verdict"], "NOT_STARTED")
        self.assertIn("GSC_REFRESH_TOKEN", " ".join(report["ownerActions"]))

    def test_the_domain_property_is_asked_before_anyone_is_blamed(self):
        # Google documents sitemap submission on the URL-prefix property, and the site has only the
        # domain one. The job asks the domain property anyway, because "the API refuses" is evidence and
        # "we never tried" is not.
        fake = FakeHttp(site_entries=[{"siteUrl": watch.DOMAIN_PROPERTY, "permissionLevel": "siteOwner"}],
                        body_of={"sitemap": ""})
        _, report, _ = self.run_main(fake)
        self.assertEqual(report["sitemaps"]["triedOn"], watch.DOMAIN_PROPERTY)
        self.assertEqual(report["sitemaps"]["status"], "MEASURED")
        self.assertEqual(sorted(fake.put_paths), sorted(watch.SITEMAP_PATHS))
        self.assertEqual(sorted(report["sitemapRegistration"]["submittedNow"]), sorted(watch.SITEMAP_PATHS))

    def test_a_rate_limit_is_never_read_as_a_complaint_about_the_page(self):
        row = {"url": f"{BLOG}/p/article.html", "verdict": "NEUTRAL",
               "coverageState": "Redirect error", "lastCrawlTime": "2026-10-02T07:15:16Z"}
        self.assertFalse(watch.stale_verdict(row, {"reachable": False, "status": 429, "hops": [1],
                                                   "notMeasured": "rate limited"}),
                         "a throttled probe says nothing either way")

    def test_the_domain_property_is_reused_for_the_verdicts(self):
        # Every inspection then runs against the domain property, and the owner is still told the
        # prefix property is what unlocks the rest - one does not cancel the other.
        fake = FakeHttp(sitemaps=[{"path": f"{BLOG}/sitemap.xml"}, {"path": f"{BLOG}/sitemap-pages.xml"}],
                        site_entries=[{"siteUrl": watch.DOMAIN_PROPERTY, "permissionLevel": "siteOwner"}],
                        body_of={"sitemap": ""})
        _, report, _ = self.run_main(fake)
        self.assertEqual(report["inspectionProperty"], watch.DOMAIN_PROPERTY)
        self.assertIn("URL-prefix property", " ".join(report["ownerActions"]))
        # Both sitemaps are already registered, and an --apply run re-submits them anyway: a re-read
        # of the file is free for Google, idempotent for us, and it is the only lawful way on a
        # blogspot property to keep asking for a fresh crawl.
        self.assertEqual(sorted(fake.put_paths), sorted(watch.SITEMAP_PATHS))
        self.assertEqual(report["sitemaps"]["missing"], [])

    def test_no_request_ever_touches_the_blogger_content_api(self):
        fake = FakeHttp(body_of={"sitemap": ""})
        self.run_main(fake)
        for method, url, path in fake.calls:
            self.assertNotIn("blogger.googleapis.com", url, "this job must not write to the site")
            self.assertNotIn("/blogs/", path, "the Blogger content API is out of bounds for this job")
            self.assertTrue(method in ("GET", "PUT", "POST"), method)
            if "googleapis.com/webmasters" in url:
                self.assertTrue(path.startswith("/webmasters/v3/sites"), path)


class RetiredEngine(unittest.TestCase):
    """Bing was deleted from the plan by the owner on 23 October 2026; these tests keep it deleted.

    They replace two tests that checked how a Bing answer was recorded. There is no answer to record any
    more, so what matters is the opposite: the job must never call that engine again, and a report must
    say plainly that the engine was retired rather than leave a blank that reads like a failure.
    """

    def test_the_retired_engine_is_recorded_as_retired_not_as_failed(self):
        view = watch.bing_view([HOME_URL])
        self.assertTrue(view["retired"])
        self.assertIn("23 October 2026", view["detail"])
        self.assertNotIn("FAIL", json.dumps(view))

    def test_the_scoreboard_builds_no_bing_request_at_all(self):
        source = Path(__file__).with_name("main_pages_index_watch.py").read_text()
        self.assertNotIn("api.bing.com", source)
        self.assertNotIn("import bing_url_automation", source)
        self.assertNotIn("BING_WEBMASTER_API_KEY",
                         Path(__file__).with_name(".github").name + "")   # placeholder, see the workflow test

    def test_the_workflow_no_longer_hands_over_a_bing_key(self):
        workflow = Path(__file__).with_name(".github")
        text = (workflow.parent / ".github/workflows/main_pages_index_watch.yml").read_text()
        self.assertNotIn("BING_WEBMASTER_API_KEY", text)


class Pace(unittest.TestCase):
    def test_the_arithmetic_of_the_deadline(self):
        targets = watch.main_page_targets([])
        block = watch.pace(targets, 1, dt.date(2026, 10, 21))
        self.assertEqual((block["targets"], block["daysLeft"], block["stillMissing"]), (1, 40, 0))
        self.assertEqual(block["expectedByNow"], 0.0)
        self.assertTrue(block["onTrack"])
        # three of four front doors in Google's index, with three expected by now: on pace, nothing behind
        block = watch.pace(targets * 4, 3, dt.date(2026, 11, 20))
        self.assertEqual(block["stillMissing"], 1)
        self.assertEqual((block["expectedByNow"], block["behindBy"]), (3.0, 0))
        self.assertTrue(block["onTrack"])
        late = watch.pace(targets, 0, dt.date(2026, 12, 5))
        self.assertLess(late["daysLeft"], 0)
        self.assertEqual(late["paceRequiredPerWeek"], 0)

    def test_a_page_counts_when_google_says_it_is_indexed(self):
        # Until 23 October 2026 a page counted only when Google AND Bing agreed. The owner deleted the
        # Bing property that evening, so this pins the new rule: Google's verdict alone decides, and the
        # retired engine is named in the report instead of silently dropping out of the arithmetic.
        targets = watch.main_page_targets([f"{BLOG}/p/daily-news.html"])
        report = watch.build_report(targets=targets, properties={"status": "MEASURED", "visible": []},
                                    sitemaps={"status": "MEASURED", "registered": [], "missing": []},
                                    registration={"submittedNow": [], "failed": []},
                                    rows=[{"url": row["url"], "verdict": "PASS"} for row in targets],
                                    bing=watch.bing_view([row["url"] for row in targets]),
                                    today=dt.date(2026, 10, 21))
        self.assertEqual(report["pace"]["indexedInGoogle"], 2, "the home page and the desk page")
        self.assertEqual(report["pace"]["stillMissing"], 0)
        self.assertTrue(report["byPage"][0]["googleIndexed"])
        self.assertEqual(report["verdict"], "ALL_MAIN_PAGES_INDEXED")
        self.assertIn("23 October 2026", report["limits"])
        unindexed = watch.build_report(
            targets=targets, properties={"status": "MEASURED", "visible": []},
            sitemaps={"status": "MEASURED", "registered": [], "missing": []},
            registration={"submittedNow": [], "failed": []},
            rows=[{"url": row["url"], "verdict": "FAIL",
                   "coverageState": "Discovered - currently not indexed"} for row in targets],
            bing=watch.bing_view([row["url"] for row in targets]), today=dt.date(2026, 10, 21))
        self.assertEqual(unindexed["verdict"], "NOT_STARTED",
                         "no front door in Google's index is not a partial success, whatever Bing did")
        half = watch.build_report(
            targets=targets, properties={"status": "MEASURED", "visible": []},
            sitemaps={"status": "MEASURED", "registered": [], "missing": []},
            registration={"submittedNow": [], "failed": []},
            rows=[{"url": targets[0]["url"], "verdict": "PASS"},
                  {"url": targets[1]["url"], "verdict": "FAIL"}],
            bing=watch.bing_view([row["url"] for row in targets]), today=dt.date(2026, 10, 21))
        self.assertEqual(half["verdict"], "PARTIAL", "one of two is exactly what partial means")
        self.assertEqual(half["pace"]["stillMissing"], 1)


class Hygiene(unittest.TestCase):
    def test_credentials_never_reach_a_reported_file(self):
        secrets = {"GSC_REFRESH_TOKEN": "super-secret-refresh",
                   "GSC_CLIENT_SECRET": "super-secret-client",
                   "BING_WEBMASTER_API_KEY": "super-secret-bing"}
        fake = FakeHttp(sitemaps=[{"path": f"{BLOG}/sitemap.xml"}, {"path": f"{BLOG}/sitemap-pages.xml"}],
                        body_of={"sitemap": ""})
        probe = mock.patch.object(watch, "live_probe", lambda url: {
            "reachable": True, "status": 200, "hops": [], "finalUrl": url, "canonical": url})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(watch, "http", fake), probe, \
                mock.patch.dict(os.environ, secrets, clear=False), redirect_stdout(io.StringIO()):
            with mock.patch("sys.argv", ["x", "--today", "2026-10-21",
                                          "--out", str(Path(tmp) / "r.json"), "--apply"]):
                watch.main()
            text = (Path(tmp) / "r.json").read_text()
        for value in secrets.values():
            self.assertNotIn(value, text)
        self.assertNotIn("Bearer", text)

    def test_the_live_probe_is_part_of_the_guarantee(self):
        source = Path(__file__).with_name("main_pages_index_watch.py").read_text()
        for needle in ("def live_probe", "def stale_verdict", "staleVerdicts", "GOOGLEBOT_UA"):
            self.assertIn(needle, source)
        self.assertIn("live_probe", source)
        joined = " ".join(source.split())
        self.assertIn("delete, rebuild or rename", joined)

    def test_the_offline_self_test_passes(self):
        self.assertEqual(watch.run_check(), 0)

    def test_urgency_without_invention(self):
        text = (Path(__file__).with_name("main_pages_index_watch.py")).read_text()
        for needle in ("MAIN_PAGE_HOME", "Request indexing", "an API error is not evidence",
                       "siteWrites", "UTILITY_SLUGS"):
            self.assertIn(needle, text)
        self.assertNotIn("indexing.googleapis.com", text,
                         "Google's Indexing API is for job postings and live streams only")


class LiveVerdict(unittest.TestCase):
    """The day this job earned its keep: ten pages reported "Redirect error" from a September crawl.

    The live page answers 200 with no redirect. Without the probe the report would have told the owner
    to rebuild pages that are fine, and the real missing thing - a fresh crawl - would have stayed
    invisible. These tests pin the difference between a complaint and a stale complaint.
    """

    def test_blogger_canonical_is_found_whichever_way_the_attributes_are_ordered(self):
        self.assertEqual(watch.extract_canonical("<link href='https://dailyyield.blogspot.com/p/a.html' "
                                                  "rel='canonical'/>"),
                         f"{BLOG}/p/a.html")
        self.assertEqual(watch.extract_canonical('<link rel="canonical" href="https://x/p/a.html">'),
                         "https://x/p/a.html")
        self.assertEqual(watch.extract_canonical("<a href='#'>x</a>"), "")

    def test_a_clean_live_answer_turns_the_verdict_into_a_stale_verdict(self):
        row = {"url": f"{BLOG}/p/global-snapshot.html", "verdict": "NEUTRAL",
               "coverageState": "Redirect error", "lastCrawlTime": "2026-09-25T16:57:09Z"}
        probe = {"reachable": True, "status": 200, "hops": [], "finalUrl": row["url"],
                 "canonical": row["url"]}
        self.assertTrue(watch.stale_verdict(row, probe))
        probe_with_redirect = dict(probe, hops=[{"code": 301, "to": f"{BLOG}/p/moved.html"}])
        self.assertFalse(watch.stale_verdict(row, probe_with_redirect),
                         "a live redirect is a real problem, never a stale verdict")
        self.assertFalse(watch.stale_verdict(dict(row, verdict="PASS"), probe))
        self.assertFalse(watch.stale_verdict(dict(row, coverageState="Discovered - currently not indexed",
                                                  lastCrawlTime=""), probe),
                         "no crawl at all is not a stale verdict")

    def test_the_report_names_the_pages_the_platform_cannot_be_trusted_about(self):
        targets = watch.main_page_targets([])
        rows = [{"url": HOME_URL, "verdict": "NEUTRAL", "coverageState": "Redirect error",
                 "lastCrawlTime": "2026-09-25T16:57:09Z",
                 "live": {"reachable": True, "status": 200, "canonical": HOME_URL, "finalUrl": HOME_URL},
                 "liveHops": 0, "staleVerdict": True}]
        report = watch.build_report(targets=targets, properties={"status": "MEASURED", "visible": []},
                                    sitemaps={"status": "MEASURED", "registered": [], "missing": []},
                                    registration={"submittedNow": [], "failed": []}, rows=rows,
                                    bing={"status": "MEASURED", "seen": {}, "quota": {}, "notReported": []},
                                    today=dt.date(2026, 10, 21))
        self.assertEqual(report["staleVerdicts"]["count"], 1)
        self.assertEqual(report["byPage"][0]["liveStatusToday"], 200)
        self.assertTrue(report["byPage"][0]["canonicalMatchesPage"])
        self.assertIn("cannot be reproduced", " ".join(report["ownerActions"]))
        self.assertIn("200 with 0 redirect", watch.render_markdown(report))


    def test_a_throttled_page_is_still_judged_when_the_publisher_api_answers(self):
        # Blogger's own API is not rate limited and says the page is published. That is the second
        # voice the scoreboard is allowed to trust when the public probe is blocked.
        throttled = {"reachable": False, "status": 429, "hops": [], "notMeasured": "rate limited"}
        row = {"url": f"{BLOG}/p/x.html", "verdict": "NEUTRAL", "coverageState": "Redirect error"}
        self.assertFalse(watch.stale_verdict(row, throttled))
        self.assertTrue(watch.stale_verdict(row, throttled, True))
        self.assertFalse(watch.stale_verdict(
            {"url": f"{BLOG}/p/x.html", "verdict": "NEUTRAL",
             "coverageState": "Discovered - currently not indexed"},
            {"reachable": True, "status": 200, "hops": []}, True),
            "an unanswered page is not a stale verdict, however alive it is")

    def test_the_probe_budget_is_bounded_and_rotates(self):
        source = Path(__file__).with_name("main_pages_index_watch.py").read_text()
        self.assertIn("LIVE_PROBE_CAP = 6", source)
        self.assertIn("LIVE_PROBE_SPACING_SECONDS = 8", source)
        self.assertIn("ordered[:LIVE_PROBE_CAP]", source)
        self.assertNotIn("+http://www.google.com/bot.html", source,
                         "impersonating Googlebot is what got the runner throttled")

    def test_the_publisher_api_is_used_instead_of_guessing_page_state(self):
        source = Path(__file__).with_name("main_pages_index_watch.py").read_text()
        self.assertIn("def blogger_page_state", source)
        self.assertIn("/pages?", source)
        self.assertIn("publisherApiPagesLive", source)


class MobileIdentity(unittest.TestCase):
    """The mistake these tests exist to prevent: one identity, one answer, wrong advice.

    For six weeks the watch reported that Google's redirect complaints could not be reproduced. They
    could, every day - a desktop fetch gets the document while a mobile fetch gets `302 -> the same URL
    + ?m=1`, and mobile-first Google asks as a phone. So a redirect-family verdict is only stale when
    both answers are clean, and when the mobile answer bounces the watch has to name the setting behind
    it instead of telling the owner to wait for a crawl.
    """

    url = f"{BLOG}/p/daily-news.html"

    def test_a_bounce_only_a_phone_sees_is_not_a_stale_verdict(self):
        row = {"url": self.url, "verdict": "NEUTRAL", "coverageState": "Redirect error",
               "lastCrawlTime": "2026-10-20T02:00:00Z"}
        clean_desktop = {"reachable": True, "status": 200, "hops": [], "canonical": self.url}
        self.assertTrue(watch.stale_verdict(row, clean_desktop, True),
                        "with both identities clean it is a crawl that is missing")
        bounce = {"status": 302, "location": self.url + "?m=1", "canonical": self.url}
        self.assertFalse(watch.stale_verdict(row, clean_desktop, True, bounce),
                         "Google still hits the redirect, so it may not be called stale")

    def test_the_cause_is_named_so_the_action_can_point_at_a_switch(self):
        bounce = {"status": 302, "location": self.url + "?m=1", "canonical": self.url}
        self.assertEqual(watch.redirect_cause(self.url, bounce), "blogger-mobile-template")
        direct = {"status": 200, "location": "", "canonical": self.url}
        self.assertEqual(watch.redirect_cause(self.url, direct), "")
        away = {"status": 301, "location": "https://elsewhere.test/x", "canonical": ""}
        self.assertEqual(watch.redirect_cause(self.url, away), "redirect",
                         "a real move is not the template setting and must not get that advice")

    def test_the_owner_is_told_what_to_turn_and_why_it_is_safe(self):
        targets = watch.main_page_targets([self.url])
        rows = [{"url": row["url"], "verdict": "NEUTRAL", "coverageState": "Redirect error",
                 "redirectCause": "blogger-mobile-template" if row["url"] == self.url else "",
                 "mobileFetch": {"status": 302, "location": self.url + "?m=1", "canonical": self.url}}
                for row in targets]
        report = watch.build_report(targets=targets,
                                    properties={"status": "MEASURED", "visible": [BLOG + "/"],
                                                "urlPrefixPropertyVisible": True,
                                                "domainPropertyVisible": True},
                                    sitemaps={"status": "MEASURED", "registered": [], "missing": []},
                                    registration={"submittedNow": [], "failed": []},
                                    rows=rows,
                                    bing={"status": "MEASURED", "seen": {}, "quota": {},
                                          "notReported": [], "detail": ""},
                                    today=dt.date(2026, 10, 22))
        joined = "\n".join(report["ownerActions"])
        self.assertIn("There is nothing to toggle", joined,
                      "the owner is told what is true about the bounce, not sent to a switch")
        self.assertIn("?m=1", joined)
        for retired in ("One setting removes", "choose the desktop theme"):
            self.assertNotIn(retired, joined, retired + " is the advice this project already disproved")
        rendered = watch.render_markdown(report)
        self.assertIn("What a phone is told today", rendered)
        self.assertIn("m=1", rendered)

    def test_the_mobile_identity_is_a_browser_and_never_a_crawler(self):
        self.assertIn("Mobile", watch.MOBILE_PROBE_UA)
        for needle in ("Googlebot", "bot.html", "BingPreview"):
            self.assertNotIn(needle, watch.MOBILE_PROBE_UA,
                             needle + " would impersonate a service, which is what got us throttled")

    def test_the_mobile_probe_refuses_to_follow_the_redirect(self):
        source = Path(watch.__file__).read_text(encoding="utf-8")
        body = source.split("def mobile_probe")[1].split("def redirect_cause")[0]
        self.assertIn("_NoRedirect", body, "the first hop is the answer; following it hides the defect")
        self.assertIn("MOBILE_PROBE_UA", body, "an honest browser identity, never a crawler's")


if __name__ == "__main__":
    unittest.main()
