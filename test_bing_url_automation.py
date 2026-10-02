import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bing_url_automation as bing


class BingUrlAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = patch.multiple(
            bing,
            STATE_PATH=root / "state.json",
            STATUS_JSON=root / "status.json",
            STATUS_MD=root / "status.md",
        )
        self.paths.start()
        self.env = patch.dict(os.environ, {"BING_WEBMASTER_API_KEY": "secret-test-key"})
        self.env.start()
        self.items = [
            {"id": "home", "kind": "home", "title": "Daily Yield", "url": bing.SITE,
             "updated": "2026-10-02T00:00:00Z", "content": "", "labels": [], "fingerprint": "home-fp"},
            {"id": "1", "kind": "post", "title": "Example financial guide", "url": bing.SITE + "2026/10/example.html",
             "updated": "2026-10-02T01:00:00Z", "content": "article", "labels": ["Finance"], "fingerprint": "post-fp"},
        ]

    def tearDown(self):
        self.env.stop()
        self.paths.stop()
        self.tmp.cleanup()

    def test_only_canonical_daily_yield_urls_are_allowed(self):
        self.assertTrue(bing.valid_daily_yield_url(bing.SITE + "2026/10/example.html"))
        self.assertFalse(bing.valid_daily_yield_url("http://dailyyield.blogspot.com/"))
        self.assertFalse(bing.valid_daily_yield_url("https://example.com/page"))
        self.assertFalse(bing.valid_daily_yield_url(bing.SITE + "?view=1"))

    def test_initial_submission_then_idempotent_retry(self):
        batches = []
        with patch.object(bing, "blogger_inventory", return_value=self.items), \
             patch.object(bing, "get_quota", return_value={"dailyAvailable": 10, "monthlyAvailable": 10}), \
             patch.object(bing, "submit_batch", side_effect=lambda key, urls: batches.append(urls)), \
             patch.object(bing, "get_url_info") as info:
            self.assertEqual(bing.main(), 0)
            self.assertEqual(sum(map(len, batches)), 2)
            self.assertFalse(info.called)
            batches.clear()
            self.assertEqual(bing.main(), 0)
            self.assertEqual(batches, [])
        report = json.loads(bing.STATUS_JSON.read_text())
        self.assertEqual(report["summary"]["candidates"], 0)
        self.assertEqual(report["summary"]["submitted"], 0)
        self.assertEqual(report["syntheticViews"], 0)

    def test_due_status_check_uses_get_url_info_without_resubmission(self):
        with patch.object(bing, "blogger_inventory", return_value=self.items), \
             patch.object(bing, "get_quota", return_value={"dailyAvailable": 10, "monthlyAvailable": 10}), \
             patch.object(bing, "submit_batch"), patch.object(bing, "get_url_info"):
            bing.main()
        state = json.loads(bing.STATE_PATH.read_text())
        for record in state["urls"].values():
            record["nextInspectionAt"] = "2000-01-01T00:00:00+00:00"
        bing.STATE_PATH.write_text(json.dumps(state))
        with patch.object(bing, "blogger_inventory", return_value=self.items), \
             patch.object(bing, "get_quota", return_value={"dailyAvailable": 10, "monthlyAvailable": 10}), \
             patch.object(bing, "submit_batch") as submit, \
             patch.object(bing, "get_url_info", return_value={"IsPage": True, "LastCrawledDate": "2026-10-02T02:00:00Z"}) as info:
            self.assertEqual(bing.main(), 0)
            self.assertFalse(submit.called)
            self.assertEqual(info.call_count, 2)
        final = json.loads(bing.STATE_PATH.read_text())
        self.assertTrue(all(row["status"] == "MONITOR_COMPLETE" for row in final["urls"].values()))

    def test_safe_error_detail_never_copies_request_url(self):
        value = bing.safe_detail(b'<html>https://ssl.bing.com/path?apikey=SECRET</html>')
        self.assertEqual(value, "provider returned a non-JSON error")
        self.assertNotIn("SECRET", value)


if __name__ == "__main__":
    unittest.main()
