#!/usr/bin/env python3
"""How much of the site does Google actually hold?

Search Console showed one impression in twenty-eight days, which is not a ranking
problem — it is an indexing problem. This report inspects every URL through the
official URL Inspection endpoint and writes a plain count by coverage state, so
the traffic plan is built on what Google has actually indexed rather than on how
many URLs the sitemap lists.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "INDEX_STATUS_REPORT.json"
SITE = "https://dailyyield.blogspot.com/"
BLOG = "https://dailyyield.blogspot.com"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def fetch(url: str, headers: dict, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def search_token() -> str:
    form = urllib.parse.urlencode({
        "client_id": required("GSC_CLIENT_ID"), "client_secret": required("GSC_CLIENT_SECRET"),
        "refresh_token": required("GSC_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def inventory() -> list[str]:
    urls = [SITE]
    for kind in ("pages", "posts"):
        start = 1
        while True:
            data = fetch(f"{BLOG}/feeds/{kind}/default?alt=json&max-results=100&start-index={start}", {})
            entries = data.get("feed", {}).get("entry", [])
            if not entries:
                break
            for entry in entries:
                url = next((x.get("href", "") for x in entry.get("link", []) if x.get("rel") == "alternate"), "")
                if url and not url.endswith("/p/share-market_0718113516.html"):
                    urls.append(url)
            start += 100
            if len(entries) < 100:
                break
    return urls


def inspect(access: str, url: str) -> dict:
    result = fetch("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                   {"Authorization": "Bearer " + access, "Content-Type": "application/json"},
                   "POST", {"inspectionUrl": url, "siteUrl": SITE, "languageCode": "en-US"})
    status = (result.get("inspectionResult", {}).get("indexStatusResult") or {})
    return {"url": url, "verdict": status.get("verdict", "UNKNOWN"),
            "coverageState": status.get("coverageState", ""),
            "lastCrawlTime": status.get("lastCrawlTime", "")}


def main() -> int:
    access = search_token()
    urls = inventory()
    rows = []
    for url in urls:
        try:
            rows.append(inspect(access, url))
        except Exception as exc:  # noqa: BLE001
            rows.append({"url": url, "verdict": "ERROR", "coverageState": str(exc)[:160]})
        time.sleep(0.15)
    indexed = [r for r in rows if r["verdict"] == "PASS"]
    report = {"checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "property": SITE,
              "urls": len(rows), "indexed": len(indexed),
              "notIndexed": len(rows) - len(indexed),
              "byCoverageState": Counter(r["coverageState"] or "unknown" for r in rows).most_common(),
              "notIndexedUrls": [r for r in rows if r["verdict"] != "PASS"][:200],
              "syntheticViews": 0, "publicDailyYieldRequests": 0}
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("urls", "indexed", "notIndexed")}))
    for state, count in report["byCoverageState"]:
        print(f"  {count:4d}  {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
