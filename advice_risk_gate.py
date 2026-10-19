#!/usr/bin/env python3
"""Automated advice-risk gate — the substitute for a human financial reviewer.

Owner decision, 19 October 2026: Daily Yield has **no human professional reviewer**.
The publication therefore never claims one, and risky material is stopped by
machinery instead of approved by a person. That is a real safety model, not a
softer one: a gate cannot be tired, cannot be talked into it, and fails closed.

What the gate does
------------------
* Blocks personalised instructions ("you should buy X"), guaranteed-return
  language, and tax-rule assertions with no dated primary source and no
  "rules change" notice.
* Blocks any claim that a chartered accountant, expert or professional reviewed
  an article, because nobody does.
* Blocks qualification claims about the publisher (a second, narrower net beside
  content_policy_guard, so a reworded sentence cannot slip between the two).
* Requires the education-only disclosure wherever high-risk subject matter appears.
* Records uncertainty warnings (undated figures, forecasts without a counterweight)
  so the weekly report can show what needs a second pass, without blocking a
  sound article.

Nothing here is professional advice, review, or a substitute for a reader's own
checks, and the generated status file says so.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "ADVICE_RISK_GATE_STATUS.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# The publication has no human reviewer. Nothing may set this to True unless the
# owner actually appoints one, and the gate's output states the value either way.
HUMAN_REVIEWER = False

HIGH_RISK_SUBJECT = re.compile(
    r"\b(invest(?:ing|ment|or)?|portfolio|mutual fund|stock|share|bond|crypto|loan|emi"
    r"|credit card|debit|mortgage|insurance|retirement|pension|tax|gst|income tax|tds"
    r"|fixed deposit|epf|nps|sukanya|ppf|market)\b", re.I)

DISCLOSURE_MARKERS = (
    "educational information only", "not personalised financial", "not personal advice",
    "general financial education", "not personalised advice")

BLOCKING_RULES = (
    ("personalised buy/sell/apply instruction",
     re.compile(r"\b(?:you|we)\s+(?:should|must|need to|ought to|advise you to|recommend that you)\b"
                r"[^.]{0,60}\b(?:buy|sell|invest in|put your money|move your money|transfer your"
                r"|apply for|take out|liquidate|exit|purchase)\b", re.I)),
    ("guaranteed or risk-free return claim",
     re.compile(r"\b(?:guaranteed|guarantees|assured|risk[- ]free|can'?t lose|no downside|certain returns?)"
                r"[^.]{0,40}\b(?:return|returns|growth|interest|profit|gain|yield|corpus)\b", re.I)),
    ("reviewed-by-a-professional claim with no reviewer",
     re.compile(r"\b(?:reviewed|checked|verified|approved|vetted|proofread)\s+by\s+(?:a|an|our|the|every)?"
                r"[^.]{0,30}\b(?:chartered accountant|\bccai\b|\bca\b|expert|professional|advisor|adviser"
                r"|accountant|analyst|committee|panel)\b", re.I)),
    ("publisher qualification claim",
     re.compile(r"\b(?:Kushal(?: Daga)?|the author|the publisher|founder|writer|we|i)\b[^.]{0,60}"
                r"\b(?:is|am|are|holds?|qualified|registered)\b[^.]{0,40}"
                r"\b(?:chartered accountant|certified accountant|\bCPA\b|\bCFA\b|registered investment adviser"
                r"|licensed (?:financial )?(?:adviser|advisor)|SEBI registered)\b", re.I)),
)

TAX_ASSERTION = re.compile(r"\b(?:section\s?\d{2,4}[A-Z]?|sub-?section|under the Income-?Tax Act"
                           r"|as per the(?: Income Tax| IT) Act|finance act|GST rate of|TDS rate of"
                           r"|deduction of up to|exempt from tax|tax-free|no tax(?: is)? (?:due|payable))\b", re.I)
TAX_HEDGE = re.compile(r"\b(?:rules? (?:change|can change)|as of \d|assessment year|financial year"
                       r"|latest available|verify with|tax rules? (?:in force|as they stand)"
                       r"|consult (?:a|your) (?:tax|income)[^.]{0,30}(?:advisor|adviser|professional))\b", re.I)
DATE_IN_SENTENCE = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:January|February|March|April|May|June|July|August"
                              r"|September|October|November|December)\s+\d{1,2}\b|\b\d{1,2}\s+(?:January|February"
                              r"|March|April|May|June|July|August|September|October|November|December)\b", re.I)
FORECAST = re.compile(r"\b(?:expects?|expected to|forecasts?|forecast to|will likely|is likely to|should reach"
                      r"|target(?:s|ed)? at|projects? that|consensus (?:is|of))\b", re.I)
UNCERTAINTY = re.compile(r"\b(?:uncertain|uncertainty|risk|may not|no guarantee|not a prediction|volatile"
                         r"|could also|depends on|estimates? vary|forecasts? differ)\b", re.I)


# Attributed reporting is not our promise. A sentence that quotes a source, names who
# said it, or describes a proposal is news copy; a bare "you get guaranteed returns"
# is advice. Without this line the gate would silence ordinary market reporting.
ATTRIBUTION = re.compile(r"\b(?:according to|\bsays?\b|\bsaid\b|stated|statement|noted|told|reported"
                         r"|\bclaims?\b|(?:company|bank|insurer|fund|provider|government|ministry|minister"
                         r"|exchange|regulator|report|study|data|figures)\s+(?:says|said|states|stated|shows|showed)"
                         r"|product document|fact sheet|circular|press release|\bbudget speech\b)\b""", re.I)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n|</p>", text or "") if s.strip()]


def sentences_about(text: str, pattern: re.Pattern) -> list[str]:
    """Sentences matching a pattern, so a finding can quote the real wording."""
    return [s for s in _sentences(text) if pattern.search(s)]


def audit(title: str, text: str) -> dict:
    """Risk verdict for one article. `blocking` must stop publication; `warnings` must not."""
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"\s+", " ", plain)
    combined = f"{title or ''} {plain}"
    lowered = combined.casefold()
    high_risk = bool(HIGH_RISK_SUBJECT.search(combined))
    disclosure = any(marker in lowered for marker in DISCLOSURE_MARKERS)

    blocking, warnings = [], []
    for name, pattern in BLOCKING_RULES:
        hits = sentences_about(combined, pattern)
        if name.startswith("guaranteed") or name.startswith("tax"):
            # Reporting what someone else promises, with the source named, is not us
            # promising it. Keep the block for unattributed assertions.
            hits = [row for row in hits if not ATTRIBUTION.search(row)]
        if hits:
            blocking.append({"rule": name, "example": hits[0][:220]})
    # Tax material is the sharpest risk: a rule stated as fact must say when it was
    # true and that rules change, and must carry a dated primary source.
    # A tax sentence is risky when it states a rule as permanent fact and nothing in
    # that sentence says when it was true or that rules change. Dated wording inside
    # the sentence is accepted, so well-sourced copy is not punished for the format
    # of its source list; a bare "tax-free forever" claim still stops.
    tax_lines = [row for row in sentences_about(combined, TAX_ASSERTION)
                 if not DATE_IN_SENTENCE.search(row) and not TAX_HEDGE.search(row)
                 and not ATTRIBUTION.search(row)]
    if tax_lines:
        blocking.append({"rule": "tax rule stated as permanent fact with no date and no change notice",
                         "example": tax_lines[0][:220]})
    if high_risk and not disclosure:
        blocking.append({"rule": "education-only disclosure missing on advice-adjacent subject matter",
                         "example": (title or "")[:220]})
    if not HUMAN_REVIEWER:
        for claim in sentences_about(combined, re.compile(r"\b(?:expert-?reviewed|expert reviewed"
                                                           r"|accountant-?reviewed|professionally reviewed)\b", re.I)):
            blocking.append({"rule": "professional review claimed; this publication has no reviewer",
                             "example": claim[:220]})

    undated = [s for s in sentences_about(plain, re.compile(r"(?:R|r)s\.?\s?[\d,]{4,}|\b\d+(?:\.\d+)?%"))
               if not DATE_IN_SENTENCE.search(s)]
    if undated:
        warnings.append({"rule": "money or percentage figure with no date in the sentence",
                         "example": undated[0][:200]})
    forecasts = [s for s in _sentences(plain) if FORECAST.search(s)]
    if forecasts and not UNCERTAINTY.search(plain):
        warnings.append({"rule": "forecast wording with no stated uncertainty",
                         "example": forecasts[0][:200]})

    return {"riskTier": "high" if (blocking or high_risk) else "general",
            "highRiskSubject": high_risk, "educationDisclosurePresent": disclosure,
            "humanReviewer": HUMAN_REVIEWER, "blocking": blocking, "warnings": warnings,
            "checkedSentences": len(_sentences(plain))}


def assert_gate(title: str, text: str) -> dict:
    """Fail closed: raise with every blocking finding named and quoted."""
    verdict = audit(title, text)
    if verdict["blocking"]:
        detail = "; ".join(f"{row['rule']} — “{row['example']}”" for row in verdict["blocking"])
        raise RuntimeError(f"ADVICE RISK GATE BLOCKED THIS ARTICLE: {detail}. Daily Yield publishes "
                           "general education checked by automated rules, not personalised advice.")
    return verdict


def _audit_local_corpus() -> dict:
    """Run the gate over already-prepared files only: no page is opened or written."""
    # Prepared article HTML only. A master package is not reader-facing prose, and
    # counting its JSON would turn one article into several findings.
    files = sorted((ROOT / "scheduled_ready").glob("*.html"))
    checked = blocked = warned = 0
    examples = []
    for path in files:
        body = path.read_text(encoding="utf-8", errors="replace")
        title = (re.search(r"<title>(.*?)</title>", body, re.S | re.I) or
                 re.search(r'"title"\s*:\s*"([^"]+)"', body))
        verdict = audit(title.group(1)[:200] if title else path.stem, body)
        checked += 1
        if verdict["blocking"]:
            blocked += 1
            if len(examples) < 5:
                examples.append({"file": path.name, "rule": verdict["blocking"][0]["rule"]})
        warned += 1 if verdict["warnings"] else 0
    return {"checkedAtIST": dt.datetime.now(IST).isoformat(),
            "scope": "Prepared article HTML in scheduled_ready; no live page was opened or changed",
            "filesChecked": checked,
            "blockedLocally": blocked, "withWarnings": warned, "examples": examples,
            "humanReviewer": HUMAN_REVIEWER,
            "note": "Offline check of prepared files. It is an automated rule pass, not a professional review, "
                    "and it creates or changes no page."}


def main() -> int:
    if "--audit" in sys.argv:
        report = _audit_local_corpus()
        STATUS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("filesChecked", "blockedLocally", "withWarnings", "humanReviewer")}))
        return 0
    sample = ("SIP vs lump sum: how the two differ over ten years",
              "<p>Investing carries risk. Returns are not guaranteed. Educational information only; "
              "not personalised financial advice. Source retrieved 2026-10-19.</p>")
    print(json.dumps(audit(*[s for s in sample]), indent=2)[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
