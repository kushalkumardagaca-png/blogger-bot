#!/usr/bin/env python3
"""Canonical Daily Yield Master Article taxonomy and rotation rules."""
from __future__ import annotations

TRENDING_CATEGORIES = [
    {"number": 1, "type": "trending", "name": "Money & Policy Now", "label": "Trend · Money & Policy Now", "eyebrow": "Trending · rules changing now", "description": "Fresh tax, rate, budget, benefit and financial-policy developments, explained for practical decisions.", "signals": ["tax rule", "budget", "interest rate decision", "government benefit", "banking regulation", "pension change", "financial policy"]},
    {"number": 2, "type": "trending", "name": "Markets & Assets in Motion", "label": "Trend · Markets & Assets in Motion", "eyebrow": "Trending · prices moving now", "description": "Fast-rising market, currency, commodity, crypto and asset stories with evidence and context beyond the price move.", "signals": ["stock market", "gold price", "oil price", "currency", "crypto", "bond yield", "market volatility"]},
    {"number": 3, "type": "trending", "name": "Companies & Deals Trending", "label": "Trend · Companies & Deals Trending", "eyebrow": "Trending · business moves now", "description": "Earnings, IPOs, mergers, funding, layoffs and company decisions attracting exceptional current interest.", "signals": ["earnings", "IPO", "merger acquisition", "startup funding", "layoffs", "bankruptcy", "company deal"]},
    {"number": 4, "type": "trending", "name": "Technology & Future Money", "label": "Trend · Technology & Future Money", "eyebrow": "Trending · finance changing now", "description": "AI, fintech, payments, cybersecurity and new financial products gaining rapid search and public attention.", "signals": ["AI finance", "fintech", "digital payment", "cybersecurity finance", "digital currency", "investing app", "financial automation"]},
    {"number": 5, "type": "trending", "name": "Viral Money Questions", "label": "Trend · Viral Money Questions", "eyebrow": "Trending · questions rising now", "description": "Money questions, myths and consumer debates showing genuine acceleration across search and public discussion.", "signals": ["viral money advice", "cost of living", "saving challenge", "money myth", "personal finance question", "consumer money trend", "financial scam"]},
]

EVERGREEN_CATEGORIES = [
    {"number": 6, "type": "evergreen", "name": "Money Hacks & Financial Habits", "label": "Money Hacks & Financial Habits", "eyebrow": "Evergreen · everyday decisions", "description": "Practical systems for budgeting, spending, behaviour and stronger everyday money decisions.", "signals": ["budgeting", "financial habits", "lifestyle inflation", "frugality", "money psychology", "financial audit", "middle class money"]},
    {"number": 7, "type": "evergreen", "name": "Saving & Emergency Planning", "label": "Saving & Emergency Planning", "eyebrow": "Evergreen · resilience", "description": "Cash reserves, savings goals and emergency preparation for financial resilience.", "signals": ["emergency fund", "saving money", "cash reserve", "sinking fund", "savings account", "short term savings", "liquidity"]},
    {"number": 8, "type": "evergreen", "name": "Credit, Debt & Loans", "label": "Credit Debt & Loans", "eyebrow": "Evergreen · borrowing clearly", "description": "Credit, borrowing costs, repayment strategies and protection from destructive debt.", "signals": ["credit score", "credit card debt", "personal loan", "student loan", "debt repayment", "refinancing", "buy now pay later"]},
    {"number": 9, "type": "evergreen", "name": "Banking, Payments & Fintech", "label": "Banking Payments & Fintech", "eyebrow": "Evergreen · moving money", "description": "Bank accounts, payments, fintech tools and the systems people use to store and move money.", "signals": ["bank account", "digital banking", "UPI", "mobile wallet", "remittance", "fintech", "digital lending"]},
    {"number": 10, "type": "evergreen", "name": "Investing & Portfolio Building", "label": "Investing & Portfolio Building", "eyebrow": "Evergreen · building wealth", "description": "Evidence-led investing, diversification and portfolio decisions for long-term wealth building.", "signals": ["asset allocation", "index fund", "ETF", "stock investing", "bond investing", "portfolio diversification", "compound returns"]},
    {"number": 11, "type": "evergreen", "name": "Markets, Trading & Crypto", "label": "Markets Trading & Crypto", "eyebrow": "Evergreen · understanding markets", "description": "Market structure, trading risk, commodities, currencies, crypto and investor psychology.", "signals": ["stock trading", "market cycle", "commodity investing", "forex", "crypto investing", "technical analysis", "market psychology"]},
    {"number": 12, "type": "evergreen", "name": "Retirement & Financial Independence", "label": "Retirement & Financial Independence", "eyebrow": "Evergreen · freedom later", "description": "Pensions, retirement income, FIRE and planning for a financially independent later life.", "signals": ["retirement planning", "pension", "provident fund", "FIRE", "retirement withdrawal", "retirement income", "longevity risk"]},
    {"number": 13, "type": "evergreen", "name": "Taxes, Benefits & Financial Planning", "label": "Taxes Benefits & Financial Planning", "eyebrow": "Evergreen · planning around rules", "description": "Tax, benefits, estate preparation and complete financial-planning decisions.", "signals": ["income tax", "tax deduction", "capital gains tax", "government benefits", "estate planning", "inheritance", "financial plan"]},
    {"number": 14, "type": "evergreen", "name": "Insurance & Risk Protection", "label": "Insurance & Risk Protection", "eyebrow": "Evergreen · protecting outcomes", "description": "Insurance choices, claims and risk protection for households, health, income and property.", "signals": ["life insurance", "health insurance", "property insurance", "insurance claim", "disability insurance", "liability insurance", "risk protection"]},
    {"number": 15, "type": "evergreen", "name": "Homes, Mortgages & Real Estate", "label": "Homes Mortgages & Real Estate", "eyebrow": "Evergreen · property decisions", "description": "Buying, renting, mortgages, housing affordability and property investment.", "signals": ["buy versus rent", "mortgage", "home loan", "real estate investing", "rental income", "housing affordability", "down payment"]},
    {"number": 16, "type": "evergreen", "name": "Careers, Income & Side Hustles", "label": "Careers Income & Side Hustles", "eyebrow": "Evergreen · earning better", "description": "Salary, skills, career moves, freelancing and responsible ways to expand income.", "signals": ["salary negotiation", "career growth", "job skills", "freelancing", "side hustle", "remote work", "workplace benefits"]},
    {"number": 17, "type": "evergreen", "name": "Business, Startups & Entrepreneurship", "label": "Business Startups & Entrepreneurship", "eyebrow": "Evergreen · building businesses", "description": "Starting, funding, pricing and operating durable businesses with sound cash flow.", "signals": ["start a business", "startup funding", "bootstrapping", "small business", "business cash flow", "pricing strategy", "entrepreneurship"]},
    {"number": 18, "type": "evergreen", "name": "Companies, Technology & Industry", "label": "Companies Technology & Industry", "eyebrow": "Evergreen · how firms compete", "description": "Business models, management, technology and the forces reshaping companies and industries.", "signals": ["company analysis", "business model", "competitive advantage", "corporate strategy", "AI automation", "industry analysis", "management"]},
    {"number": 19, "type": "evergreen", "name": "Economy, Policy & Global Finance", "label": "Economy Policy & Global Finance", "eyebrow": "Evergreen · the larger system", "description": "Inflation, rates, trade, employment, policy and global forces shaping financial choices.", "signals": ["inflation", "interest rates", "GDP", "employment", "central bank", "international trade", "global economy"]},
    {"number": 20, "type": "evergreen", "name": "Family, Life Stages & Consumer Safety", "label": "Family Life Stages & Consumer Safety", "eyebrow": "Evergreen · money through life", "description": "Money decisions across life stages, family needs, major purchases, scams and consumer protection.", "signals": ["student money", "couples finances", "family budget", "education planning", "ageing parents", "consumer rights", "financial scams"]},
]

MASTER_CATEGORIES = TRENDING_CATEGORIES + EVERGREEN_CATEGORIES
TRENDING_LABELS = [x["label"] for x in TRENDING_CATEGORIES]
EVERGREEN_LABELS = [x["label"] for x in EVERGREEN_CATEGORIES]

LEGACY_CATEGORY_MAP = {
    "Contrarian Hooks": "Money Hacks & Financial Habits",
    "Age and Wealth Milestones": "Family Life Stages & Consumer Safety",
    "Passive Income Reality": "Investing & Portfolio Building",
    "Middle Class Survival": "Money Hacks & Financial Habits",
    "Money Audits and Case Studies": "Money Hacks & Financial Habits",
    "Housing Cars and Big Buys": "Homes Mortgages & Real Estate",
    "Automation and Money Systems": "Money Hacks & Financial Habits",
    "Credit Debt and Optimization": "Credit Debt & Loans",
    "AI Fintech and Future Money": "Banking Payments & Fintech",
    "Money Psychology and Mindset": "Money Hacks & Financial Habits",
    "Investing Strategies": "Investing & Portfolio Building",
    "Retirement Pensions and FIRE": "Retirement & Financial Independence",
    "Taxes and Account Optimization": "Taxes Benefits & Financial Planning",
    "Career Salary and Raises": "Careers Income & Side Hustles",
    "Side Hustles That Work": "Careers Income & Side Hustles",
    "Insurance and Protection": "Insurance & Risk Protection",
    "Couples Family and Kids": "Family Life Stages & Consumer Safety",
    "Starters Students and First Jobs": "Family Life Stages & Consumer Safety",
    "Spending Lifestyle and Frugality": "Money Hacks & Financial Habits",
    "Rich Habits vs Broke Habits": "Money Hacks & Financial Habits",
    "Recessions Crashes and Defense": "Economy Policy & Global Finance",
    "Cash Savings and Emergency Funds": "Saving & Emergency Planning",
    "Real Estate Investing": "Homes Mortgages & Real Estate",
    "Myths Scams and Bad Advice": "Family Life Stages & Consumer Safety",
    "2026 Money Moves": "Money Hacks & Financial Habits",
}

def evergreen_rotation(day_ordinal: int):
    """Five categories daily; all fifteen are covered in each three-day cycle."""
    start = (day_ordinal % 3) * 5
    return EVERGREEN_CATEGORIES[start:start + 5]
