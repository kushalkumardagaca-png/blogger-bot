#!/usr/bin/env python3
"""
DAILY YIELD — Daily News Wires Engine (20 desks, 1 article/day each)
================================================================================
Per-desk rolling window anchored to the desk's IST editorial slot. Sources are
official institutions plus established, reputable newsrooms, with finance-only
filtering and source disclosure. Structure: the compact fbk-* wire template.
3-pass publish: draft(slug-title) -> publish -> update(real title + canonical).
Stdlib only. CLI:
  python3 news_pipeline.py --due            # publish all desks due now (catch-up safe)
  python3 news_pipeline.py --desks india,us # specific desks
  python3 news_pipeline.py --desks india --dry-run   # build, don't publish
"""
import datetime as dt
import email.utils
import hashlib
import html as htmlmod
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, quote_plus, urlencode
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from contextual_links import STYLE as CONTEXT_STYLE, card as contextual_card
from continuous_motion import ensure as ensure_continuous_motion
from related_articles import ensure as ensure_related_articles, fetch_public_posts
from image_safety import FALLBACK_MARKET, FALLBACK_PERSONAL, safe_image
from publication_preflight import assert_publishable
from page_family import ensure_family
from seo_meta import ensure_seo_meta
from seo_hygiene import compact_title, repair_image_alts

# ---------------------------------------------------------------- constants
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
BLOG = "https://dailyyield.blogspot.com"
SEO_QUERY_TERMS = ["Daily Yield", "Kushal Daga", "CA Kushal", "Kushal Jain",
                   "Kushal K. Daga", "Finance", "Finance by Kushal"]
PERSON_ALIASES = ["Kushal Daga", "CA Kushal", "Kushal Jain", "Finance by Kushal"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9"}
CTX = ssl.create_default_context()
TRACKER = os.environ.get("NEWS_TRACKER", "news_tracker.json")
SOCIAL_EVENTS_FILE = os.environ.get("SOCIAL_EVENTS_FILE", "social_events.json")
# Cluster starts 45 minutes before its first desk; paired desks can be 5–15
# minutes later, so the selector includes the full 60-minute cluster runway.
PREFLIGHT_MINUTES = 60
HERO_W, HERO_H = 1600, 900
SESSION_USED_TITLES, SESSION_USED_URLS, SESSION_USED_IMAGES = set(), set(), set()

# Wikimedia Commons searches produce a new, licensed, desk-relevant photo each day.
# Results are date-rotated, checked for image availability and attributed in-page.
HERO_SEARCH = {
 "global": "global financial district skyline", "americas": "Americas financial district skyline",
 "china": "Shanghai skyline financial district", "asia-pacific": "Asia Pacific financial district skyline",
 "india": "Mumbai skyline", "russia": "Moscow International Business Center",
 "europe": "European financial district skyline",
 "markets": "stock exchange commodities digital assets trading",
 "economy": "economic statistics trade employment",
 "banking": "banking digital payments household finance",
 "companies": "office buildings corporate capital markets",
}
# Resilient lawful fallback rotation. Each date/desk gets a different curated
# Unsplash photograph if Commons is unavailable; 25 options cover all 20 desks.
CURATED_HERO_IDS = [
 "photo-1611974789855-9c2a0a7236a3", "photo-1494522855154-9297ac14b55f",
 "photo-1560518883-ce09059eeffa", "photo-1590283603385-17ffb3a7f29f",
 "photo-1493976040374-85c8e12f0c0e", "photo-1518186285589-2f7649de83e0",
 "photo-1502602898657-3e91760cbb34", "photo-1516483638261-f4dbaf036963",
 "photo-1460925895917-afdab827c52f", "photo-1449824913935-59a10b8d2000",
 "photo-1496307653780-42ee777d4833", "photo-1506973035872-a4ec16b8e8d9",
 "photo-1538485399081-7191377e8241", "photo-1554224155-8d04cb21cd6c",
 "photo-1486406146926-c627a92ad1ab", "photo-1579621970563-ebec7560ff3e",
 "photo-1454165804606-c3d57bc86b40", "photo-1526304640581-d334cdbbf45e",
 "photo-1518770660439-4636190af475", "photo-1563013544-824ae1b704d3",
 "photo-1618005182384-a83a8bd57fbe", "photo-1506126613408-eca07ce68773",
 "photo-1532619675605-1ede6c2ed2b0", "photo-1573496359142-b8d87734a5a2",
 "photo-1522202176988-66273c2fd55f",
]

# desk -> (num, label, slug, slot IST "HH:MM", legacy fallback photo id, fallback alt)
DESKS = {
 "global":    (1, "Global Finance News", "global-finance-news", "07:00", "photo-1611974789855-9c2a0a7236a3", "Global financial district skyline at dusk"),
 "americas":  (2, "Americas Finance News", "americas-finance-news", "06:00", "photo-1611974789855-9c2a0a7236a3", "Financial district skyline in the Americas"),
 "china":     (3, "China Finance News", "china-finance-news", "13:00", "photo-1494522855154-9297ac14b55f", "Shanghai financial towers at night"),
 "asia-pacific": (4, "Asia-Pacific Finance News", "asia-pacific-finance-news", "13:45", "photo-1493976040374-85c8e12f0c0e", "Asia-Pacific financial district skyline"),
 "india":     (5, "India Finance News", "india-finance-news", "18:00", "photo-1590283603385-17ffb3a7f29f", "Bombay Stock Exchange building on Dalal Street, Mumbai"),
 "russia":    (6, "Russia Finance News", "russia-finance-news", "22:00", "photo-1460925895917-afdab827c52f", "Moscow financial district and economic analysis"),
 "europe":    (7, "Europe Finance News", "europe-finance-news", "23:00", "photo-1560518883-ce09059eeffa", "European financial district skyline"),
 "markets":   (8, "Markets, Crypto & Commodities", "markets-crypto-commodities", "07:45", "photo-1460925895917-afdab827c52f", "Trading screens, commodities and digital assets"),
 "economy":   (9, "Economy, Trade & Jobs", "economy-trade-jobs", "08:30", "photo-1554224155-8d04cb21cd6c", "Economic statistics, trade and employment analysis"),
 "banking":   (10, "Banking, Fintech & Personal Money", "banking-fintech-personal-money", "09:15", "photo-1579621970563-ebec7560ff3e", "Banking, digital payments and household finance"),
 "companies": (11, "Companies, IPOs & Deals", "companies-ipos-deals", "10:00", "photo-1486406146926-c627a92ad1ab", "Corporate headquarters and capital markets"),
}

GEOGRAPHIC_DESKS = {"global", "americas", "china", "asia-pacific", "india", "russia", "europe"}
CATEGORY_DESKS = {"markets", "economy", "banking", "companies"}
REGION_MEMBERS = {
 "americas": ("us", "canada", "mexico", "brazil"),
 "asia-pacific": ("japan", "south-korea", "australia"),
 "europe": ("uk", "germany", "france", "italy", "spain"),
}

# Canonical labels used by Blogger, the News page and social creative.
GEOGRAPHY_LABELS = {
 "global": "Global Finance News", "americas": "Americas Finance News",
 "china": "China Finance News", "asia-pacific": "Asia-Pacific Finance News",
 "india": "India Finance News", "russia": "Russia Finance News",
 "europe": "Europe Finance News",
}
TOPIC_LABELS = {
 "markets": "Markets, Crypto & Commodities",
 "economy": "Economy, Trade & Jobs",
 "banking": "Banking, Fintech & Personal Money",
 "companies": "Companies, IPOs & Deals",
}
COUNTRY_LABELS = {
 "us": "Country · United States", "canada": "Country · Canada",
 "mexico": "Country · Mexico", "brazil": "Country · Brazil",
 "china": "Country · China", "japan": "Country · Japan",
 "south-korea": "Country · South Korea", "australia": "Country · Australia",
 "india": "Country · India", "russia": "Country · Russia",
 "uk": "Country · United Kingdom", "germany": "Country · Germany",
 "france": "Country · France", "italy": "Country · Italy", "spain": "Country · Spain",
}
DESK_COUNTRIES = {
 "americas": ("us", "canada", "mexico", "brazil"), "china": ("china",),
 "asia-pacific": ("japan", "south-korea", "australia"), "india": ("india",),
 "russia": ("russia",), "europe": ("uk", "germany", "france", "italy", "spain"),
}


# keyword filters for category desks (applied to pooled items)
CATEGORY_FILTERS = {
 "markets": ["market", "trading", "exchange", "liquidity", "volatility", "derivatives",
             "equit", "bond", "yield", "fx", "currency", "bitcoin", "crypto", "token",
             "index", "futures", "gold", "silver", "oil", "gas", "commodit", "copper",
             "opec", "energy price", "fund", "etf", "investor", "reserve"],
 "economy": ["inflation", "cpi", "gdp", "growth", "unemployment", "jobs", "employment",
             "wage", "trade", "tariff", "sanction", "export", "import", "deficit", "debt",
             "policy rate", "repo", "interest rate", "fiscal", "budget", "stimulus", "pmi",
             "retail sales", "industrial", "monetary", "central bank", "economy", "economic",
             "outlook", "statistics", "survey", "consumer", "producer", "supply chain"],
 "banking": ["bank", "deposit", "savings", "mortgage", "housing", "house price", "rent",
             "pension", "retirement", "insurance", "tax", "payment", "loan", "credit",
             "household", "consumer", "cost of living", "fintech", "upi", "wallet",
             "digital payment", "open banking", "neobank", "financial literacy", "fraud",
             "scam", "phishing", "artificial intelligence", "ai ", "cyber"],
 "companies": ["corporate", "company", "earnings", "revenue", "profit", "merger",
               "acquisition", "filing", "governance", "capital", "share", "dividend",
               "buyback", "bankrupt", "restructur", "ipo", "listing", "private equity",
               "venture capital", "startup", "industry", "enterprise", "firm", "deal",
               "takeover", "spin-off", "spinoff", "valuation"],
}

SECTION_ORDER = (
 ("markets", "Markets, Crypto & Commodities"),
 ("economy", "Economy, Trade & Jobs"),
 ("banking", "Banking, Fintech & Personal Money"),
 ("companies", "Companies, IPOs & Deals"),
)


# ---------------------------------------------------------------- sources
# kind: rss | html | json   prio: 1 central bank, 2 ministry/official, 3 stats, 4 regulator/other
SOURCES = {
 "global": [
   ("International Monetary Fund", "https://www.imf.org/en/News", "html", 3),
   ("World Bank", "https://www.worldbank.org/en/news", "html", 3),
   ("European Commission", "https://ec.europa.eu/commission/presscorner/api/rss?language=en&category=press", "rss", 2),
   ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "rss", 1),
 ],
 "us": [
   ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "rss", 1),
   ("US Bureau of Economic Analysis", "https://www.bea.gov/rss/rss.xml", "rss", 3),
   ("US Commodity Futures Trading Commission", "https://www.cftc.gov/RSS/RSSGP/rssgp.xml", "rss", 4),
   ("US Securities and Exchange Commission", "https://www.sec.gov/news/pressreleases", "html", 4),
   ("US Bureau of Labor Statistics", "https://www.bls.gov/bls/news-release-home.htm", "html", 3),
 ],
 "china": [
   ("State Administration of Foreign Exchange", "https://www.safe.gov.cn/en/", "html", 2),
   ("People's Bank of China (English)", "https://www.pbc.gov.cn/en/3688110/index.html", "html", 1),
 ],
 "germany": [
   ("Deutsche Bundesbank", "https://www.bundesbank.de/en/press/press-releases", "html", 1),
   ("Federal Statistical Office of Germany", "https://www.destatis.de/EN/Press/Press-Releases/press-releases.html", "html", 3),
   ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "rss", 1),
   ("European Commission", "https://ec.europa.eu/commission/presscorner/api/rss?language=en&category=press", "rss", 2),
 ],
 "india": [
   ("Securities and Exchange Board of India", "https://www.sebi.gov.in/sebirss.xml", "rss", 4, True),
 ],
 "japan": [
   ("Bank of Japan", "https://www.boj.or.jp/en/whatsnew/index.htm", "html", 1),
   ("Ministry of Finance Japan", "https://www.mof.go.jp/english/", "html", 2),
 ],
 "uk": [
   ("Bank of England", "https://www.bankofengland.co.uk/rss/news", "rss", 1),
   ("UK Office for National Statistics", "https://www.ons.gov.uk/releasecalendar", "html", 3),
   ("Financial Conduct Authority", "https://www.fca.org.uk/news", "html", 2),
 ],
 "france": [
   ("Autorité des Marchés Financiers", "https://www.amf-france.org/en/news-publications/news", "html", 4),
   ("Banque de France", "https://www.banque-france.fr/en", "html", 1),
   ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "rss", 1),
   ("European Commission", "https://ec.europa.eu/commission/presscorner/api/rss?language=en&category=press", "rss", 2),
 ],
 "italy": [
   ("Banca d'Italia", "https://www.bancaditalia.it/chi-siamo/comunicazioni/", "html", 1),
   ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "rss", 1),
   ("European Commission", "https://ec.europa.eu/commission/presscorner/api/rss?language=en&category=press", "rss", 2),
 ],
 "russia": [
   ("Central Bank of Russia", "https://www.cbr.ru/eng/press/pr/", "html", 1),
   ("Moscow Exchange", "https://www.moex.com/en/news/", "html", 4),
 ],
 "canada": [
   ("Bank of Canada", "https://www.bankofcanada.ca/press/press-releases/", "html", 1),
   ("Statistics Canada", "https://www.statcan.gc.ca/eng/dai-quo/ndr/index.htm", "html", 3),
 ],
 "brazil": [
   ("Central Bank of Brazil (English)", "https://www.bcb.gov.br/en/press", "html", 1),
   ("IBGE Brazil", "https://www.ibge.gov.br/en/news.html", "html", 3),
 ],
 "spain": [
   ("Banco de España", "https://www.bde.es/webbde/en/secciones/notas/", "html", 1),
   ("INE Spain", "https://www.ine.es/en/index.htm", "html", 3),
   ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "rss", 1),
   ("European Commission", "https://ec.europa.eu/commission/presscorner/api/rss?language=en&category=press", "rss", 2),
 ],
 "mexico": [
   ("Banco de México", "https://www.banxico.org.mx/publications-and-press.html", "html", 1),
   ("INEGI Mexico", "https://en.www.inegi.org.mx/", "html", 3),
 ],
 "australia": [
   ("Reserve Bank of Australia", "https://www.rba.gov.au/media-releases/", "html", 1),
   ("Australian Bureau of Statistics", "https://www.abs.gov.au/releases", "html", 3),
 ],
 "south-korea": [
   ("Bank of Korea", "https://www.bok.or.kr/eng/main/contents.do?menuNo=400214", "html", 1),
   ("Statistics Korea", "https://kostat.go.kr/en/", "html", 3),
 ],
 "personal": [
   ("Consumer Financial Protection Bureau", "https://www.consumerfinance.gov/about-us/newsroom/feed/", "rss", 2),
 ],
}

# ---------------------------------------------------------------- fetch layer
def http_get(url, tries=2, timeout=14):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last or Exception("fetch failed")

def strip_tags(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", " ", s)
    return htmlmod.unescape(re.sub(r"\s+", " ", s)).strip()

DATE_PATTERNS = [
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), lambda m: (int(m[1]), int(m[2]), int(m[3]))),
    (re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})"), lambda m: (int(m[3]), int(m[2]), int(m[1]))),
    (re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})"), lambda m: (int(m[3]), int(m[1]), int(m[2]))),
    (re.compile(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(\d{4})", re.I),
     lambda m: (int(m[3]), {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}[m[2].lower()[:3]], int(m[1]))),
    (re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})", re.I),
     lambda m: (int(m[3]), {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}[m[1].lower()[:3]], int(m[2]))),
]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def extract_date(text):
    for rx, fn in DATE_PATTERNS:
        m = rx.search(text)
        if m:
            try:
                y, mo, d = fn(m)
                if 2000 < y < 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                    return dt.date(y, mo, d)
            except Exception:
                pass
    return None

def parse_rss(xml_text, source):
    items = []
    try:
        root = ET.fromstring(re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", xml_text))
    except Exception:
        return items
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall(".//item") or root.findall(".//a:entry", ns)
    for e in entries:
        def txt(tag):
            x = e.find(tag)
            if x is None:
                x = e.find("a:" + tag, ns)
            return (x.text or "").strip() if x is not None else ""
        title = txt("title")
        if not title:
            continue
        link = ""
        le = e.find("link")
        if le is None:
            le = e.find("a:link", ns)
        if le is not None:
            link = le.get("href") or (le.text or "").strip()
        if not link:
            link = source[1]
        desc_raw = txt("description") or txt("summary")
        date = None
        for tag in ("pubDate", "published", "updated", "date"):
            dv = txt(tag)
            if dv:
                try:
                    date = email.utils.parsedate_to_datetime(dv).date()
                    break
                except Exception:
                    d2 = extract_date(dv)
                    if d2:
                        date = d2
                        break
        if date is None:
            date = extract_date(title + " " + desc_raw)
        items.append({"title": strip_tags(title), "url": link,
                      "desc": strip_tags(desc_raw)[:900], "date": date,
                      "agency": source[0], "prio": source[3]})
    return items

ANCHOR_RE = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL | re.I)

def parse_html_listing(page_text, source):
    """Generic: anchors whose surroundings carry a date."""
    items = []
    base = source[1]
    NAV_JUNK = re.compile(r"^(overview|organisation|organization|executive board|location|list of|"
                          r"guide|branches|head office|public holidays|investor relations|"
                          r"feedback|subscribe|search|contact|faq|glossary|see more|see all|"
                          r"read more|learn more|back to|home|news$|press$|press releases?$|"
                          r"all releases|related links|share|print|font size|"
                          r"enable/disable.*|skip to.*|photo.*|cookie.*)$", re.I)
    out = []
    for m in ANCHOR_RE.finditer(page_text):
        href, label = m.group(1), m.group(2)
        if href.startswith(("javascript", "mailto", "tel:", "data:")):
            continue
        url = urljoin(base, href)
        if not url.startswith("http"):
            continue
        title = strip_tags(label)
        if len(title) < 25 or url.count("/") < 3:
            continue
        if NAV_JUNK.match(title.strip()):
            continue
        if any(x in url.lower() for x in ["facebook", "twitter", "linkedin", "javascript",
                                            "mailto", "#", "cookie", "privacy", "rss",
                                            "accessib", "sitemap", "terms", "disclaimer",
                                            "careers", "vacanc", "tender"]):
            continue
        if any(x in title.lower() for x in ["accessibility", "privacy policy", "terms of use",
                                            "sitemap", "careers", "vacancy", "archived"]):
            continue
        ctx = page_text[max(0, m.start() - 600): min(len(page_text), m.end() + 600)]
        d = extract_date(ctx)
        out.append({"title": title, "url": url, "desc": "", "date": d,
                    "agency": source[0], "prio": source[3]})
    return out[:80]

def fetch_source(source):
    name, url, kind, prio = source[0], source[1], source[2], source[3]
    trust = len(source) > 4 and source[4]
    media = name in MEDIA_NAMES
    try:
        text = http_get(url)
    except Exception as e:
        return name, []
    if kind == "gnr":
        items = parse_gnr(text, source)
        media = True
    else:
        items = parse_rss(text, source) if kind == "rss" else parse_html_listing(text, source)
    if media:  # newsrooms cover everything; keep only finance/economy stories
        items = [i for i in items if FINANCE_RE.search(i["title"])]
    if trust:  # feed rebuilt continuously; undated items count as current
        for i in items:
            if i["date"] is None:
                i["date"] = dt.datetime.now(IST).date() - dt.timedelta(days=1)
    for i in items:
        i["media"] = i.get("media", media)
    return name, items

# Verified-rich official sources used to top up every desk (own items still lead).
GLOBAL_POOL = [
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "rss", 2),
    ("US Bureau of Economic Analysis", "https://www.bea.gov/rss/rss.xml", "rss", 3),
    ("US Commodity Futures Trading Commission", "https://www.cftc.gov/RSS/RSSGP/rssgp.xml", "rss", 3),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", "rss", 2),
    ("European Commission", "https://ec.europa.eu/commission/presscorner/api/rss?language=en&category=press", "rss", 3),
    ("Bank of England", "https://www.bankofengland.co.uk/rss/news", "rss", 2),
    ("UK Office for National Statistics", "https://www.ons.gov.uk/releasecalendar", "html", 3),
   ("Financial Conduct Authority", "https://www.fca.org.uk/news", "html", 2),
    ("Securities and Exchange Board of India", "https://www.sebi.gov.in/sebirss.xml", "rss", 3, True),
    ("State Administration of Foreign Exchange of China", "https://www.safe.gov.cn/en/", "html", 3),
    ("Ministry of Finance Japan", "https://www.mof.go.jp/english/", "html", 3),
    ("Deutsche Bundesbank", "https://www.bundesbank.de/en/press/press-releases", "html", 3),
    ("Bank of Canada", "https://www.bankofcanada.ca/press/press-releases/", "html", 3),
    ("Financial Conduct Authority", "https://www.fca.org.uk/news", "html", 3),
]

# Trusted newsrooms (user-approved 2026-09-24: "any genuine and trustworthy sources").
# Media items must pass FINANCE_RE to stay on-topic for a finance wire.
MEDIA = {
 "us": [("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "rss", 1),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "rss", 2)],
 "uk": [("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "rss", 1),
        ("The Guardian Business", "https://www.theguardian.com/uk/business/rss", "rss", 1)],
 "russia": [("TASS", "https://tass.com/rss/v2.xml", "rss", 1),
            ("The Moscow Times", "https://www.themoscowtimes.com/rss/news", "rss", 1)],
 "south-korea": [("Yonhap News Agency", "https://en.yna.co.kr/RSS/news.xml", "rss", 1)],
 "japan": [("The Japan Times", "https://www.japantimes.co.jp/feed/", "rss", 2)],
 "china": [("South China Morning Post", "https://www.scmp.com/rss/4/feed", "rss", 1)],
 "australia": [("ABC News Australia", "https://www.abc.net.au/news/feed/51120/rss.xml", "rss", 1)],
 "canada": [("CBC Business", "https://www.cbc.ca/webfeed/rss/rss-business", "rss", 1),
            ("BNN Bloomberg Canada", "https://www.bnnbloomberg.ca/", "html", 1)],
 "mexico": [("Mexico News Daily", "https://mexiconewsdaily.com/feed/", "rss", 1),
            ("The Rio Times", "https://www.riotimesonline.com/feed/", "rss", 1),
            ("Google News: Mexico Finance", "https://news.google.com/rss/search?q=Mexico+finance+when:1d&hl=en-US&gl=US&ceid=US:en", "gnr", 2)],
 "germany": [("Deutsche Welle", "https://rss.dw.com/xml/rss-en-all", "rss", 3)],
 "france": [("Le Monde", "https://www.lemonde.fr/en/rss/une.xml", "rss", 2)],
 "india": [("The Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "rss", 2)],
 "brazil": [("ANBA", "https://www.anba.com.br/en/rss", "rss", 1),
           ("The Rio Times", "https://www.riotimesonline.com/feed/", "rss", 1),
           ("MercoPress", "https://en.mercopress.com/rss", "rss", 2)],
 "global": [("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "rss", 2),
            ("France 24 Business", "https://www.france24.com/en/business/rss", "rss", 3)],
 "spain": [("El País (English)", "https://english.elpais.com/arc/outboundfeeds/rss/?outputType=xml", "rss", 1),
           ("The Corner", "https://thecorner.eu/feed/", "rss", 2),
           ("Google News: Spain Finance", "https://news.google.com/rss/search?q=Spain+finance+when:1d&hl=en-US&gl=US&ceid=US:en", "gnr", 2)],
 "italy": [("ANSA English", "https://www.ansa.it/english/news/english_rss.xml", "rss", 1),
           ("Google News: Italy Finance", "https://news.google.com/rss/search?q=Italy+finance+when:1d&hl=en-US&gl=US&ceid=US:en", "gnr", 2)],
 "personal": [("The Guardian Money", "https://www.theguardian.com/uk/money/rss", "rss", 1)],
}
GLOBAL_MEDIA = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "rss", 3),
    ("The Guardian Business", "https://www.theguardian.com/uk/business/rss", "rss", 3),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "rss", 3),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "rss", 4),
]
MEDIA_NAMES = {s[0] for lst in MEDIA.values() for s in lst} | {s[0] for s in GLOBAL_MEDIA}

def resolve_url(u, timeout=8):
    """Follow redirects to the final publisher URL (best effort)."""
    try:
        req = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.geturl() or u
    except Exception:
        return u

GNR_ALLOWED_PUBLISHERS = {
    "Reuters", "Associated Press", "AP News", "Bloomberg", "BNN Bloomberg",
    "CNBC", "BBC", "The Guardian", "Deutsche Welle", "France 24",
    "Yahoo Finance", "Yahoo News UK", "Il Sole 24 ORE", "ANSA",
    "El País", "The Economic Times", "Mexico Business News", "Mexico News Daily",
    "Financial Times", "The New York Times", "The Telegraph", "The Globe and Mail",
    "CTV News", "South China Morning Post", "RFI", "WSJ", "Yonhap News Agency",
    "Yahoo News Canada", "Yahoo News New Zealand", "Yahoo! Finance Canada",
    "Investing.com", "Investing.com UK", "Investing.com India", "The Local Italy",
    "Olive Press News Spain", "Sur in English", "Idealista", "The Straits Times",
    "Toronto Star", "Business Standard", "Global Banking & Finance Review",
    "Morningstar", "S&P Global", "Fitch Ratings", "Moody's Ratings",
    "J.P. Morgan Research", "Goldman Sachs", "BlackRock", "Vanguard",
    "World Economic Forum", "Harvard Business Review", "Knowledge at Wharton",
}

def parse_gnr(xml_text, source):
    """Google News RSS: retain only approved publishers and their source link."""
    items = parse_rss(xml_text, source)
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        urls = list(ex.map(resolve_url, [i["url"] for i in items[:40]]))
    for i, u in zip(items[:40], urls):
        t = i["title"]
        if " - " in t:
            head, pub = t.rsplit(" - ", 1)
            head, pub = head.strip(), pub.strip()
        else:
            head, pub = t, "Google News"
        if not pub or len(pub) > 40 or pub not in GNR_ALLOWED_PUBLISHERS:
            continue
        out.append({"title": head, "url": u, "desc": i["desc"], "date": i["date"],
                    "agency": pub, "prio": source[3], "media": True,
                    "country_discovery": True})
    return out
# own-country relevance hints for media items on country desks
COUNTRY_HINTS = {
 "americas": r"\b(us|u\.s\.|united states|america|canada|canadian|mexico|mexican|brazil|brazilian|dollar|peso|real|wall street|fed|nyse|nasdaq|toronto|ottawa|banxico|sao paulo)\b",
 "asia-pacific": r"\b(japan|japanese|south korea|korean|australia|australian|yen|won|tokyo|seoul|sydney|nikkei|kospi|asx|boj|rba)\b",
 "europe": r"\b(uk|britain|british|germany|german|france|french|italy|italian|spain|spanish|euro|sterling|london|frankfurt|paris|milan|madrid|ecb|bank of england)\b",
 "us": r"\b(us|u\.s\.|united states|america|dollar|wall street|fed|nyse|nasdaq|s&p|washington)\b",
 "china": r"\b(china|chinese|yuan|renminbi|beijing|shanghai|shenzhen|hang seng|alibaba|tencent|byd)\b",
 "germany": r"\b(germany|german|frankfurt|bundesbank|dax|berlin)\b",
 "india": r"\b(india|indian|rupee|mumbai|sensex|nifty|reliance|adani|tata|rbi|sebi|gst|bharat)\b",
 "japan": r"\b(japan|japanese|yen|tokyo|nikkei|toyota|sony|boj)\b",
 "uk": r"\b(uk|britain|british|pound|sterling|london|ftse|bank of england)\b",
 "france": r"\b(france|french|paris|cac |macron)\b",
 "italy": r"\b(italy|italian|milan|ftse mib|italia)\b",
 "russia": r"\b(russia|russian|ruble|rouble|moscow|kremlin|putin|gazprom|rosneft|sberbank)\b",
 "canada": r"\b(canada|canadian|loonie|toronto|ottawa|bank of canada)\b",
 "brazil": r"\b(brazil|brazilian|brasil|bovespa|sao paulo|petrobras|vale|lula|real )\b",
 "spain": r"\b(spain|spanish|madrid|ibex|espana)\b",
 "mexico": r"\b(mexico|mexican|peso|banxico|sheinbaum|cemex|amlo)\b",
 "australia": r"\b(australia|australian|aussie|sydney|asx|rba|canberra)\b",
 "south-korea": r"\b(korea|korean|won |seoul|kospi|samsung|hyundai|chaebol)\b",
}
HINT_RE = {d: re.compile(p, re.I) for d, p in COUNTRY_HINTS.items()}
# Broad lawful discovery fallback. Google News RSS supplies discovery only; the
# edition retains the named original publisher and its source link. Country
# relevance, finance relevance, date, publisher trust and duplicate checks still apply.
ANALYSIS_TERMS = ("forecast", "outlook", "analyst expectations", "economic consequences")
ANALYSIS_RE = re.compile(r"\b(forecast|outlook|expect(?:s|ed|ation)?|project(?:s|ed|ion)?|predict(?:s|ed|ion)?|"
                         r"estimate(?:s|d)?|target|scenario|analyst|strategist|economist|adviser|advisor|"
                         r"research(?:er)?|opinion|likely|could|may|risk)\b", re.I)

DISCOVERY_LABELS = {
    "us": "United States", "canada": "Canada", "mexico": "Mexico", "brazil": "Brazil",
    "japan": "Japan", "south-korea": "South Korea", "australia": "Australia",
    "uk": "United Kingdom", "germany": "Germany", "france": "France",
    "italy": "Italy", "spain": "Spain", "china": "China", "india": "India",
    "russia": "Russia",
}

def discovery_sources(desk):
    label = DISCOVERY_LABELS.get(desk, DESKS.get(desk, (None, desk.replace("-", " ").title()))[1])
    out = []
    for term in ("finance", "economy", "business", "markets") + ANALYSIS_TERMS:
        query = quote_plus(f'{label} {term} when:1d')
        out.append((f'Google News: {label} {term.title()}',
                    f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en',
                    'gnr', 2))
    return out

def global_analysis_sources():
    """Discovery-only feeds for attributable forecasts, expectations and consequences."""
    out = []
    for term in ANALYSIS_TERMS:
        query = quote_plus(f'global finance {term} when:1d')
        out.append((f'Google News: Global {term.title()}',
                    f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en',
                    'gnr', 2))
    return out

FINANCE_RE = re.compile(r"\b(rate|inflation|cpi|gdp|growth|recession|econom|market|bank|trade|tariff|"
                        r"tax|budget|deficit|debt|currency|rupee|yen|yuan|euro|dollar|pound|ruble|"
                        r"rouble|won|peso|oil|gas|energy|gold|commodit|pric|merger|acquisition|ipo|"
                        r"earnings|revenue|profit|jobs|employ|unemploy|wage|salary|stimulus|fiscal|"
                        r"monetary|central bank|regulat|securit|bond|equit|stock|share|investor|"
                        r"fund|loan|credit|mortgage|housing|rent|pension|retirement|insurance|"
                        r"consumer|spending|retail|industrial|export|import|compan|corporate|"
                        r"business|industr|sanction|fine|penalt|startup|crypt|bitcoin|wealth|"
                        r"money|cash|payment|income|cost|fee|million|billion|trillion)", re.I)

COUNTRY_TO_REGION = {
    "us": "americas", "canada": "americas", "mexico": "americas", "brazil": "americas",
    "japan": "asia-pacific", "south-korea": "asia-pacific", "australia": "asia-pacific",
    "uk": "europe", "germany": "europe", "france": "europe", "italy": "europe", "spain": "europe",
    "china": "china", "india": "india", "russia": "russia",
}
AGENCY_COUNTRIES = {}
for _country, _sources in list(SOURCES.items()) + list(MEDIA.items()):
    if _country in COUNTRY_TO_REGION:
        for _source in _sources:
            AGENCY_COUNTRIES.setdefault(_source[0], set()).add(_country)

def classify_topic(item):
    text = (item.get("title", "") + " " + item.get("desc", "")).lower()
    scores = {key: sum(1 for term in terms if term in text) for key, terms in CATEGORY_FILTERS.items()}
    return max(scores, key=lambda key: (scores[key], -list(CATEGORY_FILTERS).index(key))) if any(scores.values()) else "economy"

def classify_country(item):
    text = item.get("title", "") + " " + item.get("desc", "")
    matches = [country for country, rx in HINT_RE.items()
               if country in COUNTRY_TO_REGION and rx.search(text)]
    if matches:
        return matches[0]
    agencies = AGENCY_COUNTRIES.get(item.get("agency", ""), set())
    return next(iter(agencies)) if len(agencies) == 1 else "global"

def fetch_desk_items(desk):
    if desk in CATEGORY_DESKS or desk == "global":
        srcs = [s for d, lst in SOURCES.items() for s in lst] + \
               [s for d, lst in MEDIA.items() for s in lst] + GLOBAL_POOL + GLOBAL_MEDIA + global_analysis_sources()
        own_off, own_med = set(), set()
    else:
        members = REGION_MEMBERS.get(desk, (desk,))
        off = [source for member in members for source in SOURCES.get(member, [])]
        med = [source for member in members for source in MEDIA.get(member, [])]
        have_media = {s[1] for s in med}
        for member in members:
            for discovery in discovery_sources(member):
                if discovery[1] not in have_media:
                    med.append(discovery)
                    have_media.add(discovery[1])
        have = {s[1] for s in off + med}
        srcs = off + med + [s for s in GLOBAL_POOL + GLOBAL_MEDIA if s[1] not in have]
        shared_official = {"European Central Bank", "European Commission"}
        own_off = {s[0] for s in off if s[0] not in shared_official}
        own_med = {s[0] for s in med}
    seen, seen_urls, out = set(), set(), []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for name, items in ex.map(fetch_source, srcs):
            for it in items:
                if it["date"] is None:
                    continue
                key = re.sub(r"\W", "", it["title"].lower())[:60]
                if key in seen or it["url"] in seen_urls:
                    continue
                seen.add(key)
                seen_urls.add(it["url"])
                it["desk_pool"] = name
                it["topic"] = classify_topic(it)
                it["country"] = classify_country(it)
                it["region"] = COUNTRY_TO_REGION.get(it["country"], "global")
                out.append(it)
    return out, own_off, own_med

# ECB official reference rates (JSON, official source)
def ecb_reference_rates():
    try:
        data = json.loads(http_get("https://api.frankfurter.app/latest?from=EUR"))
        # frankfurter mirrors ECB reference rates; official values
        return data.get("rates", {})
    except Exception:
        return {}

# ---------------------------------------------------------------- selection
SALIENT = re.compile(r"\b(rate|inflation|cpi|gdp|growth|unemploy|jobs|trade|tariff|deficit|"
                     r"debt|budget|tax|pension|deposit|mortgage|housing|market|bond|yield|"
                     r"equit|currency|rupee|dollar|euro|yen|yuan|won|ruble|real|peso|loonie|"
                     r"bitcoin|crypto|bank|regulat|circular|merger|earnings|ipo|auction|"
                     r"reserve|liquidity|repo|policy)", re.I)

def select_items(all_items, win_start, win_end, desk, selection_cap=40, own_off=None, own_med=None):
    """Rank the complete relevant pool for adaptive 24–34-headline editions.

    Significance controls ordering, never whether a desk edition exists. If a
    genuinely small pool has fewer than 12 current items, publish all of them;
    only below ten may up to three clearly dated background items supplement it.
    """
    own_off = own_off or set()
    own_med = own_med or set()
    lo = win_start.date()
    hi = win_end.date()
    hint = HINT_RE.get(desk)

    def desk_match(i):
        if desk in CATEGORY_DESKS:
            return i.get("topic") == desk
        if desk in REGION_MEMBERS:
            return i.get("region") == desk or i.get("country") == "global"
        if desk in {"china", "india", "russia"}:
            return i.get("country") in {desk, "global"}
        return True

    def score(i):
        s = 100 - i["prio"] * 10
        s += 25 if SALIENT.search(i["title"]) else 0
        if own_off or own_med:
            if i["agency"] in own_off:
                s += 60
            elif i["agency"] in own_med:
                s += 40
                if hint and not hint.search(i["title"]):
                    s -= 50
            else:
                s -= 25
        s += (i["date"] - lo).days * 2
        return -s

    def curate(items):
        """Rank, de-duplicate and limit source domination without a total ceiling."""
        counts, result, seen = {}, [], set()
        for item in sorted(items, key=score):
            key = clean_title(item["title"]).lower()
            if key in seen:
                continue
            cap = 12 if item["agency"] in own_off else (8 if item["agency"] in own_med else 5)
            if counts.get(item["agency"], 0) >= cap:
                continue
            counts[item["agency"]] = counts.get(item["agency"], 0) + 1
            seen.add(key)
            result.append(item)
        return result

    ranked = curate([i for i in all_items if i.get("date") and lo <= i["date"] <= hi and desk_match(i)])
    if desk not in CATEGORY_DESKS and desk != "global":
        # A country wire must actually be about that country or come from its
        # local official record. Generic international pool items do not fill it.
        relevant = [i for i in ranked
                    if i["agency"] in own_off or i["agency"] in own_med
                    or i.get("country_discovery")
                    or (hint and hint.search(i["title"]))]
    else:
        relevant = ranked

    def balanced_take(pool, key_name, targets, limit):
        """Meet section/geography minimums first, then fill by editorial rank."""
        chosen, used = [], set()
        for key, target in targets:
            for item in [row for row in pool if row.get(key_name) == key][:target]:
                marker = item.get("url") or story_title_key(item.get("title", ""))
                if marker not in used:
                    chosen.append(item); used.add(marker)
        for item in pool:
            marker = item.get("url") or story_title_key(item.get("title", ""))
            if marker in used:
                continue
            chosen.append(item); used.add(marker)
            if len(chosen) >= limit:
                break
        return chosen[:limit]

    if desk in CATEGORY_DESKS:
        geography_targets = (("global", 2), ("india", 4), ("china", 4), ("russia", 3),
                             ("americas", 7), ("europe", 7), ("asia-pacific", 6))
        current = balanced_take(relevant, "region", geography_targets, selection_cap)
    else:
        topic_targets = tuple((topic, 7) for topic, _label in SECTION_ORDER)
        current = balanced_take(relevant, "topic", topic_targets, selection_cap)

    # Background is a transparent context supplement, never disguised as current news.
    # It is used only below ten current items and is always capped at three.
    background = []
    if len(current) < 10:
        floor = lo - dt.timedelta(days=3)
        current_titles = {clean_title(i["title"]).lower() for i in current}
        older = [i for i in all_items if i.get("date") and floor <= i["date"] < lo
                 and desk_match(i) and SALIENT.search(i["title"])]
        if desk not in CATEGORY_DESKS and desk != "global":
            older = [i for i in older if i["agency"] in own_off or i["agency"] in own_med
                     or (hint and hint.search(i["title"]))]
        for item in curate(older):
            if clean_title(item["title"]).lower() in current_titles:
                continue
            framed = dict(item)
            framed["background"] = True
            background.append(framed)
            if len(background) >= min(3, 10 - len(current)):
                break

    upcoming = [i for i in all_items
                if i.get("date") and hi < i["date"] <= hi + dt.timedelta(days=7)][:6]
    return current + background, upcoming, lo

# ---------------------------------------------------------------- composition
def clean_title(t):
    t = re.sub(r"\s+", " ", t).strip(" .:-–|")
    return t

def story_title_key(title):
    """Stable exact-headline key shared across every desk in an edition."""
    return re.sub(r"[^a-z0-9]+", " ", clean_title(htmlmod.unescape(strip_tags(title or ""))).casefold()).strip()


def rendered_story_key(item, summary_maximum=None):
    """Match the source-led sentence that compose_item will actually display."""
    desc = re.sub(r"\s+", " ", strip_tags(item.get("desc", ""))).strip()
    if len(desc) > 20:
        cut = desc.find(". ", 60)
        if 0 < cut < 320:
            desc = desc[:cut + 1]
        core = desc
        if summary_maximum:
            core = " ".join(core.split()[:summary_maximum]).rstrip(" .") + "."
    else:
        core = clean_title(item.get("title", ""))
    value = f"{item.get('agency', '')} {core}"
    return re.sub(r"[^a-z0-9]+", " ", htmlmod.unescape(value).casefold()).strip()


def dedupe_rendered_stories(items, summary_maximum=None):
    """Prevent two source records from producing an identical visible paragraph."""
    seen, unique = set(), []
    for item in items:
        key = rendered_story_key(item, summary_maximum)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(item)
    return unique


META_DESCRIPTION_RE = re.compile(
    r'<meta\b[^>]*(?:name|property)=["\'](?:description|og:description|twitter:description)["\'][^>]*content=["\'](.*?)["\']',
    re.I | re.S)
META_DESCRIPTION_RE_ALT = re.compile(
    r'<meta\b[^>]*content=["\'](.*?)["\'][^>]*(?:name|property)=["\'](?:description|og:description|twitter:description)["\']',
    re.I | re.S)


def source_description(url):
    """Read only publisher-supplied metadata; never manufacture a source summary."""
    try:
        page = http_get(url, tries=1, timeout=10)
    except Exception:
        return ""
    candidates = META_DESCRIPTION_RE.findall(page) + META_DESCRIPTION_RE_ALT.findall(page)
    cleaned = [strip_tags(value) for value in candidates]
    cleaned = [value for value in cleaned if len(value.split()) >= 12]
    return max(cleaned, key=len)[:1200] if cleaned else ""


def enrich_item_descriptions(items):
    """Top up sparse feed records from the linked publisher's own page metadata."""
    targets = [item for item in items if len(strip_tags(item.get("desc", "")).split()) < 12]
    if not targets:
        return items
    with ThreadPoolExecutor(max_workers=8) as executor:
        descriptions = list(executor.map(lambda item: source_description(item.get("url", "")), targets))
    for item, description in zip(targets, descriptions):
        if description:
            item["desc"] = description
    return items


def item_source_is_usable(item):
    """A rich wire item needs a named source, secure link and real publisher synopsis."""
    url = item.get("url", "").strip()
    return bool(clean_title(item.get("title", "")) and item.get("agency", "").strip()
                and url.startswith("https://")
                and len(strip_tags(item.get("desc", "")).split()) >= 12)


def load_today_story_keys(day):
    """Inventory already-live News stories so later desks cannot republish them."""
    titles, urls = set(), set()
    try:
        feed = json.loads(http_get(
            f"{BLOG}/feeds/posts/default/-/News?alt=json&max-results=100", timeout=20))
        for entry in feed.get("feed", {}).get("entry", []):
            published = dt.datetime.fromisoformat(entry["published"]["$t"]).astimezone(IST)
            if published.date() != day:
                continue
            body = (entry.get("content") or entry.get("summary") or {}).get("$t", "")
            # Items appear before reference/week-ahead sections; do not reserve
            # the shared ECB reference card as though it were a news headline.
            body = re.split(r"<h2[^>]*class=[\"'][^\"']*fbk-h2[^\"']*[\"'][^>]*>\s*<b>\s*(?:04|05|BG)",
                            body, maxsplit=1, flags=re.I)[0]
            for block in re.findall(r"<div[^>]+class=[\"'][^\"']*fbk-item[^\"']*[\"'][^>]*>(.*?)</div>",
                                    body, flags=re.I | re.S):
                match = re.search(r"<h3[^>]*>(.*?)</h3>", block, flags=re.I | re.S)
                if match:
                    key = story_title_key(match.group(1))
                    if key:
                        titles.add(key)
                match = re.search(r"<a[^>]+class=[\"'][^\"']*fbk-src[^\"']*[\"'][^>]+href=[\"']([^\"']+)",
                                  block, flags=re.I)
                if match:
                    urls.add(htmlmod.unescape(match.group(1)).strip())
    except Exception as exc:
        # A feed outage must not stop a desk; in-process reservation still protects pairs.
        print(f"  [dedupe] live News inventory unavailable: {exc}")
    return titles, urls

def item_type(title):
    tl = title.lower()
    for key, typ in [("cpi", "inflation"), ("inflation", "inflation"), ("price index", "inflation"),
                     ("gdp", "growth"), ("gross domestic", "growth"), ("growth", "growth"),
                     ("unemploy", "jobs"), ("jobs", "jobs"), ("employment", "jobs"), ("payroll", "jobs"),
                     ("rate", "rates"), ("repo", "rates"), ("monetary policy", "rates"),
                     ("trade", "trade"), ("tariff", "trade"), ("export", "trade"), ("import", "trade"),
                     ("budget", "fiscal"), ("deficit", "fiscal"), ("tax", "fiscal"), ("fiscal", "fiscal"),
                     ("mortgage", "housing"), ("housing", "housing"), ("house price", "housing"),
                     ("deposit", "deposits"), ("savings", "deposits"),
                     ("merger", "corporate"), ("acquisition", "corporate"), ("earnings", "corporate"),
                     ("fine", "enforcement"), ("penalty", "enforcement"), ("enforcement", "enforcement"),
                     ("regulat", "regulation"), ("circular", "regulation"), ("rule", "regulation"),
                     ("ipo", "markets"), ("listing", "markets"), ("bond", "markets"), ("yield", "markets"),
                     ("crypto", "crypto"), ("bitcoin", "crypto"),
                     ("pension", "pensions"), ("retirement", "pensions")]:
        if key in tl:
            return typ
    return "other"

WHY = {
 "inflation": ["Inflation prints reset the path for policy rates — and through them, deposit, loan and mortgage pricing.",
               "For households, the inflation number is the silent tax on every savings balance; markets price the next policy move off it.",
               "One print rarely changes policy, but three in a direction does — this one lands in the official record either way."],
 "growth": ["Growth numbers move bond yields and currency expectations first; wages and hiring follow with a lag.",
            "The composition of growth matters more than the headline — but the headline sets the narrative."],
 "jobs": ["Labour-market prints are the twin anchor of rate policy alongside inflation; both set the cost of money.",
          "Employment data moves rate expectations within minutes of release — and household borrowing costs soon after."],
 "rates": ["The cost of money changes every other price in the system — deposits, EMIs, mortgages and bond yields all re-anchor.",
           "Rate decisions are the single most-watched official number in finance; the guidance matters as much as the move."],
 "trade": ["Trade data feeds directly into currency expectations and into the inflation path via import prices.",
           "Tariff and trade shifts reprice supply chains first, consumer prices second."],
 "fiscal": ["Fiscal numbers set the bond supply that yields must digest — and the tax burden that households must plan around.",
            "Deficits today are the tax schedules of tomorrow; the market prices the bridge."],
 "housing": ["Housing is most households' largest asset and liability at once — asking prices and mortgage rates move together.",
             "Housing data lands with a lag but compounds quietly: affordability resets slowly, then all at once."],
 "deposits": ["Deposit and savings pricing is where policy actually reaches the household balance sheet.",
              "For savers, the official rate path decides whether lock-ins are worth it this cycle."],
 "corporate": ["Corporate actions reprice sectors before they reprice the index; filings are where the record lives.",
               "Disclosure-first coverage: the filing is the news, everything else is commentary."],
 "enforcement": ["Enforcement actions set the compliance baseline for everyone else in the market.",
                 "Regulatory penalties are the tuition the industry pays — the circular that follows is the syllabus."],
 "regulation": ["New rules quietly reprice whole product lines — always read the circular before the commentary.",
                "Regulation is the operating system of finance; version updates matter."],
 "markets": ["Market plumbing news — listings, bonds and infrastructure — moves liquidity before it moves headlines.",
             "Primary-market and exchange news is where the next quarter's positioning is being set."],
 "crypto": ["Crypto now trades inside the regulated perimeter — official statements move it like any other asset.",
            "Digital-asset policy is being written in real time; each official line moves the market's boundary."],
 "pensions": ["Pension changes are the longest-dated liability most households hold — small rule changes compound for decades.",
              "Retirement math is patient math: every official tweak here lands years later, with interest."],
 "other": ["Official releases are the primary record — the market's commentary will follow, this is the source.",
           "Watch the primary document, not the headline about it."],
}

def fmt_day(d):
    return f"{MONTHS[d.month-1]} {d.day}"

CONSEQUENCE = {
 "inflation": "Inflation changes purchasing power and assumptions about rates, wages, budgets and valuation. Later releases may confirm the direction, revise it, or show that pressure was concentrated. A stronger path can keep borrowing conditions restrictive; a weaker path can support expectations of easier policy. These are conditional channels, not predictions.",
 "growth": "Growth evidence matters through revenue, tax receipts, employment and confidence, but a headline rate does not show which sectors or households gained. Compare it with earlier estimates, expectations and revisions. Upside and downside surprises can change rate, earnings and fiscal assumptions, although later evidence may alter that interpretation.",
 "jobs": "Labour evidence connects household income, demand, wage pressure and monetary policy. Useful comparisons include expectations, participation and revisions. Persistent strength can sustain demand and rate pressure, while broad weakness can affect spending and credit quality. The future path remains contingent on later releases.",
 "rates": "Rates and policy guidance transmit through deposits, loans, mortgages, bonds, currencies and company discount rates. Markets often react to the gap between the decision and expectations. Restrictive policy may raise financing costs; easier policy may support demand while interacting with inflation and currency risk. Neither scenario is guaranteed.",
 "trade": "Trade and sanctions can affect supply chains, export demand, import costs, currencies and public revenue in several economies. Timing and scale depend on implementation, exemptions, substitution and retaliation. Businesses and investors may therefore focus on exposed sectors and counterparties instead of treating the headline as an economy-wide result.",
 "fiscal": "Fiscal measures can change disposable income, public borrowing, bond supply and sector demand. Announcements may differ from final legislation, timing and measured effects. Borrowing can influence yields and currencies, while targeted support can alter cash flow. These are possible transmission channels, not certain outcomes.",
 "housing": "Housing affects affordability, wealth, construction and lenders. Prices, rents, sales and mortgage costs can move differently, so one measure cannot represent the whole market. Future effects depend on income, supply, financing and local rules. A broad outlook is not advice about one property.",
 "deposits": "Savings developments affect liquidity and returns available without market risk. Compare term, access, tax, inflation and provider protection rather than an advertised rate alone. Policy expectations may influence future rates, but those expectations change. This is general context, not an account recommendation.",
 "corporate": "Corporate news can affect cash flow, capital needs, competitors, workers and investors, but an announcement is not a completed outcome. For an IPO or valuation, uncertainties include final pricing, demand, dilution, proceeds and later trading. For earnings or transactions, guidance and conditions matter with headline figures.",
 "enforcement": "Enforcement news concerns a defined process and should not be broadened beyond the source's jurisdiction and words. Possible effects include compliance cost, operating changes, compensation or precedent, depending on the final order. A filed action, settlement, judgment and appeal are different stages.",
 "regulation": "Rules can alter eligibility, disclosure, costs and business models. Effects depend on jurisdiction, effective date, transition and enforcement. A proposal may change before adoption, while a final rule may need guidance. Forecasts about winners, losers or market size remain scenarios from their authors.",
 "markets": "Market reports combine observed prices with expectations about cash flow, policy and risk. A target, valuation or strategist view is an attributable estimate, not a fact about where an asset will trade. Useful analysis identifies assumptions, horizon, upside drivers and downside risks; liquidity and new information can change the result.",
 "crypto": "Digital assets combine price, technology, custody, regulation and counterparty risks. Forecasts are sensitive to liquidity and policy assumptions. Regulation may change access or compliance without validating value. Verify jurisdiction, product structure and methodology; the reported outlook is not personalised investment advice.",
 "pensions": "Pension changes compound over long periods and can affect contributions, tax, investments and income. Individual consequences depend on age, scheme rules, fees and jurisdiction. Projections assume returns, inflation and longevity, so they are scenarios rather than promises.",
 "other": "The development may influence expectations, financing or behaviour, but direction and scale depend on details not established by a headline. Separate what happened, what the source expects and what remains conditional. Dates, geography, methodology and revisions matter when comparing reports. A forecast belongs to its named source.",
}
READER_LENS = [
 "Compare the source's base case with upside and downside cases, then watch the next dated evidence that could confirm or challenge its assumptions. Price reaction does not prove a forecast correct, and a credible source can revise its view. Credibility supports scrutiny; it does not remove uncertainty, conflicts, or the need for independent evidence.",
 "Separate the observed development from the mechanism through which it might affect households, companies, governments or markets. Check the horizon and assumptions before comparing estimates made with different dates or definitions. An expert quotation explains that speaker’s assessment; it does not establish a universal consensus or guaranteed outcome.",
 "Check whether primary data, filings or policy documents support the interpretation and whether another credible source reaches a different view. Likely, possible and expected do not mean completed, certain or guaranteed. Adviser, educator, agency, researcher and analyst views should be weighed by expertise, evidence, incentives and disclosed methodology.",
 "Monitor implementation, revisions, guidance and measurable follow-through rather than extrapolating from one report. The linked publisher remains the record for its claim; Daily Yield does not adopt it as a prediction. Consequences can differ across countries, sectors, time horizons and financial positions, even when the same event is involved.",
]

def clip_word_count(text, maximum):
    return " ".join(re.sub(r"\s+", " ", text).strip().split()[:maximum])

def source_summary(it, maximum=68):
    desc = re.sub(r"\s+", " ", strip_tags(it.get("desc", ""))).strip()
    return clip_word_count(desc, maximum).rstrip(" .") + "."

def compose_item(it, win_end, context_target=95, summary_target=52):
    title = clean_title(it["title"])
    if len(title) > 140:
        cut = title[:140].rfind(" ")
        title = title[:cut if cut > 60 else 140].rstrip(" ,;:-(") + "…"
    day = fmt_day(it["date"]) if it["date"] else "Window"
    background = bool(it.get("background"))
    summary = source_summary(it, maximum=summary_target)
    analysis = bool(ANALYSIS_RE.search(title + " " + summary))
    kind = item_type(title + " " + summary)
    variant = int(hashlib.sha256((title + it["agency"]).encode()).hexdigest()[:2], 16) % len(READER_LENS)
    if background:
        chip, display = f"Background · originally {day}", "Background context: " + title
        status = f"Background, not current-window news: {title}. {it['agency']} published this on {day}; it is retained only for context."
    elif analysis:
        chip, display = f"{day} · Reported outlook", title
        status = f"This forecast or analytical view about {title} was reported by {it['agency']} on {day}. It is not an observed future result or a fact asserted by Daily Yield."
    else:
        chip, display = f"{day} · Reported development", title
        status = f"{it['agency']} published its account of {title} on {day}. Possible consequences below are conditional context, not a claim that a future result is certain."
    summary_words = len(summary.split())
    context_limit = max(35, context_target - summary_words)
    ordered_lenses = " ".join(READER_LENS[(variant + offset) % len(READER_LENS)]
                               for offset in range(len(READER_LENS)))
    context_seed = (f"{status} Applied specifically to the source topic — {title} — this lens separates "
                    f"the reported record from possible effects. {CONSEQUENCE[kind]} {ordered_lenses}")
    context = clip_word_count(context_seed, context_limit)
    etitle, eagency = htmlmod.escape(display), htmlmod.escape(it["agency"])
    country_name = DISCOVERY_LABELS.get(it.get("country"), it.get("region", "Global").replace("-", " ").title())
    topic_name = dict(SECTION_ORDER).get(it.get("topic"), "Economy, Trade & Jobs")
    return f'''    <div class="fbk-item{' fbk-background' if background else ''}">
      <span class="fbk-chip">{htmlmod.escape(chip)}</span>
      <span class="fbk-chip fbk-chip-muted">{htmlmod.escape(country_name)}</span>
      <span class="fbk-chip fbk-chip-muted">{htmlmod.escape(topic_name)}</span>
      <h3>{etitle}</h3>
      <p class="fbk-description"><strong>{eagency}:</strong> {htmlmod.escape(summary)}</p>
      <p class="fbk-context">{htmlmod.escape(context)}</p>
      <a class="fbk-src" href="{htmlmod.escape(it['url'])}" target="_blank" rel="noopener">{"Source:" if it.get("media") else "Official:"} {eagency}</a>
      {contextual_card(htmlmod.escape(title + ' ' + summary))}
    </div>'''

# ---------------------------------------------------------------- daily hero imagery
def _meta_value(metadata, key, default=""):
    value = metadata.get(key, default)
    if isinstance(value, dict):
        value = value.get("value", default)
    return strip_tags(str(value or default))


def curated_daily_hero(desk, edition_date, used_urls, previous_url=""):
    """Deterministic, cross-desk-unique fallback that changes every day."""
    desk_number = DESKS[desk][0]
    seed = edition_date.toordinal() * 31 + desk_number
    for step in range(len(CURATED_HERO_IDS)):
        photo_id = CURATED_HERO_IDS[(seed + step) % len(CURATED_HERO_IDS)]
        url = f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w={HERO_W}&h={HERO_H}&q=85"
        if url != previous_url and url not in used_urls and url not in SESSION_USED_IMAGES:
            return {"url": url, "alt": f"Daily financial news editorial photograph for {DESKS[desk][1]}",
                    "credit": "Editorial photograph · Unsplash", "source": "curated-fallback"}
    # Twenty desks and twenty-five photos make this practically unreachable.
    photo_id = CURATED_HERO_IDS[seed % len(CURATED_HERO_IDS)]
    return {"url": f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w={HERO_W}&h={HERO_H}&q=85",
            "alt": f"Daily financial news editorial photograph for {DESKS[desk][1]}",
            "credit": "Editorial photograph · Unsplash", "source": "curated-fallback"}


def daily_hero(desk, edition_date, used_urls=None, previous_url=""):
    """Choose a fresh licensed image for this desk/date without reusing yesterday's."""
    used_urls = set(used_urls or ())
    fallback = curated_daily_hero(desk, edition_date, used_urls, previous_url)
    params = {
        "action": "query", "format": "json", "formatversion": "2", "origin": "*",
        "generator": "search", "gsrsearch": HERO_SEARCH[desk] + " filetype:bitmap", "gsrnamespace": "6", "gsrlimit": "30",
        "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": str(HERO_W),
    }
    endpoint = "https://commons.wikimedia.org/w/api.php?" + urlencode(params)
    try:
        payload = json.loads(http_get(endpoint, tries=2, timeout=20))
        candidates = []
        for page in payload.get("query", {}).get("pages", []):
            info_list = page.get("imageinfo") or []
            if not info_list:
                continue
            info = info_list[0]
            mime = str(info.get("mime", "")).lower()
            url = info.get("thumburl") or info.get("url") or ""
            if mime not in {"image/jpeg", "image/png", "image/webp"} or not url.startswith(("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")):
                continue
            metadata = info.get("extmetadata") or {}
            license_name = _meta_value(metadata, "LicenseShortName")
            if not (license_name.lower().startswith(("cc by", "cc0", "public domain", "pdm"))):
                continue
            if url == previous_url or url in used_urls or url in SESSION_USED_IMAGES:
                continue
            title = _meta_value(metadata, "ImageDescription") or page.get("title", "Wikimedia Commons photograph")
            artist = _meta_value(metadata, "Artist", "Wikimedia Commons contributor")
            candidates.append({
                "url": url, "alt": clip_words(title, 150),
                "credit": clip_words(f"Photo: {artist} · {license_name} · Wikimedia Commons", 220),
                "source": "wikimedia-commons", "pageid": int(page.get("pageid", 0)),
            })
        if candidates:
            candidates.sort(key=lambda x: x["pageid"])
            start = int(hashlib.sha256(f"{desk}:{edition_date.isoformat()}".encode()).hexdigest()[:8], 16) % len(candidates)
            for offset in range(len(candidates)):
                chosen = candidates[(start + offset) % len(candidates)]
                try:
                    chosen["url"] = safe_image(chosen["url"], fallback["url"])
                    if chosen["url"] == fallback["url"]:
                        return fallback
                    return chosen
                except Exception:
                    continue
    except Exception as exc:
        print(f"  [{desk}] fresh Commons photo unavailable: {exc}; using rotating curated image")
    fallback["url"] = safe_image(fallback["url"], FALLBACK_PERSONAL if desk == "personal" else FALLBACK_MARKET)
    return fallback


# ---------------------------------------------------------------- template
CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fbk_styles.css")).read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fbk_styles.css")) else "/*missing*/"

TITLE_PREFIXES = {
    "markets": "Markets & Commodities News",
    "economy": "Economy, Trade & Jobs News",
    "banking": "Banking & Personal Money News",
    "companies": "Companies, IPOs & Deals News",
}

def desk_title_prefix(desk):
    return TITLE_PREFIXES.get(desk, DESKS[desk][1])

def weekday_name(d):
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][d.weekday()]

def clip_words(text, limit):
    """Limit display text at a word boundary instead of cutting words or numbers."""
    if len(text) <= limit:
        return text
    cut = text[:limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:–—-")
    return (cut or text[:limit]).rstrip() + "…"

def coverage_window_text(start, end):
    """Full-month exact range for the front of every news title."""
    names = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
    if start.date() == end.date():
        return f"{names[end.month-1]} {end.day}"
    if start.year == end.year and start.month == end.month:
        return f"{names[start.month-1]} {start.day} to {end.day}"
    if start.year == end.year:
        return f"{names[start.month-1]} {start.day} to {names[end.month-1]} {end.day}"
    return f"{names[start.month-1]} {start.day} {start.year} to {names[end.month-1]} {end.day} {end.year}"

def build_article(desk, items, upcoming, edition_date, win_start, win_end, fx, related,
                  previous_hero="", used_heroes=None, hero_override=None,
                  context_target=95, summary_target=52):
    n, label, slug, slot, legacy_hero_id, legacy_hero_alt = DESKS[desk]
    current_items = [i for i in items if not i.get("background")]
    background_items = [i for i in items if i.get("background")]
    top = [clean_title(i["title"]) for i in current_items[:3]]
    headline_bits = clip_words("; ".join(top[:2]), 90)
    date_long = f"{weekday_name(edition_date)}, {edition_date.day} {['January','February','March','April','May','June','July','August','September','October','November','December'][edition_date.month-1]} {edition_date.year}"
    win_str = f"{fmt_day(win_start.date())}–{fmt_day(win_end.date())} {win_end.year}"
    coverage_lead = coverage_window_text(win_start, win_end)
    title_date = edition_date - dt.timedelta(days=1) if desk == "americas" else edition_date
    publish_lead = f"{title_date.day} {['January','February','March','April','May','June','July','August','September','October','November','December'][title_date.month-1]} {title_date.year}"
    # The Americas edition publishes after midnight IST but retains the completed
    # Americas market date in its reader-facing title.
    # Coverage and headlines remain in the description/body; the document title
    # stays compact enough for Bing even while Blogger appends the site name.
    title = compact_title(f"{desk_title_prefix(desk)} — {publish_lead}")
    meta = (f"{desk_title_prefix(desk)}, coverage {coverage_lead}: "
            + "; ".join(t for t in top[:3])).strip()
    if len(meta) > 158:
        meta = meta[:155].rsplit(" ", 1)[0].rstrip(" ,;:.") + "..."

    flag = {"americas": "🌎", "china": "🇨🇳", "asia-pacific": "🌏", "india": "🇮🇳",
            "russia": "🇷🇺", "europe": "🇪🇺"}.get(desk, "🌐")
    tag = f"Daily News · {flag} {label}" if desk not in CATEGORY_DESKS else f"Daily News · 📑 {label}"

    hero = hero_override or daily_hero(desk, edition_date, used_urls=used_heroes, previous_url=previous_hero)
    hero_url, hero_alt, hero_credit = hero["url"], hero["alt"], hero["credit"]
    SESSION_USED_IMAGES.add(hero_url)

    # Geographic editions are organised by the four canonical topics; topic
    # editions are organised by geography so both reading paths stay distinct.
    if desk in CATEGORY_DESKS:
        geography_sections = (
            ("global", "Global and Cross-Border"), ("india", "India"),
            ("china", "China"), ("russia", "Russia"), ("americas", "Americas"),
            ("europe", "Europe"), ("asia-pacific", "Asia-Pacific"),
        )
        secs = [
            (str(index).zfill(2), name,
             f"Current {label.lower()} reporting connected to {name}.",
             [item for item in current_items if item.get("region", "global") == key])
            for index, (key, name) in enumerate(geography_sections, 1)
        ]
    else:
        secs = [
            (str(index).zfill(2), name,
             f"Current {name.lower()} developments, forecasts and consequences.",
             [item for item in current_items if item.get("topic", "economy") == key])
            for index, (key, name) in enumerate(SECTION_ORDER, 1)
        ]
    sections_html = ""
    for num, name, sub, its in secs:
        if not its:
            continue
        sections_html += f'\n    <h2 class="fbk-h2"><b>{num}</b> {name}</h2>\n    <p class="fbk-sub">{sub}</p>'
        for it in its:
            sections_html += "\n" + compose_item(it, win_end, context_target=context_target, summary_target=summary_target)

    background_html = ""
    if background_items:
        background_html = '''
    <h2 class="fbk-h2"><b>BG</b> Background Context — Not Current-Period News</h2>
    <p class="fbk-sub">At most three older items, each retaining its original date and source, reframed only to explain current context.</p>'''
        for it in background_items:
            background_html += "\n" + compose_item(it, win_end, context_target=context_target, summary_target=summary_target)

    # FX reference block (ECB official)
    fx_html = ""
    if fx:
        pairs = []
        for cur in ["USD", "GBP", "JPY", "CNY", "INR", "BRL"]:
            if cur in fx:
                pairs.append(f"<strong>EUR/{cur} {fx[cur]:.4f}</strong>")
        if pairs:
            fx_html = f'''
    <h2 class="fbk-h2"><b>04</b> Official Reference — ECB Daily Rates</h2>
    <p class="fbk-sub">Reference levels as published; labelled references, not window news.</p>
    <div class="fbk-item">
      <span class="fbk-chip">Reference · last fix</span>
      <h3>{' · '.join(pairs[:6])}</h3>
      <p>The European Central Bank publishes daily reference rates every business day around 16:00 CET. These are the last published reference levels — the anchor the whole FX market marks against.</p>
      <a class="fbk-src" href="https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html" target="_blank" rel="noopener">Official: European Central Bank</a>
    </div>'''

    # week ahead
    rows = ""
    for u in upcoming[:5]:
        rows += f"      <tr><td>{fmt_day(u['date'])}</td><td>{htmlmod.escape(clean_title(u['title'])[:110])}</td></tr>\n"
    if not rows:
        rows = '      <tr><td>—</td><td>Confirmed official calendar items will appear as agencies release them.</td></tr>\n'
    sec_num = "05" if fx_html else "04"
    week_html = f'''
    <h2 class="fbk-h2"><b>{sec_num}</b> Week Ahead — What to Watch</h2>
    <p class="fbk-sub">Forward calendar items detected in official listings. Background only.</p>
    <table class="fbk-table">
      <caption>Calendar · next 7 days</caption>
      <tr><th>Day</th><th>What</th></tr>
{rows}    </table>'''

    related_html = ""
    if related:
        links = "".join(f' <a class="fbk-src" href="{u}" style="display:block;margin:6px 0;">{htmlmod.escape(t)}</a> ' for t, u in related)
        related_html = f'''
    <div class="fbk-related">
      <span class="fbk-chip">From the blog</span>
      <p><strong>Related reading on Daily Yield:</strong></p>{links}
    </div>'''

    source_hosts = sorted({urllib.parse.urlparse(i.get("url", "")).hostname or "" for i in current_items if i.get("url")})
    subject_list = "; ".join(top) if top else "the linked current-period release"
    method_html = f'''
    <aside class="fbk-method" aria-labelledby="fbkMethodTitle">
      <span class="fbk-method-label">Reader guidance · not a news headline</span>
      <h2 class="fbk-h2" id="fbkMethodTitle"><b>METHOD</b> Facts, Forecasts and Attributed Views</h2>
      <p>This edition separates reported developments from attributable forecasts, expectations and analysis; it does not adopt a source's view as a Daily Yield prediction. Its current-period subjects are {htmlmod.escape(subject_list)}. The {len(current_items)} current item(s) come from {len(source_hosts)} distinct source website(s); each link retains the publisher's wording and date so readers can inspect the underlying record.</p>
      <p>A headline can establish that an announcement or report exists, but it cannot by itself establish investment suitability, causation or what happens next. Compare publication dates, units, geographic scope and revisions before combining figures from different items. Older material is isolated as background, while forward calendar entries are labelled separately. If a linked source changes its document after publication, the source—not this edition—remains the authoritative record.</p>
    </aside>'''

    signoff = f'''
    <div class="fbk-signoff">
      <span class="fbk-script">Read it? Question it. &#9999;</span>
      <p>Every news item above is dated inside the stated coverage period, <strong>{coverage_lead}</strong>. Where an item refers to an earlier fact, it is marked as background. The Week Ahead section looks forward only. Every item links to a genuine, trustworthy source — official or an established newsroom.</p>
      <p><strong>Education only, not personalised investment advice.</strong> This is not a recommendation or a promise of profit.</p>
      <p>Financial education, not personalised advice. Figures as reported {win_str} by the trusted sources linked above.</p>
    </div>'''

    body = f'''<div class="fbk-wrap">
  <figure class="fbk-hero"><img src="{htmlmod.escape(hero_url, quote=True)}" alt="{htmlmod.escape(hero_alt, quote=True)}" width="{HERO_W}" height="{HERO_H}" loading="eager" decoding="async" fetchpriority="high" style="display:block;width:100%;height:auto;max-width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:14px"><figcaption style="font-size:11px;color:#7A6A58;margin-top:7px">{htmlmod.escape(hero_credit)}</figcaption></figure>

  <style>{CSS}</style>
  {CONTEXT_STYLE}

  <div class="fbk-kicker">
    <span class="fbk-tag">{tag}</span>
    <span class="fbk-date">{date_long} · IST</span>
  </div>

  <h1 class="fbk-h1">{htmlmod.escape(title)}</h1>
  <div class="fbk-byline"><strong>By Kushal K. Daga</strong> · Published {date_long} · Last reviewed {date_long} · IST</div>
  <p class="fbk-note">Recency rule: every item below is news of <strong>{win_str}</strong> (or weekend trading inside that window). Levels from before the window appear only as labelled last-close references. Events before the window appear only in the Week Ahead, marked as background. Every item links to a <em>genuine, trustworthy source</em> — official releases from central banks, ministries, statistical offices, regulators and exchanges, plus reporting from established, reputable newsrooms.</p>
{sections_html}
{background_html}
{fx_html}
{week_html}
{method_html}
{related_html}
{signoff}
</div>'''

    canonical = "https://dailyyield.blogspot.com/PLACEHOLDER-CANONICAL"
    jsonld = {
        "@context": "https://schema.org", "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": canonical}, "@id": canonical,
        "headline": clip_words(title, 110), "description": meta, "inLanguage": "en",
        "datePublished": win_end.isoformat(timespec="seconds"),
        "dateModified": win_end.isoformat(timespec="seconds"),
        "author": {"@type": "Person", "name": "Kushal K. Daga",
                   "alternateName": PERSON_ALIASES,
                   "url": f"{BLOG}/p/about-us_02080501126.html"},
        "publisher": {"@type": "Organization", "name": "Daily Yield", "url": BLOG + "/"},
        "about": {"@type": "Place", "name": label} if desk not in CATEGORY_DESKS | {"global"} else {"@type": "Thing", "name": label},
        "keywords": ", ".join([
            f"{label.lower()} finance news today", f"coverage {coverage_lead}", "trusted sources",
            ', '.join(t.lower() for t in top[:4])[:150],
            f"{edition_date.day} {MONTHS[edition_date.month-1]} {edition_date.year}",
            *SEO_QUERY_TERMS]),
    }
    full_html = body + f'''
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'''

    if desk in CATEGORY_DESKS:
        labels = ["News", "Category Edition", TOPIC_LABELS[desk], *COUNTRY_LABELS.values()]
    else:
        country_labels = [COUNTRY_LABELS[country] for country in DESK_COUNTRIES.get(desk, ())]
        labels = ["News", "Geographic Edition", GEOGRAPHY_LABELS[desk],
                  *country_labels, *TOPIC_LABELS.values()]
    return {"title": title, "slug": f"{slug}-{edition_date.isoformat()}",
            "meta": meta, "labels": labels, "html": full_html,
            "canonical": canonical, "n_items": len(items),
            "hero_url": hero_url, "hero_alt": hero_alt,
            "hero_credit": hero_credit, "hero_source": hero["source"]}

NEWS_MIN_WORDS = 3800
NEWS_MAX_WORDS = 4100

def editorial_word_count(document):
    """Count reader-visible editorial words, excluding CSS, scripts and markup."""
    visible = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", document, flags=re.I | re.S)
    visible = strip_tags(visible)
    return len(re.findall(r"\b[\w’'-]+\b", visible, flags=re.UNICODE))

def assert_news_editorial_length(document):
    count = editorial_word_count(document)
    if not NEWS_MIN_WORDS <= count <= NEWS_MAX_WORDS:
        raise ValueError(f"News editorial length {count} is outside {NEWS_MIN_WORDS}-{NEWS_MAX_WORDS} words")
    return count


def reduce_news_context(document, target=4050):
    """Sentence-trim explanatory context while preserving source summaries and attribution."""
    count = editorial_word_count(document)
    if count <= NEWS_MAX_WORDS:
        return document, count
    pattern = re.compile(r'(<p class="fbk-context">)(.*?)(</p>)', re.I | re.S)
    matches = list(pattern.finditer(document))
    replacements = {}
    for match in reversed(matches):
        if count <= target:
            break
        plain = htmlmod.unescape(strip_tags(match.group(2)))
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", plain) if part.strip()]
        # Keep the opening status/attribution and at least one consequence sentence.
        while len(sentences) > 2 and count > target:
            removed = sentences.pop()
            count -= len(re.findall(r"\b[\w’'-]+\b", removed, flags=re.UNICODE))
        replacements[match.start()] = match.group(1) + htmlmod.escape(" ".join(sentences)) + match.group(3)
    if replacements:
        pieces, cursor = [], 0
        for match in matches:
            pieces.append(document[cursor:match.start()])
            pieces.append(replacements.get(match.start(), match.group(0)))
            cursor = match.end()
        pieces.append(document[cursor:])
        document = "".join(pieces)
    return document, editorial_word_count(document)


def finish_news_article(art, related_candidates):
    """Apply every final reader, SEO, accessibility and navigation enhancement."""
    current_post = {"id": "pending", "title": art["title"],
                    "labels": art["labels"], "content": art["html"]}
    art["html"] = ensure_related_articles(art["html"], current_post, related_candidates)
    hero_match = re.search(r'<img[^>]+src=["\']([^"\']+)', art["html"], re.I)
    art["html"] = ensure_seo_meta(art["html"], art["title"], art["meta"],
                                  hero_match.group(1) if hero_match else "")
    art["html"] = ensure_family(art["html"])
    art["html"] = ensure_continuous_motion(art["html"])
    art["html"], _ = repair_image_alts(art["html"], art["title"])
    return art


def build_fitted_news_article(desk, candidate_items, upcoming, edition_date, win_start,
                              win_end, fx, related, related_candidates, hero):
    """Adapt headline count and detail, then sentence-trim context into the hard range."""
    current = [item for item in candidate_items if not item.get("background")]
    background = [item for item in candidate_items if item.get("background")]
    if not current:
        raise ValueError("no current sourced items available")
    is_category = desk in CATEGORY_DESKS
    maximum = 34 if is_category else 28
    desired = 30 if is_category else 24
    base_context = 72 if is_category else 95
    summary_target = 42 if is_category else 52
    current = current[:maximum]
    first_count = min(desired, len(current))
    attempts = [(count, base_context) for count in range(first_count, len(current) + 1)]
    # If every sourced headline is still short, deepen only the item-specific
    # consequence text while retaining the concise source synopsis.
    attempts.extend((len(current), target)
                    for target in (base_context + 10, base_context + 20, base_context + 30))
    seen = set()
    last_count = 0
    for item_count, context_target in attempts:
        if (item_count, context_target) in seen:
            continue
        seen.add((item_count, context_target))
        selected = current[:item_count] + background
        art = build_article(
            desk, selected, upcoming, edition_date, win_start, win_end, fx, related,
            hero_override=hero, context_target=context_target, summary_target=summary_target,
        )
        art = finish_news_article(art, related_candidates)
        count = editorial_word_count(art["html"])
        last_count = count
        if count < NEWS_MIN_WORDS:
            continue
        if count > NEWS_MAX_WORDS:
            art["html"], count = reduce_news_context(art["html"])
        if NEWS_MIN_WORDS <= count <= NEWS_MAX_WORDS:
            mode = (f"{item_count} headlines · context target {context_target}"
                    + (" · sentence-polished" if count != last_count else ""))
            return art, selected, count, mode
    raise ValueError(
        f"adaptive News polish could not reach {NEWS_MIN_WORDS}-{NEWS_MAX_WORDS} words; "
        f"last complete sourced draft was {last_count} words"
    )


# ---------------------------------------------------------------- related links
def fetch_related(desk, prev_url, token):
    """Choose related links through Blogger API without opening the public blog."""
    rel = []
    if prev_url:
        rel.append((f"Yesterday's {DESKS[desk][1]} Wire — the previous window", prev_url))
    rel.extend([
        ("Markets Today — complete global analysis", BLOG + "/p/markets-today.html"),
        ("Global Snapshot — concise cross-asset summary", BLOG + "/p/global-snapshot.html"),
    ])
    try:
        query = urllib.parse.urlencode({"status": "live", "fetchBodies": "false", "maxResults": "50", "fields": "items(title,url,labels)"})
        data = blogger_call("/posts?" + query, token)
        kws = {"markets": ["market", "invest", "trading", "crypto", "gold", "oil"],
               "economy": ["inflation", "economy", "trade", "jobs", "gdp"],
               "banking": ["bank", "fintech", "money", "housing", "savings"],
               "companies": ["corporate", "business", "company", "ipo", "deal"]}.get(desk, [])
        label = DESKS[desk][1].lower()
        for entry in data.get("items", []):
            if "News" in entry.get("labels", []):
                continue
            title = entry.get("title", "")
            link = entry.get("url", "")
            lower = title.lower()
            if link and ((desk not in CATEGORY_DESKS and label.split()[0] in lower) or any(k in lower for k in kws)):
                rel.append((title, link))
            if len(rel) >= 4:
                break
    except Exception:
        pass
    return rel[:4]

# ---------------------------------------------------------------- publisher
def blogger_token():
    r = urllib.request.Request("https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "client_id": os.environ["BLOGGER_CLIENT_ID"],
            "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
            "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
            "grant_type": "refresh_token"}).encode(), method="POST")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]

import urllib.parse

def blogger_call(path, token, method="GET", body=None):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.environ['BLOGGER_BLOG_ID']}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1200]
        raise RuntimeError(f"Blogger {method} {path} returned HTTP {exc.code}: {detail}") from exc

def live_post_exists(url, token):
    """Confirm an existing live post through Blogger API without a public pageview."""
    try:
        path = urllib.parse.urlparse(url).path
        query = urllib.parse.urlencode({"path": path, "fields": "id,url,status"})
        post = blogger_call("/posts/bypath?" + query, token)
        return post.get("status") == "LIVE" and post.get("url", "").rstrip("/") == url.rstrip("/")
    except Exception:
        return False


def publish_post(art, token, dry=False):
    if dry:
        print(f"    [DRY] would publish: '{art['title'][:80]}' slug={art['slug']} labels={art['labels']}")
        return None
    # pass 1: draft with slug-title (Blogger derives permalink from it)
    draft = blogger_call("/posts?isDraft=true", token, "POST", {
        "kind": "blogger#post", "title": art["slug"], "content": art["html"],
        "labels": art["labels"]})
    # pass 2: publish
    live = blogger_call(f"/posts/{draft['id']}/publish", token, "POST")
    url = live.get("url", "")
    if art["slug"] not in url:
        print(f"    !! slug check: expected {art['slug']} in {url}")
    # pass 3: real title + canonical patch
    final_html = art["html"].replace(art["canonical"], url)
    if art["canonical"] not in art["html"]:
        final_html = art["html"]
    upd = blogger_call(f"/posts/{draft['id']}", token, "PUT", {
        "kind": "blogger#post", "id": draft["id"], "title": art["title"],
        "content": final_html, "labels": art["labels"]})
    return upd.get("url", url)

# ---------------------------------------------------------------- orchestration
def load_tracker():
    if os.path.exists(TRACKER):
        with open(TRACKER) as f:
            return json.load(f)
    return {"desks": {}}

def save_tracker(t):
    with open(TRACKER, "w") as f:
        json.dump(t, f, indent=1, ensure_ascii=False)

def append_social_event(desk, url):
    try:
        with open(SOCIAL_EVENTS_FILE, encoding="utf-8") as handle:
            events = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        events = []
    events.append({"item_key": f"news-{desk}", "target_url": url,
                   "content_mode": "post", "published_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    with open(SOCIAL_EVENTS_FILE, "w", encoding="utf-8") as handle:
        json.dump(events, handle, indent=2)

def run_desk(desk, tracker, dry=False, token=None):
    n, label, slug, slot, _, _ = DESKS[desk]
    now = dt.datetime.now(IST)
    hh, mm = map(int, slot.split(":"))
    slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    prev = tracker["desks"].get(desk, {})
    if prev.get("edition") == now.date().isoformat():
        print(f"  [{desk}] already published today ({prev.get('url','?')}) — skip")
        return False
    # Recover safely if Blogger published successfully but a previous tracker push failed.
    expected_url = f"{BLOG}/{now:%Y/%m}/{slug}-{now.date().isoformat()}.html"
    if not dry and live_post_exists(expected_url, token):
        tracker["desks"][desk] = {**prev, "edition": now.date().isoformat(),
                                  "window_end": now.isoformat(), "url": expected_url}
        save_tracker(tracker)
        append_social_event(desk, expected_url)
        print(f"  [{desk}] recovered existing live edition; no duplicate: {expected_url}")
        return True
    # rolling window: previous edition end -> now (24h on first run)
    win_end = now
    win_start = dt.datetime.fromisoformat(prev["window_end"]) if prev.get("window_end") \
        else now - dt.timedelta(hours=24)
    if win_start.tzinfo is None:
        win_start = win_start.replace(tzinfo=IST)
    edition_date = now.date()
    print(f"  [{desk}] window {win_start:%d %b %H:%M} -> {win_end:%d %b %H:%M} IST")

    items_raw, own_off, own_med = fetch_desk_items(desk)
    # A story belongs to one Daily Yield desk only. Exclude headlines/source URLs
    # already live today or reserved by an earlier desk in this same process.
    before_dedupe = len(items_raw)
    items_raw = [item for item in items_raw
                 if story_title_key(item.get("title", "")) not in SESSION_USED_TITLES
                 and item.get("url", "").strip() not in SESSION_USED_URLS]
    if before_dedupe != len(items_raw):
        print(f"  [{desk}] cross-desk duplicate guard excluded {before_dedupe - len(items_raw)} items")
    items, upcoming, eff_lo = select_items(items_raw, win_start, win_end, desk,
                                           own_off=own_off, own_med=own_med)
    selected_before_body_dedupe = len(items)
    items = dedupe_rendered_stories(items)
    items = enrich_item_descriptions(items)
    # Match the exact synopsis length rendered by each edition. Two source
    # records with a shared opening must not become duplicate visible paragraphs.
    items = dedupe_rendered_stories(items, 42 if desk in CATEGORY_DESKS else 52)
    before_source_gate = len(items)
    items = [item for item in items if item_source_is_usable(item)]
    if len(items) != before_source_gate:
        print(f"  [{desk}] source-integrity gate excluded {before_source_gate - len(items)} thin or unverifiable item(s)")
    # Keep enough complete candidates for 24–28-headline geographic editions and
    # 30–34-headline category editions. The polisher adds concise sourced items
    # before deepening context, then sentence-trims only explanatory prose.
    candidate_cap = 34 if desk in CATEGORY_DESKS else 28
    rich_current = [item for item in items if not item.get("background")][:candidate_cap]
    rich_background = [item for item in items if item.get("background")]
    items = rich_current + rich_background
    if len(items) != selected_before_body_dedupe:
        print(f"  [{desk}] visible-paragraph duplicate guard excluded "
              f"{selected_before_body_dedupe - len(items)} item(s)")
    eff_start = win_start
    current_count = len(rich_current)
    background_count = len(rich_background)
    print(f"  [{desk}] {len(items_raw)} raw items -> {current_count} usable current candidate(s) + "
          f"{background_count} background ({len(upcoming)} upcoming)")
    if current_count == 0:
        print(f"  [{desk}] NO CURRENT ITEMS — edition SKIPPED rather than recycling old news")
        return False
    fx = ecb_reference_rates()
    related = fetch_related(desk, prev.get("url"), token)
    related_candidates = fetch_public_posts()
    if not related_candidates:
        # Authenticated inventory can be temporarily unavailable. Reuse the
        # already-known Daily Yield destinations without opening public pages.
        related_candidates = [
            {"id": f"fallback-{index}", "title": title, "content": "",
             "labels": ["Daily Yield"], "published": edition_date.isoformat(), "url": url}
            for index, (title, url) in enumerate(related) if url
        ]
    used_heroes = {
        entry.get("hero_url") for entry in tracker.get("desks", {}).values()
        if entry.get("edition") == edition_date.isoformat() and entry.get("hero_url")
    }
    hero = daily_hero(desk, edition_date, used_urls=used_heroes,
                      previous_url=prev.get("hero_url", ""))
    art, items, word_count, polish_mode = build_fitted_news_article(
        desk, items, upcoming, edition_date, eff_start, win_end, fx, related,
        related_candidates, hero,
    )
    word_count = assert_news_editorial_length(art["html"])
    assert_publishable(art["title"], art["html"], art["labels"])
    print(f"  [{desk}] adaptive polish: {polish_mode}")
    print(f"  [{desk}] article built: {art['n_items']} items, {word_count} editorial words, '{art['title'][:70]}…'")
    url = publish_post(art, token, dry)
    if url or dry:
        # Reserve only stories that actually made the article. This protects the
        # second desk in a paired workflow even before Blogger's feed refreshes.
        for item in items:
            key = story_title_key(item.get("title", ""))
            if key:
                SESSION_USED_TITLES.add(key)
            if item.get("url"):
                SESSION_USED_URLS.add(item["url"].strip())
        if not dry:
            tracker["desks"][desk] = {"edition": edition_date.isoformat(),
                                      "window_end": win_end.isoformat(),
                                      "url": url or prev.get("url", ""),
                                      "hero_url": art["hero_url"],
                                      "hero_credit": art["hero_credit"],
                                      "hero_source": art["hero_source"]}
            save_tracker(tracker)
            append_social_event(desk, url)
        print(f"  [{desk}] PUBLISHED: {url or '(dry-run)'}")
        return True
    return False

def due_desks():
    now = dt.datetime.now(IST)
    tracker = load_tracker()
    due = []
    for desk, (n, label, slug, slot, _, _) in sorted(DESKS.items(), key=lambda x: x[1][0]):
        hh, mm = map(int, slot.split(":"))
        slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if tracker["desks"].get(desk, {}).get("edition") == now.date().isoformat():
            continue
        if slot_dt <= now + dt.timedelta(minutes=PREFLIGHT_MINUTES):
            due.append(desk)  # preflight window or missed earlier today -> catch-up
    return due

LAUNCH_DATE = dt.date(2026, 9, 25)   # news section starts Sept 25 (user instruction)

def main():
    args = sys.argv[1:]
    with open(SOCIAL_EVENTS_FILE, "w", encoding="utf-8") as handle:
        json.dump([], handle)
    dry = "--dry-run" in args
    today = dt.datetime.now(IST).date()
    if today < LAUNCH_DATE:
        print(f"News section starts {LAUNCH_DATE.isoformat()} — today is {today.isoformat()}; nothing published.")
        return
    if "--list" in args:
        for d, (n, label, slug, slot, _, _) in sorted(DESKS.items(), key=lambda x: x[1][0]):
            print(f"  {n:02d} {d:12s} {slot} IST  {label}")
        return
    if "--desks" in args:
        desks = args[args.index("--desks") + 1].split(",")
    elif "--due" in args:
        desks = due_desks()
    else:
        print("usage: --due | --desks a,b | --dry-run | --list"); return
    tracker = load_tracker()
    global SESSION_USED_TITLES, SESSION_USED_URLS
    SESSION_USED_TITLES, SESSION_USED_URLS = load_today_story_keys(today)
    print(f"Cross-desk guard: {len(SESSION_USED_TITLES)} live headlines, "
          f"{len(SESSION_USED_URLS)} source URLs already used today")
    token = None
    if not dry:
        token = blogger_token()
    ok, fail = 0, 0
    results = []
    for desk in desks:
        desk = desk.strip()
        if desk not in DESKS:
            message = f"unknown desk '{desk}'"
            print(f"  ?? {message}"); fail += 1
            results.append({"desk": desk, "status": "FAIL", "error_type": "UnknownDesk", "error": message})
            continue
        try:
            published = run_desk(desk, tracker, dry, token)
            if published:
                ok += 1
                results.append({"desk": desk, "status": "PASS", "published": not dry, "dry_run": dry})
            else:
                results.append({"desk": desk, "status": "SKIPPED", "published": False, "dry_run": dry})
        except Exception as e:
            print(f"  [{desk}] ERROR: {type(e).__name__}: {e}")
            results.append({"desk": desk, "status": "FAIL", "error_type": type(e).__name__,
                            "error": str(e)[:1000]})
            fail += 1
    report = {"status": "FAIL" if fail else "PASS", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "dry_run": dry, "published": ok, "failed": fail, "results": results}
    with open("NEWS_PIPELINE_STATUS.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(f"\nNews wires: {ok} published, {fail} failed" + (" (DRY RUN)" if dry else ""))
    if fail:
        sys.exit(1)

if __name__ == "__main__":
    main()
