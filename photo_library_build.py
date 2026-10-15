#!/usr/bin/env python3
"""Build or top up the prepared photo pools.

Run by the nightly Photo Library Refresh workflow, and safe to run by hand. It
never blocks a publication: it only widens the pools that the News desks and the
Master writers draw from.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import photo_library as pl

ROOT = Path(__file__).parent
NEWS_DESKS = ("asia-pacific", "china", "india", "russia", "markets", "europe",
              "economy", "americas", "companies", "global", "banking")


def master_topics(limit: int = 12) -> list[dict]:
    """Today's and tomorrow's planned evergreen and trending articles."""
    rows: list[dict] = []
    try:
        plan = json.loads((ROOT / "MASTER_DAILY_PLAN.json").read_text(encoding="utf-8"))
        for kind in ("trending", "evergreen"):
            for item in plan.get(kind, [])[:5]:
                rows.append({"key": str(item.get("id") or item.get("title", ""))[:60],
                             "title": item.get("title", ""), "briefs": item.get("photo_briefs") or None})
    except (OSError, json.JSONDecodeError):
        pass
    try:
        pool = json.loads((ROOT / "MASTER_TREND_POOL.json").read_text(encoding="utf-8"))
        for item in (pool.get("trending") or pool.get("items") or [])[:limit]:
            if isinstance(item, dict) and item.get("title"):
                rows.append({"key": str(item.get("id") or item["title"])[:60],
                             "title": item["title"], "briefs": None})
    except (OSError, json.JSONDecodeError):
        pass
    seen, unique = set(), []
    for row in rows:
        if not row["title"] or row["key"] in seen:
            continue
        seen.add(row["key"])
        unique.append(row)
    return unique[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=95.0,
                        help="stop widening pools after this many minutes and save what was collected")
    parser.add_argument("--scope", choices=("news", "master", "both"), default="both")
    parser.add_argument("--desk", default="", help="build a single News desk")
    parser.add_argument("--topic-key", default="")
    parser.add_argument("--title", default="")
    args = parser.parse_args()

    deadline = time.monotonic() + max(5.0, args.minutes) * 60

    if args.topic_key and args.title:
        pool = pl.ensure_master_pool(args.topic_key, args.title)
        print(json.dumps({"master": args.topic_key, "entries": len(pool["entries"])}))
        return 0

    desks = (args.desk,) if args.desk else NEWS_DESKS
    stopped_early = False
    if args.scope in ("news", "both"):
        for desk in desks:
            if time.monotonic() > deadline:
                stopped_early = True
                print(json.dumps({"stopped_early": True, "reason": "time budget reached",
                                  "pending_desks": list(desks[desks.index(desk):])}))
                break
            pool = pl.build_news_pool(desk)
            print(json.dumps({"desk": desk, "entries": len(pool["entries"]),
                              "target": pl.NEWS_TARGET}))
            sys.stdout.flush()
    if args.scope in ("master", "both"):
        for row in master_topics():
            if time.monotonic() > deadline:
                stopped_early = True
                print(json.dumps({"stopped_early": True, "reason": "time budget reached",
                                  "pending_master": row["title"][:60]}))
                break
            pool = pl.ensure_master_pool(row["key"], row["title"], row["briefs"])
            print(json.dumps({"master": row["key"][:40], "title": row["title"][:60],
                              "entries": len(pool["entries"])}, ensure_ascii=False))
            sys.stdout.flush()

    if stopped_early:
        print(json.dumps({"note": "the remaining pools are topped up on the next refresh, "
                                  "and any publication still builds what it needs at the time it is written"}))
    document = pl.status()
    pl.STATUS.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: document[k] for k in ("master_pools", "news_pools", "master_photos", "news_photos")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
