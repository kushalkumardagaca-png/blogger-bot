#!/usr/bin/env python3
"""Read the visitor counts the blog is already collecting, so "views a day" stops being a guess.

The gtag for ``G-WLEEYTKV12`` is already present on every page of the site - verified from the
live homepage, not assumed - so nothing here installs, edits or uploads anything: the blog is not
touched. What was missing is read permission. The stored Google token was created for Search
Console only, which is why every earlier attempt came back
``ACCESS_TOKEN_SCOPE_INSUFFICIENT``; ``get_analytics_token.py`` mints one that also covers
Analytics reading.

Statuses are reported honestly and separately, because they need different fixes: the tag may be
live while the property holds no data, credentials may be absent, or the token may simply lack
the scope. A number is written only when Google returned one.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "GA4_MEASUREMENT.json"
MD = ROOT / "GA4_MEASUREMENT.md"

MEASUREMENT_ID = os.environ.get("GA4_MEASUREMENT_ID", "G-WLEEYTKV12")
HOME = "https://dailyyield.blogspot.com/"
DAYS = 7
TOKEN_URL = "https://oauth2.googleapis.com/token"
DATA_API = "https://analyticsdata.googleapis.com/v1beta"
ADMIN_API = "https://analyticsadmin.googleapis.com/v1alpha"

REMEDIES = {
    "CREDENTIALS_MISSING": "run get_analytics_token.py once, then put the code it prints into the "
                           "GA4_REFRESH_TOKEN repository secret (never into a chat)",
    "SCOPE_INSUFFICIENT": "the stored token predates Analytics access: re-run get_analytics_token.py "
                          "and replace GA4_REFRESH_TOKEN with the new code",
    "PROPERTY_NOT_FOUND": "add a repository variable GA4_PROPERTY_ID with the numeric Property ID from "
                          "Analytics -> Admin -> Property settings",
    "TAG_NOT_OBSERVED": "the analytics tag is not on the live pages; it has to be added before any "
                        "count can exist",
    "NO_DATA_YET": "the property is reachable but holds no rows: check that the tag's measurement id "
                   "matches the property and that data retention includes today",
}


def http(url: str, token: str = "", body: dict | None = None, method: str = "") -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers,
                                      method=method or ("POST" if data else "GET"))
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload) if payload.strip() else {}


def site_tag() -> dict:
    """Confirm from the public homepage that the tag is installed. Needs no credential."""
    row = {"checked": True, "reachable": False, "measurementIds": [], "installedHere": False}
    try:
        request = urllib.request.Request(HOME, headers={"User-Agent": "Daily Yield self-check"})
        with urllib.request.urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", "ignore")
        row["reachable"] = True
    except Exception as exc:  # noqa: BLE001 - an unfetchable homepage says nothing about the tag
        row["error"] = str(exc)[:140]
        return row
    html = str(html)
    ids = sorted(set(re.findall(r"\bG-[A-Z0-9]{6,}\b", html)))
    row["measurementIds"] = ids
    row["installedHere"] = MEASUREMENT_ID in ids
    return row


def refresh_token() -> str:
    client_id = os.environ.get("GA4_CLIENT_ID") or os.environ.get("GSC_CLIENT_ID") or ""
    client_secret = os.environ.get("GA4_CLIENT_SECRET") or os.environ.get("GSC_CLIENT_SECRET") or ""
    stored = os.environ.get("GA4_REFRESH_TOKEN") or os.environ.get("GSC_REFRESH_TOKEN") or ""
    if not (client_id and client_secret and stored):
        raise MissingCredentials()
    form = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret,
                                   "refresh_token": stored, "grant_type": "refresh_token"}).encode()
    request = urllib.request.Request(TOKEN_URL, data=form, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


class MissingCredentials(RuntimeError):
    pass


def resolve_property(token: str, measurement_id: str) -> tuple[str, str]:
    """The Data API needs the numeric property id; find it from the measurement id if not set."""
    configured = (os.environ.get("GA4_PROPERTY_ID") or "").strip()
    if configured and not configured.startswith("G-"):
        return configured, "GA4_PROPERTY_ID repository variable"
    listing = http(f"{ADMIN_API}/properties?pageSize=200", token=token)
    for row in listing.get("properties") or []:
        name = str(row.get("name") or "")
        numeric = name.rsplit("/", 1)[-1]
        streams = [str(stream.get("measurementId") or "") for stream in row.get("dataStreams") or []]
        if not numeric.isdigit():
            continue
        if measurement_id in streams or len(streams) == 0:
            return numeric, "discovered through the Analytics Admin API"
    raise LookupError("no GA4 property carries that measurement id")


def daily_rows(token: str, property_id: str) -> list[dict]:
    start = (datetime.now(timezone.utc).date() - timedelta(days=DAYS)).isoformat()
    payload = {"dimensions": ["date"],
               "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}, {"name": "sessions"}],
               "dateRanges": [{"startDate": start, "endDate": (datetime.now(timezone.utc).date()
                                                                - timedelta(days=1)).isoformat()}],
               "orderBys": [{"dimension": {"dimensionName": "date"}, "desc": True}], "limit": str(DAYS)}
    data = http(f"{DATA_API}/properties/{property_id}:runReport", token=token, body=payload, method="POST")
    rows = []
    for row in data.get("rows") or []:
        values = [cell.get("value") for cell in row.get("dimensionValues") or []]
        metrics = [cell for cell in row.get("metricValues") or []]
        day = (values[0] if values else "").replace("-", "")
        if len(day) == 8:
            day = f"{day[0:4]}-{day[4:6]}-{day[6:8]}"
        rows.append({"date": day, "views": int(float(metrics[0])) if len(metrics) else 0,
                     "activeUsers": int(float(metrics[1])) if len(metrics) > 1 else 0,
                     "sessions": int(float(metrics[2])) if len(metrics) > 2 else 0})
    return rows


def summarise(rows: list[dict], tag: dict, property_id: str, property_source: str) -> dict:
    views = sum(row.get("views") or 0 for row in rows)
    users = sum(row.get("activeUsers") or 0 for row in rows)
    sessions = sum(row.get("sessions") or 0 for row in rows)
    status = "MEASURED" if rows and views else ("NO_DATA_YET" if rows or tag.get("installedHere") else "TAG_NOT_OBSERVED")
    # a window with no rows is "nothing read yet", never a measured audience of zero: only a real
    # report from Google is allowed to put a number in this file
    measured = status == "MEASURED"
    views = views if measured else None
    users = users if measured else None
    sessions = sessions if measured else None
    return {"status": status, "ok": measured,
            "measuredAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "windowDays": DAYS, "propertyId": property_id or None, "propertyIdSource": property_source,
            "measurementId": MEASUREMENT_ID, "siteTag": tag,
            "totals": {"views": views,
                       "viewsPerDay": round(views / DAYS, 1) if measured else None,
                       "activeUsers": users, "sessions": sessions, "daysWithRows": len(rows)},
            "daily": rows[:DAYS],
            "peak": max((row for row in rows), key=lambda row: row.get("views") or 0, default=None),
            "remedy": REMEDIES.get(status, "") or None,
            "note": "views are GA4 screenPageViews for the last 7 whole days; the blog is not "
                    "modified by this job and no tag is installed by it"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="", help="JSON of {rows, siteTag, propertyId}, for tests")
    arguments = parser.parse_args()

    if arguments.fixture:
        payload = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
        report = summarise(payload.get("rows") or [], payload.get("siteTag") or {"checked": False},
                           str(payload.get("propertyId") or ""), "fixture")
    else:
        tag = site_tag()
        rows, property_id, source, status, report_error = [], "", "not read", None, ""
        try:
            token = refresh_token()
            property_id, source = resolve_property(token, MEASUREMENT_ID)
            rows = daily_rows(token, property_id)
        except MissingCredentials:
            status = "CREDENTIALS_MISSING"
        except urllib.error.HTTPError as exc:
            status = "SCOPE_INSUFFICIENT" if exc.code == 403 else (
                "PROPERTY_NOT_FOUND" if exc.code == 404 else "READ_FAILED")
            rows = []
        except Exception as exc:  # noqa: BLE001
            status, report_error = "READ_FAILED", str(exc)[:160]
        if status:
            report = {"status": status, "ok": False,
                      "measuredAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "windowDays": DAYS, "measurementId": MEASUREMENT_ID, "siteTag": tag,
                      "totals": {"views": None, "viewsPerDay": None, "daysWithRows": 0},
                      "daily": [], "remedy": REMEDIES.get(status, "the Analytics Data API could not "
                                                                  "be reached; the failure is recorded, "
                                                                  "no number is invented"),
                      "note": "the blog is not modified by this job"}
            if report_error:
                report["error"] = report_error
        else:
            report = summarise(rows, tag, property_id, source)

    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    totals = report.get("totals") or {}
    lines = [f"# GA4 measurement · {report['measuredAt']}", "",
             f"Status: **{report['status']}**", "",
             f"- analytics tag observed on the live site: "
             f"**{'yes' if (report.get('siteTag') or {}).get('installedHere') else 'no'}** "
             f"({', '.join((report.get('siteTag') or {}).get('measurementIds') or []) or 'no G- id found'})",
             f"- property: **{report.get('propertyId') or 'not resolved'}** "
             f"({report.get('propertyIdSource') or 'unknown'})"]
    if report["ok"]:
        lines += [f"- views in the last {report['windowDays']} days: **{totals['views']:,}**",
                  f"- **views per day: {totals['viewsPerDay']}**",
                  f"- active users: **{totals['activeUsers']:,}**, sessions: **{totals['sessions']:,}**", "",
                  "| day | views | active users | sessions |", "| --- | --- | --- | --- |"]
        lines += [f"| {row['date']} | {row['views']:,} | {row['activeUsers']:,} | {row['sessions']:,} |"
                  for row in report.get("daily") or []]
    else:
        lines += ["", f"What to do: {report.get('remedy') or 'not specified'}"]
    lines += ["", "This job reads Google's numbers and the public homepage only. It changes nothing "
                  "on the blog, so it does not touch the publisher review."]
    MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": report["status"], "viewsPerDay": totals.get("viewsPerDay"),
                      "views": totals.get("views"), "tagObserved": (report.get("siteTag") or {}).get("installedHere")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
