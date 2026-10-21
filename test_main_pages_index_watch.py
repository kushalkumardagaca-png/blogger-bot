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
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(watch, "http", fake), \
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

    def test_the_domain_property_is_used_when_the_prefix_property_is_absent(self):
        fake = FakeHttp(site_entries=[{"siteUrl": watch.DOMAIN_PROPERTY, "permissionLevel": "siteOwner"}],
                        body_of={"sitemap": ""})
        _, report, _ = self.run_main(fake)
        self.assertEqual(report["inspectionProperty"], watch.DOMAIN_PROPERTY)
        self.assertIn("URL-prefix property", " ".join(report["ownerActions"]))
        self.assertIn("not verified", report["sitemaps"]["detail"])

    def test_no_request_ever_touches_the_blogger_content_api(self):
        fake = FakeHttp(body_of={"sitemap": ""})
        self.run_main(fake)
        for method, url, path in fake.calls:
            self.assertNotIn("blogger.googleapis.com", url, "this job must not write to the site")
            self.assertNotIn("/blogs/", path, "the Blogger content API is out of bounds for this job")
            self.assertTrue(method in ("GET", "PUT", "POST"), method)
            if "googleapis.com/webmasters" in url:
                self.assertTrue(path.startswith("/webmasters/v3/sites"), path)


class BingSide(unittest.TestCase):
    def test_absence_from_bing_is_recorded_as_unreported(self):
        bing = watch.bing_view([HOME_URL])
        self.assertEqual(bing["status"], "UNAVAILABLE")
        self.assertEqual(bing["notReported"], [HOME_URL])
        self.assertNotIn("FAIL", json.dumps(bing))

    def test_page_stats_that_bing_did_not_surface_do_not_count_as_indexed(self):
        fake = FakeHttp(bing={"quota": [{"Name": "DailyQuota", "Value": 0},
                                        {"Name": "MonthlyQuota", "Value": 1000}],
                             "stats": [{"Url": HOME_URL, "LastCrawledDate": "/Date(1)/",
                                        "HttpStatus": 200}]})
        targets = watch.main_page_targets([])
        with mock.patch.object(watch, "http", fake), \
                mock.patch.dict(os.environ, {"BING_WEBMASTER_API_KEY": "fake-bing-key"}, clear=False):
            bing = watch.bing_view([row["url"] for row in targets])
        self.assertEqual(bing["quota"]["dailyUrlSubmission"], 0)
        self.assertIn(HOME_URL, bing["seen"])
        self.assertEqual(bing["notReported"], [row["url"] for row in targets if row["url"] != HOME_URL])


class Pace(unittest.TestCase):
    def test_the_arithmetic_of_the_deadline(self):
        targets = watch.main_page_targets([])
        block = watch.pace(targets, 1, 1, dt.date(2026, 10, 21))
        self.assertEqual((block["targets"], block["daysLeft"], block["stillMissing"]), (1, 40, 0))
        self.assertEqual(block["expectedByNow"], 0.0)
        self.assertTrue(block["onTrack"])
        block = watch.pace(targets * 4, 2, 3, dt.date(2026, 11, 20))
        self.assertEqual(block["stillMissing"], 2)
        self.assertEqual((block["expectedByNow"], block["behindBy"]), (3.0, 1))
        self.assertFalse(block["onTrack"])
        late = watch.pace(targets, 0, 0, dt.date(2026, 12, 5))
        self.assertLess(late["daysLeft"], 0)
        self.assertEqual(late["paceRequiredPerWeek"], 0)

    def test_both_platforms_are_required_before_a_page_counts(self):
        targets = watch.main_page_targets([f"{BLOG}/p/daily-news.html"])
        report = watch.build_report(targets=targets, properties={"status": "MEASURED", "visible": []},
                                    sitemaps={"status": "MEASURED", "registered": [], "missing": []},
                                    registration={"submittedNow": [], "failed": []},
                                    rows=[{"url": row["url"], "verdict": "PASS"} for row in targets],
                                    bing={"status": "MEASURED", "seen": {}, "quota": {},
                                          "notReported": [row["url"] for row in targets]},
                                    today=dt.date(2026, 10, 21))
        self.assertEqual(report["pace"]["inBothPlatforms"], 0)
        self.assertTrue(all(row["inBoth"] is False for row in report["byPage"]))
        self.assertEqual(report["verdict"], "PARTIAL", "one platform alone is never 'done'")
        self.assertEqual(report["byPage"][0]["bing"], "unreported")
        report["bing"]["seen"] = {row["url"]: {} for row in targets}
        report["pace"] = watch.pace(targets, 2, 2, dt.date(2026, 10, 21))
        report["verdict"] = "ALL_MAIN_PAGES_INDEXED"
        self.assertEqual(report["pace"]["stillMissing"], 0)


class Hygiene(unittest.TestCase):
    def test_credentials_never_reach_a_reported_file(self):
        secrets = {"GSC_REFRESH_TOKEN": "super-secret-refresh",
                   "GSC_CLIENT_SECRET": "super-secret-client",
                   "BING_WEBMASTER_API_KEY": "super-secret-bing"}
        fake = FakeHttp(sitemaps=[{"path": f"{BLOG}/sitemap.xml"}, {"path": f"{BLOG}/sitemap-pages.xml"}],
                        body_of={"sitemap": ""})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(watch, "http", fake), \
                mock.patch.dict(os.environ, secrets, clear=False), redirect_stdout(io.StringIO()):
            with mock.patch("sys.argv", ["x", "--today", "2026-10-21",
                                          "--out", str(Path(tmp) / "r.json"), "--apply"]):
                watch.main()
            text = (Path(tmp) / "r.json").read_text()
        for value in secrets.values():
            self.assertNotIn(value, text)
        self.assertNotIn("Bearer", text)

    def test_the_offline_self_test_passes(self):
        self.assertEqual(watch.run_check(), 0)

    def test_urgency_without_invention(self):
        text = (Path(__file__).with_name("main_pages_index_watch.py")).read_text()
        for needle in ("MAIN_PAGE_HOME", "Request indexing", "an API error is not evidence",
                       "siteWrites", "UTILITY_SLUGS"):
            self.assertIn(needle, text)
        self.assertNotIn("indexing.googleapis.com", text,
                         "Google's Indexing API is for job postings and live streams only")


if __name__ == "__main__":
    unittest.main()
