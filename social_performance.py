#!/usr/bin/env python3
"""Collect genuine social performance without requesting Daily Yield pages.

Only official social-network APIs are queried. Missing metrics stay unavailable;
zeros are recorded only when a platform explicitly returns zero. The report is
an optimisation input, never a substitute for platform-native analytics.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
REPORT = ROOT / "SOCIAL_PERFORMANCE.json"
TIMEOUT = (10, 35)
USER_AGENT = "DailyYield-SocialPerformance/1.0"


def tracker(name: str) -> dict:
    path = ROOT / f"{name}_tracker.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"published": []}


def get_json(url: str, **kwargs) -> dict:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    response = requests.get(url, headers=headers, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json()


def base(entry: dict, platform: str) -> dict:
    return {
        "platform": platform,
        "social_id": (entry.get("facebook_post_id") or entry.get("bluesky_uri") or
                      entry.get("mastodon_status_id") or entry.get("tumblr_post_id") or ""),
        "title": entry.get("title", ""),
        "destination": entry.get("url", ""),
        "published_at": entry.get("published_at", ""),
    }


def bluesky_metrics(entries: list[dict]) -> tuple[list[dict], str]:
    rows = []
    by_uri = {x.get("bluesky_uri"): x for x in entries if x.get("bluesky_uri")}
    try:
        uris = list(by_uri)
        for start in range(0, len(uris), 25):
            params = [("uris", uri) for uri in uris[start:start + 25]]
            data = get_json("https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts", params=params)
            for post in data.get("posts", []):
                entry = by_uri.get(post.get("uri"))
                if not entry:
                    continue
                row = base(entry, "bluesky")
                row["metrics"] = {
                    "likes": int(post.get("likeCount", 0)),
                    "reposts": int(post.get("repostCount", 0)),
                    "replies": int(post.get("replyCount", 0)),
                    "quotes": int(post.get("quoteCount", 0)),
                }
                row["impressions_available"] = False
                rows.append(row)
        return rows, "ok"
    except Exception as exc:
        return [], f"unavailable: {type(exc).__name__}"


def mastodon_metrics(entries: list[dict]) -> tuple[list[dict], str]:
    rows = []
    failures = 0
    for entry in entries[-80:]:
        sid = str(entry.get("mastodon_status_id", ""))
        if not sid:
            continue
        try:
            post = get_json(f"https://mastodon.social/api/v1/statuses/{sid}")
            row = base(entry, "mastodon")
            row["metrics"] = {
                "favourites": int(post.get("favourites_count", 0)),
                "reblogs": int(post.get("reblogs_count", 0)),
                "replies": int(post.get("replies_count", 0)),
            }
            row["impressions_available"] = False
            rows.append(row)
        except Exception:
            failures += 1
    status = "ok" if not failures else f"partial: {failures} unavailable"
    return rows, status


def tumblr_metrics(entries: list[dict]) -> tuple[list[dict], str]:
    api_key = os.environ.get("TUMBLR_CONSUMER_KEY", "").strip()
    if not api_key:
        return [], "unavailable: API key not configured"
    rows = []
    failures = 0
    for entry in entries[-80:]:
        pid = str(entry.get("tumblr_post_id", ""))
        if not pid:
            continue
        try:
            data = get_json("https://api.tumblr.com/v2/blog/dailyyield-official/posts",
                            params={"api_key": api_key, "id": pid, "npf": "true"})
            posts = data.get("response", {}).get("posts", [])
            if not posts:
                failures += 1
                continue
            row = base(entry, "tumblr")
            row["metrics"] = {"notes": int(posts[0].get("note_count", 0))}
            row["impressions_available"] = False
            rows.append(row)
        except Exception:
            failures += 1
    status = "ok" if not failures else f"partial: {failures} unavailable"
    return rows, status


def facebook_metrics(entries: list[dict]) -> tuple[list[dict], str]:
    token = os.environ.get("FACEBOOK_SYSTEM_USER_TOKEN", "").strip()
    page_id = os.environ.get("FACEBOOK_PAGE_ID", "1303333369533572").strip()
    version = os.environ.get("FACEBOOK_GRAPH_VERSION", "v26.0").strip()
    if not token:
        return [], "unavailable: token not configured"
    try:
        page = get_json(f"https://graph.facebook.com/{version}/{page_id}",
                        params={"fields": "access_token", "access_token": token})
        page_token = page.get("access_token")
        if not page_token:
            return [], "unavailable: Page token not returned"
        rows, failures = [], 0
        for entry in entries[-80:]:
            pid = str(entry.get("facebook_post_id", ""))
            if not pid:
                continue
            try:
                # Basic engagement and insights are separate calls. A metric that
                # is unavailable for one post must not erase the genuine counts
                # that Facebook can still return for that post.
                data = get_json(
                    f"https://graph.facebook.com/{version}/{pid}",
                    params={
                        "fields": "created_time,shares,comments.limit(0).summary(true),reactions.limit(0).summary(true)",
                        "access_token": page_token,
                    },
                )
                metrics = {
                    "shares": int(data.get("shares", {}).get("count", 0)),
                    "comments": int(data.get("comments", {}).get("summary", {}).get("total_count", 0)),
                    "reactions": int(data.get("reactions", {}).get("summary", {}).get("total_count", 0)),
                }
                try:
                    insights = get_json(
                        f"https://graph.facebook.com/{version}/{pid}/insights",
                        params={"metric": "post_impressions,post_impressions_unique,post_clicks", "access_token": page_token},
                    )
                except Exception:
                    insights = {"data": []}
                for insight in insights.get("data", []):
                    values = insight.get("values", [])
                    value = values[-1].get("value") if values else None
                    if value is not None:
                        metrics[insight.get("name", "metric")] = value
                row = base(entry, "facebook")
                row["metrics"] = metrics
                row["impressions_available"] = "post_impressions" in metrics
                rows.append(row)
            except Exception:
                failures += 1
        status = "ok" if not failures else f"partial: {failures} unavailable"
        return rows, status
    except Exception as exc:
        return [], f"unavailable: {type(exc).__name__}"


def main() -> int:
    collectors = {
        "facebook": facebook_metrics,
        "bluesky": bluesky_metrics,
        "mastodon": mastodon_metrics,
        "tumblr": tumblr_metrics,
    }
    platforms, items = {}, []
    for name, collect in collectors.items():
        entries = tracker(name).get("published", [])[-100:]
        rows, status = collect(entries)
        platforms[name] = {"status": status, "observations": len(rows)}
        items.extend(rows)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Official social APIs only; no Daily Yield page requests and no synthetic views.",
        "limitations": "Impressions are recorded only where the platform API supplies them. Engagement counts are not treated as impressions.",
        "platforms": platforms,
        "items": sorted(items, key=lambda x: (x.get("published_at", ""), x["platform"]), reverse=True),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(platforms, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
