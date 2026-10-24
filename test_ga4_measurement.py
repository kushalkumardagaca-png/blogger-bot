#!/usr/bin/env python3
"""Views may only be reported when Google reported them, and this job may not touch the site.

The status codes are the point: "no credentials", "wrong scope", "tag missing" and "measured"
need four different fixes, and a flat zero in any of them would read as an audience of nobody.
"""
import json
import pathlib
import urllib.error
import tempfile
import unittest
from unittest import mock

import ga4_measurement as ga4


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = (ga4.ROOT, ga4.OUT, ga4.MD)
        ga4.ROOT, ga4.OUT, ga4.MD = self.tmp, self.tmp / "ga4.json", self.tmp / "ga4.md"

    def tearDown(self):
        ga4.ROOT, ga4.OUT, ga4.MD = self.saved

    def run_with(self, payload):
        fixture = self.tmp / "fixture.json"
        fixture.write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch("sys.argv", ["ga4_measurement.py", "--fixture", str(fixture)]):
            self.assertEqual(ga4.main(), 0)
        return json.loads(ga4.OUT.read_text(encoding="utf-8"))


class Reading(Harness):
    def test_seven_days_of_real_rows_become_a_daily_average(self):
        # the Data API returns the newest day first, and the reader metric reads that first row
        rows = [{"date": f"2026-10-{19 - index:02d}", "views": 100 + index, "activeUsers": 60 + index,
                 "sessions": 70 + index, "engagedSessions": 46 - index} for index in range(7)]
        report = self.run_with({"rows": rows, "propertyId": "412345678",
                                "siteTag": {"checked": True, "reachable": True,
                                            "measurementIds": [ga4.MEASUREMENT_ID], "installedHere": True}})
        self.assertEqual(report["status"], "MEASURED")
        self.assertTrue(report["ok"])
        self.assertEqual(report["totals"]["views"], 721)
        self.assertEqual(report["totals"]["viewsPerDay"], 103.0)
        self.assertEqual(report["peak"]["views"], 106)
        self.assertEqual(report["daily"][0]["date"], "2026-10-19")
        self.assertEqual(report["totals"]["engagedSessions"], 301)
        self.assertEqual(report["totals"]["dailyReaders"], 46,
                         "the newest whole day, because the milestone counts people per day")
        self.assertIn("views per day", ga4.MD.read_text(encoding="utf-8"))

    def test_a_live_tag_over_an_empty_property_is_not_reported_as_zero_readers(self):
        report = self.run_with({"rows": [], "propertyId": "412345678",
                                "siteTag": {"checked": True, "reachable": True,
                                            "measurementIds": [ga4.MEASUREMENT_ID], "installedHere": True}})
        self.assertEqual(report["status"], "NO_DATA_YET")
        self.assertFalse(report["ok"])
        self.assertIsNone(report["totals"]["viewsPerDay"], "no rows must not become a measured zero")
        self.assertIn("measurement id", report["remedy"])

    def test_a_page_without_the_tag_says_the_tag_is_missing(self):
        report = self.run_with({"rows": [], "siteTag": {"checked": True, "reachable": True,
                                                       "measurementIds": [], "installedHere": False}})
        self.assertEqual(report["status"], "TAG_NOT_OBSERVED")
        self.assertIn("tag", report["remedy"])


    def test_an_unreachable_homepage_does_not_claim_the_tag_is_missing(self):
        # a data-centre request can be refused while the owner's browser loads the page fine,
        # and "we could not look" must never be reported as "the tag is not there"
        report = self.run_with({"rows": [], "siteTag": {"checked": True, "reachable": False,
                                                        "measurementIds": [], "installedHere": None,
                                                        "error": "HTTP Error 403: Forbidden"}})
        self.assertEqual(report["status"], "TAG_UNKNOWN")
        self.assertIsNone(report["totals"]["viewsPerDay"])
        self.assertIn("not checked", ga4.MD.read_text(encoding="utf-8"))

class Restraint(unittest.TestCase):
    """Nothing in this file may write to the blog, and no status may fake a number."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_the_job_only_reads_and_never_writes_to_the_blog(self):
        source = pathlib.Path(ga4.__file__).read_text(encoding="utf-8")
        self.assertNotIn("googleapis.com/blogger", source)
        self.assertNotIn("DELETE", source)
        self.assertNotIn("PATCH", source)
        self.assertNotIn("BLOGGER_", source, "no Blogger credential is even readable here")

    def test_missing_credentials_are_reported_instead_of_assumptions(self):
        out = self.tmp / "g.json"
        md = self.tmp / "g.md"
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch.object(ga4, "site_tag", lambda: {"checked": False}):
                with mock.patch.object(ga4, "refresh_token", raise_missing):
                    with mock.patch("sys.argv", ["ga4_measurement.py"]):
                        with mock.patch.object(ga4, "OUT", out):
                            with mock.patch.object(ga4, "MD", md):
                                self.assertEqual(ga4.main(), 0)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "CREDENTIALS_MISSING")
        self.assertIsNone(report["totals"]["viewsPerDay"])
        self.assertIn("get_analytics_token.py", report["remedy"])

    def test_a_scope_failure_tells_the_owner_which_token_to_replace(self):
        out = self.tmp / "g.json"
        md = self.tmp / "g.md"
        with mock.patch.object(ga4, "site_tag", lambda: {"checked": False}):
            with mock.patch.object(ga4, "refresh_token", lambda: "MOCK-SECRET-VALUE-9137"):
                with mock.patch.object(ga4, "resolve_property", raise_forbidden):
                    with mock.patch("sys.argv", ["ga4_measurement.py"]):
                        with mock.patch.object(ga4, "OUT", out):
                            with mock.patch.object(ga4, "MD", md):
                                self.assertEqual(ga4.main(), 0)
        report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "SCOPE_INSUFFICIENT")
        self.assertIn("GA4_REFRESH_TOKEN", report["remedy"])
        self.assertNotIn("MOCK-SECRET-VALUE-9137", json.dumps(report),
                         "the report must never carry a credential")


def raise_missing():
    raise ga4.MissingCredentials()


def raise_forbidden(*_args, **_kwargs):
    raise urllib.error.HTTPError("https://example.invalid", 403, "Forbidden", {}, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class AudienceDistribution(unittest.TestCase):
    """The owner's question of 23 October 2026: Delhi, the other countries, and finance against the rest.

    These tests exist so the breakdown can never become a second-class part of the report: the daily
    totals must survive a Google refusal, and a place GA4 withholds must read as withheld, not as zero.
    """

    ROWS = [{"date": "2026-10-21", "views": 30, "activeUsers": 18, "engagedSessions": 18, "sessions": 20}]
    TAG = {"checked": True, "reachable": True, "measurementIds": ["G-WLEEYTKV12"], "installedHere": True}

    def test_geography_and_topics_reach_the_report_when_google_answers(self):
        detail = {"countries": {"status": "MEASURED", "rows": [{"name": "India", "views": 96}]},
                  "cities": {"status": "MEASURED", "rows": [{"name": "Delhi", "views": 41},
                                                            {"name": "Bhopal", "views": 7}]},
                  "topicSplit": {"viewsAccountedFor": 105,
                                 "families": [{"topic": "daily news editions", "views": 80}]},
                  "window": {"start": "2026-10-16", "end": "2026-10-22", "days": 7}}
        report = ga4.summarise(self.ROWS, self.TAG, "444", "test", detail=detail)
        self.assertEqual(report["totals"]["views"], 30, "the measured totals are untouched by the extra reports")
        self.assertEqual(report["geography"]["cities"]["rows"][0]["name"], "Delhi")
        self.assertEqual(report["topics"]["families"][0]["topic"], "daily news editions")
        self.assertEqual(report["breakdownWindow"]["days"], 7)

    def test_a_report_with_no_breakdown_says_so_instead_of_printing_empty_places(self):
        report = ga4.summarise(self.ROWS, self.TAG, "444", "test")
        self.assertIsNone(report["geography"])
        self.assertIsNone(report["topics"])

    def test_a_page_is_sorted_by_its_address_and_unmatched_pages_are_not_invented_into_finance(self):
        self.assertEqual(ga4.topic_of("https://dailyyield.blogspot.com/2026/10/india-finance-news-2026-10-21.html"),
                         "daily news editions")
        self.assertEqual(ga4.topic_of("https://dailyyield.blogspot.com/p/markets-today.html"),
                         "standing pages and tools")
        self.assertEqual(ga4.topic_of("https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10-18.html"),
                         "daily news editions", "the date in the address decides: it is a daily edition")
        self.assertEqual(ga4.topic_of("https://dailyyield.blogspot.com/p/gold-rate-by-city.html"),
                         "standing pages and tools")
        self.assertEqual(ga4.topic_of("https://dailyyield.blogspot.com/author/kushal.html"),
                         "other places on the site")

    def test_a_refused_report_is_recorded_as_not_measured_and_keeps_the_totals_alive(self):
        def refused(*args, **kwargs):
            raise urllib.error.HTTPError("https://example.invalid", 403, "Forbidden", {}, None)
        with mock.patch.object(ga4, "http", refused):
            detail = ga4.breakdown("token", "properties/1")
        for key in ("countries", "cities", "pages"):
            self.assertEqual(detail[key]["status"], "NOT_MEASURED", key)
            self.assertIn("not a defect", detail[key]["detail"],
                          "a Google refusal must read as a gap in the measurement, not as a site fault")
        self.assertEqual(detail["topicSplit"]["viewsAccountedFor"], 0)
        self.assertLess(detail["window"]["start"], detail["window"]["end"])
        report = ga4.summarise(self.ROWS, self.TAG, "444", "test", detail=detail)
        self.assertEqual(report["totals"]["views"], 30, "the measured totals survive a refused breakdown")
