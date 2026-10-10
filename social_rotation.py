#!/usr/bin/env python3
"""Deterministic Daily Yield social routing for live News and resources.

Every day: 21 articles receive their two-network routes and every active social
platform receives three additional rotating Daily Yield resource promotions.
Publishers use authenticated Blogger API inventory and never create synthetic
public-page views.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
PLATFORMS = ("facebook", "bluesky", "tumblr", "mastodon")
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
RESOURCE_DESTINATIONS = (
    ("daily-article", "Daily Article", "https://dailyyield.blogspot.com/p/article.html"),
    ("daily-news", "Daily News", "https://dailyyield.blogspot.com/p/daily-news.html"),
    ("markets-today", "Markets Today", "https://dailyyield.blogspot.com/p/markets-today.html"),
    ("calculators", "Calculators", "https://dailyyield.blogspot.com/p/calculator_0908148622.html"),
    ("for-corporate", "For Corporate", "https://dailyyield.blogspot.com/p/for-corporate_01804417406.html"),
    ("spotlight", "Daily Yield Spotlight", "https://dailyyield.blogspot.com/#spotlight"),
    ("website", "Daily Yield Website", "https://dailyyield.blogspot.com/"),
)
# Three audience-friendly resource windows per platform in IST. The 12 schedules
# produce exactly three page/website promotions on each network every day.
RESOURCE_SCHEDULES = {
    "30 0 * * *": ("mastodon", 0),   # 06:00 IST
    "30 1 * * *": ("facebook", 0),   # 07:00 IST
    "0 3 * * *": ("bluesky", 0),     # 08:30 IST
    "0 4 * * *": ("tumblr", 0),      # 09:30 IST
    "30 7 * * *": ("facebook", 1),   # 13:00 IST
    "30 8 * * *": ("mastodon", 1),   # 14:00 IST
    "0 10 * * *": ("bluesky", 1),    # 15:30 IST
    "30 11 * * *": ("tumblr", 1),    # 17:00 IST
    "30 13 * * *": ("mastodon", 2),  # 19:00 IST
    "30 14 * * *": ("facebook", 2),  # 20:00 IST
    "0 16 * * *": ("tumblr", 2),     # 21:30 IST
    "0 17 * * *": ("bluesky", 2),    # 22:30 IST
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
        key=item_key.split("-",1)[1]
        idx=next((i for i,row in enumerate(RESOURCE_DESTINATIONS) if row[0]==key),0)
        pattern=PLATFORMS
    elif item_key.startswith("master-"):
        parts=item_key.split('-')
        if len(parts)!=3 or parts[1] not in ('trending','evergreen'):raise ValueError(f"unknown social item key: {item_key}")
        idx=(0 if parts[1]=='trending' else 5)+int(parts[2])
        if not 0<=idx<10:raise ValueError(f"unknown social item key: {item_key}")
        pattern=NEWS_PATTERN
    else:
        raise ValueError(f"unknown social item key: {item_key}")
    return pattern[(idx + offset) % len(pattern)]


def resource_destination(platform: str, position: int, day: dt.date) -> tuple[str,str,str]:
    if platform not in PLATFORMS or position not in (0,1,2):raise ValueError('invalid resource route')
    # Distinct offsets prevent all four networks from promoting the same page at
    # once. Over seven days every platform promotes every destination three times.
    start=(day.toordinal()*3+PLATFORMS.index(platform)*2)%len(RESOURCE_DESTINATIONS)
    return RESOURCE_DESTINATIONS[(start+position)%len(RESOURCE_DESTINATIONS)]

def resource_url(slot: int, day: dt.date) -> str:
    # Backward-compatible helper: slots 0-11 map to the complete daily plan.
    schedules=list(RESOURCE_SCHEDULES.values());platform,position=schedules[slot]
    return resource_destination(platform,position,day)[2]


def make_plan(item_key: str, target_url: str, mode: str, published_at: str,
              schedule: str, now: dt.datetime | None = None, route_index: int = 0) -> dict:
    reference_now = now or dt.datetime.now(dt.timezone.utc)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=dt.timezone.utc)
    current = reference_now.astimezone(IST)
    published = parse_time(published_at)
    scheduled_platform=None;resource_name=""
    if schedule:
        if schedule not in RESOURCE_SCHEDULES:
            raise ValueError(f"unknown coordinated resource schedule: {schedule}")
        scheduled_platform,position=RESOURCE_SCHEDULES[schedule]
        resource_key,resource_name,target_url=resource_destination(scheduled_platform,position,current.date())
        item_key=f"resource-{resource_key}"
        mode="page"
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
        "platform": (scheduled_platform or (platform_pair_for(item_key)[route_index] if item_key in DAILY_ARTICLE_KEYS else platform_for(item_key, day))),
        "resource_name": resource_name,
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
