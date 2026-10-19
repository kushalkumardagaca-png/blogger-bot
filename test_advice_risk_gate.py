#!/usr/bin/env python3
"""The automated gate is the reviewer: it must stop real risks and leave safe prose alone."""
import json
import unittest

import advice_risk_gate as gate

DISCLOSURE = ('<p>Educational information only; not personalised financial, tax, investment, credit or '
              'legal advice. Primary source retrieved 2026-10-19.</p>')


def article(extra=''):
    return ('Daily Yield publishes general financial education. Section 80C deductions can change with the '
            'Finance Act, so rules change and the figures here are as of 2026-10-19.' + extra + DISCLOSURE)


class SafeProsePasses(unittest.TestCase):
    def test_general_education_with_dated_source_is_not_blocked(self):
        verdict = gate.audit('What an EPF withdrawal means for your corpus', article())
        self.assertEqual(verdict['blocking'], [])
        self.assertTrue(verdict['educationDisclosurePresent'])

    def test_the_true_qualification_statement_is_allowed(self):
        text = ('Kushal Daga has cleared the CA intermediate examination and is currently serving his '
                'articleship. ' + DISCLOSURE)
        self.assertEqual(gate.audit('Who writes Daily Yield', text)['blocking'], [])

    def test_uncertainty_notes_warn_without_blocking(self):
        verdict = gate.audit('Markets outlook', '<p>Sensex expected to reach 90,000 by 2027. ' + DISCLOSURE + '</p>')
        self.assertEqual(verdict['blocking'], [])
        self.assertTrue(any(row['rule'].startswith('forecast wording') for row in verdict['warnings']))


class RealRisksAreBlocked(unittest.TestCase):
    def check(self, text, rule_start, title='Investing basics'):
        verdict = gate.audit(title, text + DISCLOSURE)
        self.assertTrue(verdict['blocking'], 'expected a block for: ' + rule_start)
        self.assertTrue(any(row['rule'].startswith(rule_start) for row in verdict['blocking']),
                        json.dumps(verdict['blocking'])[:400])

    def test_personalised_instruction(self):
        self.check('<p>You should buy this fund before the next budget.</p>', 'personalised buy/sell/apply instruction')

    def test_guaranteed_returns(self):
        self.check('<p>This small savings scheme offers guaranteed returns of 8.2%.</p>', 'guaranteed or risk-free return claim')

    def test_invented_professional_review(self):
        self.check('<p>Every investing article is reviewed by our chartered accountant.</p>',
                   'reviewed-by-a-professional claim with no reviewer')

    def test_false_qualification(self):
        self.check('<p>I am a Chartered Accountant and this is my professional opinion.</p>',
                   'publisher qualification claim')

    def test_tax_rule_without_dated_source_or_change_notice(self):
        self.check('<p>Section 80C makes your investment tax-free forever.</p>',
                   'tax rule stated as permanent fact with no date')

    def test_advice_subject_without_the_disclosure(self):
        verdict = gate.audit('Best time to buy a house loan', '<p>Loan EMI rises when rates move, so borrowers '
                             'should watch their tenure.</p>')
        self.assertTrue(any(row['rule'].startswith('education-only disclosure') for row in verdict['blocking']))

    def test_the_gate_raises_with_the_rule_named(self):
        with self.assertRaises(RuntimeError) as caught:
            gate.assert_gate('Investing guide', '<p>You must sell your mutual funds now.</p>' + DISCLOSURE)
        self.assertIn('ADVICE RISK GATE BLOCKED', str(caught.exception))
        self.assertIn('personalised buy/sell/apply instruction', str(caught.exception))


class ReviewerPositionIsHonest(unittest.TestCase):
    def test_no_human_reviewer_is_recorded_everywhere(self):
        self.assertFalse(gate.HUMAN_REVIEWER)
        self.assertIs(gate.audit('Any title', article())['humanReviewer'], False)

    def test_the_photo_standard_has_one_owner(self):
        import master_article_v2
        from master_article_v2 import PHOTOS_PER_MASTER_ARTICLE as IN_RENDERER
        self.assertEqual(IN_RENDERER, 3)
        self.assertIn('PHOTOS_PER_MASTER_ARTICLE',
                      open('preapproval_audit.py', encoding='utf-8').read())
        self.assertIn('PHOTOS_PER_MASTER_ARTICLE',
                      open('publication_preflight.py', encoding='utf-8').read())
        self.assertNotIn("'required':10", open('preapproval_audit.py', encoding='utf-8').read())
        self.assertIn('!=PHOTOS_PER_MASTER_ARTICLE', master_article_v2.__dict__ and
                      open('master_article_v2.py', encoding='utf-8').read())


class GateIsWiredIntoPublication(unittest.TestCase):
    """A risky article must be stopped by the publish path, not only by this module."""

    def body(self, extra):
        paragraphs = []
        for index in range(1, 26):
            paragraphs.append(
                "<p>Paragraph %d explains how interest, inflation and time change the size of a corpus for "
                "a household in a city, and the effect is measured over the years named in the table beside it, "
                "with the arithmetic shown so a reader can repeat every step themselves.</p>" % index)
        sources = ('<p>Sources: <a href="https://www.rbi.org.in/returns.aspx">Reserve Bank of India return</a> '
                   'retrieved 2026-10-19 and <a href="https://www.investopedia.com/terms/e/emi.asp">Investopedia '
                   'definition</a> retrieved 2026-10-19.</p>')
        return ''.join(paragraphs) + sources + extra + DISCLOSURE

    def test_a_personal_instruction_stops_the_publish_call(self):
        import publication_preflight as preflight
        from unittest.mock import patch
        with patch.object(preflight, 'assert_green_operating_state', lambda *a, **k: True):
            with self.assertRaises(Exception) as caught:
                preflight.assert_publishable('How an EMI changes when rates move',
                                             self.body('<p>You should buy this fund before the next budget.</p>'),
                                             ['News'])
        self.assertIn('advice risk gate', str(caught.exception))

    def test_the_same_article_without_the_instruction_is_not_blocked_by_the_gate(self):
        # The article still fails the other structural checks in this stub body; what
        # matters is that the advice gate contributes no finding once the instruction
        # is gone, so a sound article is never blocked by it.
        import publication_preflight as preflight
        from unittest.mock import patch
        with patch.object(preflight, 'assert_green_operating_state', lambda *a, **k: True):
            try:
                preflight.assert_publishable('How an EMI changes when rates move',
                                             self.body('<p>Rate moves change the split between interest and capital.</p>'),
                                             ['News'])
            except RuntimeError as exc:
                self.assertNotIn('advice risk gate', str(exc))


if __name__ == '__main__':
    unittest.main(verbosity=2)
