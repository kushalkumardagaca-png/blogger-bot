#!/usr/bin/env python3
"""Measure the audience that can be counted without a single secret.

Search Console tells us what Google search does. Nothing in this repository has ever recorded
what the social accounts do, so "audience acquisition" has been a feeling rather than a number.
Bluesky and Mastodon publish follower counts over open, read-only endpoints, so this job reads
them the same way a visitor can - no token, no posting, no scraping behind a login.

Two things are deliberately stated instead of guessed: channels whose numbers need a credential
(Facebook is reported as not measured here), and the blog's own pageviews, which are counted by two
instruments at once - Google Analytics, which needs a real browser, and Blogger's own counter, read
through the authenticated API by the nightly Blogger View Ledger job. Blogger's figure counts every
page its servers hand over, crawlers and scripts included, so it is reported beside the Google number
and never used as the reader count.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "AUDIENCE_CHANNELS.json"
MD = ROOT / "AUDIENCE_CHANNELS.md"

# Open endpoints, no authentication, read-only. Handles come from the same place the publishers
# use: social_identity.py for Mastodon, the coordinated publisher's BLUESKY_HANDLE for Bluesky.
BLUESKY_HANDLE = "dailyyield.bsky.social"
MASTODON_ACCT = "dailyyield"
MASTODON_INSTANCE = "https://mastodon.social"
NOT_MEASURED = {
    "Facebook": "needs the page token this operation is not allowed to touch; coordinated_social_publish posts through it",
}


def fetch_json(url: str, timeout: int = 25) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Daily Yield audience reader (public data)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def days_since(value: str) -> int | None:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    if not match:
        return None
    try:
        born = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    return max(1, (datetime.now(timezone.utc).date() - born).days)


def bluesky(handle: str) -> dict:
    url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={urllib.parse.quote(handle)}"
    data = fetch_json(url)
    followers = int(data.get("followersCount") or 0)
    posts = int(data.get("postsCount") or 0)
    span = days_since(data.get("createdAt"))
    return {"ok": True, "handle": f"@{handle}", "followers": followers,
            "following": int(data.get("followsCount") or 0), "posts": posts,
            "created": str(data.get("createdAt") or "")[:10], "accountAgeDays": span,
            "followersPerPost": round(followers / posts, 4) if posts else None,
            "source": url}


def mastodon(instance: str, acct: str) -> dict:
    url = f"{instance}/api/v1/accounts/lookup?acct={urllib.parse.quote(acct)}"
    data = fetch_json(url)
    followers = int(data.get("followers_count") or 0)
    posts = int(data.get("statuses_count") or 0)
    span = days_since(data.get("created_at"))
    return {"ok": True, "handle": f"@{data.get('acct') or acct}", "followers": followers,
            "following": int(data.get("following_count") or 0), "posts": posts,
            "created": str(data.get("created_at") or "")[:10], "accountAgeDays": span,
            "followersPerPost": round(followers / posts, 4) if posts else None,
            "source": url}


def blog_pageviews() -> dict:
    """What the blog's own page count looks like, from the file that reconciles both counters.

    BLOGGER_VIEWS_LEDGER.json is written nightly by blogger_view_ledger.py, which reads Blogger's
    counter through the API. When that file is absent or Blogger did not answer, the honest answer
    here is "not measured" - never a stale number and never a zero.
    """
    path = OUT.parent / "BLOGGER_VIEWS_LEDGER.json"
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"measurable": False,
                "why": "BLOGGER_VIEWS_LEDGER.json has not been written yet - the nightly "
                       "Blogger View Ledger job writes it"}
    blogger = ledger.get("bloggerCounter") or {}
    human = ledger.get("humanCount") or {}
    measured = blogger.get("status") == "MEASURED"
    return {"measurable": measured,
            "bloggerLast7Days": blogger.get("last7Days"),
            "bloggerPerDay": blogger.get("perDayFrom7DayWindow"),
            "humanViewsPerDay": human.get("viewsPerDay"),
            "humanBasis": human.get("basis"),
            "warning": "Blogger's counter measures requests, not readers; the reader count is the "
                       "Google figure - see BLOGGER_VIEWS_LEDGER.json",
            "why": None if measured else str(blogger.get("reason") or "Blogger did not answer")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="", help="JSON of channel payloads, for tests and offline review")
    arguments = parser.parse_args()

    if arguments.fixture:
        payload = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
        rows = {"Bluesky": payload.get("bluesky", {"ok": False, "error": "absent from fixture"}),
                "Mastodon": payload.get("mastodon", {"ok": False, "error": "absent from fixture"})}
    else:
        rows = {}
        for name, call in (("Bluesky", lambda: bluesky(BLUESKY_HANDLE)),
                           ("Mastodon", lambda: mastodon(MASTODON_INSTANCE, MASTODON_ACCT))):
            try:
                rows[name] = call()
            except Exception as exc:  # noqa: BLE001
                # an unreachable count is unknown, never zero - a zero here would read as a
                # measured audience of nobody
                rows[name] = {"ok": False, "error": str(exc)[:160]}
    for name, why in NOT_MEASURED.items():
        rows[name] = {"ok": False, "reason": why}

    counted = {k: v for k, v in rows.items() if v.get("ok")}
    followers = sum(int(v.get("followers") or 0) for v in counted.values())
    posts = sum(int(v.get("posts") or 0) for v in counted.values())
    report = {
        "measuredAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "PUBLIC_OPEN_ENDPOINTS_ONLY",
        "credentialsUsed": False,
        "channels": rows,
        "totals": {"followers": followers if counted else None, "posts": posts if counted else None,
                   "channelsMeasured": len(counted), "channelsNotMeasured": sorted(NOT_MEASURED)},
        "blogPageviews": blog_pageviews(),
        "note": "followers per post is the honest reach test: it is what a published post has "
                "historically converted into on that network",
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    lines = [f"# Measurable audience · {report['measuredAt']}", "",
             f"- channels counted: **{len(counted)}** of {len(rows)} (public endpoints, no tokens)",
             f"- followers across the counted channels: **{followers if counted else 'unknown'}**",
             f"- posts published on them: **{posts if counted else 'unknown'}**", ""]
    for name, row in rows.items():
        if row.get("ok"):
            rate = row.get("followersPerPost")
            lines.append(f"- **{name}** {row['handle']}: {row['followers']} followers from "
                         f"{row['posts']} posts in {row['accountAgeDays']} days"
                         + (f" (that is {rate} followers per published post)" if rate is not None else ""))
        else:
            lines.append(f"- **{name}**: not measured - {row.get('reason') or row.get('error')}")
    lines += ["", "## What cannot be counted yet", "",
              f"- blog pageviews: {report['blogPageviews']['why']}",
              "- therefore any 'views per day' target is currently only checkable for the search "
              "channel; every other channel has to be judged on followers, which is what this "
              "file now does"]
    MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({"followers": followers if counted else None, "channelsMeasured": len(counted),
                      "perChannel": {k: (v.get("followers") if v.get("ok") else None) for k, v in rows.items()}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
