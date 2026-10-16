#!/usr/bin/env python3
"""Choose the desk a scheduled News run should publish.

GitHub's scheduler sometimes starts a run long after its cron minute. On
16 October the China edition began after its own 05:15 slot and reached the blog
at 06:17, and a run that starts late for a desk which is already live (or whose
window has closed) has nothing useful to do.

The rule this script applies:

* the scheduled desk keeps the run whenever its window is still open and its
  edition is not already live;
* otherwise the run takes the earliest desk that can still publish *on time* —
  within the wait a single job is allowed — so a delayed run produces a correct
  edition instead of a late one;
* if nothing qualifies, the scheduled desk is returned unchanged so the failure
  is visible in the run log rather than hidden.

A slot is expired after ``SLOT_GRACE`` minutes (the same window the News engine
uses) and is never produced late.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
LIVE = {"asia-pacific": "04:15", "china": "05:15", "india": "07:15", "russia": "10:15",
        "markets": "12:15", "europe": "12:45", "economy": "13:15", "americas": "17:15",
        "companies": "17:45", "global": "18:15", "banking": "18:45"}
SLOT_GRACE = dt.timedelta(minutes=95)    # after this a slot is expired, never late
MAX_WAIT = dt.timedelta(minutes=165)     # the longest embargo wait one job may take
TRACKER = Path("news_tracker.json")


def slot_datetime(desk: str, now: dt.datetime) -> dt.datetime:
    hour, minute = map(int, LIVE[desk].split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def load_published(now: dt.datetime, tracker_path: Path = TRACKER) -> set[str]:
    try:
        desks = json.loads(Path(tracker_path).read_text(encoding="utf-8")).get("desks", {})
    except (OSError, json.JSONDecodeError):
        return set()
    return {desk for desk, row in desks.items() if row.get("edition") == now.date().isoformat()}


def choose(scheduled: str, now: dt.datetime, published: set[str]) -> tuple[str, str]:
    """Return (desk, reason) for this run."""
    def usable(desk: str) -> bool:
        return desk not in published and now <= slot_datetime(desk, now) + SLOT_GRACE

    if scheduled in LIVE and usable(scheduled):
        return scheduled, "scheduled desk still inside its window"
    if scheduled in LIVE and scheduled in published:
        reason = "scheduled desk already live"
    elif scheduled in LIVE:
        reason = "scheduled desk past its window; a late edition is not produced"
    else:
        reason = "no scheduled desk for this run"
    ahead = sorted((slot_datetime(desk, now), desk) for desk in LIVE
                   if usable(desk) and slot_datetime(desk, now) > now
                   and slot_datetime(desk, now) - now <= MAX_WAIT)
    if ahead:
        return ahead[0][1], f"{reason}; taking the next desk that can still publish on time"
    return scheduled, f"{reason}; no desk can still publish on time"


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the News desk for a scheduled run")
    parser.add_argument("scheduled", nargs="?", default="")
    parser.add_argument("--tracker", default=str(TRACKER))
    parser.add_argument("--now", default="", help="ISO timestamp for a dry run")
    args = parser.parse_args()
    now = dt.datetime.fromisoformat(args.now).astimezone(IST) if args.now else dt.datetime.now(IST)
    desk, reason = choose(args.scheduled, now, load_published(now, Path(args.tracker)))
    print(desk)
    print(f"# {reason}", file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
