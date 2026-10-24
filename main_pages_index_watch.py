#!/usr/bin/env python3
"""Scoreboard and plumbing for the owner's target: every main page indexed at Google

Bing was part of this target until 23 October 2026, when the owner removed the property from Bing
Webmaster Tools. The target is now Google alone, and no call in this file goes anywhere else.
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
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

bing = None   # the Bing client was deleted on 23 October 2026 with the owner's instruction; never revived

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "MAIN_PAGES_INDEX_TARGET.json"
MD = ROOT / "MAIN_PAGES_INDEX_TARGET.md"
SITEMAP_EVIDENCE = ROOT / "MAIN_PAGES_SITEMAP_STATE.json"

BLOG = "https://dailyyield.blogspot.com"  # noqa: E501
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


# A plain browser identity, on purpose. This probe exists to learn whether the URL redirects, which
# is a fact about the host and not about Google; sending a Googlebot user-Agent made Blogger's own
# throttle answer instead of the page (measured: HTTP 429 after 1 redirect for eleven of thirteen).
PROBE_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0 Safari/537.36")
GOOGLEBOT_UA = PROBE_UA           # kept as a name because the audit and the tests refer to it
# The same question, asked as a phone. Six weeks of "the redirect is already gone" came from probing with
# one identity only: Blogger answers a desktop request with a direct 200 and answers any mobile client -
# Chrome on Android, Safari on iPhone, and therefore Google's smartphone crawler too - with
# "302 -> the same URL + ?m=1". A desktop-only probe cannot see that, so each URL is asked twice and a
# redirect-family verdict is only called stale when both answers are clean. Measured 22 October on the
# homepage, /p/daily-news.html and a post: mobile 302, desktop 200, every time.
# An honest browser identity, deliberately: this repository does not send Googlebot's User-Agent, because
# that is what got the runner throttled with 429s, and the redirect is a fact about the host for any
# mobile client, so impersonating a crawler buys nothing.
MOBILE_PROBE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Mobile Safari/537.36")
MOBILE_PROBE_SPACING_SECONDS = 2
LIVE_PROBE_SPACING_SECONDS = 8
LIVE_PROBE_CAP = 6
REDIRECT_FAMILY = ("Redirect error", "Page with redirect", "Duplicate without user-selected canonical",
                   "Alternate page with proper canonical")


def blogger_page_state() -> dict:
    """Ask Blogger itself which pages are live, without touching the public site.

    The repository already holds the authenticated Blogger path for other jobs, and it is the better
    instrument here: it cannot be rate limited, it cannot be confused by a theme, and it answers the
    exact question - is this page published at this URL. Absence of evidence from a public probe is
    then replaced by evidence from the publisher's own API.
    """
    names = ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN", "BLOGGER_BLOG_ID")
    if not all(os.environ.get(name) for name in names):
        return {}
    try:
        form = urllib.parse.urlencode({"client_id": os.environ["BLOGGER_CLIENT_ID"],
                                       "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
                                       "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
                                       "grant_type": "refresh_token"}).encode()
        access = str(http("https://oauth2.googleapis.com/token", method="POST", body=form,
                        timeout=30).get("access_token", ""))
        if not access:
            return {}
        rows, token = [], ""
        while True:
            query = {"status": "live", "maxResults": "100", "fields": "items(url,updated),nextPageToken"}
            if token:
                query["pageToken"] = token
            data = http("https://www.googleapis.com/blogger/v3/blogs/"
                        + os.environ["BLOGGER_BLOG_ID"] + "/pages?" + urllib.parse.urlencode(query),
                        headers={"Authorization": "Bearer " + access}, timeout=45)
            rows.extend(data.get("items", []) or [])
            token = data.get("nextPageToken", "")
            if not token or len(rows) >= 200:
                break
        return {str(row.get("url", "")): {"live": True, "updated": row.get("updated", "")}
                for row in rows if row.get("url")}
    except Exception:  # noqa: BLE001 - a control-plane outage leaves the public probe as the only voice
        return {}


def extract_canonical(markup: str) -> str:
    for tag in re.findall(r"<link\b[^>]*>", markup or ""):
        if "canonical" in tag:
            match = re.search(r"href=['\"]([^'\"]+)", tag)
            if match:
                return match.group(1)
    return ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to follow, so the first hop is the answer."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


class _RedirectCounter(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.hops: list[dict] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        self.hops.append({"code": code, "to": str(newurl)})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def live_probe(url: str) -> dict:
    """Ask the live page, as Googlebot, what it actually does today.

    The inspection API answers with Google's stored verdict for the last crawl it chose to make. On
    this site ten front doors carry "Redirect error" from crawls of 25 September to 20 October, while
    the same URLs answer 200 with no redirect today. Only a fresh crawl can clear a stale verdict, and
    on a Blogger property with no announcement queue and no registered sitemap, nothing was
    ever going to ask for one. This probe is what turns "Google says no" into "Google has not looked".
    """
    handler = _RedirectCounter()
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(url, headers={"User-Agent": GOOGLEBOT_UA})
    try:
        with opener.open(request, timeout=30) as response:
            status = int(getattr(response, "status", 200))
            body = response.read(200000).decode("utf-8", "ignore")
            final_url = response.geturl()
        if status == 429:
            # Blogger throttles a burst of requests. A rate limit says nothing about the page, so it
            # is recorded as not measured instead of being read as a redirect problem.
            return {"reachable": False, "status": 429, "hops": handler.hops,
                    "finalUrl": final_url, "canonical": "", "notMeasured": "rate limited"}
        return {"reachable": status == 200, "status": status, "hops": handler.hops,
                "finalUrl": final_url, "canonical": extract_canonical(body)}
    except urllib.error.HTTPError as exc:
        return {"reachable": False, "status": int(exc.code), "hops": handler.hops,
                "finalUrl": url, "canonical": "", "error": f"HTTP {exc.code}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"reachable": False, "status": 0, "hops": handler.hops, "finalUrl": url,
                "canonical": "", "error": type(exc).__name__}


def mobile_probe(url: str) -> dict:
    """Ask the page as a phone would, and do not follow the redirect it answers with.

    Returns the first hop only, deliberately. The answer that matters is "does the URL Google wants to
    index bounce somewhere else before it serves the document", and following the chain would hide it.
    """
    request = urllib.request.Request(url, headers={"User-Agent": MOBILE_PROBE_UA})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            status = int(getattr(response, "status", 200))
            location = response.headers.get("Location") or ""
            body = response.read(120000).decode("utf-8", "ignore") if status == 200 else ""
        if status == 429:
            return {"status": 429, "location": "", "canonical": "", "notMeasured": "rate limited"}
        return {"status": status, "location": location, "canonical": extract_canonical(body)}
    except urllib.error.HTTPError as exc:
        return {"status": int(exc.code), "location": exc.headers.get("Location") or "", "canonical": ""}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"status": 0, "location": "", "canonical": "", "error": type(exc).__name__}


def redirect_cause(url: str, mobile: dict) -> str:
    """Name the redirect Google is complaining about, when the live page still does it.

    A 302 to the same path with `?m=1` is Blogger's separate mobile template. The target declares the
    parameterless URL as its canonical, which is the exact shape Google reports as "Redirect error" (and,
    when it decides to keep the variant, "Alternate page with proper canonical"): the crawler is sent to a
    page whose own markup says the URL it came from is the real one. Nothing about the content is wrong, so
    nothing here deletes a page - and, corrected on 22 October, nothing here can be switched off either. The
    bounce is how Blogger serves mobile on blogspot.com and on a custom domain alike, Blogger Help's answer
    is "there is nothing to fix", and the public API has no mobile-template resource at all, so what this
    classification buys is only that the row is not mistaken for a real move or a broken page.
    """
    location = str(mobile.get("location") or "")
    if not location or int(mobile.get("status") or 0) not in (301, 302, 303, 307, 308):
        return ""
    canonical = str(mobile.get("canonical") or "")
    if "?" in location and "m=" in location.split("?", 1)[1]:
        if not canonical or canonical == url:
            return "blogger-mobile-template"
    return "redirect"


def stale_verdict(row: dict, probe: dict, publisher_live: bool = False,
                  mobile: dict | None = None) -> bool:
    """True when a redirect-family complaint cannot be reproduced today.

    Deliberately narrow: a page Google has merely "discovered" is not a stale verdict, it is an
    unanswered one, and calling that stale would be the same self-flattery the old automation kept
    doing. Either the live answer or Blogger's own published-state API can carry the proof, because
    the public probe is the part a shared host is allowed to throttle.
    """
    if row.get("verdict") == "PASS":
        return False
    if not any(needle in str(row.get("coverageState") or "") for needle in REDIRECT_FAMILY):
        return False
    if mobile and mobile.get("notMeasured"):
        return False
    if mobile and mobile.get("status") in (301, 302, 303, 307, 308):
        # Reproduced with Google's own identity today. This is not a stale verdict and must never be
        # reported as one, because the advice that follows "it is stale" is "wait for a crawl" - which is
        # exactly the wrong thing to do while every mobile fetch still bounces.
        return False
    if probe.get("hops") or (probe.get("reachable") and not probe.get("notMeasured")):
        return not probe.get("hops")
    return bool(publisher_live) and not (mobile and mobile.get("location"))


def blogger_mobile_view() -> dict:
    """What Blogger says about the mobile template, read only.

    This was written believing `blogs/{id}/mobileview` sat in front of the Theme → Mobile devices setting.
    It does not: Blogger's public v3 discovery document (fetched 22 October 2026) offers blogs, posts,
    pages, comments, pageviews and user info and nothing else, and the path answers HTTP 404 unauthenticated
    - before any question of permission arises. The request is kept so that the report proves the absence
    instead of asserting it, and it stays a GET because nothing in this job may write what a phone is served
    - and because there is nothing to write: no automation, mine or anyone else's, can change this setting.
    """
    names = ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN", "BLOGGER_BLOG_ID")
    if any(not os.environ.get(name) for name in names):
        return {"status": "UNAVAILABLE", "detail": "no Blogger authorisation in this environment",
                "noPublicApi": True, "read": "GET only; this job never writes the mobile template"}
    try:
        form = urllib.parse.urlencode({"client_id": os.environ["BLOGGER_CLIENT_ID"],
                                       "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
                                       "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
                                       "grant_type": "refresh_token"}).encode()
        access = str(http("https://oauth2.googleapis.com/token", method="POST", body=form,
                          timeout=30).get("access_token", ""))
        if not access:
            return {"status": "UNAVAILABLE", "detail": "no access token"}
        data = http("https://www.googleapis.com/blogger/v3/blogs/"
                    + os.environ["BLOGGER_BLOG_ID"] + "/mobileview",
                    headers={"Authorization": "Bearer " + access}, timeout=45) or {}
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
        return {"status": "UNAVAILABLE", "detail": type(exc).__name__}
    return {"status": "MEASURED", "noPublicApi": True,
            "customThemeUnavailable": bool(data.get("customThemeUnavailable")),
            "mobileDefinitionSet": bool(data.get("mobileDefinitionSet")),
            "dynamicViewsEnabled": bool(data.get("dynamicViewsEnabled")),
            "contentBytes": len(str(data.get("content") or "")),
            "read": "GET only; this job never writes the mobile template"}


def list_properties(access: str) -> dict:
    try:
        entries = (gsc(access, "GET", "sites") or {}).get("siteEntry", []) or []
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
        return {"status": "UNAVAILABLE", "detail": type(exc).__name__, "visible": []}
    visible = [str(row.get("siteUrl", "")) for row in entries]
    permission = {str(row.get("siteUrl", "")): str(row.get("permissionLevel", "")) for row in entries}
    return {"status": "MEASURED", "visible": visible, "permission": permission,
            "urlPrefixProperty": permission.get(PREFIX_PROPERTY, "ABSENT"),
            "domainProperty": permission.get(DOMAIN_PROPERTY, "ABSENT"),
            "urlPrefixPropertyVisible": PREFIX_PROPERTY in visible,
            "domainPropertyVisible": DOMAIN_PROPERTY in visible}


def sitemap_state(access: str, site: str = PREFIX_PROPERTY) -> dict:
    """Registered sitemaps on the property that accepts them, and what Google says about each."""
    out = {"status": "UNAVAILABLE", "registered": [], "missing": list(SITEMAP_PATHS), "detail": "",
           "triedOn": site}
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
        # "accessed" is not a field of sitemaps.list - Google answers lastSubmitted and
        # lastDownloaded. Reading a key that does not exist is how a sitemap that Google downloads
        # twice a day got reported as "last read never".
        "registered": [{"path": path, "isPending": bool(row.get("isPending")),
                        "errors": row.get("errors", 0), "warnings": row.get("warnings", 0),
                        "lastSubmitted": row.get("lastSubmitted", ""),
                        "lastDownloaded": row.get("lastDownloaded", ""),
                        "indexStatus": [
                            {"state": str(entry.get("indexStatus", "")), "urls": entry.get("urlCount")}
                            for entry in (row.get("indexStatus") or []) if isinstance(entry, dict)],
                        "indexStatusRaw": row.get("indexStatus", [])}
                       for path, row in registered.items()],
        "missing": [path for path in SITEMAP_PATHS if path not in registered],
        "otherRegistered": [path for path in registered if path not in SITEMAP_PATHS],
    })
    return out


def register_sitemaps(access: str, missing: list[str], *, apply: bool,
                     site: str = PREFIX_PROPERTY) -> dict:
    """PUT the two Blogger sitemaps. Idempotent: registering an existing sitemap is a no-op for
    Google and a re-read of the file, which is exactly what a stale sitemap needs."""
    done, failed = [], []
    site = urllib.parse.quote(site, safe="")
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
    """Bing is no longer asked anything, and that is a decision, not a gap.

    The property was deleted from Bing Webmaster Tools by the owner on 23 October 2026 and every Bing
    automation in this repository was removed the same evening. The field stays in the report so anyone
    reading an older copy can see what happened to it, and so no run ever reports a Bing failure again.
    """
    return {"retired": True,
            "detail": "retired by the owner on 23 October 2026; no Bing calls are made or needed",
            "quota": {}, "knownToBing": 0, "checkedUrls": len(urls)}


def pace(targets: list[dict], google_indexed: int, today: dt.date) -> dict:
    """Linear expectation against the deadline, computed from Google's own answer and nothing else.

    Bing was one of the two numbers here until 23 October 2026, when the owner deleted the property in
    Bing Webmaster Tools. Counting a page as done only once a retired engine also agreed would have
    frozen this scoreboard at one of thirteen forever, so the target is Google alone.
    """
    total = len(targets)
    in_both = google_indexed
    remaining = max(0, total - in_both)
    days_left = (DEADLINE - today).days
    weeks_left = max(1, -(-days_left // 7)) if days_left > 0 else 0
    window = max(1, (DEADLINE - START).days)
    elapsed = max(0, (today - START).days)
    expected = total * min(1.0, elapsed / window)
    return {"deadline": DEADLINE.isoformat(), "today": today.isoformat(), "daysLeft": days_left,
            "targets": total, "indexedInGoogle": in_both, "stillMissing": remaining,
            "paceRequiredPerWeek": (0 if remaining == 0 or weeks_left == 0
                                    else -(-remaining // weeks_left)),
            "expectedByNow": round(expected, 2),
            "behindBy": max(0, math.ceil(expected) - in_both),
            "onTrack": bool(in_both >= expected),
            "note": "pace is measured from Google's own verdict, not from a crawl promise"}


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
    prefix_permission = (report.get("properties") or {}).get("urlPrefixProperty", "")
    if prefix_permission and prefix_permission not in ("siteOwner", "ABSENT"):
        actions.append(f"The URL-prefix property is visible to the automation but at permission "
                       f"'{prefix_permission}'. Open Search Console → Settings → Users and "
                       "permissions for https://dailyyield.blogspot.com/ and give the account this "
                       "automation signs in as Owner (or Full) - otherwise the nightly sitemap "
                       "repair and index reads stay second-class on that property.")
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
    bouncing = sum(1 for row in (report.get("byPage") or []) if isinstance(row, dict)
                   and row.get("redirectCause") == "blogger-mobile-template")
    if bouncing:
        actions.append(
            f"{bouncing} of the redirect complaints are real right now, and they are all the same thing: "
            "Blogger answers Google's smartphone fetch with '302 -> the same URL + ?m=1', and that target "
            "declares the parameterless URL as its canonical, which is what Google files as Redirect error. "
            "There is nothing to toggle, and no page has to change. Measured on 22 October: the ?m=1 "
            "response differs from the desktop one by a single byte, its canonical points at the clean URL, "
            "and it carries no noindex - so a reader on a phone receives this same theme and pays one extra "
            "hop for it. The Theme → Mobile devices switch is not the lever (this blog was measured with "
            "the desktop theme already chosen), the same bounce happens on a custom domain, so a domain "
            "cannot trade it away, and Blogger's public API has no resource for the mobile template at all. "
            "Three changes make this worse rather than better, and none of them is a fix: a script that "
            "strips ?m=1, a robots rule that blocks ?m=1, or a mobile page that canonicalises to itself. "
            "What is left for you is the Request indexing taps on the clean URLs below; this watch re-probes "
            "both identities nightly and will report the day the complaint stops being reproducible.")
    stale = (report.get("staleVerdicts") or {}).get("count", 0)
    if stale:
        actions.append(f"{stale} of those verdicts cannot be reproduced on the live page today, checked as "
                       "a desktop fetch and as Google's smartphone fetch. Do not delete, rebuild or rename "
                       "those pages: the redirect that produced the verdict is already gone, and the only "
                       "thing missing is a crawl. Request indexing is what asks for it.")
    if report.get("manualQueue"):
        actions.append(f"Tap Request indexing for {len(report['manualQueue'])} main pages in the "
                       "Search Console interface. There is no API for it; this is the one step only "
                       "you can do.")
    return actions


def build_report(*, targets, properties, sitemaps, registration, rows, bing, today) -> dict:
    stale = [row["url"] for row in rows if row.get("staleVerdict")]
    google_indexed = sum(1 for row in rows if row.get("verdict") == "PASS")
    retired = bool(bing.get("retired"))
    report = {
        "checkedAt": now_utc(),
        "purpose": "the 13 front doors indexed in Google before 30 November 2026",
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
        "pace": pace(targets, google_indexed, today),
        "byPage": [{"url": row["url"],
                    "google": row.get("verdict", "UNKNOWN"),
                    "googleCoverage": row.get("coverageState", ""),
                    "googleLastCrawl": row.get("lastCrawlTime", ""),
                    "liveStatusToday": row.get("live", {}).get("status"),
                    "liveRedirectsToday": row.get("liveHops", 0),
                    "canonicalMatchesPage": (not row.get("live", {}).get("canonical")
                                             or row["live"]["canonical"].rstrip("/")
                                             == row["url"].rstrip("/")),
                    "mobileFetchToday": row.get("mobileFetch") or {},
                    "redirectCause": row.get("redirectCause", ""),
                    "bing": "retired with the owner's property on 23 October 2026",
                    "googleIndexed": row.get("verdict") == "PASS"}
                   for row in rows],
        "staleVerdicts": {"count": len(stale), "urls": stale,
                          "meaning": "the live page answers 200 with no redirect today, asked as a "
                                     "desktop client and as a mobile one, so the platform's complaint "
                                     "describes an older crawl and what is missing is a fresh one"},
    }
    report["manualQueue"] = manual_queue(rows)
    report["ownerActions"] = owner_actions(report)
    report["verdict"] = (
        "ALL_MAIN_PAGES_INDEXED" if report["pace"]["stillMissing"] == 0 else
        ("OFF_TRACK" if report["pace"]["daysLeft"] <= 0 else
         ("PARTIAL" if google_indexed else "NOT_STARTED")))
    report["limits"] = ("Google's indexed-version verdict is the only indexing signal this job trusts. "
                        "Bing is no longer asked anything: the property was deleted by the owner on "
                        "23 October 2026, and that retirement is recorded here so an older copy of this "
                        "report can be read against it. No figure in this file is a promise about ranking, "
                        "traffic or review."    ) if retired else ("Google's indexed-version verdict is the only indexing signal this job trusts.")
    return report


def render_markdown(report: dict) -> str:
    pace_block = report["pace"]
    lines = ["# Main pages — indexing scoreboard", "",
             f"**{report['verdict']}** · checked {report['checkedAt']}", "",
             f"- Targets: **{pace_block['targets']}** main pages (homepage first)",
             f"- In Google's index: **{report['google']['indexed']}**",
             f"- Not yet in Google's index: **{pace_block['stillMissing']}**",
             f"- Days to 30 November 2026: **{pace_block['daysLeft']}** · pace needed: "
             f"**{pace_block['paceRequiredPerWeek']} page(s) a week**", "",
             "## Every page", "", "| page | Google | coverage |", "|---|---|---|"]
    for row in report["byPage"]:
        lines.append(f"| `{row['url'].replace(BLOG, '') or '/'}` | {row['google']} | "
                     f"{row['googleCoverage'] or '—'} |")
    sitemaps = report.get("sitemaps") or {}
    props = report.get("properties") or {}
    lines += ["", "## Sitemaps registered on the URL-prefix property", ""]
    if props.get("status") == "MEASURED":
        lines.append(f"- what the automation may do: `{PREFIX_PROPERTY}` → "
                     f"**{props.get('urlPrefixProperty', 'unknown')}**, "
                     f"`{DOMAIN_PROPERTY}` → **{props.get('domainProperty', 'unknown')}**")
    if sitemaps.get("registered"):
        for row in sitemaps["registered"]:
            submitted = (row.get("lastSubmitted") or "")[:10] or "unknown"
            downloaded = (row.get("lastDownloaded") or "")[:10] or "never"
            found = ", ".join(f"{entry['state']} {entry['urls']}" for entry in row.get("indexStatus") or [])
            lines.append(f"- `{row['path'].replace(BLOG + '/', '')}` — submitted {submitted}, "
                         f"**last read by Google: {downloaded}**, errors {row['errors']}, "
                         f"warnings {row['warnings']}"
                         + (f", URLs {found}" if found else "")
                         + (" *(Google has not reported reading this file once)*"
                            if downloaded == "never" else ""))
    else:
        lines.append(f"- none readable ({sitemaps.get('detail') or 'not measured'})")
    if report.get("sitemapRegistration", {}).get("submittedNow"):
        lines.append(f"- registered by this run: "
                     + ", ".join(f"`{p}`" for p in report["sitemapRegistration"]["submittedNow"]))
    bounced_rows = [row for row in report["byPage"]
                    if isinstance(row, dict) and row.get("redirectCause") == "blogger-mobile-template"]
    if bounced_rows:
        lines += ["", "## What a phone is told today", "",
                  "Asked as a mobile client - which is how Google fetches and renders now - these URLs do "
                  "not serve the document; they bounce to Blogger's mobile template, and that template "
                  "names the URL the crawler came from as its canonical. Every one of these is why "
                  "'Redirect error' appears in Search Console, and it is one theme setting, not 453 pages "
                  "of content work.", ""]
        for row in bounced_rows:
            page = row["url"].replace(BLOG, "") or "/"
            location = str((row.get("mobileFetchToday") or {}).get("location") or "")
            status = (row.get("mobileFetchToday") or {}).get("status")
            lines.append(f"- `{page}` — a mobile fetch answers **{status}** and points at "
                         f"`{location.replace(BLOG, '') or location}`")
    stale_block = report.get("staleVerdicts") or {}
    if stale_block.get("urls"):
        lines += ["", "## Verdicts the live page does not reproduce", "",
                  stale_block["meaning"], ""]
        for row in report["byPage"]:
            if row["url"] in stale_block["urls"]:
                page = row['url'].replace(BLOG, '') or '/'
                coverage = row['googleCoverage'] or row['google']
                when = (row['googleLastCrawl'][:10] or 'a day it has not told us')
                hops = row['liveRedirectsToday']
                status = row['liveStatusToday']
                lines.append(f"- `{page}` — Google said “{coverage}” on {when}; today it answers "
                             f"{status} with {hops} redirect(s)")
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
    assert extract_canonical("<link href='https://dailyyield.blogspot.com/p/a.html' rel='canonical'/>") \
        == f"{BLOG}/p/a.html"
    assert stale_verdict({"url": targets[1]["url"], "verdict": "NEUTRAL",
                          "coverageState": "Redirect error", "lastCrawlTime": "2026-09-25T16:57:09Z"},
                         {"reachable": True, "status": 200, "hops": [], "canonical": ""})
    assert not stale_verdict({"url": targets[1]["url"], "verdict": "NEUTRAL",
                              "coverageState": "Redirect error"},
                             {"reachable": True, "status": 200, "hops": [{"code": 301}], "canonical": ""})
    # the desktop fetch is clean and the verdict still cannot be called stale, because Google fetches with
    # a smartphone identity and that is the fetch that redirects
    assert not stale_verdict({"url": targets[1]["url"], "verdict": "NEUTRAL",
                              "coverageState": "Redirect error"},
                             {"reachable": True, "status": 200, "hops": [], "canonical": ""},
                             True, {"status": 302, "location": f"{targets[1]['url']}?m=1", "canonical": ""})
    mobile_bounce = {"status": 302, "location": f"{targets[1]['url']}?m=1", "canonical": targets[1]["url"]}
    assert redirect_cause(targets[1]["url"], mobile_bounce) == "blogger-mobile-template", \
        "the ?m=1 bounce must be named, not filed as an unknown redirect"
    assert redirect_cause(targets[1]["url"], {"status": 200, "location": "", "canonical": ""}) == ""
    assert redirect_cause(targets[1]["url"], {"status": 301, "location": "https://elsewhere.test/x",
                                             "canonical": ""}) == "redirect"
    assert stale_verdict({"url": targets[1]["url"], "verdict": "NEUTRAL",
                          "coverageState": "Redirect error"},
                         {"reachable": True, "status": 200, "hops": [], "canonical": ""},
                         True, {"status": 200, "location": "", "canonical": targets[1]["url"]})
    lines = Path(__file__).read_text(encoding="utf-8").splitlines()
    at = [i for i, line in enumerate(lines) if "/mobileview" in line and "http" in "".join(lines[max(0, i - 3):i])]
    assert len(at) == 1, "exactly one request is made to the mobile-view endpoint"
    call = "\n".join(lines[at[0] - 3:at[0] + 4])
    assert "method=" not in call, \
        "the mobile view is read-only evidence; this job must never change what a phone is served"
    assert parse_sitemap_locations("<url><loc> https://dailyyield.blogspot.com/p/x.html </loc></url>") \
        == [f"{BLOG}/p/x.html"]
    rows = [{"url": row["url"], "verdict": "PASS" if index < 5 else "FAIL",
             "coverageState": "" if index < 5 else "Discovered - currently not indexed"}
            for index, row in enumerate(targets)]
    bing = bing_view([row["url"] for row in targets])   # the retired record, exactly as a live run builds it
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
        if properties.get("urlPrefixPropertyVisible"):
            sitemaps = sitemap_state(access, PREFIX_PROPERTY)
        else:
            # Google's documentation puts sitemap submission on the URL-prefix property, but the only
            # property this token can see is the domain one. Ask it directly instead of assuming: if
            # it answers, the sitemaps get registered tonight with no owner step at all.
            sitemaps = sitemap_state(access, DOMAIN_PROPERTY)
            if sitemaps.get("status") != "MEASURED":
                sitemaps["detail"] = (sitemaps.get("detail") or "no answer") + (
                    "; the URL-prefix property https://dailyyield.blogspot.com/ is not verified, and "
                    "that is where sitemap submission officially lives")
        registration = {"submittedNow": [], "failed": []}
        if sitemaps.get("status") == "MEASURED" and (sitemaps.get("missing") or arguments.apply):
            registration = register_sitemaps(access, sitemaps.get("missing") or list(SITEMAP_PATHS),
                                            apply=arguments.apply, site=site)
            if registration["submittedNow"]:
                sitemaps = sitemap_state(access, site)
        rows = [inspect_one(access, site, row["url"]) for row in targets]
    day = today.toordinal()
    published = blogger_page_state()
    need = [row for row in rows if row.get("verdict") != "PASS"
            and any(needle in str(row.get("coverageState") or "") for needle in REDIRECT_FAMILY)
            and valid_daily_yield_url(row["url"])]
    shift = day % max(1, len(need))
    ordered = need[shift:] + need[:shift]
    probed = set()
    for row in ordered[:LIVE_PROBE_CAP]:
        probe = live_probe(row["url"])
        time.sleep(MOBILE_PROBE_SPACING_SECONDS)
        mobile = mobile_probe(row["url"])
        probed.add(row["url"])
        row["mobileFetch"] = {"status": mobile.get("status"), "location": mobile.get("location", ""),
                              "canonical": mobile.get("canonical", "")}
        cause = redirect_cause(row["url"], mobile)
        if cause:
            row["redirectCause"] = cause
        row["live"] = {"reachable": probe["reachable"], "status": probe["status"],
                       "canonical": probe.get("canonical", ""), "finalUrl": probe.get("finalUrl", "")}
        row["liveHops"] = len(probe.get("hops") or [])
        if probe.get("notMeasured"):
            row["liveNote"] = probe["notMeasured"]
        row["staleVerdict"] = stale_verdict(row, probe, row["url"] in published, mobile)
        time.sleep(LIVE_PROBE_SPACING_SECONDS)
    for row in rows:
        row.setdefault("live", {"reachable": None, "status": None, "canonical": "", "finalUrl": ""})
        row.setdefault("liveHops", 0)
        if row["url"] not in probed:
            row["staleVerdict"] = stale_verdict(row, {"reachable": None, "hops": []},
                                                row["url"] in published)
            if row["url"] in published and row["staleVerdict"]:
                row["liveNote"] = "not probed today; Blogger confirms the page is published live"
    bouncing = [row for row in rows if row.get("redirectCause") == "blogger-mobile-template"]
    report_extra = {"liveProbes": len(probed), "liveProbeCap": LIVE_PROBE_CAP,
                    "publisherApiPagesLive": len(published),
                    "redirectFamilyComplaints": len(need),
                    "mobileTemplateRedirects": len(bouncing),
                    "mobileView": blogger_mobile_view()}
    report = build_report(targets=targets, properties=properties, sitemaps=sitemaps,
                          registration=registration, rows=rows, bing=bing_view(
                              [row["url"] for row in targets]), today=today)
    report.update(report_extra)
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
