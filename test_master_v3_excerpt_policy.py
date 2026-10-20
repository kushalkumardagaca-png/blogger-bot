#!/usr/bin/env python3
"""A quoted source passage may not smuggle a policy-breaking claim into a Master article.

On 20 October 2026 an evergreen slot died because the assembled package carried the phrase
"I invested in" inside a quotation, which the site's own policy refuses anywhere in the text.
These tests pin the defence: the window moves to another stretch of the same source instead of
publishing the unusable one, and it never rewrites or pads the source.
"""
import unittest

from master_v3_generator import POLICY_TRIP, head_clip, quoted_window

CLEAN = ("The filing lists fee schedules and the trust reported thirty one million dollars in "
         "assets under management this quarter").split()


class Window(unittest.TestCase):
    def test_a_clean_source_is_quoted_as_it_stands(self):
        self.assertEqual(quoted_window(CLEAN, 0, 12), " ".join(CLEAN[:12]))

    def test_a_source_made_entirely_of_banned_claims_is_not_quoted_at_all(self):
        toxic = "I invested in the fund and we tested it and returns are guaranteed forever".split()
        self.assertEqual(quoted_window(toxic, 0, 20), "")

    def test_a_banned_phrase_is_stepped_over_rather_than_rewritten(self):
        source = ("We tested the app for three weeks. The regulator published the fee table on "
                  "Tuesday and the board voted nine to two after the audit was filed").split()
        chosen = quoted_window(source, 0, 14)
        self.assertTrue(chosen, "a usable stretch exists further along the same record")
        self.assertFalse(POLICY_TRIP.search(chosen))
        # only subtraction of a stretch is allowed: the words must come from the source, in order
        self.assertIn(chosen, " ".join(source))

    def test_a_source_too_short_to_be_safe_is_dropped_not_invented(self):
        self.assertEqual(quoted_window(["fee", "table"], 0, 20), "")

    def test_every_banned_shape_is_recognised(self):
        for phrase in ("I tested the platform", "we invested in it", "guaranteed returns",
                       "risk free profit", "best casino to join", "how to phish a login"):
            with self.subTest(phrase=phrase):
                tokens = (phrase + " " + " ".join(CLEAN)).split()
                chosen = quoted_window(tokens, 0, len(tokens))
                self.assertFalse(POLICY_TRIP.search(chosen or ""),
                                 f"{phrase!r} must never survive as a quotation")


class TitleCeiling(unittest.TestCase):
    """The published title rule is the validator's, not a search-result estimate."""

    def test_a_generated_title_always_sits_inside_the_validators_range(self):
        for source in ("Payoneer: How Stablecoin is Scaling in Cross-Border Payments for Treasury",
                       "Bereaved families could face 'unjust' tax bill after the chancellor's review",
                       "X Money is here: What Elon Musk's financial super app means for savers today"):
            one = head_clip(source)
            with self.subTest(source=source[:24]):
                self.assertTrue(12 <= len(one) <= 46, one)
                self.assertTrue(source.startswith(one) or source.replace("’", "'").startswith(one))


if __name__ == "__main__":
    unittest.main(verbosity=2)
