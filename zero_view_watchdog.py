#!/usr/bin/env python3
"""Daily Yield zero-synthetic-view watchdog.

Hard policy: never request a public dailyyield.blogspot.com URL. All Daily Yield
inventory/content checks use authenticated Blogger API data. Search status uses
Search Console APIs. External links/assets/providers may be contacted because
those requests cannot register a Daily Yield pageview.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BLOG = "https://dailyyield.blogspot.com"
SITE = BLOG + "/"
IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)
UA = {"User-Agent": "DailyYield-ZeroView-Watchdog/1.0"}
OWN_HOST = "dailyyield.blogspot.com"


def is_own_public_host(url):
    host = (urlparse(url).hostname or "").lower()
    return host == OWN_HOST or host.startswith("dailyyield.blogspot.")


class ZeroViewRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if is_own_public_host(newurl):
            raise RuntimeError("ZERO-VIEW POLICY BLOCKED redirect to public Daily Yield URL")
        return super().redirect_request(request, fp, code, message, headers, newurl)


SAFE_OPENER = urllib.request.build_opener(ZeroViewRedirectHandler())
EXPECTED_SITEMAPS = [BLOG + "/sitemap.xml", BLOG + "/sitemap-pages.xml"]
LEGACY = "/p/share-market_0718113516.html"


def request_json(url, headers=None, method="GET", body=None, timeout=45):
    if is_own_public_host(url):
        raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
    data = json.dumps(body).encode() if body is not None else None
    h = dict(UA)
    h.update(headers or {})
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with SAFE_OPENER.open(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:350]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def oauth(client_id, client_secret, refresh_token):
    form = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)["access_token"]


def blogger_inventory():
    required = ["BLOGGER_BLOG_ID", "BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("missing Blogger secrets: " + ", ".join(missing))
    token = oauth(os.environ["BLOGGER_CLIENT_ID"], os.environ["BLOGGER_CLIENT_SECRET"], os.environ["BLOGGER_REFRESH_TOKEN"])
    blog_id = os.environ["BLOGGER_BLOG_ID"]
    headers = {"Authorization": "Bearer " + token}
    metadata = request_json(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}?fields=id,name,url,published,updated,posts(totalItems),pages(totalItems)",
        headers,
    )
    items = [{"id": "home", "kind": "home", "title": metadata.get("name", "Daily Yield"), "url": metadata.get("url", SITE), "content": "", "labels": [], "published": metadata.get("published", ""), "updated": metadata.get("updated", "")}]
    for resource in ("pages", "posts"):
        page_token = ""
        while True:
            item_fields = "id,title,url,content,published,updated,status"
            if resource == "posts":
                item_fields += ",labels"
            params = {"status": "live", "fetchBodies": "true", "maxResults": "50", "fields": f"items({item_fields}),nextPageToken"}
            if page_token:
                params["pageToken"] = page_token
            data = request_json(
                f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/{resource}?{urllib.parse.urlencode(params)}",
                headers,
            )
            for item in data.get("items", []):
                items.append({
                    "id": item.get("id", ""), "kind": resource[:-1],
                    "title": item.get("title", ""), "url": item.get("url", ""),
                    "content": item.get("content", ""), "labels": item.get("labels", []),
                    "published": item.get("published", ""), "updated": item.get("updated", ""),
                    "status": item.get("status", "LIVE"),
                })
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
    return metadata, list({item["url"]: item for item in items if item.get("url")}.values())


def plain(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()


def attrs(content, tag, attr):
    pattern = rf"<{tag}\b[^>]*\b{attr}=[\"']([^\"']+)"
    return [html.unescape(value) for value in re.findall(pattern, content or "", re.I)]


def normalized_internal(url):
    parsed = urlparse(url)
    return (parsed.scheme + "://" + parsed.netloc + parsed.path).rstrip("/")


def audit_content(item, known):
    if item["kind"] == "home":
        return {"kind": "home", "title": item["title"], "url": item["url"], "issues": [], "warnings": [], "images": [], "external": [], "internal": []}
    content = item.get("content", "")
    title = item.get("title", "")
    issues, warnings = [], []
    links = attrs(content, "a", "href")
    images = attrs(content, "img", "src")
    internal, external = [], []
    for link in links:
        absolute = urljoin(SITE, link)
        host = (urlparse(absolute).hostname or "").lower()
        if host == OWN_HOST:
            internal.append(absolute)
        elif urlparse(absolute).scheme in ("http", "https"):
            external.append(absolute)
    if len(plain(content).split()) < 40:
        issues.append("content unexpectedly short")
    ids = re.findall(r"\bid=[\"']([^\"']+)", content, re.I)
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        issues.append("duplicate HTML ids: " + ", ".join(duplicates[:8]))
    exempt = item["url"].endswith(LEGACY)
    if not exempt and 'id="dyPageFamily"' not in content:
        issues.append("Daily Yield family directory missing")
    if LEGACY in content and not exempt:
        issues.append("obsolete market URL present")
    schemas = re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", content, re.I | re.S)
    for number, raw in enumerate(schemas, 1):
        try:
            json.loads(html.unescape(raw).strip())
        except Exception as exc:
            issues.append(f"JSON-LD {number} invalid: {str(exc)[:80]}")
    if item["kind"] == "post":
        if not images:
            issues.append("photo missing")
        if not schemas:
            issues.append("JSON-LD schema missing")
        if "Kushal K. Daga" not in content:
            issues.append("byline missing")
        if 'class="dy-context"' not in content:
            issues.append("contextual internal link missing")
        if 'class="dy-related"' not in content:
            issues.append("related suggestions missing")
        related = set(re.findall(r"class=[\"'][^\"']*dy-related-card[^\"']*[\"'][^>]*href=[\"']([^\"']+)", content, re.I))
        if len(related) != 4:
            issues.append(f"related suggestion count {len(related)}, expected 4")
        if "DY_CONTINUOUS_MOTION_START" not in content:
            issues.append("motion/swipe package missing")
        if not any(marker in content for marker in ("DY_SEO_META_START", "metaDesc")):
            issues.append("SEO/meta description package missing")
        if "News" in item.get("labels", []) and 'class="fbk-src' not in content:
            issues.append("original News source links missing")
    for link in internal:
        clean = normalized_internal(link)
        if "/search" not in clean and clean not in known:
            issues.append("internal destination absent from Blogger inventory: " + clean)
    for image in images:
        parsed = urlparse(image)
        if parsed.scheme not in ("http", "https", "data"):
            issues.append("invalid image URL: " + image[:100])
    return {"kind": item["kind"], "title": title, "url": item["url"], "issues": sorted(set(issues)), "warnings": warnings, "images": images, "external": external, "internal": internal}


def external_status(url):
    if is_own_public_host(url):
        return {"url": url, "status": "BLOCKED_BY_ZERO_VIEW_POLICY"}
    request = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-1023"})
    try:
        with SAFE_OPENER.open(request, timeout=18) as response:
            return {"url": url, "status": response.status, "contentType": response.headers.get("Content-Type", "")}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code}
    except Exception as exc:
        return {"url": url, "status": "TRANSIENT", "detail": str(exc)[:120]}


def github_checks():
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "kushalkumardagaca-png/blogger-bot")
    output = []
    if not token:
        return [{"name": "GitHub workflow history", "status": "SKIP", "detail": "token unavailable"}]
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}
    for workflow, label in (("daily_blogger_poster.yml", "Master publisher"), ("daily_news_wires.yml", "News publisher")):
        try:
            data = request_json(f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=12", headers)
            complete = [run for run in data.get("workflow_runs", []) if run.get("status") == "completed"]
            failed = [run for run in complete if run.get("conclusion") == "failure"]
            output.append({"name": label, "status": "WARN" if failed else "OK", "detail": f"{len(failed)} failures among {len(complete)} recent completed runs"})
        except Exception as exc:
            output.append({"name": label, "status": "WARN", "detail": str(exc)[:120]})
    return output


def provider_checks():
    targets = [
        ("TradingView global scanner", "https://scanner.tradingview.com/global/scan", {"symbols": {"tickers": ["NASDAQ:AAPL", "NSE:RELIANCE", "TVC:GOLD"]}, "columns": ["name", "close", "change"]}),
        ("CoinGecko", "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&per_page=2&page=1", None),
        ("Frankfurter FX", "https://api.frankfurter.app/latest?from=USD&to=INR", None),
        ("Gold API", "https://api.gold-api.com/price/XAU", None),
        ("Mutual fund API", "https://api.mfapi.in/mf/search?q=blue", None),
    ]
    rows = []
    for name, url, body in targets:
        try:
            data = request_json(url, method="POST" if body else "GET", body=body, timeout=20)
            rows.append({"name": name, "status": "OK", "detail": "responding" if data is not None else "empty response"})
        except Exception as exc:
            rows.append({"name": name, "status": "WARN", "detail": str(exc)[:120]})
    return rows


def gsc_checks(inventory):
    required = ["GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {"connection": "SKIP", "detail": "missing: " + ", ".join(missing), "tracker": {}, "summary": {}}
    token = oauth(os.environ["GSC_CLIENT_ID"], os.environ["GSC_CLIENT_SECRET"], os.environ["GSC_REFRESH_TOKEN"])
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    sites = request_json("https://www.googleapis.com/webmasters/v3/sites", headers)
    visible = sites.get("siteEntry", [])
    exact = next((item for item in visible if item.get("siteUrl", "").rstrip("/") == SITE.rstrip("/")), None)
    if not exact:
        return {"connection": "WARN", "detail": "exact property not visible", "visibleProperties": [item.get("siteUrl", "") for item in visible], "tracker": {}, "summary": {}}
    property_url = exact.get("siteUrl", SITE)
    enc = urllib.parse.quote(property_url, safe="")
    sitemap_rows = request_json(f"https://www.googleapis.com/webmasters/v3/sites/{enc}/sitemaps", headers).get("sitemap", [])
    current = [row for row in sitemap_rows if row.get("path") in EXPECTED_SITEMAPS]
    previous_tracker = {}
    try:
        previous_tracker = json.loads(Path("ZERO_VIEW_WATCHDOG.json").read_text()).get("gsc", {}).get("tracker", {})
    except Exception:
        pass
    tracker = dict(previous_tracker)
    today = NOW.strftime("%Y-%m-%d")
    inspected = errors = 0
    for item in inventory:
        if item["url"].endswith(LEGACY):
            continue
        old = tracker.get(item["url"], {})
        if str(old.get("checkedAt", "")).startswith(today):
            continue
        try:
            result = request_json(
                "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                headers, "POST", {"inspectionUrl": item["url"], "siteUrl": property_url, "languageCode": "en-US"},
            )
            state = result.get("inspectionResult", {}).get("indexStatusResult", {})
            tracker[item["url"]] = {
                "title": item["title"], "checkedAt": NOW.isoformat(),
                "verdict": state.get("verdict", "UNKNOWN"),
                "coverageState": state.get("coverageState", ""),
                "pageFetchState": state.get("pageFetchState", ""),
                "robotsTxtState": state.get("robotsTxtState", ""),
                "lastCrawlTime": state.get("lastCrawlTime", ""),
                "googleCanonical": state.get("googleCanonical", ""),
                "userCanonical": state.get("userCanonical", ""),
            }
            inspected += 1
            time.sleep(0.12)
        except Exception as exc:
            errors += 1
            tracker[item["url"]] = {**old, "title": item["title"], "checkedAt": NOW.isoformat(), "error": str(exc)[:160]}
    live_urls = {item["url"] for item in inventory if not item["url"].endswith(LEGACY)}
    tracker = {url: row for url, row in tracker.items() if url in live_urls}
    passed = sum(row.get("verdict") == "PASS" for row in tracker.values())
    return {
        "connection": "OK", "property": property_url, "permission": exact.get("permissionLevel"),
        "sitemaps": current, "tracker": tracker,
        "summary": {"inventory": len(live_urls), "tracked": len(tracker), "pass": passed, "notPass": len(tracker) - passed, "inspectedThisRun": inspected, "inspectionErrors": errors, "sitemapsVisible": len(current)},
    }


def main():
    metadata, inventory = blogger_inventory()
    known = {normalized_internal(item["url"]) for item in inventory}
    rows = [audit_content(item, known) for item in inventory]
    external_urls = sorted({url.split("#")[0] for row in rows for url in row["external"]})
    image_urls = sorted({url for row in rows for url in row["images"] if urlparse(url).scheme in ("http", "https") and not is_own_public_host(url)})
    targets = list(dict.fromkeys(external_urls + image_urls))
    with ThreadPoolExecutor(max_workers=10) as pool:
        destination_rows = list(pool.map(external_status, targets))
    hard_external = [row for row in destination_rows if row["status"] in (404, 410)]
    transient_external = [row for row in destination_rows if row["status"] in (401, 403, 429, "TRANSIENT") or isinstance(row["status"], int) and row["status"] >= 500]
    content_failures = sum(bool(row["issues"]) for row in rows)
    github = github_checks()
    providers = provider_checks()
    gsc = gsc_checks(inventory)
    hard = content_failures + len(hard_external)
    overall = "PASS" if hard == 0 and gsc.get("connection") == "OK" else "ATTENTION"
    report = {
        "checkedAtIST": NOW.isoformat(), "mode": "ZERO_SYNTHETIC_VIEWS",
        "policy": "No public dailyyield.blogspot.com URL was requested or rendered.",
        "overall": overall, "bloggerControlPlane": metadata,
        "summary": {"urls": len(inventory), "posts": sum(item["kind"] == "post" for item in inventory), "pages": sum(item["kind"] == "page" for item in inventory), "contentFailures": content_failures, "externalDestinationsChecked": len(targets), "confirmedExternal404or410": len(hard_external), "transientExternalResponses": len(transient_external), "syntheticDailyYieldViews": 0},
        "content": rows, "confirmedBrokenExternal": hard_external,
        "transientExternal": transient_external, "github": github, "providers": providers, "gsc": gsc,
        "limitations": ["Rendered-browser and live public-page navigation are intentionally prohibited because they create synthetic pageviews.", "Responsive, metadata and structure checks are performed against Blogger API content packages rather than opening public URLs."],
    }
    Path("ZERO_VIEW_WATCHDOG.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    lines = ["# Daily Yield Zero-View Watchdog", "", f"- **Checked:** {report['checkedAtIST']}", f"- **Verdict:** {overall}", "- **Synthetic Daily Yield views:** 0", f"- **Inventory:** {len(inventory)} URLs · {report['summary']['posts']} Posts · {report['summary']['pages']} Pages", f"- **Content failures:** {content_failures}", f"- **Confirmed external 404/410:** {len(hard_external)}", f"- **Search Console:** {gsc.get('connection')} · {gsc.get('summary', {}).get('pass', 0)}/{gsc.get('summary', {}).get('tracked', 0)} tracked PASS", "", "> No public Daily Yield page was opened. Blogger API and Search Console API are the sources of truth.", "", "## Content inventory"]
    for row in rows:
        lines.append(f"- {'✅' if not row['issues'] else '❌'} **{row['kind']} · {row['title']}**" + ((" — " + "; ".join(row["issues"])) if row["issues"] else ""))
    Path("ZERO_VIEW_WATCHDOG.md").write_text("\n".join(lines) + "\n")
    Path("HEALTH_STATUS.json").write_text(json.dumps({"overall": overall, "zero_view": True, "synthetic_views": 0, "summary": report["summary"], "gsc": gsc, "github": github, "providers": providers}, indent=2))
    Path("HEALTH_REPORT.md").write_text("\n".join(lines) + "\n")
    Path("COMPREHENSIVE_SITE_AUDIT.json").write_text(json.dumps({"mode": "Blogger API source audit", "urls": len(inventory), "hard_failures": hard, "results": rows, "broken_external_links": hard_external}, indent=2, ensure_ascii=False))
    Path("COMPREHENSIVE_SITE_AUDIT.md").write_text("\n".join(lines) + "\n")
    Path("RENDERED_SITE_AUDIT.json").write_text(json.dumps({"mode": "DISABLED_ZERO_VIEW_POLICY", "failures": 0, "rendered_checks": 0, "synthetic_views": 0, "reason": "Public browser navigation is prohibited."}, indent=2))
    verdict = {"verdict": overall, "mode": "ZERO_SYNTHETIC_VIEWS", "synthetic_views": 0, "urls": len(inventory), "content_failures": hard, "rendered_checks": 0, "gsc": gsc.get("connection")}
    Path("WATCHDOG_VERDICT.json").write_text(json.dumps(verdict, indent=2))
    Path("WATCHDOG_VERDICT.md").write_text("# Daily Yield Zero-View Watchdog Verdict\n\n" + "".join(f"- **{key.replace('_', ' ').title()}:** {value}\n" for key, value in verdict.items()))
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
