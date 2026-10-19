#!/usr/bin/env python3
"""The private tool specifications must stay true to the tested arithmetic and stay private."""
import json
import unittest
from pathlib import Path

import growth_tool_math as m

ROOT = Path(__file__).resolve().parent
SPEC_FILE = ROOT / "GROWTH_BUILD_SPECS_PRIVATE.json"


class PrivateToolSpecs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(SPEC_FILE.read_text(encoding="utf-8"))

    def test_ten_pilot_tools_are_specified(self):
        self.assertEqual(self.data["status"], "PRIVATE_SPEC_ONLY")
        self.assertEqual([row["id"] for row in self.data["tools"]],
                         [f"P{n:02d}" for n in range(1, 11)])
        self.assertEqual(self.data["notInThisPass"]["missingFromShortlist"], [])

    def test_nothing_was_created_or_published(self):
        untouched = self.data["notInThisPass"]
        self.assertEqual(untouched["pagesCreated"], 0)
        self.assertEqual(untouched["urlsRegistered"], 0)
        self.assertFalse(untouched["themeChanged"])
        self.assertFalse(untouched["sitemapChanged"])
        self.assertFalse(untouched["ownerAccountChanged"])

    def test_every_tool_names_formula_inputs_bounds_and_a_disclosure(self):
        for row in self.data["tools"]:
            with self.subTest(tool=row["id"]):
                self.assertTrue(row["formula"])
                self.assertTrue(row["requiredDisclosure"])
                self.assertGreaterEqual(len(row["inputs"]), 3)
                for field in row["inputs"]:
                    self.assertLess(field["min"], field["max"])
                    self.assertLessEqual(field["min"], field["workedDefault"])
                    self.assertLessEqual(field["workedDefault"], field["max"])
                self.assertEqual(row["buildState"], "SPECIFIED_AND_MATHS_TESTED_NOT_BUILT")

    def test_worked_examples_are_the_numbers_the_pages_will_print(self):
        by_id = {row["id"]: row for row in self.data["tools"]}
        inputs = lambda tool: {field["name"]: field["workedDefault"] for field in by_id[tool]["inputs"]}

        check = inputs("P01")
        self.assertAlmostEqual(by_id["P01"]["workedExample"]["outputs"]["emi"],
                               round(m.emi(check["principal"], check["annualRatePct"], check["months"]), 2), places=2)
        check = inputs("P09")
        self.assertAlmostEqual(by_id["P09"]["workedExample"]["outputs"]["corpus"],
                               round(m.future_value_series(check["monthlyAmount"], check["annualRatePct"], check["years"]), 2),
                               places=2)
        check = inputs("P06")
        self.assertAlmostEqual(by_id["P06"]["workedExample"]["outputs"]["monthlyDeposit"],
                               round(m.monthly_deposit_for_goal(check["target"], check["annualRatePct"], check["years"]), 2),
                               places=2)

    def test_the_regressor_list_is_the_rest_of_the_fifty(self):
        self.assertEqual(len(self.data["remainingOfFifty"]), 40)
        self.assertNotIn("P01", self.data["remainingOfFifty"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
