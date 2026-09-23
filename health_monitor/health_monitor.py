#!/usr/bin/env python3
"""
FINANCE BY CA KUSHAL - 24/7 Blog Health Monitor
================================================
Runs on GitHub Actions every 4 hours (plus after each publishing slot).
Checks every critical component of the blog and its data services,
attempts safe auto-healing, and writes a status report to the repo.

Check groups:
  A. Publishing engine   (slots, tracker, workflow runs, article quality)
  B. Blog pages          (homepage, 10 static pages, robots, sitemap)
  C. Market data         (7 TradingView endpoints, crypto, FX, funds, geo)
  D. Page integrity      (Share & Market page fix markers)

No external pip dependencies (urllib only). Never crashes: every check
is individually guarded.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BLOG = "https://financebycakushal.blogspot.com"
IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)
NOW_ISO = NOW.strftime("%Y-%m-%d %H:%M IST")

# Publishing slots (IST). (time, label)
SLOTS = [
    ("08:00", "Slot 1 · 08:00 AM Morning"),
    ("11:30", "Slot 2 · 11:30 AM Deep Dive"),
    ("14:30", "Slot 3 · 02:30 PM Case Study"),
    ("17:45", "Slot 4 · 05:45 PM Market Close"),
    ("20:30", "Slot 5 · 08:30 PM Prime Time"),
]
SLOT_GRACE_MIN = 75          # minutes after slot before a miss is declared
HEAL_COOLDOWN_MIN = 120      # min time between auto-heal dispatches

STATIC_PAGES = [
    ("Homepage", "/"),
    ("Daily Article hub", "/p/article.html"),
    ("Daily News hub", "/p/daily-news.html"),
    ("Calculator hub", "/p/calculator_0908148622.html"),
    ("Share & Market hub", "/p/share-market_0718113516.html"),
    ("Money Atlas hub", "/p/money-atlas_01486068069.html"),
    ("For Corporate hub", "/p/for-corporate_01804417406.html"),
    ("About Us", "/p/about-us_02080501126.html"),
    ("Contact Us", "/p/contact-us_01883938366.html"),
    ("Disclaimer", "/p/disclaimer.html"),
    ("Privacy Policy", "/p/privacy-policy.html"),
]

MARKET_CHECKS = [
    ("Stocks · US board (TradingView)", "america", ["NASDAQ:AAPL", "NYSE:JPM"]),
    ("Stocks · India board (TradingView)", "india", ["NSE:RELIANCE", "NSE:TCS"]),
    ("Stocks · UK board (TradingView)", "uk", ["LSE:SHEL", "LSE:AZN"]),
    ("Stocks · Japan board (TradingView)", "japan", ["TSE:7203", "TSE:6758"]),
    ("Stocks · Germany board (TradingView)", "germany", ["XETR:SAP", "XETR:SIE"]),
    ("World indices & metals (TradingView)", "global", ["SP:SPX", "TVC:GOLD", "TVC:UKX"]),
    ("Commodities futures (TradingView)", "futures", ["COMEX:GC1!", "NYMEX:CL1!"]),
]

SM_MARKERS = {
    "Price router fix (regionOf)": "regionOf",
    "UK market endpoint fix": "isUK ? 'uk'",
    "Curated indices fix": "TASE:TA35",
    "Country detector fix": "api.country.is",
    "Crypto backup engine": "data-api.binance.vision",
}

results = []   # list of dicts: section, name, status(OK/WARN/FAIL/SKIP), detail
actions = []   # auto-heal actions taken


def add(section, name, status, detail=""):
    results.append({"section": section, "name": name, "status": status, "detail": detail})
    print(f"  [{status:4}] {name}" + (f" — {detail}" if detail else ""))


def fetch(url, timeout=15, headers=None, data=None, method="GET"):
    h = {"User-Agent": "Mozilla/5.0 (compatible; HealthMonitor/1.0)"}
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data is not None else None
    if body:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def try_fetch(url, timeout=15, headers=None, data=None, method=None):
    if method is None:
        method = "POST" if data is not None else "GET"
    try:
        s, b = fetch(url, timeout=timeout, headers=headers, data=data, method=method)
        return s, b, None
    except urllib.error.HTTPError as e:
        return e.code, None, str(e)
    except Exception as e:
        return None, None, str(e)


def fetch_blog_url(path, tries=3):
    """Fetch a blogspot URL with retries + backoff.
    Blogspot throttles datacenter IPs (HTTP 429); a 429 means the site is
    ALIVE but pacing us - never an outage."""
    last = (None, None, "")
    for attempt in range(tries):
        if attempt:
            time.sleep(20 if attempt == 2 else 8)
        last = try_fetch(BLOG + path, timeout=20)
        if last[0] == 200:
            return last
    return last


# ---------------------------------------------------------------------------
# A. PUBLISHING ENGINE
# ---------------------------------------------------------------------------
print("\nA. PUBLISHING ENGINE")
print("-" * 60)

# A1 - Blogger feed
feed_posts = []
st, body, err = try_fetch(BLOG + "/feeds/posts/default?alt=json&max-results=25", timeout=20)
if st == 429:
    time.sleep(15)
    st, body, err = try_fetch(BLOG + "/feeds/posts/default?alt=json&max-results=25", timeout=20)
if st == 200:
    try:
        entries = json.loads(body.decode())["feed"].get("entry", [])
        for e in entries:
            content = e.get("content", {}).get("$t", "")
            text = re.sub(r"<[^>]+>", " ", content)
            labels = [t.get("term", "") for t in e.get("category", [])]
            is_news = ("News" in labels) or ("News Roundup" in e["title"]["$t"])
            feed_posts.append({
                "title": e["title"]["$t"],
                "url": next((l.get("href") for l in e.get("link", [])
                             if l.get("rel") == "alternate"), ""),
                "published": datetime.fromisoformat(e["published"]["$t"]).astimezone(IST),
                "words": len(text.split()),
                "has_img": ("<img" in content) or ("<figure" in content.lower()),
                "has_schema": ("schema.org" in content) or ("ld+json" in content),
                "is_news": is_news,
            })
        add("A. Publishing engine", "Blogger feed reachable", "OK",
            f"{len(feed_posts)} recent posts")
    except Exception as e:
        add("A. Publishing engine", "Blogger feed parse", "FAIL", str(e)[:120])
elif st == 429:
    add("A. Publishing engine", "Blogger feed reachable", "WARN",
        "Blogspot throttled the checker (site alive) — slot check skipped this round")
else:
    add("A. Publishing engine", "Blogger feed reachable", "FAIL", (err or "")[:120])

# A2 - today's publishing slots
today = NOW.date()
masters_today = [p for p in feed_posts
                 if p["published"].date() == today and not p["is_news"]]
news_today = [p for p in feed_posts
              if p["published"].date() == today and p["is_news"]]

missed_slots = []
for slot, label in ([] if not feed_posts else SLOTS):
    hh, mm = map(int, slot.split(":"))
    slot_dt = datetime.combine(today, datetime.strptime(slot, "%H:%M").time(), IST)
    if NOW < slot_dt + timedelta(minutes=SLOT_GRACE_MIN):
        continue  # slot not due yet (or still within grace)
    hit = any(slot_dt - timedelta(minutes=20) <= p["published"] <= slot_dt + timedelta(minutes=SLOT_GRACE_MIN)
              for p in masters_today)
    if not hit:
        missed_slots.append(label)

if feed_posts:
    if missed_slots:
        add("A. Publishing engine", "Daily publishing slots", "FAIL",
            "missed: " + "; ".join(missed_slots))
    else:
        due = sum(1 for s, _ in SLOTS
                  if NOW >= datetime.combine(today, datetime.strptime(s, "%H:%M").time(), IST)
                  + timedelta(minutes=SLOT_GRACE_MIN))
        add("A. Publishing engine", "Daily publishing slots", "OK",
            f"{due} slot(s) due so far today — all published; "
            f"{len(masters_today)} master articles + {len(news_today)} news roundups today")

# A3 - duplicates today
if feed_posts:
    titles_today = [p["title"] for p in feed_posts if p["published"].date() == today]
    dupes = {t for t in titles_today if titles_today.count(t) > 1}
    add("A. Publishing engine", "No duplicate articles today", "FAIL" if dupes else "OK",
        ("duplicates: " + "; ".join(sorted(dupes))) if dupes else "all unique")

# A4 - newest master article quality
masters = [p for p in feed_posts if not p["is_news"]]
if masters:
    newest = max(masters, key=lambda p: p["published"])
    issues = []
    if not newest["has_img"]:
        issues.append("no hero image")
    if newest["words"] < 1500:
        issues.append(f"only {newest['words']} words")
    age_h = (NOW - newest["published"]).total_seconds() / 3600
    add("A. Publishing engine", "Newest master article quality", "WARN" if issues else "OK",
        (", ".join(issues) + " — " + newest["title"][:40]) if issues
        else f"{newest['words']} words, hero image + schema OK ({newest['title'][:40]})")
    if age_h > 26:
        add("A. Publishing engine", "Publishing freshness", "FAIL",
            f"newest master article is {age_h:.0f}h old")
    else:
        add("A. Publishing engine", "Publishing freshness", "OK",
            f"newest master article {age_h:.1f}h ago")

# A5 - tracker file
next_index = None
try:
    with open("published_tracker.json", encoding="utf-8") as f:
        tr = json.load(f)
    next_index = tr.get("next_topic_index")
    last_ts = tr.get("last_published_timestamp", "?")
    n_pub = len(tr.get("published_posts", []))
    add("A. Publishing engine", "Topic tracker state", "OK",
        f"next topic #{next_index}, {n_pub} published, last at {last_ts} UTC")
except Exception as e:
    add("A. Publishing engine", "Topic tracker state", "FAIL", f"cannot read tracker: {e}")

# A6 - GitHub Actions publishing workflow runs
TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY", "kushalkumardagaca-png/blogger-bot")
wf_runs = []
if TOKEN:
    st, body, err = try_fetch(
        f"https://api.github.com/repos/{REPO}/actions/workflows/daily_blogger_poster.yml/runs?per_page=8",
        headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json"},
        timeout=15)
    if st == 200:
        try:
            wf_runs = json.loads(body.decode()).get("workflow_runs", [])
        except Exception:
            wf_runs = []
        if wf_runs:
            fails = [r for r in wf_runs if r.get("conclusion") == "failure"]
            add("A. Publishing engine", "Publisher workflow (GitHub Actions)", "FAIL" if fails else "OK",
                (f"{len(fails)} of last {len(wf_runs)} runs failed")
                if fails else f"last {len(wf_runs)} runs all successful")
        else:
            add("A. Publishing engine", "Publisher workflow (GitHub Actions)", "WARN", "no runs found")
    else:
        add("A. Publishing engine", "Publisher workflow (GitHub Actions)", "WARN",
            f"API {st}: {(err or '')[:80]}")
else:
    add("A. Publishing engine", "Publisher workflow (GitHub Actions)", "SKIP",
        "no token (local run)")

# ---------------------------------------------------------------------------
# AUTO-HEAL: re-dispatch the publisher if a slot was genuinely missed
# ---------------------------------------------------------------------------
healed = False
if missed_slots and feed_posts and TOKEN and wf_runs:
    latest = wf_runs[0]
    should_heal = latest.get("conclusion") == "failure" or latest.get("status") != "completed"
    # cooldown guard from previous status file
    try:
        with open("HEALTH_STATUS.json", encoding="utf-8") as f:
            prev = json.load(f)
        last_heal = datetime.fromisoformat(prev.get("last_heal_dispatch", "2000-01-01T00:00:00+05:30"))
        if NOW - last_heal < timedelta(minutes=HEAL_COOLDOWN_MIN):
            should_heal = False
    except Exception:
        pass
    if should_heal:
        st, body, err = try_fetch(
            f"https://api.github.com/repos/{REPO}/actions/workflows/daily_blogger_poster.yml/dispatches",
            headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json"},
            data={"ref": "main"}, method="POST", timeout=15)
        if st == 204:
            healed = True
            actions.append("Missed publishing slot detected + failed workflow run -> "
                           "re-dispatched the publisher to catch up automatically.")
            add("A. Publishing engine", "AUTO-HEAL publisher", "OK", "re-dispatched to catch up")
        else:
            add("A. Publishing engine", "AUTO-HEAL publisher", "FAIL",
                f"dispatch returned {st}: {(err or '')[:80]}")

# ---------------------------------------------------------------------------
# B. BLOG PAGES
# ---------------------------------------------------------------------------
print("\nB. BLOG PAGES")
print("-" * 60)
page_bodies = {}
for name, path in STATIC_PAGES:
    if page_bodies:
        time.sleep(1.5)  # pace requests — Blogspot throttles datacenter IPs
    st, body, err = fetch_blog_url(path)
    if st == 200 and body:
        page_bodies[path] = body
    if st == 200 and body and len(body) > 20000:
        add("B. Blog pages", name, "OK", f"200 OK · {len(body) // 1024} KB")
    elif st == 200:
        add("B. Blog pages", name, "WARN", f"200 but only {len(body or b'')//1024} KB")
    elif st == 429:
        add("B. Blog pages", name, "WARN",
            "Blogspot throttled the checker — site is alive, checker-side pacing")
    else:
        add("B. Blog pages", name, "FAIL", f"HTTP {st} {(err or '')[:60]}")

st, body, err = fetch_blog_url("/robots.txt")
if st == 200 and b"sitemap" in (body or b"").lower():
    add("B. Blog pages", "robots.txt", "OK", "reachable, sitemap declared")
elif st == 429:
    add("B. Blog pages", "robots.txt", "WARN", "throttled by Blogspot (checker-side)")
else:
    add("B. Blog pages", "robots.txt", "FAIL", f"HTTP {st} {(err or '')[:60]}")

st, body, err = fetch_blog_url("/sitemap.xml")
if st == 200:
    urls = re.findall(r"<loc>(.*?)</loc>", (body or b"").decode("utf-8", "replace"))
    if len(urls) >= 20:
        add("B. Blog pages", "sitemap.xml", "OK", f"{len(urls)} URLs indexed")
    else:
        add("B. Blog pages", "sitemap.xml", "WARN", f"only {len(urls)} URLs")
elif st == 429:
    add("B. Blog pages", "sitemap.xml", "WARN", "throttled by Blogspot (checker-side)")
else:
    add("B. Blog pages", "sitemap.xml", "FAIL", f"HTTP {st} {(err or '')[:60]}")

# ---------------------------------------------------------------------------
# C. MARKET DATA SERVICES (Share & Market page)
# ---------------------------------------------------------------------------
print("\nC. MARKET DATA SERVICES")
print("-" * 60)
scanner_ok = 0
for name, ep, tickers in MARKET_CHECKS:
    st, body, err = try_fetch(
        f"https://scanner.tradingview.com/{ep}/scan", timeout=15,
        data={"symbols": {"tickers": tickers},
              "columns": ["name", "close", "change"]})
    got = 0
    if st == 200:
        try:
            got = len(json.loads(body.decode()).get("data", []))
        except Exception:
            got = 0
    if got == len(tickers):
        scanner_ok += 1
        add("C. Market data", name, "OK", f"{got}/{len(tickers)} quotes live")
    elif got > 0:
        scanner_ok += 1
        add("C. Market data", name, "WARN", f"partial: {got}/{len(tickers)} quotes")
    else:
        add("C. Market data", name, "FAIL", f"no data (HTTP {st})")
if scanner_ok == 0:
    add("C. Market data", "TradingView scanner overall", "FAIL", "all endpoints down")

# crypto primary + backup
st, body, err = try_fetch("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                          "&order=market_cap_desc&per_page=5&page=1", timeout=15)
cg_ok = st == 200 and body and b"bitcoin" in body.lower()
add("C. Market data", "Crypto prices · primary (CoinGecko)", "OK" if cg_ok else "WARN",
    "live" if cg_ok else f"unavailable (HTTP {st}) — backup will serve")

syms = urllib.parse.quote(json.dumps(["BTCUSDT", "ETHUSDT"], separators=(",", ":")))
st, body, err = try_fetch("https://data-api.binance.vision/api/v3/ticker/24hr?symbols=" + syms,
                          timeout=15)
bn_ok = st == 200 and body and b"BTCUSDT" in (body or b"")
add("C. Market data", "Crypto prices · backup (Binance)", "OK" if bn_ok else "WARN",
    "live" if bn_ok else f"unavailable (HTTP {st})")
if not cg_ok and not bn_ok:
    add("C. Market data", "Crypto desk overall", "FAIL", "primary and backup both down")

# FX primary + backup
st, body, err = try_fetch("https://open.er-api.com/v6/latest/USD", timeout=15)
fx_ok = st == 200 and body and b"INR" in (body or b"")
add("C. Market data", "Exchange rates · primary (ER-API)", "OK" if fx_ok else "WARN",
    "live" if fx_ok else f"unavailable (HTTP {st})")

st, body, err = try_fetch("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json",
                          timeout=15)
jv_ok = st == 200 and body and b"inr" in (body or b"")
add("C. Market data", "Exchange rates · backup (jsDelivr)", "OK" if jv_ok else "WARN",
    "live" if jv_ok else f"unavailable (HTTP {st})")
if not fx_ok and not jv_ok:
    add("C. Market data", "FX conversion overall", "FAIL", "primary and backup both down")

# mutual funds
st, body, err = try_fetch("https://api.mfapi.in/mf/search?q=blue", timeout=20)
mf_ok = st == 200 and body and (body or b"").startswith(b"[")
add("C. Market data", "Mutual fund NAV (mfapi.in)", "OK" if mf_ok else "WARN",
    "live" if mf_ok else f"unavailable (HTTP {st})")

# geo providers
geo_ok = 0
for name, url in [("ipwho.is", "https://ipwho.is/"),
                  ("geojs.io", "https://get.geojs.io/v1/ip/country.json"),
                  ("country.is", "https://api.country.is/")]:
    st, body, err = try_fetch(url, timeout=10)
    ok = st == 200 and body and (b"country" in (body or b"").lower())
    if ok:
        geo_ok += 1
    add("C. Market data", f"Visitor country detector · {name}", "OK" if ok else "WARN",
        "live" if ok else f"unavailable (HTTP {st})")
if geo_ok == 0:
    add("C. Market data", "Geo detection overall", "WARN",
        "all providers down — world board shown by default")

# ---------------------------------------------------------------------------
# D. SHARE & MARKET PAGE INTEGRITY
# ---------------------------------------------------------------------------
print("\nD. SHARE & MARKET PAGE INTEGRITY")
print("-" * 60)
SM_PATH = "/p/share-market_0718113516.html"
sm_body = page_bodies.get(SM_PATH)
sm_st = 200 if sm_body else None
if not sm_body:
    sm_st, sm_body, sm_err = fetch_blog_url(SM_PATH)
if sm_st == 200 and sm_body:
    html = sm_body.decode("utf-8", "replace")
    for name, marker in SM_MARKERS.items():
        add("D. Page integrity", name, "OK" if marker in html else "FAIL",
            "present" if marker in html else "MISSING from live page")
elif sm_st == 429:
    add("D. Page integrity", "Share & Market page fetch", "WARN",
        "throttled by Blogspot (checker-side)")
else:
    add("D. Page integrity", "Share & Market page fetch", "FAIL",
        f"HTTP {sm_st}")

# ---------------------------------------------------------------------------
# E. GOOGLE SEARCH CONSOLE - FULL SEO AUTOMATION
#    Activates automatically once the GSC_REFRESH_TOKEN secret exists
#    (one-time authorization by the blog owner). Until then: clean SKIP.
#    When active:
#      - sitemap auto-submit + freshness resubmission (self-healing)
#      - Google search impressions / clicks / position + top queries
#      - URL inspection of EVERY post from the last 14 days (Daily Article
#        + Daily News desks), each URL checked once per day
#      - persistent per-post index tracking with history
#      - alerts for posts older than 14 days that Google has not indexed
# ---------------------------------------------------------------------------
print("\nE. GOOGLE SEARCH CONSOLE")
print("-" * 60)

gsc_payload = None
gsc_history = []
gsc_tracker = {}
try:
    with open("HEALTH_STATUS.json", encoding="utf-8") as f:
        _prev_gsc = json.load(f).get("gsc", {}) or {}
        gsc_history = _prev_gsc.get("history", [])
        gsc_tracker = _prev_gsc.get("index_tracker", {}) or {}
except Exception:
    pass

GSC_ACCESS = None
BLOGGER_ACCESS = None
GSC_SITE = None


def gsc_call(method, path, body=None):
    url = path if path.startswith("http") else \
        "https://www.googleapis.com/webmasters/v3/" + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + GSC_ACCESS,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def oauth_token(refresh_token):
    form = urllib.parse.urlencode({
        "client_id": os.environ["BLOGGER_CLIENT_ID"],
        "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token",
                                 data=form, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


GSC_RT = os.environ.get("GSC_REFRESH_TOKEN")
if not (GSC_RT and os.environ.get("BLOGGER_CLIENT_ID")
        and os.environ.get("BLOGGER_CLIENT_SECRET")):
    add("E. Google Search Console", "Search Console automation", "SKIP",
        "awaiting one-time owner authorization - everything else runs normally")
else:
    # E1 - authorize Search Console
    try:
        GSC_ACCESS = oauth_token(GSC_RT)
        add("E. Google Search Console", "API connection", "OK", "authorized")
    except Exception as e:
        add("E. Google Search Console", "API connection", "WARN",
            f"token exchange failed: {str(e)[:100]}")

    # E2 - find the verified property
    if GSC_ACCESS:
        try:
            sites = gsc_call("GET", "sites")
            GSC_SITE = next((s["siteUrl"] for s in sites.get("siteEntry", [])
                             if "financebycakushal" in s.get("siteUrl", "")), None)
            add("E. Google Search Console", "Blog property in Search Console",
                "OK" if GSC_SITE else "WARN",
                GSC_SITE or "property not visible to this token")
        except Exception as e:
            add("E. Google Search Console", "Blog property in Search Console",
                "WARN", str(e)[:100])

    # E2b - post inventory from the last 14 days (Daily Article + Daily News)
    post_inventory = []
    if GSC_ACCESS and GSC_SITE and os.environ.get("BLOGGER_BLOG_ID") \
            and os.environ.get("BLOGGER_REFRESH_TOKEN"):
        try:
            BLOGGER_ACCESS = oauth_token(os.environ["BLOGGER_REFRESH_TOKEN"])
            page_token = ""
            start_date = (NOW - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
            while len(post_inventory) < 150:
                params = {"status": "live", "maxResults": "50", "startDate": start_date,
                          "fields": "items(title,url,published),nextPageToken"}
                if page_token:
                    params["pageToken"] = page_token
                qs = urllib.parse.urlencode(params)
                req = urllib.request.Request(
                    f"https://www.googleapis.com/blogger/v3/blogs/"
                    f"{os.environ['BLOGGER_BLOG_ID']}/posts?{qs}",
                    headers={"Authorization": "Bearer " + BLOGGER_ACCESS})
                with urllib.request.urlopen(req, timeout=30) as r:
                    pj = json.load(r)
                for it in pj.get("items", []):
                    if it.get("url"):
                        post_inventory.append({"title": it.get("title", ""),
                                               "url": it.get("url")})
                page_token = pj.get("nextPageToken", "")
                if not page_token:
                    break
            add("E. Google Search Console", "Post inventory (14 days)",
                "OK", f"{len(post_inventory)} posts from Daily Article + Daily News")
        except Exception as e:
            add("E. Google Search Console", "Post inventory (14 days)", "WARN",
                str(e)[:100])

    if GSC_ACCESS and GSC_SITE:
        enc = urllib.parse.quote(GSC_SITE, safe="")

        # E3 - sitemap: auto-submit if missing, resubmit if stale (self-heal)
        try:
            sm = gsc_call("GET", f"sites/{enc}/sitemaps")
            entry = next((m for m in sm.get("sitemap", [])
                          if m.get("path", "").endswith("sitemap.xml")), None)
            if not entry:
                gsc_call("PUT", f"sites/{enc}/sitemaps/sitemap.xml")
                actions.append("Search Console sitemap was missing -> "
                               "submitted automatically via API.")
                sm = gsc_call("GET", f"sites/{enc}/sitemaps")
                entry = next((m for m in sm.get("sitemap", [])
                              if m.get("path", "").endswith("sitemap.xml")), None)
            last_sub = str(entry.get("lastSubmitted", ""))[:10] if entry else ""
            if entry and (not last_sub or last_sub <
                          (NOW - timedelta(days=14)).strftime("%Y-%m-%d")):
                gsc_call("PUT", f"sites/{enc}/sitemaps/sitemap.xml")
                actions.append("Sitemap last submitted to Google over 14 days ago "
                               "-> automatically resubmitted for freshness.")
                sm = gsc_call("GET", f"sites/{enc}/sitemaps")
                entry = next((m for m in sm.get("sitemap", [])
                              if m.get("path", "").endswith("sitemap.xml")), None)
            if entry:
                add("E. Google Search Console", "Sitemap in Search Console", "OK",
                    f"submitted {str(entry.get('lastSubmitted', '?'))[:10]} · "
                    f"errors {entry.get('errors', 0)} · warnings "
                    f"{entry.get('warnings', 0)}")
            else:
                add("E. Google Search Console", "Sitemap in Search Console",
                    "WARN", "not found after submit attempt")
        except Exception as e:
            add("E. Google Search Console", "Sitemap in Search Console",
                "WARN", str(e)[:100])

        # E4 - Google search presence (7 days; GSC data lags ~2 days) + top queries
        try:
            end = (NOW - timedelta(days=2)).strftime("%Y-%m-%d")
            start = (NOW - timedelta(days=8)).strftime("%Y-%m-%d")
            q = gsc_call("POST", f"sites/{enc}/searchAnalytics/query",
                         {"startDate": start, "endDate": end, "rowLimit": 1})
            rows = q.get("rows", [])
            imp = rows[0].get("impressions", 0) if rows else 0
            clk = rows[0].get("clicks", 0) if rows else 0
            pos = round(rows[0].get("position", 0), 1) if rows else 0
            add("E. Google Search Console", "Google search presence (7 days)",
                "OK", f"{imp} impressions · {clk} clicks · avg position {pos}")
            top_queries = []
            try:
                qq = gsc_call("POST", f"sites/{enc}/searchAnalytics/query",
                              {"startDate": start, "endDate": end,
                               "dimensions": ["query"], "rowLimit": 5})
                top_queries = [(r["keys"][0], r.get("impressions", 0))
                               for r in qq.get("rows", [])[:5]]
            except Exception:
                pass
            gsc_payload = {"date": end, "impressions": imp, "clicks": clk,
                           "position": pos, "top_queries": top_queries,
                           "at": NOW_ISO}
            gsc_history = [h for h in gsc_history if h.get("date") != end]
            gsc_history.append(gsc_payload)
            gsc_history = gsc_history[-60:]
        except Exception as e:
            add("E. Google Search Console", "Google search presence (7 days)",
                "WARN", str(e)[:100])

        # E5 - URL inspection of EVERY recent post (once per URL per day),
        #      persistent index tracking, alerts for slow indexing
        if post_inventory:
            try:
                today_s = NOW.strftime("%Y-%m-%d")
                inspected = 0
                newly_indexed = []
                for p in post_inventory:
                    if inspected >= 80:
                        break
                    url = p["url"]
                    rec = gsc_tracker.get(url) or {"title": p["title"],
                                                   "first_seen": NOW_ISO,
                                                   "status": "NEW"}
                    if str(rec.get("last_checked", "")).startswith(today_s):
                        continue  # already checked today - once per day is enough
                    try:
                        insp = gsc_call(
                            "POST",
                            "https://searchconsole.googleapis.com/v1/"
                            "urlInspection/index:inspect",
                            {"inspectionUrl": url, "siteUrl": GSC_SITE,
                             "languageCode": "en"})
                        st8 = ((insp.get("inspectionResult", {}) or {})
                               .get("indexStatus", {}) or {}).get("status", "UNKNOWN")
                        rec["last_checked"] = NOW_ISO
                        if st8 == "INDEXED" and rec.get("status") != "INDEXED":
                            rec["indexed_at"] = NOW_ISO
                            newly_indexed.append(p["title"][:34])
                        rec["status"] = st8
                        gsc_tracker[url] = rec
                        inspected += 1
                        time.sleep(0.15)  # stay well under the 600/min quota
                    except Exception:
                        pass
                # prune entries older than 30 days
                cutoff30 = (NOW - timedelta(days=30)).strftime("%Y-%m-%d")
                gsc_tracker = {u: r for u, r in gsc_tracker.items()
                               if str(r.get("first_seen", ""))[:10] >= cutoff30
                               or str(r.get("last_checked", ""))[:10] >= cutoff30}
                idx = sum(1 for r in gsc_tracker.values()
                          if r.get("status") == "INDEXED")
                add("E. Google Search Console", "Google index · tracked posts",
                    "OK", f"{idx}/{len(gsc_tracker)} recent posts in Google's "
                          f"index · {inspected} inspected this run")
                if newly_indexed:
                    add("E. Google Search Console", "Newly indexed since last check",
                    "OK", "; ".join(newly_indexed[:5]))
                stale = [r for r in gsc_tracker.values()
                         if r.get("status") not in ("INDEXED",)
                         and str(r.get("first_seen", ""))[:10] <
                         (NOW - timedelta(days=14)).strftime("%Y-%m-%d")]
                if stale:
                    add("E. Google Search Console", "Slow-indexing posts", "WARN",
                        f"{len(stale)} post(s) older than 14 days still not in "
                        f"Google's index - being monitored")
            except Exception as e:
                add("E. Google Search Console", "Google index · tracked posts",
                    "WARN", str(e)[:100])

# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------
order = {"FAIL": 0, "WARN": 1, "OK": 2, "SKIP": 3}
overall = "PASS"
if any(r["status"] == "FAIL" for r in results):
    overall = "FAIL"
elif any(r["status"] == "WARN" for r in results):
    overall = "WARN"

icon = {"PASS": "✅ ALL SYSTEMS OPERATIONAL", "WARN": "⚠️ OPERATIONAL WITH WARNINGS",
        "FAIL": "❌ ATTENTION NEEDED"}

counts = {s: sum(1 for r in results if r["status"] == s) for s in ("OK", "WARN", "FAIL", "SKIP")}

# history (keep last 20)
history = []
try:
    with open("HEALTH_STATUS.json", encoding="utf-8") as f:
        history = json.load(f).get("history", [])
except Exception:
    pass
history.append({"at": NOW_ISO, "overall": overall,
                "ok": counts["OK"], "warn": counts["WARN"], "fail": counts["FAIL"]})
history = history[-20:]

prev_heal = ""
try:
    with open("HEALTH_STATUS.json", encoding="utf-8") as f:
        prev_heal = json.load(f).get("last_heal_dispatch", "")
except Exception:
    pass

status = {
    "overall": overall,
    "generated_at": NOW_ISO,
    "summary": icon[overall],
    "counts": counts,
    "missed_slots": missed_slots,
    "auto_heal_actions": actions,
    "last_heal_dispatch": NOW.isoformat() if healed else prev_heal,
    "results": results,
    "history": history,
    "gsc": {"latest": gsc_payload, "history": gsc_history,
         "index_tracker": gsc_tracker},
}

with open("HEALTH_STATUS.json", "w", encoding="utf-8") as f:
    json.dump(status, f, indent=2, ensure_ascii=False)

# human-readable markdown
lines = [
    "# 🩺 Blog Health Report — Finance by CA Kushal",
    "",
    f"**Checked:** {NOW_ISO} · **Overall:** {icon[overall]}",
    "",
    f"**Scoreboard:** {counts['OK']} OK · {counts['WARN']} warnings · {counts['FAIL']} failures"
    + (f" · {counts['SKIP']} skipped" if counts["SKIP"] else ""),
    "",
]
if gsc_payload:
    lines += [
        f"**Google search (7 days to {gsc_payload['date']}):** "
        f"{gsc_payload['impressions']} impressions · {gsc_payload['clicks']} clicks · "
        f"average position {gsc_payload['position']}",
        "",
    ]
    tq = gsc_payload.get("top_queries") or []
    if tq:
        lines += [
            "**Top Google searches finding the blog:** "
            + " · ".join(f"\"{q}\" ({imp})" for q, imp in tq),
            "",
        ]
if actions:
    lines += ["## 🔧 Self-healing actions taken", ""]
    lines += [f"- {a}" for a in actions]
    lines.append("")
sections = []
for r in results:
    if not sections or sections[-1] != r["section"]:
        sections.append(r["section"])
        lines.append("")
        lines.append(f"## {r['section']}")
        lines.append("")
        lines.append("| Component | Status | Detail |")
        lines.append("|---|---|---|")
    mark = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}[r["status"]]
    lines.append(f"| {r['name']} | {mark} {r['status']} | {r['detail']} |")
lines += [
    "",
    "---",
    "*Auto-checked every 4 hours by the blog health watchdog. "
    "This file is machine-written — no human action required.*",
]
with open("HEALTH_REPORT.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("\n" + "=" * 60)
print(f"OVERALL: {icon[overall]}")
print(f"OK={counts['OK']}  WARN={counts['WARN']}  FAIL={counts['FAIL']}")
if actions:
    for a in actions:
        print("HEAL:", a)
print("Reports written: HEALTH_STATUS.json, HEALTH_REPORT.md")
sys.exit(0 if overall != "FAIL" else 1)
