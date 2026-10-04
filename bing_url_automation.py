#!/usr/bin/env python3
"""Quota-aware Bing URL submission and index-status monitoring.

Daily Yield public URLs are never requested. Inventory comes from the authenticated
Blogger API; submission and status checks use Bing's control-plane APIs only.
Secrets are never written to evidence or included in raised error messages.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

SITE = "https://dailyyield.blogspot.com/"
OWN_HOST = "dailyyield.blogspot.com"
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
STATE_PATH = Path("BING_URL_AUTOMATION_STATE.json")
STATUS_JSON = Path("BING_URL_AUTOMATION_STATUS.json")
STATUS_MD = Path("BING_URL_AUTOMATION_STATUS.md")
BING_BASE = "https://ssl.bing.com/webmaster/api.svc/json"
INSPECTION_DELAYS = (6, 24, 72, 168)
# Evaluate a bounded number of pending records against the site-wide page-stats
# response each run; remaining records stay queued for later reconciliation.
MAX_INSPECTIONS_PER_RUN = min(10, max(1, int(os.environ.get("BING_MAX_INSPECTIONS_PER_RUN", "10"))))
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


class SafeApiError(RuntimeError):
    def __init__(self, service: str, code: int | str, detail: str = ""):
        self.service, self.code = service, code
        clean = " ".join((detail or "").split())[:220]
        super().__init__(f"{service} API error {code}" + (f": {clean}" if clean else ""))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or now_utc()).isoformat()


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required secret: {name}")
    return value


def safe_detail(raw: bytes) -> str:
    """Return bounded provider detail without URLs, query strings or secrets."""
    text = raw.decode("utf-8", "replace")[:1000]
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            candidate = payload.get("error_description") or payload.get("message") or payload.get("error")
            if isinstance(candidate, dict):
                candidate = candidate.get("message") or candidate.get("code")
            text = str(candidate or "provider returned a JSON error")
    except Exception:
        text = "provider returned a non-JSON error"
    return " ".join(text.split())[:220]


def json_request(url: str, *, service: str, method: str = "GET", headers=None, body=None,
                 retries: int = 0, timeout: int = 60) -> dict:
    if OWN_HOST in (urlparse(url).hostname or "").lower():
        raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    merged = {"User-Agent": "DailyYield-BingURLAutomation/1.0", **(headers or {})}
    if body is not None:
        merged["Content-Type"] = "application/json; charset=utf-8"
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=data, headers=merged, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = safe_detail(exc.read())
            if exc.code in TRANSIENT_HTTP and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise SafeApiError(service, exc.code, detail) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise SafeApiError(service, "NETWORK", exc.__class__.__name__) from exc
    raise SafeApiError(service, "UNKNOWN")


def blogger_oauth() -> str:
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode("utf-8")
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)["access_token"]
    except urllib.error.HTTPError as exc:
        raise SafeApiError("Google OAuth", exc.code, safe_detail(exc.read())) from exc


def fingerprint(item: dict) -> str:
    material = json.dumps({
        "title": item.get("title", ""), "content": item.get("content", ""),
        "labels": item.get("labels", []), "updated": item.get("updated", ""),
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def valid_daily_yield_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname == OWN_HOST and not parsed.fragment and not parsed.query


def blogger_inventory() -> list[dict]:
    token = blogger_oauth()
    headers = {"Authorization": "Bearer " + token}
    metadata = json_request(
        f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}?fields=id,name,url,updated",
        service="Blogger", headers=headers,
    )
    items = [{
        "id": "home", "kind": "home", "title": metadata.get("name", "Daily Yield"),
        "url": SITE, "updated": metadata.get("updated", ""), "content": "", "labels": [],
    }]
    for resource in ("pages", "posts"):
        page_token = ""
        while True:
            fields = "id,title,url,content,published,updated,status"
            if resource == "posts":
                fields += ",labels"
            params = {"status": "live", "fetchBodies": "true", "maxResults": "50", "fields": f"items({fields}),nextPageToken"}
            if page_token:
                params["pageToken"] = page_token
            data = json_request(
                f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{resource}?{urllib.parse.urlencode(params)}",
                service="Blogger", headers=headers,
            )
            for item in data.get("items", []):
                item["kind"] = resource[:-1]
                items.append(item)
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
    clean = []
    for item in items:
        url = item.get("url", "")
        if not valid_daily_yield_url(url):
            raise RuntimeError(f"Blogger returned an invalid/noncanonical URL for {item.get('kind')} {item.get('id')}")
        item["fingerprint"] = fingerprint(item)
        clean.append(item)
    return sorted(clean, key=lambda x: (x["kind"] != "home", x.get("published", ""), x["url"]))


def bing_url(operation: str, key: str, **params) -> str:
    # The key is required by Bing in the query string. This URL is never logged,
    # persisted or included in exceptions.
    query = urllib.parse.urlencode({**params, "apikey": key})
    return f"{BING_BASE}/{operation}?{query}"


def unwrap(payload: dict):
    return payload.get("d", payload) if isinstance(payload, dict) else payload


def get_quota(key: str) -> dict:
    payload = json_request(
        bing_url("GetUrlSubmissionQuota", key, siteUrl=SITE),
        service="Bing quota", retries=2,
    )
    data = unwrap(payload) or {}
    daily = max(0, int(data.get("DailyQuota", 0)))
    monthly_raw = data.get("MonthlyQuota")
    monthly = daily if monthly_raw is None else max(0, int(monthly_raw))
    return {"dailyAvailable": daily, "monthlyAvailable": monthly}


def submit_batch(key: str, urls: list[str]) -> None:
    if not urls or len(urls) > 500 or any(not valid_daily_yield_url(url) for url in urls):
        raise RuntimeError("invalid Bing submission batch")
    json_request(
        bing_url("SubmitUrlbatch", key), service="Bing submission", method="POST",
        body={"siteUrl": SITE, "urlList": urls}, retries=2,
    )


def get_page_stats(key: str) -> dict[str, dict]:
    """Return Bing-observed Daily Yield pages from Search Performance.

    Bing's GetUrlInfo family currently returns provider-side HTTP 400/UnknownError
    even for valid verified properties. GetPageStats remains supported and is a
    truthful control-plane signal: a URL present there has generated a Bing
    impression. Absence is kept as pending, never misrepresented as not indexed.
    """
    payload = json_request(
        bing_url("GetPageStats", key, siteUrl=SITE),
        service="Bing page stats", retries=2,
    )
    rows = unwrap(payload) or []
    if not isinstance(rows, list):
        return {}
    observed: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = row.get("Query", "")
        if not valid_daily_yield_url(url):
            continue
        previous = observed.setdefault(url, {"Impressions": 0, "Clicks": 0, "LatestDate": ""})
        previous["Impressions"] += max(0, int(row.get("Impressions", 0) or 0))
        previous["Clicks"] += max(0, int(row.get("Clicks", 0) or 0))
        previous["LatestDate"] = max(str(previous["LatestDate"]), str(row.get("Date", "")))
    return observed


def load_state() -> dict:
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(state, dict) and isinstance(state.get("urls"), dict):
            return state
    except Exception:
        pass
    return {"version": 1, "urls": {}}


def schedule_after(submitted_at: datetime, stage: int) -> str:
    delay = INSPECTION_DELAYS[min(stage, len(INSPECTION_DELAYS) - 1)]
    return iso(submitted_at + timedelta(hours=delay))


def write_evidence(report: dict) -> None:
    STATUS_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = report["summary"]
    lines = [
        "# Bing URL Submission and Index-Status Automation", "",
        f"- **Status:** {report['status']}", f"- **Checked:** {report['checkedAt']}",
        "- **Mode:** authenticated control-plane, zero public Daily Yield requests",
        "- **Synthetic Daily Yield views:** 0", "",
        "## Current run", "",
        f"- Blogger inventory: **{summary['inventory']}**",
        f"- Submission candidates: **{summary['candidates']}**",
        f"- URLs submitted: **{summary['submitted']}**",
        f"- Quota deferred: **{summary['quotaDeferred']}**",
        f"- URL-info checks: **{summary['inspected']}**",
        f"- Known/crawled by Bing: **{summary['knownToBing']}**",
        f"- Pending monitoring: **{summary['pendingMonitoring']}**",
        f"- Removed inventory alerts: **{summary['removedAlerts']}**", "",
        "## Guardrails", "",
        "- API key remains only in the GitHub secret and is never written to evidence.",
        "- No public Daily Yield URL, Bing Live URL fetch or synthetic pageview is created.",
        "- Unchanged URLs are not resubmitted.",
        "- Submission does not guarantee crawling, indexing, ranking or traffic.", "",
    ]
    if report.get("errors"):
        lines += ["## Errors", ""] + [f"- {error}" for error in report["errors"]] + [""]
    if report.get("warnings"):
        lines += ["## Provider warnings", ""] + [f"- {warning}" for warning in report["warnings"]] + [""]
    STATUS_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    started = now_utc()
    key = required("BING_WEBMASTER_API_KEY")
    inventory = blogger_inventory()
    state = load_state()
    records = state["urls"]
    current_urls = {item["url"] for item in inventory}
    removed = sorted(set(records) - current_urls)
    errors: list[str] = []

    for url in removed:
        records[url]["status"] = "REMOVED_INVENTORY_ALERT"
        records[url]["lastSeenAt"] = records[url].get("lastSeenAt", "")

    candidates = []
    for item in inventory:
        url = item["url"]
        record = records.setdefault(url, {})
        record.update({
            "bloggerId": item.get("id", ""), "kind": item["kind"],
            "title": item.get("title", ""), "updated": item.get("updated", ""),
            "fingerprint": item["fingerprint"], "lastSeenAt": iso(started),
        })
        if record.get("submittedFingerprint") != item["fingerprint"]:
            candidates.append(item)
            record["status"] = "SUBMISSION_PENDING"

    # When quota is limited, protect new/current publications before historical
    # backfill. The homepage remains first, then the most recently published or
    # updated items. Deferred URLs keep their fingerprint and are retried later.
    def candidate_priority(item: dict):
        freshness = parse_time(item.get("published", "")) or parse_time(item.get("updated", ""))
        stamp = freshness.timestamp() if freshness else 0.0
        return (0 if item["kind"] == "home" else 1, -stamp, item["url"])

    candidates.sort(key=candidate_priority)
    quota = {"dailyAvailable": 0, "monthlyAvailable": 0}
    submitted = []
    deferred = []
    try:
        quota = get_quota(key)
        available = min(quota["dailyAvailable"], quota["monthlyAvailable"])
        selected, deferred = candidates[:available], candidates[available:]
        for offset in range(0, len(selected), 500):
            batch = selected[offset:offset + 500]
            submit_batch(key, [item["url"] for item in batch])
            submitted.extend(batch)
        submission_time = now_utc()
        for item in submitted:
            record = records[item["url"]]
            record.update({
                "submittedFingerprint": item["fingerprint"],
                "lastSubmittedAt": iso(submission_time), "status": "SUBMITTED",
                "inspectionStage": 0, "nextInspectionAt": schedule_after(submission_time, 0),
            })
        for item in deferred:
            records[item["url"]]["status"] = "QUOTA_DEFERRED"
    except Exception as exc:
        errors.append(str(exc))
        deferred = candidates
        for item in deferred:
            records[item["url"]]["status"] = "SUBMISSION_ERROR"

    # Inspect only URLs submitted in an earlier run. A submission never causes an
    # immediate public fetch from this automation.
    due = []
    current_time = now_utc()
    for url, record in records.items():
        if url not in current_urls or record.get("status") in ("MONITOR_COMPLETE", "BING_PERFORMANCE_OBSERVED"):
            continue
        next_at = parse_time(record.get("nextInspectionAt", ""))
        # Migrate records left by the provider-broken GetUrlInfo monitor into the
        # working page-performance reconciliation immediately.
        if record.get("status") == "INSPECTION_ERROR" and record.get("monitorVersion") != 2:
            next_at = current_time
            record["nextInspectionAt"] = iso(current_time)
        if record.get("lastSubmittedAt") and next_at and next_at <= current_time:
            due.append((next_at, url, record))
    due.sort(key=lambda row: (row[0], row[1]))
    inspected = 0
    warnings: list[str] = []
    observed_pages: dict[str, dict] = {}
    stats_available = not due
    if due:
        try:
            observed_pages = get_page_stats(key)
            stats_available = True
        except Exception as exc:
            # Search Performance is supplementary monitoring. Submission/quota
            # errors remain fatal, but a reporting outage must not turn a valid
            # zero-view submission run into repeated failure notifications.
            warnings.append(str(exc))
    for _, url, record in due[:MAX_INSPECTIONS_PER_RUN]:
        inspected += 1
        record["lastInspectedAt"] = iso()
        record["monitorVersion"] = 2
        if not stats_available:
            record["status"] = "MONITORING_PROVIDER_DELAY"
            record["nextInspectionAt"] = iso(current_time + timedelta(hours=2))
            continue
        if url in observed_pages:
            record["lastPageStats"] = observed_pages[url]
            record["status"] = "BING_PERFORMANCE_OBSERVED"
            record["nextInspectionAt"] = ""
            continue
        stage = int(record.get("inspectionStage", 0)) + 1
        record["inspectionStage"] = stage
        submitted_at = parse_time(record.get("lastSubmittedAt", "")) or current_time
        if stage >= len(INSPECTION_DELAYS):
            record["status"] = "NO_PERFORMANCE_SIGNAL_AFTER_7_DAYS"
            record["nextInspectionAt"] = ""
        else:
            record["status"] = "MONITORING_PENDING"
            record["nextInspectionAt"] = schedule_after(submitted_at, stage)

    state.update({
        "version": 1, "site": SITE, "updatedAt": iso(),
        "mode": "BING_AND_BLOGGER_CONTROL_PLANE_ZERO_PUBLIC_VIEWS",
        "syntheticViews": 0, "urls": records,
    })
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    known_count = sum(r.get("status") == "BING_PERFORMANCE_OBSERVED" for u, r in records.items() if u in current_urls)
    pending_count = sum(r.get("status") in ("SUBMITTED", "MONITORING_PENDING", "MONITORING_PROVIDER_DELAY") for u, r in records.items() if u in current_urls)
    report = {
        "checkedAt": iso(), "status": "PASS" if not errors else "ATTENTION",
        "mode": "BING_AND_BLOGGER_CONTROL_PLANE_ZERO_PUBLIC_VIEWS", "syntheticViews": 0,
        "site": SITE, "quota": quota,
        "summary": {
            "inventory": len(inventory), "candidates": len(candidates), "submitted": len(submitted),
            "quotaDeferred": len(deferred), "inspected": inspected, "knownToBing": known_count,
            "pendingMonitoring": pending_count, "removedAlerts": len(removed),
        },
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "notes": [
            "Bing GetPageStats supplies a performance-observed signal; absence is not represented as proof that a URL is unindexed.",
            "The provider-failing GetUrlInfo family is not called.",
            "No Live URL fetch is performed.",
            "Submission does not guarantee crawling, indexing, ranking or traffic.",
        ],
    }
    write_evidence(report)
    print(json.dumps({"status": report["status"], **report["summary"], "syntheticViews": 0}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
