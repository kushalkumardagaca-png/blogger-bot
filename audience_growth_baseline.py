#!/usr/bin/env python3
"""Build Daily Yield's authenticated search-acquisition baseline.

This process calls Google OAuth and Search Console APIs only. It never requests a
public Daily Yield URL and therefore cannot create a website pageview. Search
clicks are acquisition evidence, not DAU, sessions or total pageviews.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SITE = "sc-domain:dailyyield.blogspot.com"
API = "https://www.googleapis.com/webmasters/v3/sites/" + urllib.parse.quote(SITE, safe="") + "/searchAnalytics/query"
JSON_REPORT = Path("AUDIENCE_GROWTH_BASELINE.json")
MD_REPORT = Path("AUDIENCE_GROWTH_BASELINE.md")


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("missing required secret: " + name)
    return value


def oauth_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": required("GSC_CLIENT_ID"),
        "client_secret": required("GSC_CLIENT_SECRET"),
        "refresh_token": required("GSC_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def query(token: str, start: date, end: date, dimensions: list[str]) -> list[dict]:
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": dimensions,
        "type": "web",
        "dataState": "final",
        "rowLimit": 25000,
    }
    request = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": "DailyYield-GrowthBaseline/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response).get("rows", [])


def aggregate(rows: list[dict]) -> dict:
    clicks = sum(float(row.get("clicks", 0) or 0) for row in rows)
    impressions = sum(float(row.get("impressions", 0) or 0) for row in rows)
    weighted_position = sum(float(row.get("position", 0) or 0) * float(row.get("impressions", 0) or 0) for row in rows)
    return {
        "clicks": round(clicks),
        "impressions": round(impressions),
        "ctr": round(clicks / impressions, 6) if impressions else 0,
        "averagePosition": round(weighted_position / impressions, 2) if impressions else None,
    }


def rows_for_window(daily: list[dict], days: int, end: date) -> list[dict]:
    start = end - timedelta(days=days - 1)
    return [row for row in daily if row.get("keys") and start.isoformat() <= row["keys"][0] <= end.isoformat()]


def ranked(rows: list[dict], dimension: str, limit: int = 25) -> list[dict]:
    result = []
    for row in sorted(rows, key=lambda item: (item.get("clicks", 0), item.get("impressions", 0)), reverse=True)[:limit]:
        key = (row.get("keys") or [""])[0]
        result.append({dimension: key, **aggregate([row])})
    return result


def build_report(token: str, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    # Search Console final data can lag. Query through yesterday and report the
    # exact returned dates rather than describing unavailable data as real-time.
    end = today - timedelta(days=1)
    start90 = end - timedelta(days=89)
    start28 = end - timedelta(days=27)
    daily = query(token, start90, end, ["date"])
    pages = query(token, start28, end, ["page"])
    countries = query(token, start28, end, ["country"])
    devices = query(token, start28, end, ["device"])
    returned_dates = sorted(row["keys"][0] for row in daily if row.get("keys"))
    return {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "AUTHENTICATED_SEARCH_CONSOLE_ZERO_PUBLIC_VIEWS",
        "syntheticViews": 0,
        "property": SITE,
        "requestedThrough": end.isoformat(),
        "availableThrough": returned_dates[-1] if returned_dates else None,
        "searchAcquisition": {
            "last7Days": aggregate(rows_for_window(daily, 7, end)),
            "last28Days": aggregate(rows_for_window(daily, 28, end)),
            "last90Days": aggregate(rows_for_window(daily, 90, end)),
            "topPages28Days": ranked(pages, "page"),
            "countries28Days": ranked(countries, "country", 20),
            "devices28Days": ranked(devices, "device", 10),
        },
        "readerMeasurement": {
            "status": "NOT_AVAILABLE_FROM_SEARCH_CONSOLE",
            "dau": None,
            "wau": None,
            "mau": None,
            "retention7Day": None,
            "retention30Day": None,
            "explanation": "Search clicks and impressions are not users, sessions, pageviews or retention. DAU and cohort retention require consented first-party analytics reporting access.",
        },
        "limitations": [
            "Search Console data is delayed and may omit privacy-protected rows.",
            "Clicks are genuine search-acquisition evidence but are not total website traffic.",
            "No public Daily Yield URL was requested.",
        ],
    }


def markdown(report: dict) -> str:
    acquisition = report["searchAcquisition"]
    lines = [
        "# Daily Yield Audience Growth Baseline", "",
        f"- **Checked:** {report['checkedAt']}",
        f"- **Mode:** {report['mode']}",
        "- **Synthetic views:** 0",
        f"- **Search data available through:** {report['availableThrough'] or 'No final rows returned'}", "",
        "## Authenticated Google search acquisition", "",
        "| Window | Clicks | Impressions | CTR | Average position |", "|---|---:|---:|---:|---:|",
    ]
    for label, key in (("7 days", "last7Days"), ("28 days", "last28Days"), ("90 days", "last90Days")):
        row = acquisition[key]
        ctr = f"{row['ctr'] * 100:.2f}%"
        position = "—" if row["averagePosition"] is None else str(row["averagePosition"])
        lines.append(f"| {label} | {row['clicks']} | {row['impressions']} | {ctr} | {position} |")
    lines += ["", "## Reader measurement", "", "DAU, WAU, MAU and retention are deliberately not inferred from Search Console. Consented analytics reporting evidence is required before those fields can be populated.", "", "## Top search entry pages — 28 days", ""]
    if acquisition["topPages28Days"]:
        lines += [f"- `{row['page']}` — {row['clicks']} clicks · {row['impressions']} impressions" for row in acquisition["topPages28Days"]]
    else:
        lines.append("- No final page rows returned.")
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        report = build_report(oauth_token())
    except Exception as exc:
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "status": "ERROR",
            "mode": "AUTHENTICATED_SEARCH_CONSOLE_ZERO_PUBLIC_VIEWS",
            "syntheticViews": 0,
            "errorType": type(exc).__name__,
            "error": str(exc)[:500],
        }
        JSON_REPORT.write_text(json.dumps(report, indent=2) + "\n")
        MD_REPORT.write_text("# Daily Yield Audience Growth Baseline\n\n- **Status:** ERROR\n- **Synthetic views:** 0\n- **Error:** " + type(exc).__name__ + "\n")
        raise
    JSON_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    MD_REPORT.write_text(markdown(report))
    print(json.dumps({"status": "PASS", "availableThrough": report["availableThrough"], "windows": {key: report["searchAcquisition"][key] for key in ("last7Days", "last28Days", "last90Days")}, "syntheticViews": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
