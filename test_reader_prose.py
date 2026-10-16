#!/usr/bin/env python3
"""The reader-quality pass must keep machine-assembled pages readable."""
import re
import unittest

import reader_prose as rp

LIVE_TSFA = ('<p>In Canada, tax-free savings accounts let you invest without paying tax on the '
             'contributions or earnings. <a href="https://hdl.handle.net/1807/88117" rel="noopener" '
             'target="_blank">documented source evidence</a> One of the key features is that '
             'withdrawals can be made at any time.</p>')

LIVE_BOLD = ('<h2>Best Financial Habits For Gen Z</h2><p>**Best Financial Habits For Gen Z: '
             'Budgeting, Saving, And Investing** <a href="https://zenodo.org/records/9">documented '
             'source evidence</a> As Gen Z navigates personal finance, they face unique '
             'challenges.</p>')

LIVE_SCAFFOLD = ('<p>Digital USD University of San evidence frames The Troubled Distinction '
                 'between Capital Gain and Ordinary Income through \u201cSaving the Farm or Giving '
                 'Away the Farm A Critical Analysis of.\u201d The retrieved record states, in part, '
                 '\u201chave centered on whether capital gains has an effect on the economy\u201d.</p>')


class ReaderProseTests(unittest.TestCase):
    def test_a_named_source_replaces_the_generic_link_label(self):
        fixed, fixes = rp.normalise(LIVE_TSFA)
        self.assertGreaterEqual(fixes, 1)
        self.assertNotIn("documented source evidence", fixed)
        self.assertIn("Source:", fixed)
        self.assertIn("https://hdl.handle.net/1807/88117", fixed)
        self.assertIn("the archived record", fixed)

    def test_the_same_source_is_named_once_per_article(self):
        twice = LIVE_TSFA.replace("</p>", LIVE_TSFA.split("<p>")[1][:0] + "") + LIVE_TSFA
        fixed, _ = rp.normalise(twice)
        self.assertEqual(1, fixed.count("https://hdl.handle.net/1807/88117"))

    def test_markdown_bold_and_hashes_never_reach_a_reader(self):
        fixed, _ = rp.normalise('<p>### Heading</p><p>**Use of Deductible Expenses**: costs count.</p>')
        self.assertNotIn("**", fixed)
        self.assertNotIn("###", fixed)
        self.assertIn("<strong>Use of Deductible Expenses</strong>", fixed)

    def test_a_drafting_note_is_rewritten_as_prose(self):
        fixed, _ = rp.normalise(LIVE_SCAFFOLD)
        self.assertNotIn("evidence frames", fixed)
        self.assertNotIn("The retrieved record states, in part,", fixed)
        self.assertIn("A study from Digital USD University of San examines", fixed)
        self.assertIn("The record notes, in its own words:", fixed)

    def test_a_paragraph_that_only_repeats_the_heading_is_dropped(self):
        html = '<h2>Reading inflation signals</h2><p>### Reading inflation signals</p><p>Real prose follows here and continues for a while.</p>'
        fixed, fixes = rp.normalise(html)
        self.assertEqual(1, fixed.count("Reading inflation signals"))
        self.assertIn("Real prose follows here", fixed)
        self.assertGreaterEqual(fixes, 1)

    def test_repairs_are_repeat_safe(self):
        for sample in (LIVE_TSFA, LIVE_BOLD, LIVE_SCAFFOLD):
            once, _ = rp.normalise(sample)
            twice, second = rp.normalise(once)
            self.assertEqual(once, twice)
            self.assertEqual(0, second)
            self.assertEqual([], rp.problems(twice))

    def test_every_publication_name_is_taken_from_its_own_address(self):
        self.assertEqual("Bloomberg", rp.source_label("https://www.bloomberg.com/news/x"))
        self.assertEqual("Google News", rp.source_label("https://news.google.com/rss/articles/x"))
        self.assertEqual("William & Mary Law School", rp.source_label("https://scholarship.law.wm.edu/facpubs/630"))
        self.assertEqual("Example journal", rp.source_label("https://example-journal.org/a/b"))
        self.assertTrue(rp.is_generic_label("Documented Source Evidence"))
        self.assertFalse(rp.is_generic_label("Bloomberg"))

    def test_problems_lists_what_a_finished_page_must_not_show(self):
        found = rp.problems(LIVE_BOLD + LIVE_SCAFFOLD)
        self.assertTrue(any("generic source phrase" in x for x in found))
        self.assertTrue(any("markdown bold" in x for x in found))
        self.assertTrue(any("drafting note" in x for x in found))


if __name__ == "__main__":
    unittest.main()


class BrandSeoTests(unittest.TestCase):
    """Every page and article must name the publication and the author the same way."""

    def setUp(self):
        import brand_seo
        self.bs = brand_seo

    def test_every_page_carries_the_four_brand_phrases(self):
        out, changed = self.bs.enrich("<p>Body</p>", "article", "EU budget talks", "https://x/y.html")
        self.assertTrue(changed)
        for phrase in self.bs.BRAND_QUERIES:
            self.assertIn(phrase, out, phrase)

    def test_the_block_is_repeat_safe_and_carries_entity_data(self):
        once, _ = self.bs.enrich("<p>Body</p>", "article", "T", "https://x/y.html")
        twice, changed = self.bs.enrich(once, "article", "T", "https://x/y.html")
        self.assertEqual(once, twice)
        self.assertFalse(changed)
        self.assertEqual(1, twice.count('application/ld+json'))
        self.assertIn('#organization', twice)
        for key, value in self.bs.report(twice).items():
            self.assertTrue(value, key)

    def test_a_description_names_the_publication_once(self):
        text = self.bs.front_meta("EU budget", "")
        self.assertIn("Daily Yield", text)
        self.assertLessEqual(len(text), 158)
        self.assertEqual(1, text.count("Daily Yield"))

    def test_no_article_claims_a_professional_qualification_beside_the_name(self):
        out, _ = self.bs.enrich("<p>Body</p>", "article", "T", "https://x/y.html")
        plain = re.sub(r"<[^>]+>", " ", out)
        for match in re.finditer(r"Kushal.{0,55}(?:Certified Accountant|Chartered Accountant|CPA|CFA)",
                                 plain, re.I | re.S):
            self.fail(f"qualification claim stated beside the author's name: {match.group(0)[:80]}")
