#!/usr/bin/env python3
"""An interrupted News run must be repaired, not repeated as a failure.

The Banking desk failed repeatedly on 15 October with "editorial integrity
fingerprint missing": an earlier run had left a partial live post behind, and
every later attempt stopped on the same verification instead of fixing it. These
tests lock in the repair path.
"""
from __future__ import annotations

import unittest

import news_pipeline as np


def article(title="Banking & Personal Money News"):
    return {"title": title, "slug": "banking-fintech-personal-money", "labels": ["News", "Banking"],
            "html": "<article><h1>" + title + "</h1><p>Body text for the edition.</p></article>",
            "canonical": "https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10.html"}


class RepairPathTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.stored = {"id": "42", "url": "https://dailyyield.blogspot.com/2026/10/x.html",
                       "title": "Banking & Personal Money News", "status": "LIVE",
                       "content": "<p>Partial body from an interrupted run.</p>"}
        self.put_payload = {}

        def fake_blogger_call(path, token, method="GET", payload=None, **kwargs):
            self.calls.append((method, path))
            if method == "PUT":
                self.put_payload.update(payload or {})
                self.stored["content"] = (payload or {}).get("content", self.stored["content"])
                self.stored["title"] = (payload or {}).get("title", self.stored["title"])
                return self.stored
            if path.endswith("fetchBody=true"):
                return self.stored
            return {"items": []}

        self._blogger_call, np.blogger_call = np.blogger_call, fake_blogger_call
        self._green, np.assert_green_operating_state = np.assert_green_operating_state, lambda *a, **k: True
        self._find, np.find_duplicate = np.find_duplicate, lambda *a, **k: (dict(self.stored), "same canonical path")
        self._incomplete, np.find_incomplete_live_post = np.find_incomplete_live_post, lambda *a, **k: None

    def tearDown(self):
        np.blogger_call, np.assert_green_operating_state = self._blogger_call, self._green
        np.find_duplicate, np.find_incomplete_live_post = self._find, self._incomplete

    def test_partial_post_is_stamped_and_returned(self):
        url = np.publish_post(article(), "token")
        self.assertTrue(url)
        self.assertIn(("PUT", "/posts/42"), self.calls)
        self.assertIn("DY_EDITORIAL_INTEGRITY_V1", self.put_payload.get("content", ""))
        self.assertIn("DY_AUTOMATION_DISCLOSURE_GREEN_V2", self.put_payload.get("content", ""))
        self.assertEqual(self.put_payload.get("title"), "Banking & Personal Money News")

    def test_healthy_duplicate_is_still_returned_untouched(self):
        green = dict(self.stored)
        green["content"] = (np.stamp(article()["html"], "Banking & Personal Money News", "news-desk")
                            + np.automation_disclosure("article"))
        np.find_duplicate = lambda *a, **k: (dict(green), "same canonical path")
        url = np.publish_post(article(), "token")
        self.assertTrue(url)
        self.assertNotIn(("PUT", "/posts/42"), self.calls)

    def test_older_edition_post_is_left_intact_and_today_gets_its_own_post(self):
        # the Americas desk case: a green post carrying the previous day's edition.
        # Overwriting it (which is what happened to Banking on 18 October) destroyed
        # an earlier published edition and made today's article inherit yesterday's
        # publish time and address, so the day's slot could not be verified.
        self.stored = {"id": "77", "url": "https://dailyyield.blogspot.com/2026/10/americas.html",
                       "title": "Americas Finance News \u2014 14 October 2026", "status": "LIVE",
                       "published": "2026-10-13T22:45:00Z",
                       "content": np.stamp("<h1>Americas Finance News \u2014 14 October 2026</h1><p>old</p>",
                                            "Americas Finance News \u2014 14 October 2026", "news-desk")
                       + np.automation_disclosure("news edition")}
        np.find_duplicate = lambda *a, **k: (dict(self.stored), "near-duplicate topic title")
        art = article("Americas Finance News \u2014 15 October 2026")
        finished = (np.stamp(art["html"], art["title"], "news-desk")
                    + np.automation_disclosure("news edition"))
        fresh = {"id": "78", "url": "https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-15.html",
                 "status": "LIVE", "title": art["title"], "content": finished}
        def create_aware(path, token, method="GET", payload=None, **kwargs):
            self.calls.append((method, path))
            if method == "POST" and path.startswith("/posts?"):
                return {"id": "78"}
            if path.startswith("/posts/78/publish"):
                return {"id": "78", "url": fresh["url"], "status": "LIVE"}
            if path.startswith("/posts/78"):
                return dict(fresh)
            return {"items": []}

        np.blogger_call = create_aware
        url = np.publish_post(art, "token")
        self.assertNotIn(("PUT", "/posts/77"), self.calls,
                         "an earlier edition must not be rewritten")
        self.assertIn(("POST", "/posts?isDraft=true"), self.calls)
        self.assertEqual(url, fresh["url"])

    def test_same_edition_post_is_not_rewritten(self):
        html = np.stamp(article()["html"], "Banking & Personal Money News", "news-desk")
        html += np.automation_disclosure("news edition")
        html = html.replace("Banking & Personal Money News", "Banking & Personal Money News \u2014 15 October 2026")
        self.stored.update({"title": "Banking & Personal Money News \u2014 15 October 2026",
                            "content": html})
        np.find_duplicate = lambda *a, **k: (dict(self.stored), "same slug path")
        np.publish_post(article("Banking & Personal Money News \u2014 15 October 2026"), "token")
        self.assertNotIn(("PUT", "/posts/42"), self.calls)

    def test_repair_that_still_fails_raises(self):
        def broken_put(path, token, method="GET", payload=None, **kwargs):
            self.calls.append((method, path))
            if method == "PUT":
                return {"id": "42", "status": "LIVE", "content": "<p>still partial</p>",
                        "url": self.stored["url"], "title": "Banking & Personal Money News"}
            return {"items": []}

        np.blogger_call = broken_put
        with self.assertRaises(RuntimeError):
            np.publish_post(article(), "token")


class LiveEditionTests(unittest.TestCase):
    """An address occupied by an older edition must never count as published."""

    def setUp(self):
        self.day = __import__("datetime").date(2026, 10, 15)
        self._call = np.blogger_call
        self._green = np.assert_saved_green
        np.assert_saved_green = lambda *a, **k: True

    def tearDown(self):
        np.blogger_call, np.assert_saved_green = self._call, self._green

    def test_yesterdays_edition_at_todays_address_is_not_current(self):
        np.blogger_call = lambda *a, **k: {"status": "LIVE", "url": "https://x", "id": "1",
                                           "title": "Americas Finance News \u2014 14 October 2026",
                                           "content": "<h1>Americas Finance News \u2014 14 October 2026</h1>"}
        self.assertFalse(np.live_current_edition("https://dailyyield.blogspot.com/p.html", "t", self.day))

    def test_todays_edition_is_current(self):
        np.blogger_call = lambda *a, **k: {"status": "LIVE", "url": "https://x", "id": "1",
                                           "title": "Americas Finance News \u2014 15 October 2026",
                                           "content": "<h1>Americas Finance News \u2014 15 October 2026</h1>"}
        self.assertTrue(np.live_current_edition("https://dailyyield.blogspot.com/p.html", "t", self.day))

    def test_americas_edition_keeps_the_completed_market_date(self):
        # by design the Americas heading carries the previous day
        np.blogger_call = lambda *a, **k: {"status": "LIVE", "url": "https://x", "id": "1",
                                           "title": "Americas Finance News \u2014 14 October 2026",
                                           "content": "<h1>Americas Finance News \u2014 14 October 2026</h1>"}
        import datetime as _dt
        url = "https://dailyyield.blogspot.com/p.html"
        self.assertFalse(np.live_current_edition(url, "t", self.day))
        self.assertTrue(np.live_current_edition(url, "t", self.day, (_dt.date(2026, 10, 14),)))

    def test_other_desk_does_not_accept_yesterdays_heading(self):
        np.blogger_call = lambda *a, **k: {"status": "LIVE", "url": "https://x", "id": "1",
                                           "title": "Europe Finance News \u2014 14 October 2026",
                                           "content": "<h1>Europe Finance News \u2014 14 October 2026</h1>"}
        self.assertFalse(np.live_current_edition("https://dailyyield.blogspot.com/p.html", "t", self.day))

    def test_missing_or_draft_post_is_not_current(self):
        np.blogger_call = lambda *a, **k: {"status": "DRAFT", "url": "https://x", "id": "1", "content": ""}
        self.assertFalse(np.live_current_edition("https://dailyyield.blogspot.com/p.html", "t", self.day))
        self.assertFalse(np.live_current_edition("", "t", self.day))


class RenderingGuardTests(unittest.TestCase):
    def test_stamp_is_idempotent(self):
        html = article()["html"]
        once = np.stamp(html, "Banking & Personal Money News", "news-desk")
        twice = np.stamp(once, "Banking & Personal Money News", "news-desk")
        self.assertEqual(once, twice)
        self.assertEqual(once.count("DY_EDITORIAL_INTEGRITY_V1"), 1)




class ByPathLivenessTests(unittest.TestCase):
    """A by-path read does not return `status`; that absence must not read as dead.

    The recovery controller rejected every healthy edition on 16 October because
    this rule treated a missing field as "not live".
    """

    def setUp(self):
        self._call = np.blogger_call
        self._green = np.assert_saved_green
        np.assert_saved_green = lambda *a, **k: True
        self.addCleanup(self.restore)

    def restore(self):
        np.blogger_call, np.assert_saved_green = self._call, self._green

    def test_a_by_path_reply_without_a_status_field_still_counts(self):
        np.blogger_call = lambda *a, **k: {
            "id": "1", "url": "https://x/p.html",
            "title": "India Finance News \u2014 16 October 2026",
            "content": '<div class="fbk-kicker"><span class="fbk-date">Thursday, 16 October 2026 \u00b7 IST</span></div>'
                       '<h1 class="fbk-h1">India Finance News \u2014 16 October 2026</h1>'}
        self.assertTrue(np.live_current_edition("https://x/p.html", "t", __import__("datetime").date(2026, 10, 16)))

    def test_an_explicitly_non_live_reply_is_still_rejected(self):
        np.blogger_call = lambda *a, **k: {"id": "1", "url": "https://x/p.html", "status": "DRAFT",
                                           "title": "t", "content": "<h1>t</h1>"}
        self.assertFalse(np.live_current_edition("https://x/p.html", "t", __import__("datetime").date(2026, 10, 16)))

if __name__ == "__main__":
    unittest.main()
