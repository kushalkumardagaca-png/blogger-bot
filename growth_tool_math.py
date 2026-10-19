#!/usr/bin/env python3
"""Reference arithmetic for the ten private growth-tool specifications.

Nothing here publishes or changes a page. The module exists so that every planned
calculator has one agreed formula, one rounding rule and one worked example before
any page is written, after the site freeze ends. Each function is deliberately
plain arithmetic that a reader can follow on the page itself.

Money rules used throughout
---------------------------
* Monthly rate = annual percentage / 1200 (never /100 then /12 twice).
* Annuity payments fall at the end of each month, which is how Indian loan EMIs,
  SIP debits and credit-card payments are described by their providers.
* Rounding happens once, at presentation. Schedules are carried at full precision
  so a reader's total does not drift by a rupee per month.
"""
from __future__ import annotations

MONTHS_PER_YEAR = 12


def monthly_rate(annual_rate_pct: float) -> float:
    """The monthly decimal rate behind an annual percentage."""
    return float(annual_rate_pct) / (100.0 * MONTHS_PER_YEAR)


def annuity_present_value(payment: float, annual_rate_pct: float, months: int) -> float:
    """What a stream of equal future payments is worth today."""
    rate = monthly_rate(annual_rate_pct)
    if months <= 0:
        return 0.0
    if rate == 0:
        return payment * months
    return payment * (1.0 - (1.0 + rate) ** -months) / rate


def emi(principal: float, annual_rate_pct: float, months: int) -> float:
    """P01 - fixed-rate monthly instalment for a loan."""
    if principal <= 0 or months <= 0:
        return 0.0
    rate = monthly_rate(annual_rate_pct)
    if rate == 0:
        return principal / months
    growth = (1.0 + rate) ** months
    return principal * rate * growth / (growth - 1.0)


def amortisation_schedule(principal: float, annual_rate_pct: float, months: int,
                          extra_payment: float = 0.0) -> list[dict]:
    """Month-by-month interest and capital, with an optional extra capital payment."""
    rate = monthly_rate(annual_rate_pct)
    balance = float(principal)
    instalment = emi(balance, annual_rate_pct, months)
    rows: list[dict] = []
    for month in range(1, max(months, 1) * 12 + 1):  # hard stop guards a 0% typo
        if balance <= 0.005:
            break
        interest = balance * rate
        capital = instalment - interest + float(extra_payment or 0.0)
        if capital <= 0:
            break  # the payment never covers interest: the debt cannot be cleared
        if capital > balance:
            capital, instalment_for_row = balance, balance + interest
        else:
            instalment_for_row = instalment
        balance -= capital
        rows.append({"month": month, "payment": round(instalment_for_row, 2),
                     "interest": round(interest, 2), "capital": round(capital, 2),
                     "balance": round(max(balance, 0.0), 2)})
    return rows


def total_interest(principal: float, annual_rate_pct: float, months: int) -> float:
    """P01 - total borrowing cost of a standard EMI loan."""
    return emi(principal, annual_rate_pct, months) * months - float(principal)


def loan_affordability(monthly_budget: float, annual_rate_pct: float, months: int) -> float:
    """P03 - the largest principal a monthly budget can carry."""
    return annuity_present_value(float(monthly_budget), annual_rate_pct, months)


def payoff_months(balance: float, monthly_payment: float, annual_rate_pct: float) -> int | None:
    """P04 - months to clear a card balance; None when the payment cannot win."""
    rate = monthly_rate(annual_rate_pct)
    remaining, months = float(balance), 0
    while remaining > 0.005:
        interest = remaining * rate
        capital = float(monthly_payment) - interest
        if capital <= 0:
            return None
        remaining -= capital
        months += 1
        if months > 1200:
            return None
    return months


def prepayment_saving(principal: float, annual_rate_pct: float, months: int,
                      lump: float, at_month: int) -> dict:
    """P02 - what one extra capital payment saves, measured against the same loan."""
    base = amortisation_schedule(principal, annual_rate_pct, months)
    rate = monthly_rate(annual_rate_pct)
    instalment = emi(principal, annual_rate_pct, months)
    balance, rows, month = float(principal), [], 0
    while balance > 0.005 and month < months * 12:
        month += 1
        interest = balance * rate
        capital = instalment - interest
        if month == max(1, int(at_month)):
            capital += float(lump)
        if capital <= 0:
            break
        capital = min(capital, balance)
        balance -= capital
        rows.append({"interest": interest, "capital": capital})
    base_interest = sum(row["interest"] for row in base)
    new_interest = sum(row["interest"] for row in rows)
    return {"monthsSaved": max(len(base) - len(rows), 0),
            "interestSaved": round(base_interest - new_interest, 2),
            "monthsAfter": len(rows), "monthsBefore": len(base)}


def future_value_lump(principal: float, annual_rate_pct: float, years: float,
                      compounds_per_year: int = 12) -> float:
    """P05 / P11 - growth of one amount, compounded at a chosen frequency."""
    periods = float(years) * compounds_per_year
    rate = float(annual_rate_pct) / (100.0 * compounds_per_year)
    if rate == 0:
        return float(principal)
    return float(principal) * (1.0 + rate) ** periods


def future_value_series(monthly_amount: float, annual_rate_pct: float, years: float) -> float:
    """P09 - the value of equal monthly contributions (a SIP without step-up)."""
    months = int(round(float(years) * MONTHS_PER_YEAR))
    rate = monthly_rate(annual_rate_pct)
    if months <= 0:
        return 0.0
    if rate == 0:
        return float(monthly_amount) * months
    return float(monthly_amount) * ((1.0 + rate) ** months - 1.0) / rate


def step_up_series(start_monthly: float, annual_rate_pct: float, years: float,
                   annual_step_up_pct: float) -> float:
    """P10 - monthly contributions that grow by a fixed percentage each year."""
    rate = monthly_rate(annual_rate_pct)
    contribution = float(start_monthly)
    balance = 0.0
    for month in range(1, int(round(float(years) * MONTHS_PER_YEAR)) + 1):
        if month > 1 and (month - 1) % MONTHS_PER_YEAR == 0:
            contribution *= 1.0 + float(annual_step_up_pct) / 100.0
        balance = balance * (1.0 + rate) + contribution
    return balance


def monthly_deposit_for_goal(target: float, annual_rate_pct: float, years: float) -> float:
    """P06 - what to set aside monthly to reach a goal."""
    months = int(round(float(years) * MONTHS_PER_YEAR))
    if months <= 0:
        return 0.0
    rate = monthly_rate(annual_rate_pct)
    if rate == 0:
        return float(target) / months
    return float(target) * rate / ((1.0 + rate) ** months - 1.0)


def inflation_effect(amount: float, inflation_pct: float, years: float) -> dict:
    """P07 - the future price of today's spending, and today's price of future money."""
    factor = (1.0 + float(inflation_pct) / 100.0) ** float(years)
    return {"futureCost": round(float(amount) * factor, 2),
            "buyingPowerOfToday": round(float(amount) / factor, 2),
            "priceIncreasePct": round((factor - 1.0) * 100.0, 2)}


def retirement_years(fund_at_retirement: float, annual_expense: float,
                     return_pct: float, withdrawal_pct: float | None = None) -> float:
    """P08 - how many years a retirement fund lasts at a fixed real withdrawal."""
    draw = float(annual_expense) if withdrawal_pct is None else float(fund_at_retirement) * withdrawal_pct / 100.0
    balance, years = float(fund_at_retirement), 0.0
    rate = float(return_pct) / 100.0
    while balance > 0.5 and years < 100.0:
        balance = balance * (1.0 + rate) - draw
        years += 1.0
        if balance <= 0.5:
            return years
    return years


EXAMPLE = {
    "tool": "P01 Loan EMI",
    "inputs": {"principal": 2500000, "annualRatePct": 8.6, "months": 240},
    "outputs": {
        "emi": round(emi(2500000, 8.6, 240), 2),
        "totalInterest": round(total_interest(2500000, 8.6, 240), 2),
        "totalPayment": round(emi(2500000, 8.6, 240) * 240, 2),
    },
}

if __name__ == "__main__":
    import json
    print(json.dumps(EXAMPLE, indent=2))
