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
* a **priority list** - which URLs are worth asking Google about today, and which
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
DEMAND = ROOT / "SEARCH_DEMAND_TRENDS.json"
QUEUE = ROOT / "ASK_GOOGLE_QUEUE.json"
OUT = ROOT / "INDEXING_CAPACITY.json"
MD = ROOT / "INDEXING_CAPACITY.md"
PRIORITY = ROOT / "INDEX_PRIORITY.json"

# Blogger's duplicate suffix: the same title published twice gets "_01450325346" appended.
DUPLICATE_SLUG = re.compile(r"_\d{8,}\.html?/?$")
UTILITY_PATH = re.compile(r"/p/|/search|indexnow-key|\?m=1|/robots|\.xml$")

# Owner decision, 20 October 2026: stop trying to get 551 article URLs indexed and get the main
# pages in first - the hubs, the calculators, the markets and snapshot pages, and the standing
# information pages (about us, contact us, disclaimer, privacy). They are thirteen URLs, they are
# what the whole site links to, and a search engine that trusts them has a place to send readers
# to. Article pages are held, not deleted: they stay published and linked from the hubs, so the
# daily 21 keeps running, and Google reaches them through the hub instead of through a queue that
# has indexed one page in ninety days.
MAIN_PAGE_URL = re.compile(r"https://dailyyield\.blogspot\.com/p/(?!indexnow-key|robots)[a-z0-9\-_]+\.html?$")
MAIN_PAGE_PRIORITY = ("daily-news", "article", "markets-today", "global-snapshot", "calculator",
                      "money-atlas", "for-corporate")
MAIN_PAGE_CAP = 16
# A test shaped like /p/<name>.html can never match the homepage, so the homepage was silently
# missing from the thirteen: it was announced to no one, and it is not in either Blogger sitemap.
# Owner instruction, 21 October 2026: "all the 13 pages including the homepage".
MAIN_PAGE_HOME = "https://dailyyield.blogspot.com/"
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
    parser.add_argument("--include-articles", action="store_true",
                        help="announce ranked article URLs too, instead of the main pages only")
    arguments = parser.parse_args()

    today = datetime.strptime(arguments.today, "%Y-%m-%d").date() if arguments.today else datetime.now(
        timezone.utc).date()
    status = load(STATUS, {})
    baseline = load(BASELINE, {})
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
    # The queue used to be an IndexNow hand-off. Since 23 October 2026 it is this file only: a list of URLs
    # the site would like Google to look at, written by the gate itself and read by no engine. Empty file,
    # empty queue - which is the truth since the owner retired Bing, not a queue that pretends to be stuck.
    queue = load(QUEUE, {})
    pool = list(dict.fromkeys(list(queue.get("pending") or []) + list((queue.get("asked") or {}).keys())))
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

    main_pages = sorted(
        {url for url in (list(pool) + [str(row.get("url") or "") for row in (status.get("rows") or [])])
         if MAIN_PAGE_URL.search(str(url))},
        key=lambda url: (MAIN_PAGE_PRIORITY.index(next((key for key in MAIN_PAGE_PRIORITY
                                                        if key in url), "")) if any(
            key in url for key in MAIN_PAGE_PRIORITY) else len(MAIN_PAGE_PRIORITY), url))
    # The homepage is put in by hand rather than discovered: it is in no Blogger sitemap, it matches
    # no /p/ pattern, and the queue only ever carried what a post feed produced. Search Console
    # reported a "Redirect error" on exactly this URL, which is a reason to announce and inspect it
    # more often, not less.
    if MAIN_PAGE_HOME not in main_pages:
        main_pages.insert(0, MAIN_PAGE_HOME)
        home_forced = True
    else:
        home_forced = False
    if main_pages and not arguments.include_articles:
        announce = [{"url": url, "score": 1000 - index,
                     "why": ["main page: the site's own front doors, indexed before any article"]}
                    for index, url in enumerate(main_pages[:MAIN_PAGE_CAP])]
        suppressed += [{"url": url, "reason": "article URL held while the main pages get indexed "
                                             "(owner decision, 20 October 2026)"}
                       for _points, url, _why in ranked]
        ranked = [(row["score"], row["url"], row["why"]) for row in announce]

    # The queue was retired the same evening. It stays retired on purpose: a list of URLs that nothing
    # submits is a report that lies about itself, which is exactly why this gate replaced it.
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site": "https://dailyyield.blogspot.com",
        **verdict,
        "history": history,
        "askList": {"announceTop": len(announce), "suppressedDuplicatesAndUtility": len(suppressed),
                    "queueFile": QUEUE.name, "pendingInQueue": len(queue.get("pending") or []),
                    "note": "a Google-side priority list only: no engine submission is made from this file"},
        "mainPagePolicy": {"on": bool(main_pages) and not arguments.include_articles,
                           "mainPagesFound": len(main_pages), "announced": min(len(main_pages), MAIN_PAGE_CAP),
                           "articleUrlsHeld": len(suppressed) if main_pages and not arguments.include_articles else 0,
                           "pages": main_pages[:MAIN_PAGE_CAP],
                           "homepageIncluded": MAIN_PAGE_HOME in main_pages,
                           "homepageForcedByThisRun": home_forced,
                           "ownerInstruction": "owner, 21 October 2026: the 13 pages including the "
                                               "homepage, indexed by the end of November 2026",
                           "decidedBy": "owner, 20 October 2026: index the main pages first"},
        "evidenceFiles": {name: bool(path.exists()) for name, path in (
            ("INDEX_STATUS_REPORT.json", STATUS), ("AUDIENCE_GROWTH_BASELINE.json", BASELINE),
            (QUEUE.name, QUEUE), ("SEARCH_DEMAND_TRENDS.json", DEMAND))},
    }
    save(OUT, report)
    save(PRIORITY, {"day": today.isoformat(), "decision": verdict["decision"],
                    "announce": [row["url"] for row in announce],
                    "suppressCount": len(suppressed),
                    "note": ("Announce only the main pages: thirteen hub, calculator, markets and standing "
                             "information URLs, published 20 October 2026 by owner decision. Article URLs stay "
                             "published and linked from these pages; they are held back from announcement, not "
                             "removed. The suppressed list is article, duplicate-title and utility URLs whose "
                             "announcement would spend the crawl budget the front doors need.")})
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
              ("Main pages announced: **%d** of %d found; **%d** article and utility URLs held back "
              "(owner decision: index the front doors first)."
              % (report["mainPagePolicy"]["announced"], report["mainPagePolicy"]["mainPagesFound"],
                 report["mainPagePolicy"]["articleUrlsHeld"])
              if report["mainPagePolicy"]["on"] else
              "Main-page-first policy is off for this run: ranked article URLs are being announced."), "",
             f"Priority list for Google: {report['askList']['announceTop']} URLs; "
              f"{report['askList']['suppressedDuplicatesAndUtility']} duplicate/utility URLs held back.",
              ""]
    MD.write_text("\n".join(lines), encoding="utf-8")
    if not arguments.quiet:
        print(json.dumps({"decision": report["decision"], "cap": {"masterArticlesPerDay": report["masterArticlesPerDay"],
                                                                  "newsWiresPerDay": report["newsWiresPerDay"]},
                          "indexed": (verdict.get("measured") or {}).get("indexed"),
                          "submitted": (verdict.get("measured") or {}).get("submitted"),
                          "announce": report["askList"]["announceTop"],
                          "suppressed": report["askList"]["suppressedDuplicatesAndUtility"]},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
