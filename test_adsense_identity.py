#!/usr/bin/env python3
"""One honest story about who publishes Daily Yield, everywhere.

The first AdSense application was declined under *Dishonest declarations*: what a
publisher tells Google and readers must be accurate, complete and consistent. The
live site contradicted itself — the theme footer promised 24–48 hour replies on
every page while the Contact page promised 2–3 working days — and showed a single
address although the blog is administered from a different account. These tests
keep the one-voice rule.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import identity_contact as ident
import theme_contact_consistency as tcc

ROOT = Path(__file__).parent


class IdentityModuleTests(unittest.TestCase):
    def test_both_addresses_are_real_and_distinct(self):
        self.assertNotEqual(ident.PRIMARY_EMAIL, ident.OWNER_EMAIL)
        for address in (ident.PRIMARY_EMAIL, ident.OWNER_EMAIL):
            self.assertRegex(address, r"^[\w.+-]+@[\w.-]+\.\w{2,}$")

    def test_identity_block_states_the_facts_without_claiming_more(self):
        block = ident.identity_block()
        for fact in (ident.PUBLICATION, ident.SITE, ident.PUBLISHER_NAME, ident.PUBLISHER_ROLE,
                     ident.OPERATING_FROM, ident.PRIMARY_EMAIL, ident.OWNER_EMAIL):
            self.assertIn(fact, block)
        self.assertIn("no postal address is published", block)
        self.assertIn("no claim of membership, registration, office, award or partnership", block)

    def test_contact_sentence_carries_both_inboxes_and_one_response_time(self):
        sentence = ident.contact_sentence()
        self.assertIn(ident.PRIMARY_EMAIL, sentence)
        self.assertIn(ident.OWNER_EMAIL, sentence)
        self.assertIn(ident.RESPONSE_TIME, sentence)
        self.assertNotIn("24", sentence)

    def test_identity_block_is_stable_when_rendered_twice(self):
        self.assertEqual(ident.identity_block(), ident.identity_block())


class ThemeConsistencyTests(unittest.TestCase):
    def sample(self):
        return ("<div class='ft-identity'><b>Daily Yield</b><span class='ft-by'>By Kushal K. Daga</span></div>"
                "<div class='ft-contact'><span class='ft-eyebrow'>Start a conversation</span>"
                f"<a class='ft-email' href='mailto:{ident.PRIMARY_EMAIL}'>{ident.PRIMARY_EMAIL}</a>"
                "<p>Replies within 24&#8211;48 hours. Comments answered fastest.</p></div>"
                f"<strong>Email the editorial desk</strong><small>{ident.PRIMARY_EMAIL}</small>")

    def test_reply_time_is_unified_and_second_address_added(self):
        out, changes = tcc.apply(self.sample())
        self.assertNotRegex(out, r"24\s*[\u2013\u2014-]\s*48")
        self.assertIn(ident.OWNER_EMAIL, out)
        self.assertIn("Replies usually within 2\u20133 working days", out)
        self.assertGreaterEqual(len(changes), 3)

    def test_apply_is_repeat_safe(self):
        once, _ = tcc.apply(self.sample())
        twice, second_changes = tcc.apply(once)
        self.assertEqual(once, twice)
        self.assertEqual(second_changes, [])

    def test_footer_card_never_stacks_copies_of_an_address(self):
        once, _ = tcc.apply(self.sample())
        twice, _ = tcc.apply(once)
        self.assertEqual(twice.count(tcc.OWNER_ANCHOR), 1)
        self.assertEqual(twice.count(tcc.PRIMARY_ANCHOR), 1)
        self.assertIn("Replies usually within 2\u20133 working days", twice)

    def test_audit_flags_the_old_theme(self):
        problems = tcc.audit("Replies within 24&#8211;48 hours.")
        self.assertTrue(any("24" in p for p in problems))
        self.assertTrue(any("own monitored address" in p for p in problems))
        self.assertTrue(any("legal name" in p for p in problems))
        repaired = tcc.apply(self.sample() + f"<p>{ident.LEGAL_NAME}</p>")[0]
        self.assertEqual(tcc.audit(repaired), [])

    def test_repository_themes_pass_the_audit(self):
        for path in sorted((ROOT / "theme").glob("*.xml")):
            with self.subTest(theme=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(tcc.audit(text), [])
                self.assertIn(ident.OWNER_EMAIL, text)


class PageSourceTests(unittest.TestCase):
    def test_page_family_contact_card_shows_both_addresses(self):
        text = (ROOT / "update_page_family.py").read_text(encoding="utf-8")
        self.assertIn(ident.OWNER_EMAIL, text)

    def test_every_reader_facing_contact_line_uses_the_shared_facts(self):
        guard = (ROOT / "content_policy_guard.py").read_text(encoding="utf-8")
        self.assertIn(ident.PRIMARY_EMAIL, guard)
        self.assertIn(ident.OWNER_EMAIL, guard)
        self.assertIn("both inboxes are monitored", guard)


if __name__ == "__main__":
    unittest.main()


class PageDescriptionTests(unittest.TestCase):
    """A stored search description must never contradict the page itself."""

    def test_every_policy_page_gets_a_corrected_description(self):
        for url, description in tcc.PAGE_DESCRIPTIONS.items():
            self.assertIn(url, url)
            self.assertNotRegex(description, r"24\s*[\u2013-]\s*48")
            self.assertLessEqual(len(description), 200)
        contact = tcc.PAGE_DESCRIPTIONS["https://dailyyield.blogspot.com/p/contact-us_01883938366.html"]
        self.assertIn(ident.OWNER_EMAIL, contact)

    def test_corrected_descriptions_are_placed_before_blogger_head_output(self):
        theme = "<b:include data='blog' name='all-head-content'/>"
        out, done = tcc.apply_meta(theme)
        self.assertTrue(done)
        self.assertLess(out.index(tcc.META_MARKER_START), out.index("<b:include data='blog'"))

    def test_repeat_safe(self):
        theme = "<b:include data='blog' name='all-head-content'/>"
        once, _ = tcc.apply_meta(theme)
        twice, done = tcc.apply_meta(once)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count(tcc.META_MARKER_START), 1)


class LegalNameTests(unittest.TestCase):
    """The legal name, the byline and the site must tell one story."""

    def test_public_name_and_legal_name_are_both_stated(self):
        self.assertEqual(ident.LEGAL_NAME, "Kushal Kumar Daga")
        self.assertEqual(ident.BYLINE, "Kushal Daga")
        block = ident.identity_block()
        self.assertIn(ident.BYLINE, block)
        self.assertIn(ident.LEGAL_NAME, block)
        self.assertIn("short form of the publisher's legal name", block)
        self.assertIn("ownership, payment and platform records", block)
        self.assertNotRegex(block, r"Kushal\s+K\.?\s+Daga")

    def test_article_footer_names_the_public_author_and_the_legal_name(self):
        from content_policy_guard import automation_disclosure
        block = automation_disclosure("article")
        self.assertIn(ident.BYLINE, block)
        self.assertIn(ident.LEGAL_NAME, block)
        self.assertIn("short form of the publisher's legal name", block)
        self.assertIn("not state that every automated draft was personally reviewed", block)

    def test_none_of_the_honest_strings_claims_an_unrelated_surname(self):
        from content_policy_guard import automation_disclosure
        import importlib
        for text in (ident.identity_block(), ident.contact_sentence(), automation_disclosure("article")):
            self.assertEqual(ident.name_problems(text), [], text[:60])
        self.assertNotIn("Jain", ident.NAME_EXPLAINER)
        self.assertEqual(ident.NAME_ALIASES[0], ident.BYLINE)
        self.assertIn(ident.LEGAL_NAME, ident.NAME_ALIASES)
        self.assertTrue(all("Jain" not in alias for alias in ident.NAME_ALIASES))

    def test_pretty_printed_alias_list_is_still_repaired(self):
        """Structured data arrives both compactly and pretty-printed; both must be fixed."""
        pretty = '\n'.join(('"author": {', '  "@type": "Person",', '  "name": "Kushal Daga",',
                             '  "alternateName": [', '    "Kushal Daga",', '    "CA Kushal",',
                             '    "Kushal Jain",', '    "Finance by Kushal"', '  ],', '}'))
        fixed, changed = ident.repair_names(pretty)
        self.assertTrue(changed)
        self.assertNotIn("Kushal Jain", fixed)
        self.assertIn(ident.LEGAL_NAME, fixed)
        self.assertEqual([], ident.name_problems(fixed))
        self.assertEqual((fixed, False), ident.repair_names(fixed))
        # the canonical list is left exactly as it is
        honest = '"alternateName": [' + ident.alias_list_json() + ']'
        self.assertEqual((honest, False), ident.repair_names(honest))
        # and a list naming another person's surname never survives
        for alias in ident.NAME_ALIASES:
            self.assertIn(alias, fixed)

    def test_every_published_wording_is_repaired_and_the_repair_is_repeat_safe(self):
        published_forms = (
            "Daily Yield is the finance publication of Kushal K. Daga, also known as Kushal Daga and Kushal Jain.",
            "Daily Yield is the finance publication of Kushal Daga, also known as Kushal Daga and Kushal Jain.",
            "Daily Yield is the finance publication of Kushal K. Daga, also known as Kushal Daga.",
            "Daily Yield is the finance publication of Kushal Kumar Daga, whose articles carry the "
            "abbreviated byline \u201cKushal K. Daga\u201d.",
        )
        for published in published_forms:
            with self.subTest(published=published[:60]):
                fixed, changed = ident.repair_names(published)
                self.assertTrue(changed)
                self.assertEqual(fixed, ident.PUBLIC_IDENTITY_SENTENCE)
                self.assertEqual(ident.name_problems(fixed), [])
                again, changed_again = ident.repair_names(fixed)
                self.assertFalse(changed_again)
        retired = "By <strong>Kushal K. Daga</strong> \u00b7 Daily Yield"
        fixed, changed = ident.repair_names(retired)
        self.assertTrue(changed)
        self.assertIn("By <strong>Kushal Daga</strong>", fixed)
        self.assertFalse(ident.repair_names(fixed)[1])

    def test_a_json_ld_keyword_line_is_cleaned_and_stays_clean(self):
        live = ('"keywords": "finance news today, Daily Yield, Kushal Daga, CA Kushal, '
                'Kushal Jain, Kushal Daga, Finance, Finance by Kushal"')
        fixed, changed = ident.repair_names(live)
        self.assertTrue(changed)
        self.assertNotIn("Kushal Jain", fixed)
        self.assertIn(ident.LEGAL_NAME, fixed)
        self.assertEqual(1, fixed.count('Kushal Daga'))
        self.assertEqual((fixed, False), ident.repair_names(fixed))
        self.assertEqual([], ident.name_problems(fixed))

    def test_structured_data_aliases_include_the_legal_name(self):
        import news_pipeline as np
        self.assertIn("Kushal Kumar Daga", np.PERSON_ALIASES)
        self.assertTrue(all("Jain" not in alias for alias in np.PERSON_ALIASES))
        self.assertIn("Kushal Kumar Daga", np.SEO_QUERY_TERMS)

    def test_theme_footer_states_the_public_name_and_the_legal_name(self):
        for path in sorted((ROOT / "theme").glob("*.xml")):
            with self.subTest(theme=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(ident.LEGAL_NAME, text)
                self.assertIn("By Kushal Daga", text)
                self.assertIn("short form of the publisher's legal name", tcc.FOOTER_LEGAL_NOTE)
                self.assertIn(tcc.FOOTER_LEGAL_NOTE, text)
                self.assertNotRegex(text, r"Kushal\s+K\.?\s+Daga")
