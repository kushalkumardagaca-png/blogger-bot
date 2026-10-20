#!/usr/bin/env python3
"""Hold the growth promise to arithmetic, once a day, using only measured inputs.

The question this answers is not "can we dream bigger" - it is "what did Google and the open
network endpoints actually report today, and what does that imply". Everything comes from
evidence files in this repository:

- INDEX_STATUS_REPORT.json      how many pages Google has indexed
- AUDIENCE_GROWTH_BASELINE.json clicks and impressions from authenticated Search Console
- AUDIENCE_CHANNELS.json        followers on the networks with public counters
- INDEXING_CAPACITY.json        how much publishing Google can currently absorb
- GROWTH_CONTROL_TOWER.json     the target the operation itself declared

The history file it appends is the point of the whole job: a target with no measured series
beside it is a wish. Two weeks from now there are enough points to compute a growth rate, and
from then the projection is a number that came out of the blog's own behaviour.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "GROWTH_LADDER.json"
MD = ROOT / "GROWTH_LADDER.md"
HISTORY = ROOT / "GROWTH_LADDER_HISTORY.json"

# The commitment made on 20 October 2026, kept here so the daily report can be judged against it
# rather than against a mood. Views per day are search clicks plus everything measurable; the
# upper pair is what Google News acceptance could plausibly add inside a quarter.
DEADLINE = date(2026, 12, 31)
SUB_TARGET_INDEXED = (150, 400)
SUB_TARGET_VIEWS = (150, 1500)
OWNER_ASK_VIEWS = 50_000
CTR_RANGE = (0.02, 0.03)  # a normal search click-through rate; the ceiling case of the ask
MIN_POINTS_FOR_RATE = 3   # a straight line through two points is not a growth rate


def load(name: str) -> dict:
    try:
        return json.loads((ROOT / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def measure() -> dict:
    index = load("INDEX_STATUS_REPORT.json")
    baseline = load("AUDIENCE_GROWTH_BASELINE.json")
    channels = load("AUDIENCE_CHANNELS.json")
    capacity = load("INDEXING_CAPACITY.json")
    tower = load("GROWTH_CONTROL_TOWER.json")
    search = ((baseline.get("searchAcquisition") or {}).get("last28Days") or {})
    indexed = index.get("indexed")
    submitted = index.get("urls")
    impressions = search.get("impressions")
    clicks = search.get("clicks")
    followers = (channels.get("totals") or {}).get("followers")
    return {
        "asOf": (index.get("checkedAt") or baseline.get("checkedAt") or "")[:10] or None,
        "indexedPages": indexed if isinstance(indexed, int) else None,
        "submittedPages": submitted if isinstance(submitted, int) else None,
        "impressions28d": impressions if isinstance(impressions, int) else None,
        "clicks28d": clicks if isinstance(clicks, int) else None,
        # a daily rate, because the target it is compared with is a daily rate
        "viewsPerDay": round(clicks / 28, 3) if isinstance(clicks, int) else None,
        "measurableFollowers": followers if isinstance(followers, int) else None,
        "gateVerdict": capacity.get("decision") or capacity.get("verdict"),
        "declaredTarget": tower.get("target") if isinstance(tower.get("target"), (int, float)) else None,
        "declaredDeadline": str(tower.get("deadline") or "")[:10] or None,
        "evidenceComplete": all(value is not None for value in (indexed, impressions, clicks)),
    }


def arithmetic(today: dict) -> dict:
    """The part of the answer that is not a judgement call."""
    out: dict = {"impressionsNeededPerDayForAsk": None, "yieldPerIndexedPagePerDay": None,
                 "indexedPagesNeededForAskAtTodayYield": None,
                 "yieldMultipleNeededAtTopOfSubTarget": None}
    low_ctr, high_ctr = CTR_RANGE
    if high_ctr:
        need = [round(OWNER_ASK_VIEWS / high_ctr), round(OWNER_ASK_VIEWS / low_ctr)]
        out["impressionsNeededPerDayForAsk"] = {"atCtre3pct": need[0], "atCtre2pct": need[1],
                                               "range": need}
    indexed = today.get("indexedPages")
    impressions = today.get("impressions28d")
    if isinstance(indexed, int) and isinstance(impressions, int) and indexed >= 1:
        per_page = impressions / (28 * indexed)
        out["yieldPerIndexedPagePerDay"] = round(per_page, 6)
        if per_page > 0 and out["impressionsNeededPerDayForAsk"]:
            out["indexedPagesNeededForAskAtTodayYield"] = round(
                out["impressionsNeededPerDayForAsk"]["range"][0] / per_page)
        if out["impressionsNeededPerDayForAsk"]:
            want = out["impressionsNeededPerDayForAsk"]["range"][0]
            out["yieldMultipleNeededAtTopOfSubTarget"] = round(
                want / (per_page * SUB_TARGET_INDEXED[1]), 0) if per_page > 0 else None
    if isinstance(today.get("declaredTarget"), (int, float)) and today.get("declaredDeadline"):
        try:
            end = date.fromisoformat(today["declaredDeadline"])
            days = max(1, (end - datetime.now(timezone.utc).date()).days)
            out["declaredPlanDailyAverage"] = round(today["declaredTarget"] / days)
            out["declaredPlanDaysRemaining"] = days
            out["askVsDeclaredPlanMultiple"] = round(OWNER_ASK_VIEWS * days / today["declaredTarget"], 2)
        except ValueError:
            pass
    return out


def ladder(today: dict, points: list[dict]) -> list[dict]:
    """Weekly rungs from the first measurement to 31 December, with a verdict where data exists."""
    start = date.fromisoformat(points[0]["date"]) if points else datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc).date()
    total_weeks = max(1, -(-(DEADLINE - start).days // 7))
    now_day = now
    base_indexed = (today.get("indexedPages") or 0)
    rungs = []
    for week in range(1, total_weeks + 1):
        share = min(1.0, week / total_weeks)
        rung_by = min(start + timedelta(days=7 * week), DEADLINE)
        target = {
            "week": week,
            "by": rung_by.isoformat(),
            "indexedPages": (round(base_indexed + (SUB_TARGET_INDEXED[0] - base_indexed) * share),
                             round(base_indexed + (SUB_TARGET_INDEXED[1] - base_indexed) * share)),
            "viewsPerDay": (round(SUB_TARGET_VIEWS[0] * share + 1 * (1 - share)),
                            round(SUB_TARGET_VIEWS[1] * share + 1 * (1 - share))),
        }
        if rung_by > now_day:
            target["measuredIndexedPages"] = None
            target["verdict"] = "FUTURE"
            rungs.append(target)
            continue
        reached = [point for point in points if point.get("date") and point["date"] <= target["by"]]
        if reached:
            last = reached[-1]
            actual = last.get("indexedPages")
            if isinstance(actual, int):
                target["measuredIndexedPages"] = actual
                target["verdict"] = ("ON TRACK" if actual >= target["indexedPages"][0] else "BEHIND")
            else:
                target["verdict"] = "UNKNOWN"
        else:
            target["measuredIndexedPages"] = None
            target["verdict"] = "FUTURE"
        rungs.append(target)
    return rungs


def projection(points: list[dict], rungs: list[dict]) -> dict:
    """When does 50,000/day arrive at the measured rate? Honest answer first: often unknowable."""
    usable = [p for p in points if isinstance(p.get("viewsPerDay"), (int, float))]
    result = {"method": "linear on the blog's own measured daily gain", "points": len(usable),
              "impressionsPerDayGain": None, "date50k": None, "status": "UNKNOWN"}
    if len(usable) >= MIN_POINTS_FOR_RATE:
        first, last = usable[0], usable[-1]
        span = (date.fromisoformat(last["date"]) - date.fromisoformat(first["date"])).days
        if span >= 1:
            gain = (last["viewsPerDay"] - first["viewsPerDay"]) / span
            result["impressionsPerDayGain"] = round(gain, 3)
            if gain > 0:
                days = max(0, math.ceil((OWNER_ASK_VIEWS - last["viewsPerDay"]) / gain))
                result["date50k"] = (date.fromisoformat(last["date"]) + timedelta(days=days)).isoformat()
                result["status"] = "PROJECTED"
            else:
                result["status"] = "FLAT_OR_FALLING"
        else:
            result["status"] = "NEEDS_MORE_DAYS"
    else:
        result["needsMoreDays"] = MIN_POINTS_FOR_RATE - len(usable)
        result["status"] = "NOT_ENOUGH_MEASUREMENT"
    if rungs:
        result["subTargetOnTrack"] = rungs[-1]["verdict"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="", help="JSON of today's measurement, for tests")
    arguments = parser.parse_args()

    today = json.loads(Path(arguments.fixture).read_text(encoding="utf-8")) if arguments.fixture else measure()
    history = load(HISTORY.name) if HISTORY.exists() else {"points": []}
    points = list(history.get("points") or [])
    stamp = {"date": (today.get("asOf") or datetime.now(timezone.utc).date().isoformat()), **today}
    if not points or points[-1].get("date") != stamp["date"]:
        points.append(stamp)
    points = points[-180:]
    HISTORY.write_text(json.dumps({"updated": stamp["date"], "points": points}, indent=1) + "\n")

    rungs = ladder(today, points)
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "measured": today,
        "commitment": {"deadline": DEADLINE.isoformat(), "indexedPages": list(SUB_TARGET_INDEXED),
                       "viewsPerDay": list(SUB_TARGET_VIEWS), "weeksRemaining": len(rungs)},
        "ownerAsk": {"viewsPerDay": OWNER_ASK_VIEWS, "deadline": DEADLINE.isoformat(),
                     "arithmetic": arithmetic(today),
                     "reachable": False if today.get("evidenceComplete") else None},
        "ladder": rungs,
        "projection": projection(points, rungs),
        "policy": "no number in this file is invented: a missing measurement reads as None and "
                  "the verdict reads UNKNOWN",
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

    last_done = next((r for r in reversed(rungs) if r["verdict"] in ("ON TRACK", "BEHIND")), None)
    lines = [f"# Growth ladder · {report['generatedAt']}", "",
             "Measured today: "
             f"**{today.get('indexedPages') if today.get('indexedPages') is not None else 'not measured'}** indexed pages of "
             f"**{today.get('submittedPages') or 'not measured'}** submitted, "
             f"**{today.get('impressions28d') if today.get('impressions28d') is not None else 'not measured'}** impressions and "
             f"**{today.get('clicks28d') if today.get('clicks28d') is not None else 'not measured'}** clicks in 28 days, "
             f"**{today.get('measurableFollowers') if today.get('measurableFollowers') is not None else 'not measured'}** "
             f"countable social followers. Indexing gate: **{today.get('gateVerdict') or 'UNKNOWN'}**.", "",
             f"Committed by {DEADLINE:%d %b %Y}: indexed pages {SUB_TARGET_INDEXED[0]}-{SUB_TARGET_INDEXED[1]}, "
             f"{SUB_TARGET_VIEWS[0]}-{SUB_TARGET_VIEWS[1]} views a day.", ""]
    if last_done:
        lines.append(f"**Ladder verdict at the last completed rung (by {last_done['by']}): "
                     f"{last_done['verdict']}** - measured {last_done.get('measuredIndexedPages')} indexed pages "
                     f"against a rung of {last_done['indexedPages'][0]}-{last_done['indexedPages'][1]}.")
        lines.append("")
    lines += ["| week | by | indexed pages (target) | views/day (target) | measured | verdict |",
              "| --- | --- | --- | --- | --- | --- |"]
    for rung in rungs:
        measured = rung.get("measuredIndexedPages")
        lines.append(f"| {rung['week']} | {rung['by']} | {rung['indexedPages'][0]}-{rung['indexedPages'][1]} | "
                     f"{rung['viewsPerDay'][0]}-{rung['viewsPerDay'][1]} | "
                     f"{measured if measured is not None else '-'} | {rung['verdict']} |")
    numbers = report["ownerAsk"]["arithmetic"]
    lines += ["", f"## The {OWNER_ASK_VIEWS:,}-a-day question", "",
              "At a normal 2-3% click rate, 50,000 visits a day out of search needs "
              f"**{numbers['impressionsNeededPerDayForAsk']['range'][0]:,}-"
              f"{numbers['impressionsNeededPerDayForAsk']['range'][1]:,} impressions a day**." if
              numbers.get("impressionsNeededPerDayForAsk") else
              "At a normal 2-3% click rate, 50,000 visits a day needs about two million impressions a day.",
              ""]
    if numbers.get("yieldPerIndexedPagePerDay") is not None:
        lines.append(f"- one indexed page currently earns **{numbers['yieldPerIndexedPagePerDay']}** impressions a day")
    if numbers.get("indexedPagesNeededForAskAtTodayYield"):
        lines.append(f"- at that rate the ask would need about **{numbers['indexedPagesNeededForAskAtTodayYield']:,} "
                     "indexed pages**")
    if numbers.get("yieldMultipleNeededAtTopOfSubTarget"):
        lines.append(f"- with the indexed count at the top of the committed range, each page would have to earn "
                     f"**{int(numbers['yieldMultipleNeededAtTopOfSubTarget']):,}×** today's yield")
    if numbers.get("declaredPlanDailyAverage"):
        lines.append(f"- the operation's own declared target ({today.get('declaredTarget'):,} by "
                     f"{today.get('declaredDeadline')}) averages **{numbers['declaredPlanDailyAverage']:,} a day** "
                     f"over {numbers['declaredPlanDaysRemaining']} days - the ask is "
                     f"**{numbers['askVsDeclaredPlanMultiple']}× that whole plan per day**")
    proj = report["projection"]
    lines += ["", f"## Projection to {OWNER_ASK_VIEWS:,} a day", "",
              f"- status: **{proj['status']}** ({proj['method']}, {proj['points']} measured points"
              + (f", needs {proj.get('needsMoreDays', 0)} more)" if proj["points"] < MIN_POINTS_FOR_RATE else ")"),
              ]
    if proj.get("date50k"):
        lines.append(f"- at the measured daily gain: **{proj['date50k']}**")
    lines += ["", "Nothing in this report is a forecast of effort. It is a record of what was measured, "
                  "so that the ladder can be checked rather than argued about."]
    MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({"indexed": today.get("indexedPages"), "viewsPerDay": today.get("viewsPerDay"),
                      "verdict": last_done["verdict"] if last_done else "NO RUNG COMPLETED",
                      "projection": proj["status"], "weeksRemaining": len(rungs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
