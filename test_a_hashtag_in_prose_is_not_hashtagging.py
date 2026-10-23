#!/usr/bin/env python3
"""A hash in prose is not a hashtag, and a policy refusal is not a broken connection.

On 23 October the Americas edition never reached Facebook. The run's own health file said why:
`SOCIAL CONTENT POLICY GATE FAILED — excessive hashtagging`. Nothing had been wrong with the token and
nothing was wrong with Facebook - the ceiling is four tags, the caption carries four tags by design, and
the fifth token was an ordinal inside the quoted article line. A count that reads `#1` as a hashtag turns
a day's editorial prose into a refused share, and a refused share that is blamed on credentials sends
the owner to re-authorise something that was never broken.

The ceiling is untouched: four real tags still pass, five still fail. What changed is what counts as a
tag - a word, not any hash-shaped mark, and not a colour code - and what the health file advises when
our own rule is the thing that said no.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from content_policy_guard import assert_social_compliant  # noqa: E402
import social_credential_health as health  # noqa: E402

BRAND = "#DailyYield #KushalDaga #CAKushalDaga #Markets"


class HashtagCount(unittest.TestCase):
    def test_four_tags_still_pass(self):
        self.assertTrue(assert_social_compliant(f"Americas shipped more wheat this quarter. {BRAND}"))

    def test_five_tags_still_fail(self):
        with self.assertRaises(RuntimeError) as caught:
            assert_social_compliant(f"Quarterly figures. {BRAND} #Economy")
        self.assertIn("excessive hashtagging", str(caught.exception))

    def test_an_ordinal_in_the_article_is_not_a_hashtag(self):
        text = ("The United States is the #1 buyer of Indian pharmaceuticals and the #2 exporter of wheat "
                f"to the region. {BRAND}")
        self.assertTrue(assert_social_compliant(text), "a ranking is prose; it must not cost the share")

    def test_a_colour_or_code_is_not_a_hashtag(self):
        self.assertTrue(assert_social_compliant(f"The palette runs #c86a3d to #F8F0E3. {BRAND}"))

    def test_a_real_tag_that_happens_to_look_numeric_still_counts(self):
        # `#4thquarter` carries letters, so it is a tag and the ceiling applies to it.
        with self.assertRaises(RuntimeError):
            assert_social_compliant(f"{BRAND} #4thquarter")


class HealthAdvice(unittest.TestCase):
    def setUp(self):
        self.path = pathlib.Path(tempfile.mkdtemp()) / "health.json"

    def test_a_policy_refusal_is_not_reported_as_a_broken_connection(self):
        row = health.record("facebook", False,
                            "RuntimeError: SOCIAL CONTENT POLICY GATE FAILED — excessive hashtagging",
                            path=self.path)
        self.assertFalse(row["ok"])
        self.assertNotIn("re-authorise", row["action"], "the owner must not be sent to fix a token that works")
        self.assertIn("our own content policy", row["action"])
        self.assertIn("re-plans", row["action"], "and the share must stay owed until it goes out")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["facebook"]["ok"], False)

    def test_a_network_failure_still_asks_the_owner(self):
        row = health.record("facebook", False, "Graph returned (#190) the access token has expired",
                            path=self.path)
        self.assertIn("re-authorise", row["action"])

    def test_a_working_platform_says_so(self):
        row = health.record("bluesky", True, path=self.path)
        self.assertEqual(row["action"], "none; the network is publishing")


class CopyStillAnswersTheRule(unittest.TestCase):
    def test_the_facebook_caption_keeps_exactly_the_four_designed_tags(self):
        source = (ROOT / "social_creative.py").read_text(encoding="utf-8")
        self.assertIn('tags = ["#DailyYield", "#KushalDaga", "#CAKushalDaga", TOPIC_TAGS[group]]', source)
        self.assertNotIn("SOCIAL_HASHTAGE_CEILING", source, "no new knob: the gate's four is the ceiling")


if __name__ == "__main__":
    unittest.main()
