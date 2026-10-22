"""The publisher must recover its own lost response rather than print a second copy of the article.

Blogger will not overwrite a permalink that is taken, so a second creation of the same post lands
beside the first with a number glued onto the slug. Each pair is one article offered to Google and Bing
as two URLs with identical text, which is the single clearest thing both webmasters' guidelines tell a
publisher not to do - and on 22 October 2026 eight articles were in exactly that state.
"""
from __future__ import annotations

import unittest

from editorial_integrity import canonical_path, duplicate_reason

BLOG = "https://dailyyield.blogspot.com"


class NumberedTwins(unittest.TestCase):
    def test_blogger_s_numbered_permalink_resolves_to_the_article_it_copies(self):
        self.assertEqual("/2026/10/banking-fintech-personal-money-2026-10.html",
                         canonical_path(f"{BLOG}/2026/10/banking-fintech-personal-money-2026-10_01450325346.html"))

    def test_a_real_slug_that_ends_in_numbers_is_left_exactly_as_it_is(self):
        """The fix must not swallow a legitimate address: only the glued stamp is removed."""
        for slug in ("india-finance-news-2026-10-20", "top-10-stocks-2026-10", "quarter-2-2026"):
            self.assertEqual(f"/2026/10/{slug}.html", canonical_path(f"{BLOG}/2026/10/{slug}.html"), slug)

    def test_a_lost_publish_response_is_recognised_as_the_post_to_recover(self):
        """With the titles differing after an edit, the address alone still has to identify the article."""
        prior = {"title": "Banking and Fintech: October 2026", "url":
                 f"{BLOG}/2026/10/banking-fintech-personal-money-2026-10_01450325346.html"}
        reason = duplicate_reason("Banking & Fintech, October 2026 - Updated", "completely different prose",
                                  prior, f"{BLOG}/2026/10/banking-fintech-personal-money-2026-10.html")
        self.assertEqual("same canonical path", reason)

    def test_the_stamp_stripper_survives_a_malformed_address(self):
        self.assertEqual("", canonical_path(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
