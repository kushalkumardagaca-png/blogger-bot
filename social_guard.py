#!/usr/bin/env python3
"""Guarantee the two social posts every article is owed.

The owner's rule is 42 social posts a day: two per article, on two different
networks, published next to the article. This guard checks the platforms' own
trackers — not our intentions — and closes any gap it finds.

For every article confirmed live today it counts the tracker rows that carry
that Blogger id or URL. If fewer than two exist, the missing route is dispatched
through the same coordinated workflow the publisher uses, so a retry is
indistinguishable from a normal post. Anything that could not be posted inside
the tolerance is recorded as missed rather than quietly dropped.

Reads trackers only: no platform API call is made to check, and no Daily Yield
page is fetched, so no pageview is added.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from social_rotation import platform_pair_for
from merge_social_tracker import identity
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "SOCIAL_GUARANTEE_STATUS.json"
LEDGER = ROOT / "SOCIAL_GUARD_LEDGER.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
TRACKERS = {"facebook": "facebook_tracker.json", "bluesky": "bluesky_tracker.json",
            "tumblr": "tumblr_tracker.json", "mastodon": "mastodon_tracker.json"}
WORKFLOW = "coordinated_social_publish.yml"
REQUIRED = 2
TOLERANCE = dt.timedelta(minutes=30)
DISPATCH_SPACING = dt.timedelta(minutes=10)


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def todays_articles(day: dt.date) -> list[dict]:
    """Every article the site says went live today, with its publication time."""
    articles: list[dict] = []
    tracker = load(ROOT / "news_tracker.json", {}).get("desks", {})
    for desk, row in tracker.items():
        if row.get("edition") == day.isoformat() and row.get("url"):
            articles.append({"key": f"news-{desk}", "title": f"{desk} edition",
                             "url": row["url"], "publishedAt": row.get("window_end", "")})
    master = load(ROOT / "MASTER_AUTOMATION_TRACKER.json", {}).get("published", [])
    plan = load(ROOT / "MASTER_DAILY_PLAN.json", {})
    from master_slot_state import record_slot, keeper_for_slot
    for row in master:
        if row.get("date") == day.isoformat() and row.get("url"):
            slot=record_slot(row,plan)
            routing=f"master-{row.get('kind')}-{slot}" if slot is not None else f"master-{row.get('kind')}-{row.get('topic_id')}"
            keeper=keeper_for_slot(plan,master,row.get('kind'),slot) if slot is not None else None
            key=routing if keeper and keeper.get('url')==row['url'] else 'extra-'+routing+'-'+str(row.get('topic_id'))
            articles.append({"key":key,"routingKey":routing,
                             "title":row.get('title',''),"url":row['url'],"publishedAt":row.get('published_at','')})
    return articles


def tracker_rows() -> dict[str, list[dict]]:
    return {name: load(ROOT / path, {}).get("published", []) for name, path in TRACKERS.items()}


def matches(row: dict, article: dict) -> bool:
    url = str(row.get("url", "")).rstrip("/")
    if url and url == str(article["url"]).rstrip("/"):
        return True
    return False


def covered_by(article: dict, trackers: dict[str, list[dict]]) -> dict[str, int]:
    """How many of today's posts each platform carries for this article."""
    counts = {}
    for platform, rows in trackers.items():
        counts[platform] = len({identity(row) for row in rows if matches(row, article)})
    return counts


def dispatch(article: dict, route_index: int, apply: bool) -> str:
    if not apply:
        return "would dispatch"
    try:
        subprocess.run(["gh", "workflow", "run", WORKFLOW, "--ref", "main",
                        "-f", f"item_key={article.get('routingKey',article['key'])}",
                        "-f", f"target_url={article['url']}",
                        "-f", "content_mode=post",
                        "-f", f"published_at={article.get('publishedAt', '')}",
                        "-f", f"route_index={route_index}"],
                       check=True, capture_output=True, timeout=90)
        return "dispatched"
    except Exception as exc:  # noqa: BLE001
        return f"dispatch failed: {type(exc).__name__}: {str(exc)[:160]}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="dispatch the missing posts")
    parser.add_argument("--now", default="")
    args = parser.parse_args()
    now = dt.datetime.fromisoformat(args.now).astimezone(IST) if args.now else dt.datetime.now(IST)
    day = now.date()
    trackers = tracker_rows()
    ledger = load(LEDGER, {})
    rows, dispatched, missing = [], 0, 0
    duplicates, extra_networks = 0, 0
    # Articles are chased whatever their lateness: a late edition is still owed its
    # two posts, because the audience is still there when the article lands.
    recorded=todays_articles(day)
    slots=load(ROOT / "SLOT_GUARANTEE_STATUS.json", {})
    confirmed_urls={r.get('url') for r in slots.get('rows',[]) if r.get('live') and r.get('url')} if slots.get('dateIST')==day.isoformat() else set()
    if slots.get('dateIST')==day.isoformat():
        confirmed_urls.update(r.get('url') for r in slots.get('extraLiveArticles',[]) if r.get('url'))
    awaiting=[a for a in recorded if a['url'] not in confirmed_urls]
    for article in [a for a in recorded if a['url'] in confirmed_urls]:
        counts = covered_by(article, trackers)
        have = sum(1 for value in counts.values() if value)
        needed = max(0, REQUIRED - have)
        duplicate_count = sum(max(0, value - 1) for value in counts.values())
        duplicates += duplicate_count
        extra_networks += max(0, have - REQUIRED)
        record = {"key": article["key"], "title": article["title"][:70],
                  "url": article["url"], "posts": have, "byPlatform": counts,
                  "observedDistinctPosts": sum(counts.values()), "duplicatePosts": duplicate_count}
        if needed:
            missing += needed
            try:
                pair = platform_pair_for(article.get('routingKey',article['key']), day)
                route_indexes = [index for index, platform in enumerate(pair) if not counts.get(platform)][:needed]
            except ValueError:
                route_indexes = []
                record['routingIssue'] = 'Cannot identify the approved daily slot; no guessed route is posted.'
            for route_index in route_indexes:
                key = f"{day}:{article['key']}:{route_index}"
                last = ledger.get(key, "")
                if last and now - dt.datetime.fromisoformat(last) < DISPATCH_SPACING:
                    record.setdefault("actions", []).append("waiting for the last attempt")
                    continue
                record.setdefault("actions", []).append(dispatch(article, route_index, args.apply))
                if args.apply:
                    ledger[key] = now.isoformat()
                    dispatched += 1
        rows.append(record)
    if args.apply:
        save(LEDGER, {k: v for k, v in ledger.items() if v.startswith(day.isoformat())})
    complete = sum(1 for row in rows if row["posts"] >= REQUIRED)
    report = {"generatedAt": now.isoformat(), "dateIST": day.isoformat(), "apply": args.apply,
              "articles": len(rows), "expectedPosts": len(rows) * REQUIRED,
              "articlesWithBothPosts": complete, "postsMissing": missing,
              "dispatched": dispatched, "rows": rows,
              "duplicatePosts": duplicates, "extraNetworks": extra_networks,
              "liveVerificationSourceAt": slots.get('generatedAt'),
              "awaitingLiveVerification": [{"key":a['key'],"url":a['url']} for a in awaiting],
              "articlesWithExactlyTwoPosts": sum(1 for row in rows if row['posts'] == REQUIRED and row['duplicatePosts'] == 0),
              "syntheticViews": 0, "publicDailyYieldRequests": 0,
              "status": "PASS" if complete == len(rows) and duplicates == 0 and extra_networks == 0 and not awaiting else "ATTENTION"}
    save(STATUS, report)
    print(json.dumps({k: report[k] for k in ("status", "articles", "expectedPosts",
                                             "articlesWithBothPosts", "postsMissing",
                                             "dispatched")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
