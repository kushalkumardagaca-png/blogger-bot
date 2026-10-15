#!/usr/bin/env python3
"""A repeatable sentence must never stop a safe Master article.

Two Master slots failed on 15 October only because the same sentence appeared
twice in the assembled prose. The repair below always converges: the first real
occurrence stays, every later copy goes, and the article keeps publishing.
"""
from __future__ import annotations

import unittest

import master_v3_generator as mv3
import master_v3_pipeline as mvp


def block(heading, paragraphs):
    return {"heading": heading, "paragraphs": list(paragraphs)}


LONG = ("Planners seeking to promote multigenerational housing should pair by-right "
        "accessory dwelling unit authorisation with complementary measures such as "
        "preapproved plans and alternative financing methods across the state.")


class DropLaterDuplicateTests(unittest.TestCase):
    def test_later_copy_is_dropped_and_first_kept(self):
        blocks = [block("One", [LONG, "A different sentence about mortgage rates and household budgets."]),
                  block("Two", [LONG])]
        removed = mv3.drop_later_duplicate_sentences(blocks)
        self.assertEqual(removed, 1)
        self.assertIn(LONG, blocks[0]["paragraphs"][0])
        self.assertEqual(blocks[1]["paragraphs"], [])

    def test_short_connective_wording_is_never_removed(self):
        blocks = [block("One", ["In short, rates matter today."]), block("Two", ["In short, rates matter today."])]
        self.assertEqual(mv3.drop_later_duplicate_sentences(blocks), 0)

    def test_repeated_sentence_inside_one_paragraph_is_removed_once(self):
        blocks = [block("One", [LONG + " " + LONG])]
        self.assertEqual(mv3.drop_later_duplicate_sentences(blocks), 1)

    def test_clearing_the_gate_after_a_repair(self):
        title = "How to Plan Multigenerational Housing Without Financial Coercion"
        blocks = [block("One", [LONG, "Household budgets shift when land use rules change."]),
                  block("Two", [LONG, "Municipal fee schedules decide what is actually buildable."])]
        joined = " ".join(" ".join(b["paragraphs"]) for b in blocks)
        self.assertIn("repeated substantive sentence within the content",
                      mv3.audit_text(title, joined, "master-package", False))
        mv3.drop_later_duplicate_sentences(blocks)
        joined = " ".join(" ".join(b["paragraphs"]) for b in blocks)
        self.assertNotIn("repeated substantive sentence within the content",
                         mv3.audit_text(title, joined, "master-package", False))


class PipelineRepairRouteTests(unittest.TestCase):
    def test_both_repairs_are_available_to_the_final_render(self):
        source = (mvp.__file__ and open(mvp.__file__, encoding="utf-8").read()) or ""
        self.assertIn("repair_repeated_prose", source)
        self.assertIn("scrub_repeated_sentences", source)
        self.assertIn("duplicated substantive paragraph", source)


if __name__ == "__main__":
    unittest.main()
