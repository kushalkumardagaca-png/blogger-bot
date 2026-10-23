#!/usr/bin/env python3
"""A deterministic section may assert only the figures a cited record carries - and one bad figure must
not cost the day's slot.

On 23 October 2026 the trending writer lost its slot with `deterministic evidence section failed:
unsupported number 9`. The rule that refused it is right and stays exactly as strict: a number in the
prose has to appear in one of the supplied records. What was wrong is that the fallback applied that rule
once, to the first draft, and then kept topping the section up with more paragraphs without measuring
them again - so the prose that failed the check was the prose that had never been checked. The 20 October
repair for the same class of defect had the same hole. Nothing here loosens a gate: a section that still
cannot be built from supported sentences is refused, and refused sections now spend the topic instead of
spending the slot.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import master_v3_generator as gen
import master_v3_pipeline as pipe

UNSUPPORTED = re.compile(r"(?<![SI])\b\d[\d,.]*%?\b")


def sources(count=8, text_numbers=()):
    rows = []
    for index in range(1, count + 1):
        text = ("The recorded discussion sets out scope, definitions and the jurisdiction the figures "
                "apply to, and it states its limits plainly before any conclusion is drawn from it. ") * 4
        for number in text_numbers:
            text = text.replace("sets out scope", f"reports {number} per cent of cases and sets out scope", 1)
        rows.append((index, {"name": f"Provider {index}", "title": f"Study on household capital number {index}",
                             "url": f"https://example.org/{index}", "text": text}))
    return rows


class DeterministicSectionsCarryOnlySupportedFigures(unittest.TestCase):
    def test_a_number_in_the_planned_heading_is_not_asserted_as_fact(self):
        # "Top 9 ways" is the shape that killed the slot: the heading is quoted into the prose, and no
        # record supplies the 9. The figure has to go, and the section has to survive without it.
        paragraphs = gen.deterministic_section("Top 9 ways a household hedges capital gains", sources())
        rows = sources()
        prose = re.sub(r"\[\[S\d+\|[^]]+\]\]", " ", " ".join(paragraphs))
        self.assertNotIn(" 9 ", f" {prose} ")
        blob = " ".join(gen.evidence_text(rows).values())
        for number in UNSUPPORTED.findall(prose):
            self.assertIn(number, blob, f"the section asserts {number!r}, which no cited record carries")
        self.assertTrue(gen.validate_section(paragraphs, gen.evidence_text(rows))[0])

    def test_the_section_still_meets_every_measure_the_validator_applies(self):
        rows = sources()
        paragraphs = gen.deterministic_section("Q3 outlook for pension contributions", rows)
        ok, error = gen.validate_section(paragraphs, gen.evidence_text(rows))
        self.assertTrue(ok, f"the fallback stopped satisfying the rules: {error}")
        self.assertGreaterEqual(len(paragraphs), 4)
        count=gen.words(" ".join(paragraphs))
        self.assertTrue(400<=count<=490, f"the section left the required window at {count} words")

    def test_figures_a_record_does_supply_are_kept_not_stripped(self):
        rows = sources(text_numbers=("47",))
        paragraphs = gen.deterministic_section("Where the reported 47 per cent share sits", rows)
        self.assertIn("47", " ".join(paragraphs), "a supported figure was removed to avoid a failure")

    def test_the_validator_still_refuses_an_unsupported_figure(self):
        rows = sources()
        paragraphs = gen.deterministic_section("Anything at all about capital", rows)
        poisoned = paragraphs[0] + " In 2031 the board raised rates by 77 per cent."
        ok, error = gen.validate_section([poisoned] + paragraphs[1:], gen.evidence_text(rows))
        self.assertFalse(ok, "the number rule stopped being enforced")
        self.assertIn("unsupported number", error)


class ARefusedSectionCostsTheTopicNotTheSlot(unittest.TestCase):
    def test_the_refusal_is_recognised_as_a_gates_no(self):
        for message in ("deterministic evidence section failed: unsupported number 9",
                        "deterministic evidence section lacked four usable source passages",
                        "V3 source gate found 2 topic-specific sources; eight required"):
            self.assertTrue(pipe.gate_refusal(RuntimeError(message)), message)

    def test_a_real_failure_is_still_a_real_failure(self):
        for message in ("HTTP 503 from the provider", "EDITION IDENTITY FAILED for asia-pacific",
                        "the day's plan is not READY", "release embargo has not passed"):
            self.assertFalse(pipe.gate_refusal(RuntimeError(message)), message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
