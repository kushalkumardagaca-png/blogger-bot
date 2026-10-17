#!/usr/bin/env python3
"""Keep every URL of the site known to Bing — automatically, inside its quota.

Bing's URL Submission API is rate-limited: the account shows a monthly allowance
and a daily one, and when the daily figure is zero every URL is deferred. IndexNow
(``indexnow_submit.py``) removes most of the need for this API, but the API is the
safety net when a search engine refuses the key location, so it must be spent
deliberately:

1. newest URLs first — a new article is worth more than a page from last month;
2. never spend more than the quota the provider reports;
3. remember what was sent, so nothing is paid for twice;
4. anything that could not be sent stays in the queue, ready for tomorrow.

The run is quiet: it reads the site's own sitemap, so no pageview is added.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent
SITE = "https://dailyyield.blogspot.com/"
SITEMAP = SITE + "sitemap.xml"
STATE = ROOT / "BING_INDEX_QUEUE.json"
API = "https://ssl.bing.com/webmaster/api.svc/json"
BATCH = 100          # keep each call modest so a failure costs little


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def sitemap_urls() -> list[str]:
    """Every URL the blog advertises, newest last-modified first."""
    found: dict[str, str] = {}
    for page in range(1, 6):
        url = SITEMAP if page == 1 else f"{SITEMAP}?page={page}"
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                tree = ElementTree.fromstring(response.read())
        except Exception:  # noqa: BLE001
            break
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        entries = tree.findall(".//s:url", ns)
        if not entries:
            break
        for entry in entries:
            loc = entry.findtext("s:loc", default="", namespaces=ns)
            lastmod = entry.findtext("s:lastmod", default="", namespaces=ns)
            if loc:
                found[loc] = lastmod
    return [u for u, _ in sorted(found.items(), key=lambda kv: kv[1], reverse=True)]


def api_call(operation: str, key: str, params: dict, body: dict | None = None):
    query = urllib.parse.urlencode({"apikey": key, **params})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{API}/{operation}?{query}", data=data,
                                     method="POST" if body is not None else "GET",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "DailyYield-BingIndex/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read() or b"{}")


def quota(key: str) -> tuple[int, int]:
    data = api_call("GetUrlSubmissionQuota", key, {"siteUrl": SITE})
    data = data.get("d", data) or {}
    daily = max(0, int(data.get("DailyQuota", 0)))
    monthly_raw = data.get("MonthlyQuota")
    monthly = daily if monthly_raw is None else max(0, int(monthly_raw))
    return daily, monthly


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="send at most this many URLs")
    args = parser.parse_args()
    import os
    key = os.environ.get("BING_WEBMASTER_API_KEY", "").strip()
    state = load(STATE, {"sent": {}, "queue": [], "lastRun": ""})
    urls = sitemap_urls()
    unsent = [u for u in urls if u not in state.get("sent", {})]
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(), "site": SITE,
              "sitemapUrls": len(urls), "alreadySent": len(urls) - len(unsent),
              "neverSent": len(unsent), "apply": args.apply}
    if not key:
        state["queue"] = unsent[:500]
        save(STATE, state)
        print(json.dumps({**report, "status": "NO_KEY",
                          "note": "BING_WEBMASTER_API_KEY is not configured; the queue is kept"}))
        return 0
    try:
        daily, monthly = quota(key)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({**report, "status": "QUOTA_UNREADABLE", "detail": str(exc)[:200]}))
        return 0
    allowance = min(daily, monthly)
    if args.limit:
        allowance = min(allowance, args.limit)
    to_send = unsent[:allowance]
    report.update({"quotaDaily": daily, "quotaMonthly": monthly, "willSend": len(to_send)})
    if not args.apply:
        print(json.dumps(report))
        return 0
    sent = 0
    for start in range(0, len(to_send), BATCH):
        batch = to_send[start:start + BATCH]
        try:
            api_call("SubmitUrlbatch", key, {"siteUrl": SITE},
                     {"siteUrl": SITE, "urlList": batch})
            now = datetime.now(timezone.utc).isoformat()
            for url in batch:
                state.setdefault("sent", {})[url] = now
            sent += len(batch)
        except Exception as exc:  # noqa: BLE001
            report["error"] = str(exc)[:200]
            break
    state["queue"] = [u for u in urls if u not in state.get("sent", {})][:500]
    state["lastRun"] = datetime.now(timezone.utc).isoformat()
    save(STATE, state)
    report.update({"status": "SENT" if sent else "NOTHING_SENT", "sent": sent,
                   "stillQueued": len(state["queue"])})
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
