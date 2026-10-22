"""A wire headline about tax rules must not be able to hold up a whole edition.

On 22 October 2026 the global desk failed its slot twice and the failure brief said "tax rule stated as
permanent fact with no date and no change notice". Nothing was wrong with the reporting, and the rule was
right: an article must not tell a reader that a tax position is permanent. What was wrong was the format -
an agency's own headline, carried into a heading and two explanatory sentences, arrived as though it were
our claim, with the filing date sitting in a chip beside it where the rule cannot see it.

The fix states the truth in the sentence instead of loosening the rule, and these tests hold both halves:
the claim gets attributed and dated, and an ordinary item is left exactly as it was.
"""
from __future__ import annotations

import datetime as dt
import re
import unittest

import news_pipeline
from advice_risk_gate import audit

TITLE = "New rules make solar exports tax-free for two years"
ORDINARY = "China exports rise as factory output recovers"


def item(title: str, **extra) -> dict:
    base = {"title": title, "agency": "Xinhua", "date": dt.date(2026, 10, 21),
            "desc": "The ministry said the change takes effect from April.",
            "url": "https://example.org/filing", "topic": "global"}
    base.update(extra)
    return base


def plain(block: str) -> str:
    return re.sub(r"<[^>]+>", " ", block)


class TaxClaimsAreAnchored(unittest.TestCase):
    def compose(self, title: str, **extra) -> str:
        return news_pipeline.compose_item(item(title, **extra),
                                          dt.datetime.now(dt.timezone.utc))

    def test_a_tax_rule_from_a_wire_headline_is_attributed_and_dated_in_the_sentence(self):
        block = self.compose(TITLE)
        self.assertIn("as Xinhua reported on 21 October 2026", block)
        verdict = audit("Markets and policy at the start of the week", plain(block))
        self.assertEqual([], [row["rule"] for row in verdict["blocking"] if "tax rule" in row["rule"]],
                         "the edition must not be held for a format the reader can already see")

    def test_every_sentence_carrying_the_claim_is_anchored_not_just_the_heading(self):
        """The gate reads sentences, so the fix has to work on sentences, wherever the title is repeated.

        Judged with the gate's own patterns rather than a keyword of my invention, so this test cannot
        drift from the rule it is meant to prove - and so it cannot pass by my wording being luckier.
        """
        from advice_risk_gate import ATTRIBUTION, DATE_IN_SENTENCE, TAX_ASSERTION, TAX_HEDGE
        block = self.compose(TITLE)
        unanchored = []
        for sentence in re.split(r"(?<=[.!?])\s+", plain(block)):
            body = sentence.strip()
            if (TAX_ASSERTION.search(body)
                    and not (ATTRIBUTION.search(body) or DATE_IN_SENTENCE.search(body) or TAX_HEDGE.search(body))):
                unanchored.append(body[:180])
        self.assertEqual([], unanchored,
                         "an unanchored copy of the claim would still stop the edition: "
                         + " | ".join(unanchored))
        self.assertGreaterEqual(block.count("as Xinhua reported on 21 October 2026"), 3,
                               "the heading, the status line and the context sentence all repeat the claim")

    def test_a_background_filing_is_anchored_too(self):
        block = self.compose(TITLE, background=True)
        self.assertIn("as Xinhua reported on 21 October 2026", block)

    def test_an_ordinary_headline_is_left_exactly_as_it_was(self):
        """No needless rewriting: a story that makes no tax promise reads the same as yesterday."""
        block = self.compose(ORDINARY)
        self.assertNotIn("as Xinhua reported", block)
        self.assertIn(f"<h3>{ORDINARY}</h3>", block)

    def test_an_undated_filing_is_still_attributed(self):
        """A filing with no date in the feed gets the attribution without inventing a day."""
        block = self.compose(TITLE, date=None)
        self.assertIn("as Xinhua reported", block)
        self.assertNotIn("21 October", block)

    def test_the_rule_itself_is_untouched(self):
        """This is not a softer gate: the same sentence, without the attribution, must still be stopped."""
        verdict = audit("Tax guide", "The new limit is exempt from tax for everyone.")
        self.assertTrue(any("tax rule" in row["rule"] for row in verdict["blocking"]),
                        "the gate must still refuse a bare permanent-fact claim")


if __name__ == "__main__":
    unittest.main(verbosity=2)
