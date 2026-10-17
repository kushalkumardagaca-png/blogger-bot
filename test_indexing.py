#!/usr/bin/env python3
"""Indexing automation: never lose a URL, never spend quota twice."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


class SitemapCatchUpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "INDEXNOW_STATE.json"
        self._state, ix.STATE = ix.STATE, self.state
        self._urls, ix.sitemap_urls = ix.sitemap_urls, lambda: [
            "https://dailyyield.blogspot.com/old.html",
            "https://dailyyield.blogspot.com/new.html"]

    def tearDown(self):
        ix.STATE, ix.sitemap_urls = self._state, self._urls

    def test_only_urls_never_announced_before_are_sent(self):
        self.state.write_text(json.dumps({"submitted": {
            "https://dailyyield.blogspot.com/old.html": "2026-10-17"}, "pending": []}))
        sent = []
        def fake_post(endpoint, payload):
            sent.append(payload["urlList"])
            return True, "HTTP 200"
        import sys
        with patch.dict("os.environ", {"INDEXNOW_KEY": "k"}, clear=True), \
             patch.object(ix, "post", fake_post):
            sys.argv = ["indexnow_submit.py", "--apply", "--from-sitemap"]
            ix.main()
        self.assertIn("https://dailyyield.blogspot.com/new.html", sent[0])
        self.assertNotIn("https://dailyyield.blogspot.com/old.html", sent[0])


class BlockedHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "INDEXNOW_STATE.json"
        self._state, ix.STATE = ix.STATE, self.state

    def tearDown(self):
        ix.STATE = self._state

    def test_a_html_key_location_parks_the_channel_instead_of_retrying_forever(self):
        refused = (False, "HTTP 422: URLs are not related to your site verified "
                          "through the keylocation parameter")
        with patch.dict("os.environ", {"INDEXNOW_KEY": "k"}, clear=True), \
             patch.object(ix, "post", lambda *a, **k: refused):
            first = ix.submit(["https://dailyyield.blogspot.com/a.html"], apply=True)
            self.assertEqual(first["sent"], 0)
            parked = json.loads(self.state.read_text())["blocked"]
            self.assertIn("blogspot", parked["reason"])
            # The next run must not touch the network again.
            with patch.object(ix, "post") as call:
                second = ix.submit(["https://dailyyield.blogspot.com/b.html"], apply=True)
                call.assert_not_called()
            self.assertIn("blocked", second)

    def test_a_later_success_clears_the_block(self):
        self.state.write_text(json.dumps({"blocked": {"reason": "x"}, "pending": []}))
        with patch.dict("os.environ", {"INDEXNOW_KEY": "k", "INDEXNOW_FORCE": "1"}, clear=True), \
             patch.object(ix, "post", lambda *a, **k: (True, "HTTP 200")):
            ix.submit(["https://dailyyield.blogspot.com/a.html"], apply=True)
        self.assertNotIn("blocked", json.loads(self.state.read_text()))


if __name__ == "__main__":
    unittest.main()
