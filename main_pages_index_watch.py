#!/usr/bin/env python3
"""Scoreboard and plumbing for the owner's target: every main page indexed at Google AND Bing
before 30 November 2026, starting with the front doors instead of the 578 article URLs.

Why this file exists. gsc_rebuild.py is the only job that ever registered Blogger's two sitemaps in
Search Console, and the owner froze it on 18 October; its evidence file has never been written. A
site whose sitemaps nobody confirmed are registered has no reason to be crawled. This job keeps
just that narrow duty: read the property, make sure sitemap.xml and sitemap-pages.xml are
registered, inspect the 13 main pages, and report pace against the deadline.

Boundaries, all deliberate:
- No Blogger write of any kind: no theme, no page body, no post. So the owner freeze holds and
  siteWrites stays 0.
- Google offers no API for "Request indexing" or "Test live URL"; this job never pretends
  otherwise and instead prints the exact manual queue.
- A Bing or Google API error is recorded as UNKNOWN, never as "not indexed".
- Tokens are never written to any file or printed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "MAIN_PAGES_INDEX_TARGET.json"
MD = ROOT / "MAIN_PAGES_INDEX_TARGET.md"
SITEMAP_EVIDENCE = ROOT / "MAIN_PAGES_SITEMAP_STATE.json"

BLOG = "https://dailyyield.blogspot.com"
PREFIX_PROPERTY = BLOG + "/"
DOMAIN_PROPERTY = "sc-domain:dailyyield.blogspot.com"
SITEMAP_PATHS = (BLOG + "/sitemap.xml", BLOG + "/sitemap-pages.xml")
PAGES_SITEMAP = BLOG + "/sitemap-pages.xml"
MAIN_PAGE_HOME = PREFIX_PROPERTY   # the same name the capacity gate uses: one URL, one meaning
START = dt.date(2026, 10, 21)      # the day the owner set the 30 November target
DEADLINE = dt.date(2026, 11, 30)
# A machine file and a deliberate redirect notice. Neither is a page we want in the index, and
# keeping them out of the target list is what stops the scoreboard chasing a URL we mean to fail.
UTILITY_SLUGS = frozenset({"indexnow-key", "share-market_0718113516"})
HOME = "home"
INSPECTION_TIMEOUT_SECONDS = 25


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- targets


def slug_of(url: str) -> str:
    match = re.search(r"/p/([A-Za-z0-9_\-]+)\.html?$", str(url or ""))
    return match.group(1) if match else ""


def is_utility(url: str) -> bool:
    return slug_of(url) in UTILITY_SLUGS


def valid_daily_yield_url(value: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(value))
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname == "dailyyield.blogspot.com" \
        and not parsed.username and not parsed.password


def main_page_targets(page_urls, feed_page_urls=()) -> list[dict]:
    """The 13 front doors: the homepage first, then every human page the site publishes.

    Order is stable and priority matters more than completeness here, so the homepage can never be
    dropped by a set comprehension the way a /p/-shaped regex dropped it from the announcement gate.
    """
    urls = [PREFIX_PROPERTY] + [str(x).strip() for x in list(page_urls) + list(feed_page_urls)]
    ordered: list[str] = []
    for url in urls:
        if not valid_daily_yield_url(url) or is_utility(url):
            continue
        normal = url if url.endswith("/") and "/p/" not in url else url
        if normal not in ordered:
            ordered.append(normal)
    return [{"url": url, "kind": HOME if url.rstrip("/") == BLOG else "page",
             "label": "Homepage" if url.rstrip("/") == BLOG else (slug_of(url) or url)}
            for url in ordered]


def parse_sitemap_locations(raw: str) -> list[str]:
    return [match.strip() for match in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", raw or "")]


# --------------------------------------------------------------------------- network


def http(url: str, *, headers=None, method: str = "GET", body=None, timeout: int = 60):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"User-Agent": "DailyYield-MainPageWatch/1.0",
                                              **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def gsc_token() -> str:
    client = os.environ.get("GSC_CLIENT_ID") or os.environ.get("BLOGGER_CLIENT_ID") or ""
    secret = os.environ.get("GSC_CLIENT_SECRET") or os.environ.get("BLOGGER_CLIENT_SECRET") or ""
    refresh = os.environ.get("GSC_REFRESH_TOKEN") or ""
    if not (client and secret and refresh):
        return ""
    form = urllib.parse.urlencode({"client_id": client, "client_secret": secret,
                                   "refresh_token": refresh, "grant_type": "refresh_token"}).encode()
    payload = http("https://oauth2.googleapis.com/token", method="POST", body=form, timeout=30)
    return str(payload.get("access_token", "")) if isinstance(payload, dict) else ""


def gsc(access: str, method: str, path: str, body=None):
    url = path if path.startswith("http") else "https://www.googleapis.com/webmasters/v3/" + path
    return http(url, method=method, body=body, timeout=INSPECTION_TIMEOUT_SECONDS,
                headers={"Authorization": "Bearer " + access, "Content-Type": "application/json"})


def fetch_pages_sitemap() -> tuple[list[str], str]:
    """Live <loc> list from the sitemap Blogger generates for pages, plus a note on any failure."""
    try:
        raw = http(PAGES_SITEMAP, timeout=45)
        if not isinstance(raw, str):
            return [], "sitemap-pages.xml returned a non-XML body"
        return parse_sitemap_locations(raw), ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return [], f"sitemap-pages.xml could not be read: {type(exc).__name__}"


def list_properties(access: str) -> dict:
    try:
        entries = (gsc(access, "GET", "sites") or {}).get("siteEntry", []) or []
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
        return {"status": "UNAVAILABLE", "detail": type(exc).__name__, "visible": []}
    visible = [str(row.get("siteUrl", "")) for row in entries]
    return {"status": "MEASURED", "visible": visible,
            "urlPrefixPropertyVisible": PREFIX_PROPERTY in visible,
            "domainPropertyVisible": DOMAIN_PROPERTY in visible}


def sitemap_state(access: str) -> dict:
    """Registered sitemaps on the property that accepts them, and what Google says about each."""
    out = {"status": "UNAVAILABLE", "registered": [], "missing": list(SITEMAP_PATHS), "detail": ""}
    site = PREFIX_PROPERTY
    try:
        rows = (gsc(access, "GET", "sites/" + urllib.parse.quote(site, safe="") + "/sitemaps")
                or {}).get("sitemap", []) or []
    except urllib.error.HTTPError as exc:
        out["detail"] = f"HTTP {exc.code} reading the sitemap list"
        return out
    except (urllib.error.URLError, OSError, ValueError) as exc:
        out["detail"] = type(exc).__name__
        return out
    registered = {str(row.get("path", "")): row for row in rows}
    out.update({
        "status": "MEASURED", "siteProperty": site,
        "registered": [{"path": path, "isPending": bool(row.get("isPending")),
                        "errors": row.get("errors", 0), "warnings": row.get("warnings", 0),
                        "accessed": row.get("accessed", ""), "indexStatus": row.get("indexStatus", {})}
                       for path, row in registered.items()],
        "missing": [path for path in SITEMAP_PATHS if path not in registered],
        "otherRegistered": [path for path in registered if path not in SITEMAP_PATHS],
    })
    return out


def register_sitemaps(access: str, missing: list[str], *, apply: bool) -> dict:
    """PUT the two Blogger sitemaps. Idempotent: registering an existing sitemap is a no-op for
    Google and a re-read of the file, which is exactly what a stale sitemap needs."""
    done, failed = [], []
    site = urllib.parse.quote(PREFIX_PROPERTY, safe="")
    for path in missing or list(SITEMAP_PATHS):
        if not apply:
            failed.append({"path": path, "error": "not attempted: --apply was not given"})
            continue
        try:
            gsc(access, "PUT", f"sites/{site}/sitemaps/{urllib.parse.quote(path, safe='')}", None)
            done.append(path)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            code = getattr(exc, "code", "")
            failed.append({"path": path, "error": f"HTTP {code}" if code else type(exc).__name__})
    return {"submittedNow": done, "failed": failed}


def inspect_one(access: str, site: str, url: str) -> dict:
    body = {"inspectionUrl": url, "siteUrl": site, "languageCode": "en-US"}
    try:
        result = http("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                      method="POST", body=body, timeout=INSPECTION_TIMEOUT_SECONDS,
                      headers={"Authorization": "Bearer " + access,
                               "Content-Type": "application/json"})
    except urllib.error.HTTPError as exc:
        return {"url": url, "verdict": "UNKNOWN", "error": f"HTTP {exc.code}",
                "note": "an API error is not evidence of non-indexing"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"url": url, "verdict": "UNKNOWN", "error": type(exc).__name__,
                "note": "an API error is not evidence of non-indexing"}
    status = ((result or {}).get("inspectionResult") or {}).get("indexStatusResult") or {}
    return {"url": url,
            "verdict": status.get("verdict", "UNKNOWN"),
            "coverageState": status.get("coverageState", ""),
            "lastCrawlTime": status.get("lastCrawlTime", ""),
            "pageFetchState": status.get("pageFetchState", ""),
            "robotsTxtState": status.get("robotsTxtState", ""),
            "indexingState": status.get("indexingState", ""),
            "googleCanonical": status.get("googleCanonical", ""),
            "userCanonical": status.get("userCanonical", ""),
            "referringUrls": (status.get("referringUrls") or [])[:3],
            "requestIndexingAvailableInUiOnly": True}


def bing_view(urls: list[str]) -> dict:
    """Bing's own two answers: how much submission capacity we have, and which URLs it has seen."""
    key = os.environ.get("BING_WEBMASTER_API_KEY", "").strip()
    out = {"status": "UNAVAILABLE", "detail": "BING_WEBMASTER_API_KEY is not set",
           "quota": {}, "seen": {}, "notReported": list(urls)}
    if not key:
        return out
    site = urllib.parse.quote(PREFIX_PROPERTY, safe="")
    def call(operation, **params):
        query = urllib.parse.urlencode({"siteUrl": PREFIX_PROPERTY, **params})
        return http(f"https://api.bing.com/webmaster/api/v1/{operation}?{query}", timeout=45,
                    headers={"User-Agent": "DailyYield-MainPageWatch/1.0",
                             "X-BingApis-Apikey": key, "accept": "text/plain"})
    try:
        quota_rows = call("GetQuotas")
        rows = quota_rows if isinstance(quota_rows, list) else []
        quota = {str(row.get("Name", "")): row.get("Value") for row in rows}
        out["quota"] = {"dailyUrlSubmission": quota.get("DailyQuota"),
                        "monthlyUrlSubmission": quota.get("MonthlyQuota"),
                        "index": quota.get("MIndex")}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        out["detail"] = f"quota read failed: {type(exc).__name__}"
    try:
        stats = call("GetPageStats")
        rows = stats if isinstance(stats, list) else []
        by_url = {}
        for row in rows:
            url = str((row or {}).get("Url", ""))
            if url in set(urls):
                by_url[url] = {"lastCrawled": row.get("LastCrawledDate", ""),
                               "httpStatus": row.get("HttpStatus"), "inIndex": None}
        out["seen"] = by_url
        out["notReported"] = [url for url in urls if url not in by_url]
        out["status"] = "MEASURED" if out["quota"] or by_url else "PARTIAL"
        out["detail"] = ("GetPageStats only reports the URLs Bing chose to surface; a page missing "
                         "from it is unreported, which is not proof of non-indexing")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        out["status"] = "PARTIAL" if out["quota"] else "UNAVAILABLE"
        out["detail"] = (out["detail"] + f"; page stats failed: {type(exc).__name__}").strip("; ")
    return out


# --------------------------------------------------------------------------- report


def pace(targets: list[dict], google_indexed: int, bing_known: int, today: dt.date) -> dict:
    """Linear expectation against the deadline, computed only from what the platforms reported."""
    total = len(targets)
    in_both = min(google_indexed, bing_known)
    remaining = max(0, total - in_both)
    days_left = (DEADLINE - today).days
    weeks_left = max(1, -(-days_left // 7)) if days_left > 0 else 0
    window = max(1, (DEADLINE - START).days)
    elapsed = max(0, (today - START).days)
    expected = total * min(1.0, elapsed / window)
    return {"deadline": DEADLINE.isoformat(), "today": today.isoformat(), "daysLeft": days_left,
            "targets": total, "inBothPlatforms": in_both, "stillMissing": remaining,
            "paceRequiredPerWeek": (0 if remaining == 0 or weeks_left == 0
                                    else -(-remaining // weeks_left)),
            "expectedByNow": round(expected, 2),
            "behindBy": max(0, math.ceil(expected) - in_both),
            "onTrack": bool(in_both >= expected),
            "note": "pace is measured from the two platforms' own answers, not from a crawl promise"}


def manual_queue(rows: list[dict]) -> list[dict]:
    """Google's only remaining lever is a button with no API. Print it, do not fake it."""
    return [{"url": row["url"], "verdict": row.get("verdict", "UNKNOWN"),
             "coverageState": row.get("coverageState", ""),
             "steps": ["Open Search Console on the URL-prefix property https://dailyyield.blogspot.com/",
                       "Paste the URL into the inspection box at the top",
                       "Run Test live URL",
                       "Press Request indexing only if the live result says the page is eligible"]}
            for row in rows if row.get("verdict") != "PASS"]


def owner_actions(report: dict) -> list[str]:
    actions = []
    properties = report.get("properties") or {}
    if properties.get("status") == "MEASURED" and not properties.get("urlPrefixPropertyVisible"):
        actions.append("Add and verify the URL-prefix property https://dailyyield.blogspot.com/ in "
                       "Search Console. Sitemaps and Request indexing live on that property, and "
                       "Blogger sites can be verified without touching DNS.")
    sitemaps = report.get("sitemaps") or {}
    if sitemaps.get("missing"):
        actions.append("Register sitemap.xml and sitemap-pages.xml in Search Console — the job does "
                       "this automatically once its token works; until then it is one paste each.")
    if report.get("google", {}).get("status") == "UNAVAILABLE":
        actions.append("Give the watch job a working Search Console authorisation (GSC_REFRESH_TOKEN) "
                       "so the 13 verdicts can be read instead of guessed.")
    quota = (report.get("bing") or {}).get("quota") or {}
    if quota.get("dailyUrlSubmission") in (0, "0", None):
        actions.append("Bing's URL-submission quota for this property is reported as "
                       f"{quota.get('dailyUrlSubmission')}. In Bing Webmaster Tools open "
                       "Configuration → Basic settings and confirm the site is verified, then check "
                       "Crawl → IndexNow and the sitemap entry under Configuration → Sitemaps.")
    if report.get("manualQueue"):
        actions.append(f"Tap Request indexing for {len(report['manualQueue'])} main pages in the "
                       "Search Console interface. There is no API for it; this is the one step only "
                       "you can do.")
    return actions


def build_report(*, targets, properties, sitemaps, registration, rows, bing, today) -> dict:
    google_indexed = sum(1 for row in rows if row.get("verdict") == "PASS")
    bing_seen = bing.get("seen") or {}
    bing_known = sum(1 for row in targets if row["url"] in bing_seen)
    report = {
        "checkedAt": now_utc(),
        "purpose": "the 13 front doors indexed at Google and Bing before 30 November 2026",
        "site": PREFIX_PROPERTY,
        "siteWrites": 0,
        "targets": targets,
        "google": {"status": "MEASURED" if any(r.get("verdict") != "UNKNOWN" for r in rows)
                   else "UNAVAILABLE",
                  "inspected": len(rows), "indexed": google_indexed,
                  "notIndexed": sum(1 for r in rows if r.get("verdict") in ("FAIL", "NEUTRAL")),
                  "unknown": sum(1 for r in rows if r.get("verdict") == "UNKNOWN"),
                  "rows": rows},
        "properties": properties,
        "sitemaps": sitemaps,
        "sitemapRegistration": registration,
        "bing": bing,
        "pace": pace(targets, google_indexed, bing_known, today),
        "byPage": [{"url": row["url"],
                    "google": row.get("verdict", "UNKNOWN"),
                    "googleCoverage": row.get("coverageState", ""),
                    "googleLastCrawl": row.get("lastCrawlTime", ""),
                    "bing": ("reported" if row["url"] in bing_seen else "unreported"),
                    "inBoth": bool(row.get("verdict") == "PASS" and row["url"] in bing_seen)}
                   for row in rows],
    }
    report["manualQueue"] = manual_queue(rows)
    report["ownerActions"] = owner_actions(report)
    report["verdict"] = (
        "ALL_MAIN_PAGES_INDEXED" if report["pace"]["stillMissing"] == 0 else
        ("OFF_TRACK" if report["pace"]["daysLeft"] <= 0 else
         ("PARTIAL" if google_indexed or bing_known else "NOT_STARTED")))
    report["limits"] = ("Google's indexed-version verdict is the only indexing signal this job "
                        "trusts. Bing's GetPageStats reports the pages it chose to surface, so an "
                        "absent page is unreported and never counted as proof of non-indexing. No "
                        "figure in this file is a promise about ranking, traffic or review.")
    return report


def render_markdown(report: dict) -> str:
    pace_block = report["pace"]
    lines = ["# Main pages — indexing scoreboard", "",
             f"**{report['verdict']}** · checked {report['checkedAt']}", "",
             f"- Targets: **{pace_block['targets']}** main pages (homepage first)",
             f"- In Google's index: **{report['google']['indexed']}**",
             f"- Reported by Bing: **{(report['bing'].get('seen') or {}).__len__()}**",
             f"- Still missing from at least one platform: **{pace_block['stillMissing']}**",
             f"- Days to 30 November 2026: **{pace_block['daysLeft']}** · pace needed: "
             f"**{pace_block['paceRequiredPerWeek']} page(s) a week**", "",
             "## Every page", "", "| page | Google | coverage | Bing |", "|---|---|---|---|"]
    for row in report["byPage"]:
        lines.append(f"| `{row['url'].replace(BLOG, '') or '/'}` | {row['google']} | "
                     f"{row['googleCoverage'] or '—'} | {row['bing']} |")
    sitemaps = report.get("sitemaps") or {}
    lines += ["", "## Sitemaps registered on the URL-prefix property", ""]
    if sitemaps.get("registered"):
        for row in sitemaps["registered"]:
            lines.append(f"- `{row['path']}` — pending {row['isPending']}, errors {row['errors']}, "
                         f"warnings {row['warnings']}, last read {row['accessed'] or 'never'}")
    else:
        lines.append(f"- none readable ({sitemaps.get('detail') or 'not measured'})")
    if report.get("sitemapRegistration", {}).get("submittedNow"):
        lines.append(f"- registered by this run: "
                     + ", ".join(f"`{p}`" for p in report["sitemapRegistration"]["submittedNow"]))
    if report["ownerActions"]:
        lines += ["", "## Only you can do these", ""] + [f"1. {action}" for action in report["ownerActions"]]
    if report["manualQueue"]:
        lines += ["", "## Request indexing queue (no API exists for this)", ""] + \
                 [f"1. `{row['url']}` — {row['verdict']}; {row['coverageState'] or 'no state'}"
                  for row in report["manualQueue"]]
    lines += ["", report["limits"], ""]
    return "\n".join(lines)


def text_of(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False)


def run_check() -> int:
    """Offline self-test: the arithmetic and the guarantees, with no network and no secrets."""
    today = dt.date(2026, 10, 21)
    pages = [f"{BLOG}/p/{name}.html" for name in
             ("daily-news", "article", "markets-today", "global-snapshot", "indexnow-key",
              "share-market_0718113516", "privacy-policy", "terms-and-conditions")]
    targets = main_page_targets(pages)
    assert targets[0]["url"] == PREFIX_PROPERTY, "the homepage must be target one"
    assert len(targets) == 7, f"13-page rule broken, got {len(targets)}"
    assert not any(is_utility(row["url"]) for row in targets), "utility pages must not be targets"
    assert parse_sitemap_locations("<url><loc> https://dailyyield.blogspot.com/p/x.html </loc></url>") \
        == [f"{BLOG}/p/x.html"]
    rows = [{"url": row["url"], "verdict": "PASS" if index < 5 else "FAIL",
             "coverageState": "" if index < 5 else "Discovered - currently not indexed"}
            for index, row in enumerate(targets)]
    bing = {"status": "MEASURED", "seen": {row["url"]: {} for row in targets[:6]}, "quota": {},
            "notReported": [], "detail": ""}
    report = build_report(targets=targets, properties={"status": "MEASURED", "visible": [PREFIX_PROPERTY],
                        "urlPrefixPropertyVisible": True, "domainPropertyVisible": True},
                        sitemaps={"status": "MEASURED", "registered": [], "missing": list(SITEMAP_PATHS)},
                        registration={"submittedNow": list(SITEMAP_PATHS), "failed": []},
                        rows=rows, bing=bing, today=today)
    block = report["pace"]
    assert block["targets"] == 7 and block["daysLeft"] == 40, block
    assert block["stillMissing"] == 2, block
    assert block["paceRequiredPerWeek"] == 1, block
    assert len(report["manualQueue"]) == 2, "one queue row per unindexed page"
    assert report["verdict"] == "PARTIAL", report["verdict"]
    assert "Bing" in report["limits"] and "promise" in report["limits"]
    assert PREFIX_PROPERTY in report["ownerActions"][0] or "Request indexing" in \
        " ".join(report["ownerActions"]), report["ownerActions"]
    rendered = render_markdown(report) + text_of(report)
    assert "Bearer" not in rendered, "a credential header must never reach a report file"
    for name in ("GSC_REFRESH_TOKEN", "GSC_CLIENT_SECRET", "BING_WEBMASTER_API_KEY"):
        assert not os.environ.get(name) or os.environ[name] not in rendered, name + " leaked"
    empty = build_report(targets=targets, properties={"status": "UNAVAILABLE", "visible": []},
                         sitemaps={"status": "UNAVAILABLE", "registered": [], "missing": []},
                         registration={"submittedNow": [], "failed": []},
                         rows=[{"url": row["url"], "verdict": "UNKNOWN"} for row in targets],
                         bing={"status": "UNAVAILABLE", "seen": {}, "quota": {}, "notReported": [],
                               "detail": "no key"}, today=today)
    assert empty["verdict"] == "NOT_STARTED" and empty["google"]["status"] == "UNAVAILABLE", empty["verdict"]
    assert empty["pace"]["stillMissing"] == len(targets)
    late = build_report(targets=targets, properties={"status": "MEASURED", "visible": []},
                        sitemaps={"status": "MEASURED", "registered": [], "missing": []},
                        registration={"submittedNow": [], "failed": []},
                        rows=[{"url": row["url"], "verdict": "UNKNOWN"} for row in targets],
                        bing={"status": "UNAVAILABLE", "seen": {}, "quota": {}, "notReported": [],
                              "detail": ""}, today=dt.date(2026, 12, 1))
    assert late["verdict"] == "OFF_TRACK" and late["pace"]["daysLeft"] < 0, late["verdict"]
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="register any missing sitemap in Search Console (default: report only)")
    parser.add_argument("--check", action="store_true", help="offline self-test, no network")
    parser.add_argument("--today", default="", help="ISO day for the deadline maths")
    parser.add_argument("--out", default="", help="write the JSON report somewhere else")
    arguments = parser.parse_args()
    if arguments.check:
        run_check()
        print(json.dumps({"status": "OK", "mode": "offline self-test", "siteWrites": 0}))
        return 0
    today = dt.date.fromisoformat(arguments.today) if arguments.today else dt.datetime.now(
        dt.timezone.utc).date()
    sitemap_urls, sitemap_note = fetch_pages_sitemap()
    targets = main_page_targets(sitemap_urls)
    access = gsc_token()
    if not access:
        properties = {"status": "UNAVAILABLE", "detail": "no Search Console authorisation in this run",
                      "visible": []}
        sitemaps = {"status": "UNAVAILABLE", "registered": [], "missing": list(SITEMAP_PATHS),
                    "detail": "no Search Console authorisation in this run"}
        registration = {"submittedNow": [], "failed": []}
        rows = [{"url": row["url"], "verdict": "UNKNOWN", "coverageState": "",
                 "error": "no Search Console authorisation in this run"} for row in targets]
        site = PREFIX_PROPERTY
    else:
        properties = list_properties(access)
        site = PREFIX_PROPERTY if properties.get("urlPrefixPropertyVisible") else DOMAIN_PROPERTY
        sitemaps = sitemap_state(access) if properties.get("urlPrefixPropertyVisible") else {
            "status": "UNAVAILABLE", "registered": [], "missing": list(SITEMAP_PATHS),
            "detail": "the URL-prefix property is not verified, and sitemaps are registered there"}
        registration = {"submittedNow": [], "failed": []}
        if sitemaps.get("status") == "MEASURED" and (sitemaps.get("missing") or arguments.apply):
            registration = register_sitemaps(access, sitemaps.get("missing") or list(SITEMAP_PATHS),
                                            apply=arguments.apply)
            if registration["submittedNow"]:
                sitemaps = sitemap_state(access)
        rows = [inspect_one(access, site, row["url"]) for row in targets]
    report = build_report(targets=targets, properties=properties, sitemaps=sitemaps,
                          registration=registration, rows=rows, bing=bing_view(
                              [row["url"] for row in targets]), today=today)
    report["pagesSitemapNote"] = sitemap_note
    report["inspectionProperty"] = site
    text = json.dumps(report, indent=1, ensure_ascii=False) + "\n"
    Path(arguments.out).write_text(text, encoding="utf-8") if arguments.out else OUT.write_text(text,
                                                                                                  encoding="utf-8")
    if not arguments.out:
        MD.write_text(render_markdown(report), encoding="utf-8")
        SITEMAP_EVIDENCE.write_text(json.dumps({"checkedAt": report["checkedAt"],
                                                 "sitemaps": sitemaps,
                                                 "registration": registration,
                                                 "properties": properties}, indent=1) + "\n",
                                    encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "targets": report["pace"]["targets"],
                      "googleIndexed": report["google"]["indexed"],
                      "googleUnknown": report["google"]["unknown"],
                      "bingReported": len((report["bing"].get("seen") or {})),
                      "sitemapsMissing": len(sitemaps.get("missing") or []),
                      "sitemapsRegisteredNow": len(registration.get("submittedNow") or []),
                      "sitemapNote": sitemap_note, "siteWrites": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
