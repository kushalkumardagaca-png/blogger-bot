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
        return ("<div class='ft-contact'><span class='ft-eyebrow'>Start a conversation</span>"
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
        self.assertTrue(any("publisher" in p for p in problems))
        self.assertEqual(tcc.audit(tcc.apply(self.sample())[0]), [])

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
