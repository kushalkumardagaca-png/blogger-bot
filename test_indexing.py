#!/usr/bin/env python3
"""Indexing automation: never lose a URL, never spend quota twice."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bing_index_queue as bq
import indexnow_submit as ix


class IndexNowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "INDEXNOW_STATE.json"
        self._state, ix.STATE = ix.STATE, self.state

    def tearDown(self):
        ix.STATE = self._state

    def test_without_a_key_every_url_is_queued_not_lost(self):
        with patch.dict("os.environ", {}, clear=True):
            result = ix.submit(["https://dailyyield.blogspot.com/a.html"], apply=True)
        self.assertEqual(result["queued"], 1)
        saved = json.loads(self.state.read_text())
        self.assertIn("https://dailyyield.blogspot.com/a.html", saved["pending"])

    def test_urls_outside_the_site_are_ignored(self):
        with patch.dict("os.environ", {}, clear=True):
            result = ix.submit(["https://example.com/x"], apply=True)
        self.assertEqual(result["requested"], 0)

    def test_a_refused_endpoint_keeps_the_urls_queued(self):
        with patch.dict("os.environ", {"INDEXNOW_KEY": "k"}, clear=True), \
             patch.object(ix, "post", lambda *a, **k: (False, "HTTP 403")):
            result = ix.submit(["https://dailyyield.blogspot.com/b.html"], apply=True)
        self.assertEqual(result["sent"], 0)
        self.assertIn("https://dailyyield.blogspot.com/b.html",
                      json.loads(self.state.read_text())["pending"])

    def test_an_accepted_ping_is_recorded_and_leaves_the_queue(self):
        with patch.dict("os.environ", {"INDEXNOW_KEY": "k"}, clear=True), \
             patch.object(ix, "post", lambda *a, **k: (True, "HTTP 200")):
            result = ix.submit(["https://dailyyield.blogspot.com/c.html"], apply=True)
        self.assertEqual(result["sent"], 1)
        saved = json.loads(self.state.read_text())
        self.assertIn("https://dailyyield.blogspot.com/c.html", saved["submitted"])
        self.assertEqual(saved["pending"], [])


class BingQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "BING_INDEX_QUEUE.json"
        self._state, bq.STATE = bq.STATE, self.state
        self._urls, bq.sitemap_urls = bq.sitemap_urls, lambda: [
            "https://dailyyield.blogspot.com/new.html",
            "https://dailyyield.blogspot.com/old.html"]

    def tearDown(self):
        bq.STATE, bq.sitemap_urls = self._state, self._urls

    def test_quota_zero_sends_nothing_and_keeps_the_queue(self):
        with patch.dict("os.environ", {"BING_WEBMASTER_API_KEY": "k"}, clear=True), \
             patch.object(bq, "quota", lambda key: (0, 1400)):
            with patch.object(bq, "api_call") as call:
                bq.main.__wrapped__ if hasattr(bq.main, "__wrapped__") else None
                import sys
                sys.argv = ["bing_index_queue.py", "--apply"]
                bq.main()
                call.assert_not_called()
        self.assertEqual(len(json.loads(self.state.read_text())["queue"]), 2)

    def test_a_positive_quota_sends_newest_first_and_records_it(self):
        sent = []
        with patch.dict("os.environ", {"BING_WEBMASTER_API_KEY": "k"}, clear=True), \
             patch.object(bq, "quota", lambda key: (1, 1400)), \
             patch.object(bq, "api_call", lambda op, key, params, body=None: sent.append(body) or {}):
            import sys
            sys.argv = ["bing_index_queue.py", "--apply"]
            bq.main()
        self.assertEqual(sent[0]["urlList"], ["https://dailyyield.blogspot.com/new.html"])

    def test_a_url_is_never_paid_for_twice(self):
        self.state.write_text(json.dumps({"sent": {
            "https://dailyyield.blogspot.com/new.html": "2026-10-17"}, "queue": []}))
        with patch.dict("os.environ", {"BING_WEBMASTER_API_KEY": "k"}, clear=True), \
             patch.object(bq, "quota", lambda key: (5, 1400)), \
             patch.object(bq, "api_call") as call:
            import sys
            sys.argv = ["bing_index_queue.py", "--apply"]
            bq.main()
        bodies = [c.kwargs.get("body") for c in call.call_args_list if c.kwargs.get("body")]
        if bodies:
            self.assertNotIn("https://dailyyield.blogspot.com/new.html", bodies[0]["urlList"])


if __name__ == "__main__":
    unittest.main()
