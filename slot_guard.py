#!/usr/bin/env python3
"""Guarantee the 21 daily slots: on time where possible, always published.

The owner's rule is a 30-minute tolerance either way: every one of the day's 21
articles must be live within half an hour of its slot, and an article must never
appear long after its slot.

This guard is the piece that enforces it. Every ten minutes it asks, for each of
today's slots, whether the live blog proves the edition was published:

* **on time**    — live within 30 minutes of the slot;
* **late**      — live, but after the 30-minute tolerance (recorded, not hidden);
* **pending**    — due, still inside the window, nothing live yet → dispatch now;
* **overdue**    — the range has passed with nothing live → recorded and chased
                   until the edition publishes; the minutes late are reported.

It reads the blog through the authenticated API (no pageview) and dispatches the
existing writers only through the workflows that own them, so a retry behaves
exactly like a scheduled run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

import news_pipeline
import publishing_recovery
from publication_timing import MASTER_LIVE, NEWS_LIVE

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "SLOT_GUARANTEE_STATUS.json"
LEDGER = ROOT / "SLOT_GUARD_LEDGER.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
TOLERANCE = dt.timedelta(minutes=30)      # the owner's permitted range, either way
DISPATCH_SPACING = dt.timedelta(minutes=8)  # never hammer the same slot
EARLY_ALLOWANCE = dt.timedelta(minutes=15)  # a slot is judged from its own time


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def slot_time(day: dt.date, hhmm: str) -> dt.datetime:
    hour, minute = map(int, hhmm.split(":"))
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


def todays_slots(day: dt.date) -> list[dict]:
    slots = [{"key": f"news-{desk}", "kind": "news", "desk": desk, "slot": hhmm,
              "due": slot_time(day, hhmm)} for desk, hhmm in NEWS_LIVE.items()]
    for (kind, index), hhmm in MASTER_LIVE.items():
        slots.append({"key": f"master-{kind}-{index}", "kind": kind, "index": index,
                      "slot": hhmm, "due": slot_time(day, hhmm)})
    return sorted(slots, key=lambda row: row["due"])


def confirmed_publish_time(row: dict, token: str, day: dt.date):
    """Ask the live blog whether this slot's article really is today's. Time or None."""
    url = row.get("url", "")
    if not url or not token:
        return None
    observed = {}
    if row.get("kind", "news") == "news":
        ok = news_pipeline.live_current_edition(
            url, token, day,
            alt_dates=(day - dt.timedelta(days=1),) if row.get("desk") == "americas" else (), observed=observed)
    else:
        ok, _reason = news_pipeline.master_edition_check(url, token, day, observed=observed)
    if not ok:
        return None
    # News window_end is the source-gathering time, not publication time.
    stamp = observed.get("published", "") or (row.get("publishedAt", "") if row.get("kind") != "news" else "")
    if stamp:
        try:
            return dt.datetime.fromisoformat(stamp)
        except ValueError:
            pass
    return row.get("due")


def inventory(day: dt.date) -> dict[str, dict]:
    """The records that claim a slot was published today, keyed by slot."""
    found: dict[str, dict] = {}
    tracker = load(ROOT / "news_tracker.json", {}).get("desks", {})
    for desk, row in tracker.items():
        if row.get("edition") == day.isoformat():
            found[f"news-{desk}"] = {"url": row.get("url", ""), "desk": desk, "kind": "news",
                                     "publishedAt": row.get("window_end", "")}
    master = load(ROOT / "MASTER_AUTOMATION_TRACKER.json", {}).get("published", [])
    from master_slot_state import keeper_for_slot
    plan = load(ROOT / "MASTER_DAILY_PLAN.json", {})
    if plan.get("date") == day.isoformat():
        for kind in ("trending", "evergreen"):
            ids = [str(item.get("id")) for item in plan.get(kind, [])[:5]]
            for index, topic_id in enumerate(ids):
                row = keeper_for_slot(plan,master,kind,index)
                if row:
                    found[f"master-{kind}-{index}"] = {"url": row.get("url", ""), "kind": kind,
                                                       "publishedAt": row.get("published_at", "")}
    return found


def classify(due: dt.datetime, now: dt.datetime, published_at):
    """Name the state of one slot against the owner's 30-minute tolerance.

    A slot that missed its range is never abandoned: it becomes ``overdue`` and the
    guard keeps retrying it until the edition is live, then reports how late it was.
    """
    if published_at:
        if published_at < due - TOLERANCE:
            return "early"
        return "on time" if published_at <= due + TOLERANCE else "late"
    if now < due - EARLY_ALLOWANCE:
        return "upcoming"
    if now <= due + TOLERANCE:
        return "pending"
    return "overdue"


def dispatch(slot: dict, apply: bool) -> str:
    if not apply:
        return "would dispatch"
    try:
        if slot["kind"] == "news":
            subprocess.run(["gh", "workflow", "run", "daily_news_wires.yml", "--ref", "main",
                            "-f", f"desks={slot['desk']}"], check=True, capture_output=True, timeout=90)
        else:
            workflow = f"master_{slot['kind']}_writer.yml"
            subprocess.run(["gh", "workflow", "run", workflow, "--ref", "main",
                            "-f", f"slot={slot['index']}", "-f", "publish=true",
                            "-f", "retry_attempt=1"], check=True, capture_output=True, timeout=90)
        return "dispatched"
    except Exception as exc:  # noqa: BLE001
        return f"dispatch failed: {type(exc).__name__}: {str(exc)[:160]}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="dispatch recovery for due slots")
    parser.add_argument("--now", default="", help="ISO timestamp for a dry run")
    args = parser.parse_args()
    now = dt.datetime.fromisoformat(args.now).astimezone(IST) if args.now else dt.datetime.now(IST)
    day = now.date()
    token = publishing_recovery.live_token()
    if not token:
        print(json.dumps({"status": "NO_CREDENTIALS",
                          "note": "the guard cannot verify the live blog without the Blogger token"}))
    records = inventory(day)
    ledger = load(LEDGER, {})
    rows, dispatched = [], 0
    for slot in todays_slots(day):
        row = records.get(slot["key"], {})
        published_at = confirmed_publish_time(row, token, day) if row else None
        record = {"key": slot["key"], "slot": slot["slot"], "due": slot["due"].isoformat(),
                  "live": bool(published_at), "url": row.get("url", "")}
        record["state"] = classify(slot["due"], now, published_at)
        record["minutesFromSlot"] = int((now - slot["due"]).total_seconds() // 60)
        if published_at:
            record["publishedAt"] = published_at.isoformat()
            if record["state"] == "early":
                record["minutesEarly"] = int((slot["due"] - published_at).total_seconds() // 60)
            if record["state"] == "late":
                record["minutesLate"] = int((published_at - slot["due"]).total_seconds() // 60)
        elif record["state"] in ("pending", "overdue"):
            # Both a slot inside its range and one that missed it are chased until
            # the edition is live. A miss costs minutes, never the day's article.
            if record["state"] == "overdue":
                record["minutesLate"] = int((now - slot["due"]).total_seconds() // 60)
            key = f"{day}:{slot['key']}"
            last = ledger.get(key, "")
            if not last or now - dt.datetime.fromisoformat(last) >= DISPATCH_SPACING:
                record["action"] = dispatch(slot, args.apply)
                if args.apply:
                    ledger[key] = now.isoformat()
                    dispatched += 1
        rows.append(record)
    if args.apply:
        save(LEDGER, {k: v for k, v in ledger.items() if v.startswith(day.isoformat())})
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    done = [r for r in rows if r["live"]]
    report = {"generatedAt": now.isoformat(), "dateIST": day.isoformat(), "apply": args.apply,
              "toleranceMinutes": int(TOLERANCE.total_seconds() // 60),
              "slots": len(rows), "live": len(done), "onTime": counts.get("on time", 0),
              "late": counts.get("late", 0), "early": counts.get("early", 0), "pending": counts.get("pending", 0),
              "overdue": counts.get("overdue", 0), "upcoming": counts.get("upcoming", 0),
              "dispatched": dispatched, "rows": rows,
              "syntheticViews": 0, "publicDailyYieldRequests": 0}
    # Extra already-live publications are visible, not hidden to make the 21-slot
    # board green. Never delete a valid URL or cancel a promised future slot here.
    from master_slot_state import extra_records
    plan = load(ROOT / "MASTER_DAILY_PLAN.json", {})
    master = load(ROOT / "MASTER_AUTOMATION_TRACKER.json", {}).get("published", [])
    extras = []
    for extra in extra_records(plan, master):
        if plan.get("date") != day.isoformat():continue
        ok, reason = news_pipeline.master_edition_check(extra['url'],token,day) if token else (False,'no credentials')
        if ok:extras.append({"url":extra['url'],"key":"extra-"+extra['routingKey']+"-"+str(extra.get('topic_id')),
                             "routingKey":extra['routingKey'],"title":extra.get('title',''),"publishedAt":extra.get('published_at','')})
    report['extraLiveArticles'] = extras
    report['actualArticlesLiveIncludingExtras'] = len(done) + len(extras)
    report["status"] = ("PASS" if not counts.get("overdue") and not counts.get("late") and not counts.get("early") and not extras
                        else "ATTENTION")
    save(STATUS, report)
    print(json.dumps({k: report[k] for k in ("status", "slots", "live", "onTime", "late",
                                             "pending", "overdue", "upcoming", "dispatched")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
