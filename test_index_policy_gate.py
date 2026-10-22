#!/usr/bin/env python3
"""The indexing-policy gate must be able to say no, and must stay silent when nothing is wrong.

Every rule here came out of the 22 October 2026 whole-corpus audit, so each test is a defect that was
actually published: an ALL-CAPS page title, a headline clipped onto a comma, a title shared by six URLs,
an image with no alt text, and a post whose title was the string "http://schema.org".

No network, no Blogger calls, no writes: this module is pure measurement, and the tests keep it that way.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import index_policy_gate as gate

def varied(count: int) -> str:
    """Distinct lowercase words, so the prose does not trip the stuffing rule by construction.

    A filler paragraph that repeats "desk" 200 times would fail the stuffing test the audit is also
    enforcing, and the compliant fixture has to be compliant for every reason at once.
    """
    return " ".join(f"{chr(97 + (i // 26) % 26)}{chr(97 + i % 26)}tion" for i in range(count))


SENTENCES = varied(400)
BODY = f"<p>{SENTENCES}</p>"


class Stuffing(unittest.TestCase):
    def test_a_word_hammered_through_every_paragraph_is_held(self):
        body = "<p>" + "best loan best loan best loan best loan at the counter</p>" * 8
        self.assertIn(gate.most_used_word(body)[0], ("best", "loan"))
        self.assertTrue(any("paragraphs" in row for row in gate.check_article("Best loan rates", body)))

    def test_an_article_may_name_its_own_subject(self):
        # the share-of-prose version of this rule reported 12 live URLs as stuffed: "china" on the China
        # edition, "insurance" on a guide to types of insurance, "social" on Social Security. None of
        # them was keyword stuffing, and a gate that holds good articles gets switched off.
        topical = "<p>" + " ".join(f"china {index} export figure settled" for index in range(300)) + "</p>"
        self.assertEqual(gate.most_used_word(topical)[0], "")

    def test_link_labels_are_navigation_not_prose(self):
        hub = ("<p>" + " ".join(f"gold {index} rate in india" for index in range(200)) + "</p>"
               + "".join(f'<a href="/x{i}">article {i}</a>' for i in range(300)))
        self.assertEqual(gate.most_used_word(hub)[0], "")


class Titles(unittest.TestCase):
    def test_an_all_caps_title_becomes_sentence_case_without_losing_acronyms(self):
        self.assertEqual(gate.publish_title("TERMS AND CONDITIONS"), "Terms and conditions")
        self.assertEqual(gate.publish_title("GOLD RATE AND EMI CALCULATOR TODAY"),
                         "Gold rate and EMI calculator today")
        self.assertEqual(gate.sentence_case("How Nifty and SENSEX moved today"),
                         "How Nifty and SENSEX moved today")

    def test_a_headline_is_never_left_ending_on_a_comma_a_preposition_or_a_possessive(self):
        cut = ("Student Loan Interest Rates: Federal, Private, And Public Compared Across Every Product "
               "Offered This Quarter")
        fixed = gate.publish_title(cut)
        self.assertTrue(fixed)
        self.assertLessEqual(len(fixed), gate.TITLE_MAX)
        self.assertFalse(gate.title_is_cut(fixed), fixed)
        self.assertFalse(fixed.endswith(","))
        possessive = "Billionaire Mukesh Ambani launches India's largest retail fund in a decade of deals"
        self.assertFalse(gate.publish_title(possessive).lower().endswith("'s"))

    def test_a_raw_token_is_refused_rather_than_pretty_printed(self):
        for junk in ("article", "http://schema.org", "untitled", "42", "indexnow-key"):
            self.assertEqual(gate.publish_title(junk), "", f"{junk!r} must never become a headline")
        self.assertTrue(gate.title_problems("https://example.com/a"))

    def test_a_compliant_title_comes_back_unchanged(self):
        for good in ("Gold rate today in India", "Markets today: Asia opens higher",
                     "Daily articles: every desk index"):
            self.assertEqual(gate.publish_title(good), good)
            self.assertEqual(gate.title_problems(good), [])

    def test_a_second_url_with_the_same_title_gets_a_number_not_a_new_subject(self):
        taken = {"Gold rate today in India"}
        self.assertEqual(gate.publish_title("Gold rate today in India", taken),
                         "Gold rate today in India (2)")
        self.assertEqual(gate.publish_title("Gold rate today in India", taken, number_if_taken=False), "")

    def test_a_title_too_long_is_measured_the_way_both_engines_read_it(self):
        long = "Corporate Finance and Industry News · 8 October 2026 · Coverage October 7 to 8 — " \
               "After a quiet session the desk reopened higher on rate expectations"
        self.assertTrue(any("characters" in row for row in gate.title_problems(long)))
        self.assertLessEqual(len(gate.publish_title(long)), gate.TITLE_MAX)


class PageTitles(unittest.TestCase):
    def test_a_pages_own_heading_is_a_better_title_than_its_all_caps_label(self):
        body = f'<h2>EMI, SIP and loan calculators</h2><p>{SENTENCES}</p>'
        self.assertEqual(gate.page_title(body), "EMI, SIP and loan calculators")

    def test_a_heading_too_short_to_describe_anything_is_not_used(self):
        self.assertEqual(gate.page_title(f"<h1>News</h1><p>{SENTENCES}</p>"), "")


class ImagesAndDuplicates(unittest.TestCase):
    def test_missing_alt_text_is_counted_and_weak_alt_text_does_not_pass(self):
        markup = '<img src="/a.jpg" alt="Traders watch the BSE tickers"><img src="/b.jpg">' \
                 '<img src="/c.jpg" alt="image">'
        self.assertEqual(gate.alt_failures(markup), 2)

    def test_identical_documents_match_and_different_ones_do_not(self):
        other = varied(400).replace("tion", "ment")
        self.assertEqual(gate.near_duplicate(SENTENCES, [SENTENCES])[1], 0)
        self.assertEqual(gate.near_duplicate(SENTENCES, [other])[1], -1)
        self.assertEqual(gate.similarity("alpha " * 20, "alpha " * 20), 0.0,
                         "a page below the document floor gets no similarity opinion at all")

    def test_link_labels_are_navigation_not_prose(self):
        hub = f"<p>{SENTENCES}</p>" + "".join(f'<a href="/x{i}">article {i}</a>' for index in range(1)
                                              for i in range(30))
        word, share = gate.most_used_word(hub)
        self.assertNotEqual(word, "article")
        self.assertEqual(gate.alt_failures(hub), 0)


class TheWholeGate(unittest.TestCase):
    def test_a_sound_article_passes_with_no_comment(self):
        self.assertEqual(gate.check_article("Gold rate today in India", BODY), [])

    def test_a_thin_or_unalticed_page_is_held_before_it_is_published(self):
        problems = gate.check_article("Gold rate today in India", "<p>one two three</p>")
        self.assertTrue(any("thin" in row for row in problems), problems)
        problems = gate.check_article("Gold rate today in India", BODY + '<img src="/x.jpg">',
                                       taken_titles={"Gold rate today in India"})
        self.assertTrue(any("alt" in row for row in problems), problems)
        self.assertTrue(any("exact title" in row for row in problems), problems)

    def test_a_duplicate_of_a_sibling_is_held(self):
        problems = gate.check_article("Gold rate today in India", BODY, siblings=[BODY])
        self.assertTrue(any("Bing §6" in row for row in problems), problems)


class Boundaries(unittest.TestCase):
    def test_measurement_ignores_comments_and_the_repair_never_touches_them(self):
        # The site's SEO meta package is delivered inside an HTML comment on purpose, so a job that
        # "cleaned up comments" would delete the meta description of every post on the blog. This module
        # only ignores comments when counting words, and there is no content scrubbing to undo.
        package = ('<div class="enh-original"><!--\n Install the XML via Blogger > Theme > Restore.\n'
                   '-->\n<p>Real words here.</p></div>')
        self.assertEqual(gate.strip_markup(package), "Real words here.")
        src = Path(gate.__file__).read_text(encoding="utf-8")
        self.assertNotIn("def remove_editor_notes", src)
        self.assertNotIn("content=", src)

    def test_the_module_opens_no_connection_and_writes_no_site(self):
        src = Path(gate.__file__).read_text(encoding="utf-8")
        for banned in ("urllib", "requests", "http.client", "socket", "blogger.googleapis"):
            self.assertNotIn(banned, src, f"{banned} would put a measurement module on the network")
        self.assertEqual(gate.self_test()["status"], "OK")
        self.assertEqual(gate.self_test()["siteWrites"], 0)

    def test_the_asset_name_rule_describes_the_subject(self):
        self.assertEqual(gate.asset_file_name("Gold Rate In India 2026", 2),
                         "gold-rate-in-india-2026-2.jpg")
        self.assertEqual(gate.asset_file_name("", 1), "daily-yield-1.jpg")
        self.assertNotIn("photo-1", gate.asset_file_name("gold-rate", 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
