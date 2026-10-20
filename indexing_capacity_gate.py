#!/usr/bin/env python3
"""Bound Daily Yield's publishing to what Google can actually index.

This is the lever nobody wants and every stuck property needs. On 20 Oct 2026 Search
Console reported **1 indexed URL out of 551 submitted**, with 360 in "discovered -
currently not indexed" and 180 "unknown to Google". While that stands, every extra URL
the automation announces makes the property look less like a publication and more like a
content factory - which is precisely the signal that keeps Google from indexing it. Volume
is not the missing ingredient; trust is, and trust is spent per URL, not earned per URL.

So this script turns the measured index into two live things:

* a **cap** - how many new URLs the site should be creating per day right now;
* a **priority list** - which URLs are worth announcing to IndexNow today, and which
  duplicates and utility pages must stop being announced at all, because each one spends
  crawl budget that a real article needs.

It never requests a Daily Yield page, never invents a number, and only tightens the cap
when the measured evidence says the index is not growing. Absent evidence is reported as
absent and leaves the cap alone rather than guessing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "INDEX_STATUS_REPORT.json"
BASELINE = ROOT / "AUDIENCE_GROWTH_BASELINE.json"
INDEXNOW = ROOT / "INDEXNOW_STATE.json"
DEMAND = ROOT / "SEARCH_DEMAND_TRENDS.json"
OUT = ROOT / "INDEXING_CAPACITY.json"
MD = ROOT / "INDEXING_CAPACITY.md"
PRIORITY = ROOT / "INDEX_PRIORITY.json"

# Blogger's duplicate suffix: the same title published twice gets "_01450325346" appended.
DUPLICATE_SLUG = re.compile(r"_\d{8,}\.html?/?$")
UTILITY_PATH = re.compile(r"/p/|/search|indexnow-key|\?m=1|/robots|\.xml$")
NEWS_SLUG = re.compile(r"(finance-news|markets|crypto|commodities|ipos|global-finance|news-\d{4}-)")


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def slug_of(url: str) -> str:
    return str(url or "").rstrip("/").rsplit("/", 1)[-1]


def dated(slug: str, within_days: int, today: date) -> bool:
    """True when the slug carries a date inside the window (news is only worth pushing fresh)."""
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", slug or "")
    if not match:
        return False
    try:
        stamp = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return False
    return 0 <= (today - stamp).days <= within_days


def lexicon() -> list[str]:
    demand = load(DEMAND, {})
    terms = demand.get("lexicon") or demand.get("terms") or []
    return [str(term).strip().lower() for term in terms if str(term).strip()]


def template_of(url: str) -> str:
    """The slug family a URL belongs to, with any date removed.

    "companies-ipos-deals-2026-10-10" and "...-2026-10-11" are one template. Announcing a
    dozen of them spends the crawl budget on pages that compete with each other, so the
    ranking keeps two per family, the freshest first, and lets the rest wait their turn.
    """
    slug = re.sub(r"\d{4}-\d{2}-\d{2}", "", slug_of(url))
    slug = re.sub(r"[-_]?\d*$", "", slug)
    return slug.split(".html")[0].strip("-_")


def score(url: str, words: list[str], today: date) -> tuple[int, list[str]]:
    """How much this URL deserves the crawl budget it would spend."""
    slug = slug_of(url)
    points, why = 0, []
    if UTILITY_PATH.search(url):
        return -1, ["utility or policy page: announcing it only spends crawl budget"]
    if DUPLICATE_SLUG.search(slug):
        return -1, ["duplicate of the same title published twice (Blogger suffix)"]
    if dated(slug, 2, today):
        points += 60
        why.append("published in the last 48 hours")
    if NEWS_SLUG.search(slug):
        points += 30
        why.append("news-led slug, the kind search indexes on freshness")
    hits = [term for term in words if term.replace(" ", "-") in slug]
    if hits:
        points += 10 * len(hits)
        why.append("matches live search demand: " + ", ".join(hits[:4]))
    if not slug.endswith(".html"):
        points -= 20
        why.append("not an article URL")
    return points, why


def measure_history(previous: dict, indexed: int | None, today: str) -> list[dict]:
    history = [row for row in (previous.get("history") or []) if isinstance(row, dict)]
    if indexed is not None:
        if not history or history[-1].get("day") != today:
            history.append({"day": today, "indexed": indexed})
        else:
            history[-1]["indexed"] = indexed
    return history[-45:]


def decide(indexed: int | None, submitted: int | None, history: list[dict], impressions28: int | None) -> dict:
    """The cap, with the arithmetic that produced it written beside it."""
    if indexed is None:
        return {"decision": "UNKNOWN", "masterArticlesPerDay": None, "newsWiresPerDay": None,
                "why": ["no Search Console index measurement on file, so nothing is throttled and "
                        "nothing is claimed. Run index_status_report first"]}
    week = [row for row in history if row.get("day", "") >= (
        datetime.strptime(history[-1]["day"], "%Y-%m-%d").date() - timedelta(days=7)).strftime("%Y-%m-%d")] \
        if history else []
    growth = (week[-1].get("indexed", indexed) and indexed - week[0].get("indexed", indexed)) if len(week) > 1 else 0
    ratio = (indexed / submitted) if submitted else 0.0
    note = {
        "indexed": indexed, "submitted": submitted, "indexedShare": round(ratio, 4),
        "indexedGrowth7d": growth, "impressions28d": impressions28,
    }
    if indexed < 25 and growth <= 0:
        verdict = "CONTRACT"
        cap = {"masterArticlesPerDay": 2, "newsWiresPerDay": 1}
        why = [f"only {indexed} of {submitted} submitted URLs are indexed and none were added in the last "
               f"7 days: the property is not being trusted, so more URLs cannot become more readers",
               "publishing is held to the depth the site can get indexed, and the freed time goes into "
               "rewriting what already exists rather than adding to the pile"]
    elif indexed < 150 or growth < 5:
        verdict = "HOLD"
        cap = {"masterArticlesPerDay": 5, "newsWiresPerDay": 2}
        why = [f"indexed {indexed} with {growth} added in 7 days: the index is moving, slowly. Current "
               f"output is kept and the backlog is cleaned rather than grown"]
    else:
        verdict = "EXPAND"
        cap = {"masterArticlesPerDay": 8, "newsWiresPerDay": 3}
        why = [f"indexed {indexed} with {growth} added in 7 days: the site is absorbing new URLs, so "
               f"more of them help"]
    return {"decision": verdict, "masterArticlesPerDay": cap["masterArticlesPerDay"],
            "newsWiresPerDay": cap["newsWiresPerDay"], "why": why, "measured": note}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", default="", help="ISO day to judge against (default: now UTC)")
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args()

    today = datetime.strptime(arguments.today, "%Y-%m-%d").date() if arguments.today else datetime.now(
        timezone.utc).date()
    status = load(STATUS, {})
    baseline = load(BASELINE, {})
    indexnow = load(INDEXNOW, {})
    previous = load(OUT, {})

    indexed = status.get("indexed") if status else None
    submitted = status.get("urls") if status else None
    acquisition = ((baseline.get("searchAcquisition") or {}).get("last28Days") or {})
    impressions = acquisition.get("impressions") if isinstance(acquisition, dict) else None

    history = measure_history(previous, indexed, today.isoformat())
    verdict = decide(indexed if isinstance(indexed, int) else None,
                     submitted if isinstance(submitted, int) else None, history,
                     impressions if isinstance(impressions, int) else None)

    words = lexicon()
    pool = list(dict.fromkeys(list(indexnow.get("pending") or []) + list((indexnow.get("submitted") or {}).keys())))
    ranked, suppressed = [], []
    for url in pool:
        points, why = score(url, words, today)
        if points < 0:
            suppressed.append({"url": url, "reason": "; ".join(why)})
        else:
            ranked.append((points, url, why))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    per_template: dict[str, int] = {}
    announce = []
    for points, url, why in ranked:
        family = template_of(url)
        if per_template.get(family, 0) >= 2:
            suppressed.append({"url": url, "reason": "third or later URL of the template "
                               + family + ": one family cannot need the crawl budget twice over"})
            continue
        per_template[family] = per_template.get(family, 0) + 1
        announce.append({"url": url, "score": points, "why": why})
        if len(announce) >= 40:
            break

    # IndexNow that never actually submits is the failure mode this replaced: the queue grew
    # while nothing left it, and the workflow printed a line and stayed green.
    submitted_total = len(indexnow.get("submitted") or {})
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site": "https://dailyyield.blogspot.com",
        **verdict,
        "history": history,
        "announcementQueue": {"pending": len(indexnow.get("pending") or []), "submittedEver": submitted_total,
                             "indexnowLooksBlocked": submitted_total == 0 and bool(indexnow.get("pending")),
                             "announceTop": len(announce), "suppressedDuplicatesAndUtility": len(suppressed)},
        "evidenceFiles": {name: bool(path.exists()) for name, path in (
            ("INDEX_STATUS_REPORT.json", STATUS), ("AUDIENCE_GROWTH_BASELINE.json", BASELINE),
            ("INDEXNOW_STATE.json", INDEXNOW), ("SEARCH_DEMAND_TRENDS.json", DEMAND))},
    }
    save(OUT, report)
    save(PRIORITY, {"day": today.isoformat(), "decision": verdict["decision"],
                    "announce": [row["url"] for row in announce],
                    "suppressCount": len(suppressed),
                    "note": "Announce only these. The suppressed list is duplicate-title and utility URLs; "
                            "submitting them spends the crawl budget the articles need."})
    lines = [f"# Indexing capacity gate · {today.isoformat()}", "",
             f"Decision: **{verdict['decision']}**", ""]
    if verdict.get("measured"):
        measured = verdict["measured"]
        lines += [f"- indexed: **{measured['indexed']}** of {measured['submitted']} submitted "
                  f"({measured['indexedShare'] * 100:.1f}%)",
                  f"- added to the index in the last 7 days: {measured['indexedGrowth7d']}",
                  f"- Search Console clicks/impressions, 28 days: "
                  f"{baseline.get('searchAcquisition', {}).get('last28Days', {}).get('clicks', 'n/a')}"
                  f" / {measured['impressions28d']}", ""]
    lines += ["**Cap that follows from it**", ""]
    lines += [f"- new Master articles per day: **{verdict['masterArticlesPerDay']}**",
              f"- news wires per day: **{verdict['newsWiresPerDay']}**", ""]
    lines += ["**Why**", ""] + [f"- {row}" for row in verdict["why"]] + ["",
              f"IndexNow: {report['announcementQueue']['pending']} URLs queued, "
              f"{report['announcementQueue']['submittedEver']} ever accepted"
              + (" — **nothing is actually being submitted**, so the queue is only a list"
                 if report['announcementQueue']['indexnowLooksBlocked'] else ""),
              f"Priority list for today's announcement: {report['announcementQueue']['announceTop']} URLs; "
              f"{report['announcementQueue']['suppressedDuplicatesAndUtility']} duplicate/utility URLs held back.",
              ""]
    MD.write_text("\n".join(lines), encoding="utf-8")
    if not arguments.quiet:
        print(json.dumps({"decision": report["decision"], "cap": {"masterArticlesPerDay": report["masterArticlesPerDay"],
                                                                  "newsWiresPerDay": report["newsWiresPerDay"]},
                          "indexed": (verdict.get("measured") or {}).get("indexed"),
                          "submitted": (verdict.get("measured") or {}).get("submitted"),
                          "announce": report["announcementQueue"]["announceTop"],
                          "suppressed": report["announcementQueue"]["suppressedDuplicatesAndUtility"],
                          "indexnowLooksBlocked": report["announcementQueue"]["indexnowLooksBlocked"]},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
