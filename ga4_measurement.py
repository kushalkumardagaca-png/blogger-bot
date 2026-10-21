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
TOKEN_INFO = "https://oauth2.googleapis.com/tokeninfo"
ADMIN_API = "https://analyticsadmin.googleapis.com/v1alpha"
ADMIN_API_BETA = "https://analyticsadmin.googleapis.com/v1beta"

REMEDIES = {
    "CREDENTIALS_MISSING": "follow GA4_CONNECT.md - browser steps, nothing to install, or run "
                           "get_analytics_token.py on a computer with Python - then put the code it "
                           "prints into the GA4_REFRESH_TOKEN repository secret (never into a chat)",
    "SCOPE_INSUFFICIENT": "the stored token predates Analytics access: repeat step 3 of "
                          "GA4_CONNECT.md (or re-run get_analytics_token.py) and replace "
                          "GA4_REFRESH_TOKEN with the new code",
    "TOKEN_REFUSED": "Google refused the stored refresh token: it was made while the OAuth app was in "
                     "Testing (Google expires those after 7 days), or it was revoked. Repeat the browser "
                     "steps in GA4_CONNECT.md and replace only the GA4_REFRESH_TOKEN secret",
    "API_DISABLED_IN_PROJECT": "Google refused because the Analytics API is not switched on for the "
                               "project that owns the OAuth client: open the project that holds "
                               "'Daily Yield Search Console Automation' and press Enable on "
                               "analyticsadmin.googleapis.com and analyticsdata.googleapis.com, then run "
                               "the check again - no new authorisation is needed for this",
    "ACCESS_DENIED": "Google answered but will not show this property to that account: the signed-in "
                     "Google account must be a Viewer (or Editor) on the Analytics property itself - "
                     "Analytics -> Admin -> Property Access Management -> add the account, then run the "
                     "check again; the stored token needs no change",
    "REQUEST_REJECTED": "Google turned down the request this job built, not your authorisation: its "
                        "own sentence is recorded above, and the repair belongs in this repository. "
                        "Nothing on the blog is involved and no number is invented in the meantime",
    "PROPERTY_NOT_FOUND": "add a repository variable GA4_PROPERTY_ID with the numeric Property ID from "
                          "Analytics -> Admin -> Property settings",
    "TAG_NOT_OBSERVED": "the analytics tag is not on the live pages; it has to be added before any "
                        "count can exist",
    "TAG_UNKNOWN": "the public homepage could not be fetched from this network (a data-centre "
                   "request can be refused while your own browser loads the page), so the tag is "
                   "neither confirmed nor denied - the nightly job asks again",
    "NO_DATA_YET": "the property is reachable but holds no rows: check that the tag's measurement id "
                   "matches the property and that data retention includes today",
}


def credential_label() -> str:
    """Which repository variable each credential came from, with no values in it."""
    try:
        from google_credentials import credential_source
        return credential_source()
    except Exception:  # noqa: BLE001 - the label is a courtesy; the measurement is the job
        return "not recorded"


def token_scopes(token: str) -> list[str]:
    """Ask Google, before any data call, what the token just obtained is allowed to do.

    A 403 has several causes and a report that must pick one ends up guessing; the scope list settles
    it. The question is asked about the short-lived access token, and that token is never written into
    the report or the log.
    """
    try:
        payload = http(TOKEN_INFO + "?access_token=" + urllib.parse.quote(token, safe=""))
    except Exception:  # noqa: BLE001 - knowing the scopes is a courtesy, not a requirement
        return []
    scope_text = payload.get("scope") if isinstance(payload, dict) else ""
    # every name Google lists is kept, not just the https:// form: a tokeninfo reply may answer
    # "analytics.readonly" or the full url depending on how the consent was requested, and dropping
    # either one would make the report claim a permission the token does have
    return sorted({str(part) for part in str(scope_text or "").split() if part})


def grants_analytics(scopes: list[str]) -> bool:
    """Whether any listed scope is the Analytics read permission, in either spelling."""
    return any(str(scope).endswith("auth/analytics.readonly") or str(scope) == "analytics.readonly"
               for scope in scopes)


def classify_forbidden(payload: dict) -> tuple[str, str, list[str]]:
    """Split Google's 403 into the three things an owner can actually fix.

    A 403 arrived as one label - "scope insufficient" - and that was wrong twice over: the same status
    covers an API that is not switched on for the project, an account that is not a Viewer on the
    property, and a token minted before Analytics was added. Each needs a different click, and only one
    of them needs a new authorisation, so the difference is the whole value of the report.
    """
    error = payload.get("error") if isinstance(payload, dict) else {}
    error = error if isinstance(error, dict) else {}
    message = str(error.get("message") or "")
    status = str(error.get("status") or "")
    reasons: list[str] = []
    for key in ("details", "errors"):
        for row in error.get(key) or []:
            if isinstance(row, dict):
                for field in ("reason", "domain", "api"):
                    value = str(row.get(field) or "")
                    if value:
                        reasons.append(value)
    blob = (message + " " + status + " " + " ".join(reasons)).casefold()
    if not blob.strip():
        # Google refused without saying why (only ever seen from a proxy or a test): the historic
        # default is kept, because a scope that was never asked for is by far the commonest reason a
        # first connection is refused - and the report says plainly that no reason came back.
        return "SCOPE_INSUFFICIENT", message, reasons
    if "accessnotconfigured" in blob or "has not been used" in blob or "is not enabled" in blob \
            or "service disabled" in blob or "enable it" in blob:
        return "API_DISABLED_IN_PROJECT", message, reasons
    if "insufficient" in blob or "scope" in blob:
        return "SCOPE_INSUFFICIENT", message, reasons
    if "permission" in blob or "denied" in blob or "not accessible" in blob or "viewer" in blob:
        return "ACCESS_DENIED", message, reasons
    return "READ_FAILED", message, reasons


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
    # Three answers, not two: an unfetchable page has not shown that the tag is missing.
    row = {"checked": True, "reachable": False, "measurementIds": [], "installedHere": None}
    try:
        request = urllib.request.Request(HOME, headers={"User-Agent": "Mozilla/5.0 (Daily Yield self-check)"})
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
    # a failure here means something entirely different from a failure on an Analytics call: the token
    # or the client pair was refused. Until 21 October both were reported as "token refused", which
    # sent the owner to re-authorise a connection Google had already accepted.
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = str((json.loads(exc.read().decode("utf-8", "replace")).get("error") or ""))
        except Exception:  # noqa: BLE001 - the code alone still tells the owner where to look
            pass
        raise TokenRefused(f"Google refused the stored token at its own endpoint (HTTP {exc.code})"
                           + (f": {detail}" if detail else "")
                           + ". If that is wrong and the token is fine, the client id or secret "
                             "belongs to a different app: the three must come from one client.") from None
    token = str(payload.get("access_token") or "")
    if not token:
        raise TokenRefused("Google answered the refresh request without an access token")
    return token


class TokenRefused(RuntimeError):
    pass


class MissingCredentials(RuntimeError):
    pass


def resolve_property(token: str, measurement_id: str) -> tuple[str, str]:
    """The Data API needs the numeric property id; find it from the measurement id if not set."""
    configured = (os.environ.get("GA4_PROPERTY_ID") or "").strip()
    if configured and not configured.startswith("G-"):
        return configured, "GA4_PROPERTY_ID repository variable"
    # The account tree is walked, not the property list. A bare `properties` list is refused by the
    # Admin API with "The value for the 'filter' field was empty, but must be provided" - which is what
    # broke the owner's first working connection on 21 October, after the token and its scope were both
    # already right. accountSummaries needs no filter and names every property the account holds.
    listing = http(f"{ADMIN_API_BETA}/accountSummaries", token=token)
    candidates: list[tuple[str, str]] = []
    for account in listing.get("accountSummaries") or []:
        for row in account.get("propertySummaries") or []:
            numeric = str(row.get("property") or "").rsplit("/", 1)[-1]
            if numeric.isdigit():
                candidates.append((numeric, str(row.get("displayName") or "")))
    for numeric, display in candidates:
        try:
            streams = http(f"{ADMIN_API_BETA}/properties/{numeric}/dataStreams", token=token)
        except urllib.error.HTTPError:
            continue                      # a property we may list but not open is not the one to bet on
        ids = [str(row.get("measurementId") or "") for row in streams.get("dataStreams") or []]
        if measurement_id in ids:
            return numeric, f"data stream {measurement_id} in this account" + (
                f", property \"{display}\"" if display else "")
    if len(candidates) == 1:
        # exactly one property and no matching stream is still an answer worth taking, but it is said
        # out loud how it was reached, because a wrong property would report the wrong numbers
        return candidates[0][0], ("the only property in this account, "
                                 f"\"{candidates[0][1] or 'unnamed'}\" - its data streams do not name "
                                 f"{measurement_id}")
    raise LookupError("no GA4 property in this account carries that measurement id; "
                      f"{len(candidates)} propert" + ("y" if len(candidates) == 1 else "ies") +
                      " were listed")


def number(cell) -> int:
    """One cell of a GA4 metric row, turned into a whole number.

    The Data API wraps a metric exactly as it wraps a dimension: the figure arrives as the *string*
    inside `{"value": "412"}`, and a metric with nothing to report arrives as an empty object rather
    than a zero. Until 21 October 2026 this file passed the whole object to `float()`, so a
    correctly authorised connection still ended as "the Analytics Data API could not be reached" -
    the failure looked like permissions and was really our own parser. Anything unreadable counts as
    no data, never as a crash and never as a guess.
    """
    value = cell.get("value") if isinstance(cell, dict) else cell
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


# GA4 asks for every field of a report by name, so the names live here once instead of inside a
# dict literal that a reader has to trust.
FULL_METRICS = ["screenPageViews", "activeUsers", "sessions", "engagedSessions"]
CORE_METRICS = ["screenPageViews", "activeUsers"]
ROW_KEYS = {"screenPageViews": "views", "activeUsers": "activeUsers", "sessions": "sessions",
            "engagedSessions": "engagedSessions"}


def named(field) -> dict:
    """One GA4 field, spelled the way `runReport` requires: an object carrying a name, not a bare word."""
    return field if isinstance(field, dict) else {"name": str(field)}


def report_request(metrics: list[str]) -> dict:
    """The body of the seven-day `runReport` call.

    `dimensions` is a list of objects, exactly like `metrics`. The fourth check run on 21 October 2026
    died on Google's `Invalid value at 'dimensions[0]'
    (type.googleapis.com/google.analytics.data.v1beta.Dimension), "date"` because the request held the
    bare word `"date"`, while the owner's authorisation had been correct since the first round.
    `named()` accepts either spelling, so a later edit cannot reintroduce the crash.
    """
    today = datetime.now(timezone.utc).date()
    return {"dimensions": [named("date")], "metrics": [named(field) for field in metrics],
            "dateRanges": [{"startDate": (today - timedelta(days=DAYS)).isoformat(),
                            "endDate": (today - timedelta(days=1)).isoformat()}],
            "orderBys": [{"dimension": {"dimensionName": "date"}, "desc": True}],
            "limit": str(DAYS)}


def parse_rows(data: dict, metrics: list[str]) -> list[dict]:
    """One `runReport` answer, turned into one record per day.

    A metric Google had nothing to say about that day is 0. A metric that was never asked for is
    missing rather than zero, which is how `summarise` knows not to claim a reader count with no basis.
    """
    days: list[dict] = []
    for row in data.get("rows") or []:
        cells = [cell.get("value") if isinstance(cell, dict) else cell
                 for cell in row.get("dimensionValues") or []]
        values = [number(cell) for cell in row.get("metricValues") or []]
        day = str(cells[0] if cells else "").replace("-", "")
        if len(day) == 8:
            day = f"{day[0:4]}-{day[4:6]}-{day[6:8]}"
        if len(day) != 10:
            continue
        record = {"date": day}
        for position, field in enumerate(metrics):
            record[ROW_KEYS.get(field, field)] = values[position] if position < len(values) else 0
        days.append(record)
    return days


def daily_rows(token: str, property_id: str) -> tuple[list[dict], list[str]]:
    """The seven-day report, as (rows, fields Google would not answer for).

    A `400` naming a field means a metric has stopped existing under that name, which is Google's
    change to make, not the owner's. The two figures the milestone is counted on - views and people -
    have been stable since GA4 launched, so the request is rebuilt with those alone rather than leave
    someone pressing a button again for nothing. Any other code is re-raised untouched: a `403` in
    particular has to reach the classifier that decides whose permission is missing.
    """
    def ask(metrics: list[str]) -> list[dict]:
        data = http(f"{DATA_API}/properties/{property_id}:runReport", token=token,
                    body=report_request(metrics), method="POST")
        return parse_rows(data, metrics)

    try:
        return ask(FULL_METRICS), []
    except urllib.error.HTTPError as exc:
        if exc.code != 400:
            raise
        return ask(CORE_METRICS), [field for field in FULL_METRICS if field not in CORE_METRICS]


def summarise(rows: list[dict], tag: dict, property_id: str, property_source: str,
              dropped: list[str] | None = None) -> dict:
    views = sum(row.get("views") or 0 for row in rows)
    users = sum(row.get("activeUsers") or 0 for row in rows)
    # a field nobody asked for is not a zero: it is unknown, and printing 0 there would invent a
    # measurement Google refused to give
    have = lambda key: any(key in row for row in rows)
    sessions = sum(row.get("sessions") or 0 for row in rows) if have("sessions") else None
    engaged = sum(row.get("engagedSessions") or 0 for row in rows) if have("engagedSessions") else None
    # the owner's definition of the milestone, written 20 October 2026: not pageviews but people -
    # at least 50,000 readers a day, each opening one or two articles. GA4's engagedSessions is the
    # closest honest count of that, because it drops the visit that bounced without reading
    latest = rows[0] if rows else None
    # "readers" is the owner's own word for the milestone and GA4 has no field for it; engagedSessions
    # is the closest honest count. Where Google would not answer for that field the count falls back to
    # activeUsers on the same day, and the basis is named, so a ladder can never print a label that
    # does not match the number beside it.
    readers_field = ("engagedSessions" if latest and latest.get("engagedSessions") is not None
                     else "activeUsers")
    if rows and views:
        status = "MEASURED"
    elif rows or tag.get("installedHere") is True:
        status = "NO_DATA_YET"
    elif tag.get("installedHere") is None:
        status = "TAG_UNKNOWN"
    else:
        status = "TAG_NOT_OBSERVED"
    # a window with no rows is "nothing read yet", never a measured audience of zero: only a real
    # report from Google is allowed to put a number in this file
    measured = status == "MEASURED"
    views = views if measured else None
    users = users if measured else None
    sessions = sessions if measured else None
    return {"status": status, "ok": measured, "credentialSource": credential_label(),
            "measurementId": MEASUREMENT_ID,
            "measuredAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "windowDays": DAYS, "propertyId": property_id or None, "propertyIdSource": property_source,
            "measurementId": MEASUREMENT_ID, "siteTag": tag,
            "totals": {"views": views,
                       "viewsPerDay": round(views / DAYS, 1) if measured else None,
                       "activeUsers": users, "sessions": sessions, "engagedSessions": engaged,
                       "dailyReaders": (latest or {}).get(readers_field) if measured else None,
                       "readersBasis": ("GA4_ENGAGED_SESSIONS_LATEST_DAY"
                                        if readers_field == "engagedSessions"
                                        else "GA4_ACTIVE_USERS_LATEST_DAY"),
                       "readersDefinition": (
                           "engaged sessions on the most recent whole day: people who opened at "
                           "least one article and did not bounce" if readers_field == "engagedSessions"
                           else "active users on the most recent whole day: Google would not answer "
                                "for engagedSessions, so this counts people rather than reads"),
                       "droppedFields": list(dropped or []),
                       "daysWithRows": len(rows)},
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
        scopes: list[str] = []
        try:
            token = refresh_token()
            scopes = token_scopes(token)
            if scopes and not grants_analytics(scopes):
                # Google has answered for itself: this token was never given Analytics, so no call
                # could succeed and none is attempted. Naming the scopes beats describing a 403.
                raise PermissionError("the stored token carries only: " + ", ".join(scopes))
            property_id, source = resolve_property(token, MEASUREMENT_ID)
            rows, dropped = daily_rows(token, property_id)
        except MissingCredentials:
            status = "CREDENTIALS_MISSING"
        except TokenRefused as exc:
            status, report_error, rows = "TOKEN_REFUSED", str(exc)[:400], []
        except urllib.error.HTTPError as exc:
            # 400/401 from the token endpoint means the token itself is no longer accepted, which is a
            # different repair from a missing scope: one needs a fresh authorisation, the other needs
            # the same authorisation to include Analytics. A 403 needs splitting further still, so the
            # body Google sent is read and kept: without it three unrelated fixes look identical.
            try:  # a refusal with no body at all must not become an unclassified failure
                payload = json.loads(exc.read().decode("utf-8", "replace")) if exc.fp else {}
            except Exception:  # noqa: BLE001 - the body is a courtesy, not a guarantee
                payload = {}
            rows = []
            if exc.code == 403:
                status, message, reasons = classify_forbidden(payload)
                report_error = " ".join(part for part in (
                    f"HTTP 403 {message}".strip(),
                    ("reasons: " + ", ".join(dict.fromkeys(reasons))) if reasons else "") if part)
            else:
                # 400/401 here is NOT a refused token - the token was exchanged two lines up, and a
                # refusal there now raises TokenRefused. A 400 from an API call is Google rejecting the
                # request we built, which is our bug to fix, not the owner's connection.
                status = "PROPERTY_NOT_FOUND" if exc.code == 404 else (
                    "REQUEST_REJECTED" if exc.code in (400, 401) else "READ_FAILED")
                detail = str((payload.get("error") or {}).get("message") or "") if isinstance(payload, dict) else ""
                report_error = f"HTTP {exc.code}" + (f" {detail}" if detail else "")
        except PermissionError as exc:
            status, report_error, rows = "SCOPE_INSUFFICIENT", str(exc)[:300], []
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
                      "credentialSource": credential_label(), "tokenScopes": scopes,
                      "note": "the blog is not modified by this job"}
            if report_error:
                report["error"] = report_error
            if "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in report_error:
                # the one answer that saves someone an hour: this failure is about the scopes the
                # token was given, not about which client it belongs to, so the stored client id and
                # secret are innocent and must not be replaced as though they were the fault
                report["whatThisMeans"] = ("the stored client id and secret are fine for this failure: Google "
                                  "says the token itself carries too few permissions. Re-authorise with "
                                  "BOTH scope lines listed separately, and replace only GA4_REFRESH_TOKEN")
        else:
            report = summarise(rows, tag, property_id, source, dropped)

    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    totals = report.get("totals") or {}
    lines = [f"# GA4 measurement · {report['measuredAt']}", "",
             f"Status: **{report['status']}**", "",
             "- analytics tag observed on the live site: "
             + {True: "**yes**", False: "**no**", None: "**not checked**"}
               .get((report.get("siteTag") or {}).get("installedHere"), "**not checked**")
             + " (" + (", ".join((report.get("siteTag") or {}).get("measurementIds") or [])
                      or (report.get("siteTag") or {}).get("error")
                      or "no G- id on the page that came back") + ")",
             f"- property: **{report.get('propertyId') or 'not resolved'}** "
             f"({report.get('propertyIdSource') or 'unknown'})"]
    if report.get("tokenScopes"):
        lines.append("- what the stored token is permitted to do: "
                     + ", ".join("`" + str(x).rsplit("/", 1)[-1] + "`" for x in report["tokenScopes"]))
    if (report.get("totals") or {}).get("droppedFields"):
        # a field Google no longer offers is said out loud, because a smaller number with no
        # explanation reads as a fall in the audience
        lines.append("- counted without: " + ", ".join("`" + str(x) + "`"
                                                     for x in report["totals"]["droppedFields"])
                     + " - Google did not answer for those, so the figures below come from the fields"
                       " it did")
    if report.get("error"):
        lines.append("- google said: `" + str(report["error"])[:300] + "`")
    if report["ok"]:
        lines += [f"- views in the last {report['windowDays']} days: **{totals['views']:,}**",
                  f"- **views per day: {totals['viewsPerDay']}**",
                  f"- active users: **{totals['activeUsers']:,}**, sessions: **{totals['sessions']:,}**",
                  (f"- **readers on the latest whole day: {totals['dailyReaders']:,}** "
                   f"({totals['readersDefinition']})"
                   if isinstance(totals.get("dailyReaders"), int) else
                   "- readers on the latest whole day: that property reported no engaged-session "
                   "count, so it is left unmeasured rather than guessed"), "",
                  "| day | views | active users | sessions | engaged sessions |",
                  "| --- | --- | --- | --- | --- |"]
        lines += [f"| {row['date']} | {row['views']:,} | {row['activeUsers']:,} | {row['sessions']:,} | "
                  f"{row.get('engagedSessions', 0):,} |" for row in report.get("daily") or []]
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
