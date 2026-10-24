#!/usr/bin/env python3
"""Put the two view counters side by side, and say in plain words what each one counts.

Blogger's own Stats page and Google Analytics answer two different questions, and the
difference is not a mistake in either of them:

  * Blogger counts every page its servers hand over. A crawler, an AI reader, a checking
    script and the owner's own browser all receive a page, so all of them are counted.
    Nothing those visitors run JavaScript, so no ad on the page is ever seen by them.
  * Google Analytics counts a page only when a real browser ran the analytics script,
    which needs a person with a screen in front of them.

Both numbers are recorded here, plus the automation's own self-requests, so that a
difference between them is explained on the page where it appears instead of being
argued about later.

This script reads the blog through the authenticated Blogger API only. It never requests
a public Daily Yield address, so it cannot add a view to the very counter it reports.
The growth ladder keeps using the human figure: this file records the second instrument,
it does not replace the first one.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JSON_REPORT = ROOT / "BLOGGER_VIEWS_LEDGER.json"
MD_REPORT = ROOT / "BLOGGER_VIEWS_LEDGER.md"
LADDER = ROOT / "GROWTH_LADDER.json"
BASELINE = ROOT / "AUDIENCE_GROWTH_BASELINE.json"

# The ranges Blogger's own page-view endpoint answers, and the window each one covers.
RANGES = (("all", "ALL_TIME", None), ("30DAYS", "THIRTY_DAYS", 30), ("7DAYS", "SEVEN_DAYS", 7))
HUMAN_BASIS = "GA4_PAGEVIEWS_7_DAY_AVERAGE"


def blogger_pageviews(read=None) -> dict:
    """Ask Blogger for its own page-view counts. `read` is injected by the tests.

    Returns {"status": "MEASURED", ...} or {"status": "NOT_MEASURED", "reason": ...}.
    A missing credential is reported as an honest gap; no number is invented and no
    earlier reading is repeated as if it were new.
    """
    if read is None:
        try:
            import news_pipeline

            token = news_pipeline.blogger_token()
            read = lambda path: news_pipeline.blogger_call(path, token)  # noqa: E731
        except (KeyError, RuntimeError, OSError) as exc:
            return {"status": "NOT_MEASURED", "reason": f"Blogger credentials unavailable: {type(exc).__name__}"}
    try:
        reply = read("/pageviews?range=all&range=30DAYS&range=7DAYS")
    except Exception as exc:  # noqa: BLE001
        return {"status": "NOT_MEASURED", "reason": f"pageViews read failed: {type(exc).__name__}: {str(exc)[:200]}"}
    counts = {}
    for row in (reply or {}).get("counts", []) or []:
        key = str(row.get("timeRange", "")).lower()
        try:
            counts[key] = int(row.get("count", 0))
        except (TypeError, ValueError):
            continue
    out = {"status": "MEASURED" if counts else "NOT_MEASURED",
           "allTime": counts.get("all_time"),
           "last30Days": counts.get("thirty_days"),
           "last7Days": counts.get("seven_days"),
           "source": "Blogger API v3 pageViews.get - the same figure Blogger's Stats page shows"}
    if not counts:
        out["reason"] = "Blogger answered without any count rows"
    if out["last7Days"] is not None:
        out["perDayFrom7DayWindow"] = round(out["last7Days"] / 7, 1)
    return out


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def human_reading(ladder: dict) -> dict:
    """The reader count, taken from the growth ladder's measured block, unchanged."""
    measured = ladder.get("measured") or {}
    return {
        "viewsPerDay": measured.get("viewsPerDay"),
        "basis": measured.get("viewsBasis"),
        "status": measured.get("ga4Status", "NOT_MEASURED"),
        "dailyReaders": measured.get("dailyReaders"),
        "asOf": measured.get("asOf"),
        "source": "Google Analytics 4 report, carried into GROWTH_LADDER.json",
        "whatItCounts": "a browser that ran the analytics script, which needs a person looking at a screen",
    }


def self_requests(baseline: dict) -> dict:
    """What our own automation adds to the counter - measured, not assumed."""
    return {
        "syntheticViews": baseline.get("syntheticViews"),
        "source": "AUDIENCE_GROWTH_BASELINE.json",
        "note": "the nightly measurement jobs read the blog through the authenticated Blogger API only, "
                "so they do not hand Blogger a page request to count",
    }


def verdict(blogger: dict, human: dict) -> dict:
    """One plain sentence per question the owner is actually asking."""
    daily = blogger.get("perDayFrom7DayWindow")
    readers = human.get("viewsPerDay")
    ratio = round(daily / readers, 1) if daily and readers else None
    lines = []
    if ratio is None:
        lines.append("Both counters cannot be compared yet because one of them has no measurement.")
    elif ratio > 12:
        lines.append(
            f"Blogger answers {daily:.0f} pages a day while Google Analytics sees {readers:.1f} readers a day "
            f"({ratio:.0f} times apart). A small blog normally sits at 5 to 10 times, so the excess is "
            "machines reading the site - search engines, AI readers and checkers - not people.")
    else:
        lines.append(
            f"Blogger answers {daily:.0f} pages a day and Google Analytics sees {readers:.1f} readers a day; "
            f"a ratio of {ratio:.1f} is within the ordinary range for a blog this size.")
    return {
        "bloggerToHumanRatio": ratio,
        "expectedNormalRatioOnSmallBlogs": "5 to 10 times, because every blog gets crawled",
        "plainEnglish": " ".join(lines),
        "whichOneIsReal": "Both count honestly; only the Google number can be read as an audience, "
                          "because a page a machine fetched was never seen by anyone and carried no ad",
        "revenueEffect": "none - an advert is only counted when a browser draws it, and a script that "
                         "fetches the text runs no JavaScript, so the extra pages can neither earn money "
                         "nor create invalid ad traffic",
        "usedForGrowthProjection": False,
        "guard": "GROWTH_LADDER.json keeps its human viewsPerDay; this file records the second "
                 "instrument and never replaces the first",
    }


def build(read=None, today=None) -> dict:
    blogger = blogger_pageviews(read=read)
    ladder = _read_json(LADDER)
    baseline = _read_json(BASELINE)
    human = human_reading(ladder)
    return {
        "generatedAt": (today or datetime.now(timezone.utc)).isoformat(),
        "policy": "two instruments recorded together, neither one silenced",
        "bloggerCounter": {**blogger,
                           "whatItCounts": "every page Blogger hands over: people, crawlers, AI readers, "
                                           "scripts and the owner's own browser"},
        "humanCount": human,
        "automationSelfRequests": self_requests(baseline),
        "verdict": verdict(blogger, human),
    }


def markdown(report: dict) -> str:
    b, h, v = report["bloggerCounter"], report["humanCount"], report["verdict"]
    n = lambda x: "not measured" if x is None else f"{x:,}" if isinstance(x, int) else x
    return "\n".join([
        "# Daily Yield - the two view counters, side by side",
        "",
        f"_Generated {report['generatedAt'][:19]} UTC. Read by machine and by you, so the same page answers both._",
        "",
        "| | Blogger's own Stats | Google Analytics |",
        "|---|---|---|",
        f"| Last 7 days | {n(b.get('last7Days'))} | {n(round((h.get('viewsPerDay') or 0) * 7)) if h.get('viewsPerDay') else 'not measured'} |",
        f"| Last 30 days | {n(b.get('last30Days'))} | - |",
        f"| All time | {n(b.get('allTime'))} | - |",
        f"| Per day | {n(b.get('perDayFrom7DayWindow'))} | {n(h.get('viewsPerDay'))} |",
        f"| What is counted | {b.get('whatItCounts')} | {h.get('whatItCounts')} |",
        "",
        f"**The reading:** {v['plainEnglish']}",
        "",
        f"**Which one is real:** {v['whichOneIsReal']}.",
        "",
        f"**Money:** {v['revenueEffect']}.",
        "",
        f"**Our own tooling added:** {n(report['automationSelfRequests']['syntheticViews'])} synthetic views "
        "(measured, from the nightly baseline file).",
        "",
        f"**Growth maths:** {v['guard']}.",
        "",
    ])


def main() -> int:
    report = build()
    JSON_REPORT.write_text(json.dumps(report, indent=2) + "\n")
    MD_REPORT.write_text(markdown(report))
    print(json.dumps({"bloggerStatus": report["bloggerCounter"]["status"],
                      "humanStatus": report["humanCount"]["status"],
                      "ratio": report["verdict"]["bloggerToHumanRatio"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
