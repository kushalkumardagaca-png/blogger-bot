#!/usr/bin/env python3
"""Deterministic Daily Yield social routing for live News and resources.

Every day: 11 comprehensive News editions plus the homepage and four rotating
header Pages. Each destination is assigned to exactly one active network using
the established
Daily Yield platform pattern. Publishers use the authenticated Blogger API and
never create synthetic public-page views.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
PLATFORMS = ("facebook", "bluesky", "tumblr", "mastodon")
RESOURCE_PATTERN = ("facebook", "bluesky", "facebook", "tumblr", "mastodon")
NEWS_PATTERN = (
    "facebook", "bluesky", "tumblr", "mastodon", "facebook",
    "bluesky", "facebook", "tumblr", "bluesky", "mastodon",
    "facebook", "bluesky", "tumblr", "mastodon", "facebook",
    "bluesky", "facebook", "tumblr", "bluesky", "mastodon",
)
NEWS_KEYS = (
    "americas", "global", "markets", "economy", "banking", "companies",
    "china", "asia-pacific", "india", "russia", "europe",
)
DAILY_ARTICLE_KEYS=(
 "news-asia-pacific","news-china","news-india","news-russia","news-markets",
 "news-europe","news-economy","news-americas","news-companies","news-global","news-banking",
 "master-trending-0","master-evergreen-0","master-trending-1","master-evergreen-1",
 "master-trending-2","master-evergreen-2","master-trending-3","master-evergreen-3",
 "master-trending-4","master-evergreen-4",
)
# Exactly 42 daily assignments: Facebook 13, Bluesky 11, Mastodon 10, Tumblr 8.
DAILY_PLATFORM_PAIRS=(
 ('bluesky','mastodon'),('bluesky','mastodon'),('facebook','tumblr'),('mastodon','tumblr'),('bluesky','facebook'),
 ('bluesky','mastodon'),('mastodon','facebook'),('facebook','bluesky'),('bluesky','facebook'),('facebook','mastodon'),('facebook','tumblr'),
 ('mastodon','facebook'),('facebook','tumblr'),('bluesky','facebook'),('facebook','tumblr'),
 ('bluesky','mastodon'),('facebook','tumblr'),('bluesky','mastodon'),('facebook','tumblr'),
 ('bluesky','tumblr'),('bluesky','mastodon'),
)

def platform_pair_for(item_key:str)->tuple[str,str]:
 if item_key not in DAILY_ARTICLE_KEYS:raise ValueError(f'unknown daily article key: {item_key}')
 pair=DAILY_PLATFORM_PAIRS[DAILY_ARTICLE_KEYS.index(item_key)]
 if pair[0]==pair[1]:raise RuntimeError('social pair must use two different platforms')
 return pair
HEADER_PAGES = (
    "https://dailyyield.blogspot.com/p/article.html",
    "https://dailyyield.blogspot.com/p/daily-news.html",
    "https://dailyyield.blogspot.com/p/calculator_0908148622.html",
    "https://dailyyield.blogspot.com/p/markets-today.html",
    "https://dailyyield.blogspot.com/p/global-snapshot.html",
    "https://dailyyield.blogspot.com/p/money-atlas_01486068069.html",
    "https://dailyyield.blogspot.com/p/for-corporate_01804417406.html",
)
RESOURCE_SCHEDULES = {
    "45 23 * * *": 0,  # 05:15 IST
    "30 1 * * *": 1,   # 07:00 IST
    "30 4 * * *": 2,   # 10:00 IST
    "30 8 * * *": 3,   # 14:00 IST
    "30 14 * * *": 4,  # 20:00 IST
}


def parse_time(value: str) -> dt.datetime | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed


def platform_for(item_key: str, day: dt.date) -> str:
    if item_key in DAILY_ARTICLE_KEYS:return platform_pair_for(item_key)[0]
    offset = day.toordinal()
    if item_key.startswith("news-"):
        desk = item_key.split("-", 1)[1]
        idx = NEWS_KEYS.index(desk)
        pattern = NEWS_PATTERN
    elif item_key.startswith("resource-"):
        idx = int(item_key.split("-", 1)[1])
        pattern = RESOURCE_PATTERN
    elif item_key.startswith("master-"):
        parts=item_key.split('-')
        if len(parts)!=3 or parts[1] not in ('trending','evergreen'):raise ValueError(f"unknown social item key: {item_key}")
        idx=(0 if parts[1]=='trending' else 5)+int(parts[2])
        if not 0<=idx<10:raise ValueError(f"unknown social item key: {item_key}")
        pattern=NEWS_PATTERN
    else:
        raise ValueError(f"unknown social item key: {item_key}")
    return pattern[(idx + offset) % len(pattern)]


def resource_url(slot: int, day: dt.date) -> str:
    if slot == 0:
        return "https://dailyyield.blogspot.com/"
    # Four consecutive header Pages rotate daily; all seven are covered fairly.
    start = day.toordinal() % len(HEADER_PAGES)
    return HEADER_PAGES[(start + slot - 1) % len(HEADER_PAGES)]


def make_plan(item_key: str, target_url: str, mode: str, published_at: str,
              schedule: str, now: dt.datetime | None = None, route_index: int = 0) -> dict:
    reference_now = now or dt.datetime.now(dt.timezone.utc)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=dt.timezone.utc)
    current = reference_now.astimezone(IST)
    published = parse_time(published_at)
    if schedule:
        if schedule not in RESOURCE_SCHEDULES:
            raise ValueError(f"unknown coordinated resource schedule: {schedule}")
        slot = RESOURCE_SCHEDULES[schedule]
        item_key = f"resource-{slot}"
        target_url = resource_url(slot, current.date())
        mode = "page"
    if not item_key or not target_url:
        raise ValueError("item key and target URL are required")
    if not target_url.startswith("https://dailyyield.blogspot.com/"):
        raise ValueError("target URL is outside the official Daily Yield domain")
    day = (published.astimezone(IST).date() if published else current.date())
    if route_index not in (0,1):raise ValueError('route index must be 0 or 1')
    delay = 0
    if published:
        due = published.astimezone(dt.timezone.utc) + dt.timedelta(minutes=5)
        delay = max(0, min(20 * 60, int((due - reference_now.astimezone(dt.timezone.utc)).total_seconds())))
    return {
        "item_key": item_key,
        "target_url": target_url,
        "content_mode": mode or "post",
        "platform": (platform_pair_for(item_key)[route_index] if item_key in DAILY_ARTICLE_KEYS else platform_for(item_key, day)),
        "route_index": route_index,
        "delay_seconds": delay,
        "plan_date_ist": day.isoformat(),
    }


def write_outputs(plan: dict) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            for key, value in plan.items():
                handle.write(f"{key}={value}\n")
    print(json.dumps(plan, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-key", default="")
    parser.add_argument("--target-url", default="")
    parser.add_argument("--content-mode", choices=("post", "page"), default="post")
    parser.add_argument("--published-at", default="")
    parser.add_argument("--schedule", default="")
    parser.add_argument("--route-index",type=int,choices=(0,1),default=0)
    args = parser.parse_args()
    write_outputs(make_plan(args.item_key, args.target_url, args.content_mode,
                            args.published_at, args.schedule,route_index=args.route_index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
