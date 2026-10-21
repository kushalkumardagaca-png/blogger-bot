"""The Analytics credential must be assembled value by value, not set by set.

A repository that holds only ``GA4_REFRESH_TOKEN`` plus the existing Search Console client pair is
the *finished* setup GA4_CONNECT.md asks for. Selecting a whole prefix instead made two jobs read the
older Search Console token, which has no Analytics scope, so the owner's one correct paste would still
have been reported as "not connected".
"""
import os
import unittest
from unittest.mock import patch

import google_credentials as gc

COMPLETE = {name: "" for name in gc.CLIENT_ID + gc.CLIENT_SECRET + gc.REFRESH_TOKEN}


class ValueByValue(unittest.TestCase):
    def test_one_paste_with_the_existing_client_pair_counts_as_configured(self):
        env = {**COMPLETE, "GSC_CLIENT_ID": "cid", "GSC_CLIENT_SECRET": "sec",
               "GSC_REFRESH_TOKEN": "old-token", "GA4_REFRESH_TOKEN": "new-token"}
        with patch.dict(os.environ, env, clear=True):
            cid, secret, refresh, source, complete = gc.analytics_credentials()
        self.assertEqual((cid, secret, refresh), ("cid", "sec", "new-token"))
        self.assertTrue(complete, "the Analytics token must win over the older Search Console one")
        self.assertIn("GA4_REFRESH_TOKEN", source)
        self.assertIn("GSC_CLIENT_ID", source)

    def test_the_full_analytics_set_is_used_when_present(self):
        env = {**COMPLETE, "GSC_CLIENT_ID": "cid", "GSC_CLIENT_SECRET": "sec",
               "GA4_CLIENT_ID": "ga4-cid", "GA4_CLIENT_SECRET": "ga4-sec",
               "GA4_REFRESH_TOKEN": "ga4-token"}
        with patch.dict(os.environ, env, clear=True):
            cid, secret, refresh, source, complete = gc.analytics_credentials()
        self.assertEqual((cid, secret, refresh), ("ga4-cid", "ga4-sec", "ga4-token"))
        self.assertEqual(source, "GA4_REFRESH_TOKEN")

    def test_a_half_stored_setup_is_reported_as_incomplete_not_guessed(self):
        env = {**COMPLETE, "GSC_CLIENT_ID": "cid", "GSC_CLIENT_SECRET": "sec"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(gc.analytics_credentials()[4])
            with self.assertRaises(RuntimeError) as caught:
                gc.access_token()
        self.assertIn("GA4_REFRESH_TOKEN", str(caught.exception))

    def test_a_token_google_returned_without_one_is_not_invented(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            @staticmethod
            def read(): return b'{"expires_in": 3600}'
        with patch.dict(os.environ, {**COMPLETE, "GA4_CLIENT_ID": "a", "GA4_CLIENT_SECRET": "b",
                                     "GA4_REFRESH_TOKEN": "c"}, clear=True), \
             patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaises(RuntimeError):
                gc.access_token()


if __name__ == "__main__":
    unittest.main()
