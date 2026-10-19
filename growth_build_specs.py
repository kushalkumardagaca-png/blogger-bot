#!/usr/bin/env python3
"""Write the private build specification for the first ten growth tools.

This is preparation only. No page, URL or theme change is made while the site is
frozen for the AdSense review, and nothing here is published. The file exists so the
build can be reviewed, tested and released in one pass when the owner lifts the freeze.

Each tool is specified against growth_tool_math.py, whose arithmetic is verified by
test_growth_tool_math.py independently of the formulas the pages will print.
"""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path
import growth_tool_math as math_ref

ROOT = Path(__file__).parent
SHORTLIST = ROOT / "GROWTH_PRIORITY_SHORTLIST_PRIVATE.json"
OUT = ROOT / "GROWTH_BUILD_SPECS_PRIVATE.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

SPEC = {
    "P01": {"inputs": {"principal": [1000, 50000000, 2500000, "rupees"],
                       "annualRatePct": [0, 30, 8.6, "percent per year"],
                       "months": [6, 360, 240, "months"]},
            "formula": "EMI = P x r x (1+r)^n / ((1+r)^n - 1), r = annual rate / 1200",
            "outputs": ["Monthly instalment", "Total interest", "Total payment"],
            "call": lambda i: {"emi": round(math_ref.emi(i["principal"], i["annualRatePct"], i["months"]), 2),
                               "totalInterest": round(math_ref.total_interest(i["principal"], i["annualRatePct"], i["months"]), 2),
                               "totalPayment": round(math_ref.emi(i["principal"], i["annualRatePct"], i["months"]) * i["months"], 2)}},
    "P02": {"inputs": {"principal": [1000, 50000000, 2000000, "rupees"],
                       "annualRatePct": [0, 30, 9.0, "percent per year"],
                       "months": [6, 360, 240, "months"],
                       "lump": [1000, 10000000, 300000, "rupees"],
                       "atMonth": [1, 300, 12, "month number"]},
            "formula": "re-run the amortisation with the extra capital payment added at month k, then compare",
            "outputs": ["Months saved", "Interest saved", "New final month"],
            "call": lambda i: math_ref.prepayment_saving(i["principal"], i["annualRatePct"], i["months"],
                                                        i["lump"], i["atMonth"])},
    "P03": {"inputs": {"monthlyBudget": [1000, 500000, 45000, "rupees"],
                       "annualRatePct": [0, 30, 8.75, "percent per year"],
                       "months": [6, 360, 240, "months"]},
            "formula": "Principal = budget x (1 - (1+r)^-n) / r",
            "outputs": ["Largest affordable loan", "Implied EMI at that size"],
            "call": lambda i: {"affordablePrincipal": round(math_ref.loan_affordability(i["monthlyBudget"], i["annualRatePct"], i["months"]), 2),
                               "emiAtThatSize": round(math_ref.emi(math_ref.loan_affordability(i["monthlyBudget"], i["annualRatePct"], i["months"]),
                                                                   i["annualRatePct"], i["months"]), 2)}},
    "P04": {"inputs": {"balance": [1000, 5000000, 400000, "rupees"],
                       "monthlyPayment": [100, 500000, 20000, "rupees"],
                       "annualRatePct": [0, 60, 42, "percent per year"]},
            "formula": "iterate: interest = balance x r; capital = payment - interest; stop when capital <= 0",
            "outputs": ["Months to clear", "Total interest", "A plain warning when the payment cannot clear the card"],
            "call": lambda i: {"months": math_ref.payoff_months(i["balance"], i["monthlyPayment"], i["annualRatePct"]),
                               "interestApprox": round(max(i["monthlyPayment"] * (math_ref.payoff_months(i["balance"], i["monthlyPayment"], i["annualRatePct"]) or 0) - i["balance"], 0), 2)}},
    "P05": {"inputs": {"principal": [100, 10000000, 100000, "rupees"],
                       "annualRatePct": [0, 20, 7.5, "percent per year"],
                       "years": [0.25, 40, 10, "years"],
                       "compoundsPerYear": [1, 12, 12, "times a year"]},
            "formula": "Amount x (1 + rate/periods)^(periods x years)",
            "outputs": ["Value at the end", "Interest earned", "Growth as a percentage"],
            "call": lambda i: {"futureValue": round(math_ref.future_value_lump(i["principal"], i["annualRatePct"], i["years"], i["compoundsPerYear"]), 2),
                               "interestEarned": round(math_ref.future_value_lump(i["principal"], i["annualRatePct"], i["years"], i["compoundsPerYear"]) - i["principal"], 2)}},
    "P06": {"inputs": {"target": [1000, 100000000, 3000000, "rupees"],
                       "annualRatePct": [0, 20, 9, "percent per year"],
                       "years": [0.25, 40, 12, "years"]},
            "formula": "Monthly deposit = target x r / ((1+r)^n - 1)",
            "outputs": ["Monthly deposit needed", "Total contributed", "Interest earned"],
            "call": lambda i: {"monthlyDeposit": round(math_ref.monthly_deposit_for_goal(i["target"], i["annualRatePct"], i["years"]), 2),
                               "totalContributed": round(math_ref.monthly_deposit_for_goal(i["target"], i["annualRatePct"], i["years"]) * i["years"] * 12, 2)}},
    "P07": {"inputs": {"amount": [100, 100000000, 1000000, "rupees"],
                       "inflationPct": [0, 20, 6.2, "percent per year"],
                       "years": [0.25, 60, 10, "years"]},
            "formula": "Future price = amount x (1 + inflation)^years; buying power is its inverse",
            "outputs": ["Future price of today's spending", "Today's value of that future money", "Price rise %"],
            "call": lambda i: math_ref.inflation_effect(i["amount"], i["inflationPct"], i["years"])},
    "P08": {"inputs": {"fundAtRetirement": [100000, 100000000, 25000000, "rupees"],
                       "annualExpense": [10000, 10000000, 1000000, "rupees a year"],
                       "returnPct": [0, 15, 7, "percent per year"]},
            "formula": "year by year: fund = fund x (1 + return) - withdrawal",
            "outputs": ["Years the fund lasts", "When it runs out", "What a 20% larger withdrawal changes"],
            "call": lambda i: {"yearsLasts": round(math_ref.retirement_years(i["fundAtRetirement"], i["annualExpense"], i["returnPct"]), 2)}},
    "P09": {"inputs": {"monthlyAmount": [100, 1000000, 10000, "rupees a month"],
                       "annualRatePct": [0, 25, 12, "percent per year"],
                       "years": [0.25, 45, 20, "years"]},
            "formula": "FV = deposit x ((1+r)^n - 1) / r, payments at month end",
            "outputs": ["Corpus", "Total invested", "Gain", "Gain as a share of the corpus"],
            "call": lambda i: {"corpus": round(math_ref.future_value_series(i["monthlyAmount"], i["annualRatePct"], i["years"]), 2),
                               "invested": round(i["monthlyAmount"] * i["years"] * 12, 2)}},
    "P10": {"inputs": {"startMonthly": [100, 1000000, 10000, "rupees a month"],
                       "annualRatePct": [0, 25, 11, "percent per year"],
                       "years": [1, 45, 15, "years"],
                       "annualStepUpPct": [0, 50, 10, "percent a year"]},
            "formula": "raise the monthly amount each 12th month, then compound month by month",
            "outputs": ["Corpus", "Extra versus a flat contribution", "Total invested"],
            "call": lambda i: {"corpus": round(math_ref.step_up_series(i["startMonthly"], i["annualRatePct"], i["years"], i["annualStepUpPct"]), 2),
                               "flatCorpus": round(math_ref.future_value_series(i["startMonthly"], i["annualRatePct"], i["years"]), 2)}},
}


def main() -> int:
    shortlist = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in shortlist.get("items", [])}
    tools, missing = [], []
    for pid, spec in SPEC.items():
        source = by_id.get(pid)
        if not source:
            missing.append(pid)
            continue
        inputs = {name: default for name, (low, high, default, _unit) in spec["inputs"].items()}
        tools.append({
            "id": pid, "type": source["type"], "name": source["name"], "cluster": source["cluster"],
            "readerQuestion": source["suggestedReaderQuestion"],
            "publishedSpecification": source.get("specification", ""),
            "inputs": [{"name": name, "min": low, "max": high, "unit": unit, "workedDefault": default}
                       for name, (low, high, default, unit) in spec["inputs"].items()],
            "formula": spec["formula"],
            "outputs": spec["outputs"],
            "roundingRule": "full precision inside the calculation; round once at display; two decimals for rupees, one for percentages",
            "invalidInputRule": "negative or absurd values return a plain explanation, never a number",
            "workedExample": {"inputs": inputs, "outputs": spec["call"](inputs)},
            "verification": f"test_growth_tool_math.py ({'growth_tool_math.' + pid[1:] + ' arithmetic cross-checked by loop and inverse calls'})",
            "pageIntent": {"onePagePerIntent": True, "sections": [
                "what the number means", "the worked example above", "the formula in words",
                "the limits of the estimate", "related Daily Yield articles"],
                "wordTarget": [900, 1400]},
            "requiredDisclosure": "An illustration from stated inputs, not advice. Rates, taxes and charges must be confirmed with the lender, fund or tax rules in force.",
            "buildState": "SPECIFIED_AND_MATHS_TESTED_NOT_BUILT",
        })
    OUT.write_text(json.dumps({
        "preparedAtIST": dt.datetime.now(IST).isoformat(),
        "status": "PRIVATE_SPEC_ONLY",
        "shortlistStatus": shortlist.get("status"),
        "releaseRule": shortlist.get("releaseRule", "No page may be created while SITE_CHANGE_POLICY.json is frozen."),
        "whyPrivate": ("Publishing new URLs, changing the sitemap or restructuring pages is held until the AdSense review "
                       "is finished and the owner lifts the freeze. The arithmetic and the page shape are proved now so the "
                       "release is one careful pass later."),
        "tools": tools,
        "notInThisPass": {
            "pagesCreated": 0, "urlsRegistered": 0, "themeChanged": False,
            "sitemapChanged": False, "ownerAccountChanged": False,
            "missingFromShortlist": missing,
        },
        "remainingOfFifty": [row["id"] for row in shortlist.get("items", []) if row["id"] not in SPEC],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"tools": len(tools), "missingFromShortlist": missing,
                      "example": tools[0]["workedExample"] if tools else None}, indent=2)[:700])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
