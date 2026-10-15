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


class RenderingGuardTests(unittest.TestCase):
    def test_stamp_is_idempotent(self):
        html = article()["html"]
        once = np.stamp(html, "Banking & Personal Money News", "news-desk")
        twice = np.stamp(once, "Banking & Personal Money News", "news-desk")
        self.assertEqual(once, twice)
        self.assertEqual(once.count("DY_EDITORIAL_INTEGRITY_V1"), 1)


if __name__ == "__main__":
    unittest.main()
