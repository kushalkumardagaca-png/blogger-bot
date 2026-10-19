#!/usr/bin/env python3
"""The ten private tool specifications must compute exactly what their pages will claim.

Every expected value here is derived a second way (a loop, a geometric sum, or an
inverse call), not by repeating the closed-form formula the module already uses.
"""
import unittest

import growth_tool_math as m


def fv_by_loop(monthly, annual_rate_pct, years):
    rate = annual_rate_pct / (100.0 * 12)
    balance = 0.0
    for _ in range(int(round(years * 12))):
        balance = balance * (1.0 + rate) + monthly
    return balance


def balance_after(principal, annual_rate_pct, months, payment):
    rate = annual_rate_pct / (100.0 * 12)
    balance = principal
    for _ in range(months):
        balance = balance * (1.0 + rate) - payment
    return balance


class LoanTests(unittest.TestCase):
    def test_emi_is_the_payment_that_clears_the_loan(self):
        principal, rate, months = 2500000, 8.6, 240
        payment = m.emi(principal, rate, months)
        self.assertAlmostEqual(balance_after(principal, rate, months, payment), 0.0, places=4)
        # and any larger payment must leave a negative balance (overpaid)
        self.assertLess(balance_after(principal, rate, months, payment + 100), -1000)

    def test_emi_schedules_reconcile_to_the_paisa(self):
        rows = m.amortisation_schedule(1200000, 9.25, 180)
        self.assertEqual(len(rows), 180)
        self.assertAlmostEqual(rows[-1]["balance"], 0.0, delta=0.6)
        self.assertAlmostEqual(sum(row["interest"] for row in rows),
                               m.total_interest(1200000, 9.25, 180), delta=1.0)

    def test_zero_interest_loan_is_a_plain_division(self):
        self.assertAlmostEqual(m.emi(150000, 0, 30), 5000.0, places=6)
        self.assertEqual(m.total_interest(150000, 0, 30), 0.0)

    def test_affordability_is_the_inverse_of_the_emi(self):
        budget, rate, months = 45000, 8.75, 240
        principal = m.loan_affordability(budget, rate, months)
        self.assertAlmostEqual(m.emi(principal, rate, months), budget, places=4)

    def test_a_payment_below_monthal_interest_never_clears_the_card(self):
        self.assertIsNone(m.payoff_months(400000, 1000, 42))
        # 42% on 400,000 is 14,000 of interest in the first month, so a 12,000
        # payment loses every month and the card is never cleared.
        self.assertIsNone(m.payoff_months(400000, 14000, 42))
        slow, fast = m.payoff_months(400000, 20000, 42), m.payoff_months(400000, 40000, 42)
        self.assertLess(fast, slow)
        self.assertGreater(slow, 0)
        self.assertEqual(m.payoff_months(400000, 400000, 0), 1)

    def test_a_lump_payment_saves_exactly_the_remaining_interest(self):
        saving = m.prepayment_saving(2000000, 9.0, 240, 2000000, 1)
        self.assertGreater(saving["monthsSaved"], 200)
        self.assertGreater(saving["interestSaved"], 0)
        self.assertEqual(saving["monthsAfter"], 1)


class GrowthTests(unittest.TestCase):
    def test_lump_growth_matches_year_by_year_arithmetic(self):
        self.assertAlmostEqual(m.future_value_lump(100, 10, 2, compounds_per_year=1), 121.0, places=9)
        self.assertEqual(m.future_value_lump(50000, 0, 7), 50000)

    def test_series_growth_matches_a_month_by_month_loop(self):
        self.assertAlmostEqual(m.future_value_series(5000, 12, 20), fv_by_loop(5000, 12, 20), places=2)
        self.assertEqual(m.future_value_series(5000, 0, 3), 180000)

    def test_step_up_never_pays_less_than_a_flat_contribution(self):
        flat = m.future_value_series(10000, 11, 15)
        self.assertAlmostEqual(m.step_up_series(10000, 11, 15, 0), flat, places=2)
        self.assertGreater(m.step_up_series(10000, 11, 15, 10), flat)

    def test_goal_deposit_reaches_the_goal(self):
        deposit = m.monthly_deposit_for_goal(3000000, 9, 12)
        self.assertAlmostEqual(m.future_value_series(deposit, 9, 12), 3000000, places=2)

    def test_inflation_round_trips(self):
        effect = m.inflation_effect(1000000, 6.2, 10)
        self.assertAlmostEqual(effect["futureCost"] / (1.62 ** 0), effect["futureCost"], places=2)
        self.assertAlmostEqual(effect["buyingPowerOfToday"] * (1.062 ** 10), 1000000, places=0)

    def test_a_zero_return_fund_lasts_principal_over_withdrawal_years(self):
        self.assertAlmostEqual(m.retirement_years(25000000, 1000000, 0), 25.0, places=6)

    def test_monthly_rate_uses_one_division_by_1200(self):
        self.assertAlmostEqual(m.monthly_rate(12), 0.01, places=12)


class PresentationTests(unittest.TestCase):
    def test_worked_example_is_a_real_number_from_this_module(self):
        example = m.EXAMPLE
        self.assertEqual(example["tool"], "P01 Loan EMI")
        inputs = example["inputs"]
        self.assertAlmostEqual(example["outputs"]["emi"],
                               m.emi(**{"principal": inputs["principal"],
                                        "annual_rate_pct": inputs["annualRatePct"],
                                        "months": inputs["months"]}), places=2)
        self.assertGreater(example["outputs"]["totalInterest"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
