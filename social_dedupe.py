#!/usr/bin/env python3
"""Refuse to post the same article to the same network twice.

On 16 October the Europe edition reached Tumblr twice: a live dispatch and a
recovery replay raced, and each read a tracker that did not yet hold the other's
row. Reading the tracker fresh, from the repository the moment before posting,
removes the race for the ordinary case and makes an accidental repeat impossible
in the common path.

Exit code 0 means "go ahead"; 78 means "already posted, skip this route".
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

RAW = "https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/{platform}_tracker.json"


def already_posted(platform: str, url: str) -> bool:
    target = url.split("#")[0].rstrip("/")
    try:
        with urllib.request.urlopen(RAW.format(platform=platform), timeout=30) as response:
            rows = json.load(response).get("published", [])
    except Exception:  # noqa: BLE001 - a tracker read failure must not block a post
        return False
    return any(str(row.get("url", "")).split("#")[0].rstrip("/") == target for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True,
                        choices=("facebook", "bluesky", "tumblr", "mastodon"))
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    if already_posted(args.platform, args.url):
        print(f"skip: {args.platform} already carries {args.url}")
        return 78
    print(f"clear: {args.platform} does not carry {args.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
