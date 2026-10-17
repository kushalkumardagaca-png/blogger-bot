#!/usr/bin/env python3
"""One page that answers "did all 21 articles and all 42 posts happen today?".

Run after the last slot (22:45 IST). It reads the two guarantee status files and
writes a single table: each slot, its state, its minutes late, and the two social
posts. Anything not delivered is named, so tomorrow starts from a fact.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "SLOT_DAY_REPORT.md"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")


def load(name: str) -> dict:
    try:
        return json.loads((ROOT / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    slots = load("SLOT_GUARANTEE_STATUS.json")
    social = load("SOCIAL_GUARANTEE_STATUS.json")
    posts = {row["key"]: row for row in social.get("rows", [])}
    rows = slots.get("rows", [])
    lines = [f"# Daily Yield — delivery report for {slots.get('dateIST', 'today')}", "",
             f"Generated {dt.datetime.now(IST):%d %B %Y %H:%M} IST", "",
             "| Slot | Item | Article | Minutes | Social posts |", "|---|---|---|---|---|"]
    for row in rows:
        key = row["key"]
        when = row.get("state", "?")
        minutes = row.get("minutesLate", row.get("minutesFromSlot", ""))
        post = posts.get(key, {})
        count = post.get("posts", "-")
        lines.append(f"| {row['slot']} | {key} | {when} | {minutes} | {count}/2 |")
    articles = sum(1 for r in rows if r.get("live"))
    on_time = sum(1 for r in rows if r.get("state") == "on time")
    both = sum(1 for p in posts.values() if p.get("posts", 0) >= 2)
    lines += ["", f"**Articles live: {articles} of {len(rows)}** · "
                  f"**on time: {on_time}** · late: {sum(1 for r in rows if r.get('state') == 'late')} · "
                  f"overdue: {sum(1 for r in rows if r.get('state') == 'overdue')}",
              f"**Articles with both social posts: {both} of {len(posts)}**"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
