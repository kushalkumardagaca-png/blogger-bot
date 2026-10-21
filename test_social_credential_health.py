#!/usr/bin/env python3
"""The point of this module is that a broken network becomes readable, not that it is forgiven."""
import json
import tempfile
import unittest
from pathlib import Path

import social_credential_health as health
import social_guard


class Recording(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "SOCIAL_CREDENTIAL_HEALTH.json"

    def test_a_failure_is_recorded_with_the_platforms_own_words(self):
        row = health.record("bluesky", False, "Bluesky refresh returned no access token", self.path)
        self.assertFalse(row["ok"])
        self.assertIn("re-authorise", row["action"])
        self.assertEqual(json.loads(self.path.read_text())["bluesky"]["reason"],
                         "Bluesky refresh returned no access token")

    def test_a_working_network_is_recorded_as_working(self):
        health.record("bluesky", True, "", self.path)
        rows = json.loads(self.path.read_text())
        self.assertTrue(rows["bluesky"]["ok"])
        self.assertEqual(rows["bluesky"]["action"], "none; the network is publishing")

    def test_previous_platforms_survive_a_single_update(self):
        health.record("bluesky", False, "token expired", self.path)
        health.record("mastodon", True, "", self.path)
        rows = json.loads(self.path.read_text())
        self.assertEqual({"bluesky", "mastodon"}, set(rows))
        self.assertFalse(rows["bluesky"]["ok"])

    def test_a_token_shaped_string_never_reaches_the_repository(self):
        secret = "bearer " + "Ab3" * 20
        health.record("facebook", False, f"rejected {secret} outright", self.path)
        written = self.path.read_text()
        self.assertNotIn("Ab3Ab3", written)
        self.assertIn("[redacted]", json.loads(written)["facebook"]["reason"])

    def test_an_unusable_file_does_not_raise(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertTrue(health.record("bluesky", True, "", self.path)["ok"])


class ReasonExtraction(unittest.TestCase):
    def test_the_last_useful_line_is_the_one_a_human_needs(self):
        tmp = Path(tempfile.mkdtemp()) / "out.txt"
        tmp.write_text("fetching inventory\nHTTP 429 Too Many Requests from mastodon.social\n", encoding="utf-8")
        self.assertIn("429", health.reason_from(tmp))

    def test_output_with_no_error_word_gives_no_invented_reason(self):
        tmp = Path(tempfile.mkdtemp()) / "quiet.txt"
        tmp.write_text("starting up\nall good so far\n", encoding="utf-8")
        self.assertEqual("", health.reason_from(tmp))

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual("", health.reason_from(Path(tempfile.mkdtemp()) / "absent.txt"))


class GuardSeesIt(unittest.TestCase):
    """social_guard already refuses to dispatch to a network recorded as broken; this proves the
    file this module writes is the file that guard reads."""

    def test_a_recorded_failure_blocks_that_route(self):
        root = Path(tempfile.mkdtemp())
        (root / "SOCIAL_CREDENTIAL_HEALTH.json").write_text(json.dumps(
            {"mastodon": {"ok": False, "reason": "token revoked by the network"},
             "bluesky": {"ok": True, "reason": ""}}), encoding="utf-8")
        blocked = social_guard.blocked_platforms(root)
        self.assertEqual({"mastodon"}, set(blocked))
        self.assertIn("revoked", blocked["mastodon"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
