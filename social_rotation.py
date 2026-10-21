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
# Tumblr was dropped from social automation on 21 October 2026 at the owner's instruction, so the live
# destinations are these three. Every table below is derived from PLATFORMS: an entry that names a
# retired network would route a post into a publisher that no longer exists, and the audit rejects it.
PLATFORMS = ("facebook", "bluesky", "mastodon")
# User-approved cross-day application rotation. The anchor preserves the established routes; each
# following IST date advances Facebook -> Bluesky -> Mastodon -> Facebook. A cyclic permutation keeps
# the exact daily post count while preventing any desk, Master slot or Page from staying on one app.
ROTATION_PLATFORMS=("facebook","bluesky","mastodon")
ROTATION_ANCHOR=dt.date(2026,10,13)

def rotate_platform(platform:str,day:dt.date)->str:
 if platform not in ROTATION_PLATFORMS:raise ValueError(f'unknown social platform: {platform}')
 phase=(day-ROTATION_ANCHOR).days%len(ROTATION_PLATFORMS)
 return ROTATION_PLATFORMS[(ROTATION_PLATFORMS.index(platform)+phase)%len(ROTATION_PLATFORMS)]
# The news-desk and Master single-slot rhythm: fifteen positions, five turns for each live network, so no
# desk or slot is favoured as the day advances. It used to be twenty positions across four networks.
NEWS_PATTERN = (
    "facebook", "bluesky", "mastodon",
    "bluesky", "facebook", "mastodon",
    "facebook", "mastodon", "bluesky",
    "mastodon", "bluesky", "facebook",
    "mastodon", "facebook", "bluesky",
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
# Exactly 42 daily assignments over 21 articles, two different networks each. With Tumblr retired the
# eight slots it held are redistributed so the three live networks carry fourteen each: seven
# Facebook+Bluesky, seven Facebook+Mastodon and seven Bluesky+Mastodon articles. The count per article
# is untouched, which is the point of the 42-pair rule - dropping a network must not change how much
# each article is promoted, only where it lands.
_DAILY_PAIR_KINDS=(("facebook", "bluesky"), ("facebook", "mastodon"), ("bluesky", "mastodon"))
DAILY_PLATFORM_PAIRS=tuple(_DAILY_PAIR_KINDS[index % 3] for index in range(len(DAILY_ARTICLE_KEYS)))

def platform_pair_for(item_key:str,day:dt.date|None=None)->tuple[str,str]:
 if item_key not in DAILY_ARTICLE_KEYS:raise ValueError(f'unknown daily article key: {item_key}')
 route_day=day or dt.datetime.now(IST).date();base=DAILY_PLATFORM_PAIRS[DAILY_ARTICLE_KEYS.index(item_key)]
 pair=(rotate_platform(base[0],route_day),rotate_platform(base[1],route_day))
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
# Three audience-friendly resource windows per platform in IST, plus the three windows that belonged to
# Tumblr and are now spread over the live networks so the site still gets nine daily promotions: the
# 12 schedules are unchanged in number and time, only the destination of three of them moved.
RESOURCE_SCHEDULES = {
    "15 23 * * *": ("mastodon", 0), # 04:45 IST: Asia-Pacific morning
    "15 1 * * *": ("facebook", 0),  # 06:45 IST: China/India morning
    "15 3 * * *": ("bluesky", 0),   # 08:45 IST: India commute
    "15 5 * * *": ("mastodon", 3),   # 10:45 IST: Europe morning - the window Tumblr held, reassigned
    "30 6 * * *": ("mastodon", 1),  # 12:00 IST: Europe lunch approach
    "15 8 * * *": ("facebook", 1),  # 13:45 IST: India/Europe overlap
    "15 10 * * *": ("bluesky", 1),  # 15:45 IST: Europe midday
    "30 11 * * *": ("bluesky", 3),   # 17:00 IST: India evening - reassigned from Tumblr
    "30 13 * * *": ("mastodon", 2), # 19:00 IST: India prime/US morning
    "30 14 * * *": ("facebook", 2), # 20:00 IST: India prime/US morning
    "0 16 * * *": ("bluesky", 2),   # 21:30 IST: US midday
    "45 17 * * *": ("facebook", 3),  # 23:15 IST: US afternoon - reassigned from Tumblr
}



def parse_time(value: str) -> dt.datetime | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed


def platform_for(item_key: str, day: dt.date) -> str:
    if item_key in DAILY_ARTICLE_KEYS:return platform_pair_for(item_key,day)[0]
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
    if platform not in PLATFORMS or position not in range(len(RESOURCE_DESTINATIONS)):
        raise ValueError('invalid resource route')
    # Distinct offsets prevent every live network from promoting the same page at once. The position is
    # the destination slot, not a fixed three-per-day quota: when Tumblr was retired its three windows
    # were handed to the live networks, so a platform may now hold four, and each still promotes a
    # different page in each window.
    start=(day.toordinal()*3+PLATFORMS.index(platform)*2)%len(RESOURCE_DESTINATIONS)
    return RESOURCE_DESTINATIONS[(start+position)%len(RESOURCE_DESTINATIONS)]

def resource_url(slot: int, day: dt.date) -> str:
    # Backward-compatible helper: slots 0-11 map to the complete daily plan.
    schedules=list(RESOURCE_SCHEDULES.values());platform,position=schedules[slot]
    return resource_destination(rotate_platform(platform,day),position,day)[2]


def make_plan(item_key: str, target_url: str, mode: str, published_at: str,
              schedule: str, now: dt.datetime | None = None, route_index: int = 0,
              platforms: tuple[str, ...] | None = None) -> dict:
    reference_now = now or dt.datetime.now(dt.timezone.utc)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=dt.timezone.utc)
    current = reference_now.astimezone(IST)
    published = parse_time(published_at)
    scheduled_platform=None;resource_name=""
    if schedule:
        if schedule not in RESOURCE_SCHEDULES:
            raise ValueError(f"unknown coordinated resource schedule: {schedule}")
        base_platform,position=RESOURCE_SCHEDULES[schedule]
        scheduled_platform=rotate_platform(base_platform,current.date())
        resource_key,resource_name,target_url=resource_destination(scheduled_platform,position,current.date())
        item_key=f"resource-{resource_key}"
        mode="page"
    if not item_key or not target_url:
        raise ValueError("item key and target URL are required")
    if platforms:
        # A supervised revival may name its own rotation of networks. The list is
        # validated here so no route can leave the approved Daily Yield accounts.
        if any(x not in PLATFORMS for x in platforms) or len(set(platforms)) != len(platforms):
            raise ValueError(f"invalid platform rotation: {platforms}")
        if len(platforms) < 2:
            raise ValueError("a coordinated route needs at least two networks")
    if not target_url.startswith("https://dailyyield.blogspot.com/"):
        raise ValueError("target URL is outside the official Daily Yield domain")
    day = (published.astimezone(IST).date() if published else current.date())
    if route_index not in (0,1,2):raise ValueError('route index must be 0, 1 or 2')
    delay = 0
    if published:
        # Start one minute inside the five-minute SLA so API and workflow overhead
        # cannot push either confirmed post past the reader-visible deadline.
        due = published.astimezone(dt.timezone.utc) + dt.timedelta(minutes=4)
        delay = max(0, min(20 * 60, int((due - reference_now.astimezone(dt.timezone.utc)).total_seconds())))
    return {
        "item_key": item_key,
        "target_url": target_url,
        "content_mode": mode or "post",
        "platform": (scheduled_platform or (platforms[route_index] if platforms and route_index < len(platforms) else (platform_pair_for(item_key,day)[route_index] if item_key in DAILY_ARTICLE_KEYS else platform_for(item_key, day)))),
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
    parser.add_argument("--route-index",type=int,choices=(0,1,2),default=0)
    parser.add_argument("--platforms",default="")
    args = parser.parse_args()
    platforms=tuple(x.strip() for x in args.platforms.split(',') if x.strip()) or None
    write_outputs(make_plan(args.item_key, args.target_url, args.content_mode,
                            args.published_at, args.schedule,route_index=args.route_index,
                            platforms=platforms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
