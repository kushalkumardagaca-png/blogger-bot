#!/usr/bin/env python3
"""
FINANCE BY CA KUSHAL — Daily News Wires Engine (20 desks, 1 article/day each)
================================================================================
Per-desk rolling 24-hour window anchored to the desk's IST slot. Official
sources only (central banks, ministries, stats offices, regulators, exchanges).
Structure: fbk-* template (verbatim from reference articles).
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
import urllib.request
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------- constants
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
BLOG = "https://dailyyield.blogspot.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9"}
CTX = ssl.create_default_context()
TRACKER = os.environ.get("NEWS_TRACKER", "news_tracker.json")
HERO_W, HERO_H = 1600, 900

# desk -> (num, label, slug, slot IST "HH:MM", hero unsplash id, hero alt)
DESKS = {
 "global":  (1, "Global News", "global-wire-top15", "06:30", "photo-1611974789855-9c2a0a7236a3", "Global financial district skyline at dusk"),
 "us":      (2, "US", "us", "18:00", "photo-1611974789855-9c2a0a7236a3", "United States Treasury building, Washington DC"),
 "china":   (3, "China", "china", "13:00", "photo-1494522855154-9297ac14b55f", "Shanghai financial towers at night"),
 "germany": (4, "Germany", "germany", "10:30", "photo-1560518883-ce09059eeffa", "Frankfurt banking skyline, Germany"),
 "india":   (5, "India", "india", "06:45", "photo-1590283603385-17ffb3a7f29f", "Bombay Stock Exchange building on Dalal Street, Mumbai"),
 "japan":   (6, "Japan", "japan", "12:05", "photo-1493976040374-85c8e12f0c0e", "Tokyo financial district skyline"),
 "uk":      (7, "UK", "uk", "12:00", "photo-1518186285589-2f7649de83e0", "Bank of England and City of London skyline"),
 "france":  (8, "France", "france", "10:35", "photo-1502602898657-3e91760cbb34", "Paris La Défense business district"),
 "italy":   (9, "Italy", "italy", "15:50", "photo-1516483638261-f4dbaf036963", "Milan financial district, Italy"),
 "russia":  (10, "Russia", "russia", "22:00", "photo-1513326738677-b964603b3d50", "Moscow City international business centre"),
 "canada":  (11, "Canada", "canada", "18:05", "photo-1449824913935-59a10b8d2000", "Toronto financial district skyline"),
 "brazil":  (12, "Brazil", "brazil", "17:00", "photo-1496307653780-42ee777d4833", "São Paulo financial district, Brazil"),
 "spain":   (13, "Spain", "spain", "13:05", "photo-1509845350455-fc3f10b16bac", "Madrid financial street, Spain"),
 "mexico":  (14, "Mexico", "mexico", "19:30", "photo-1518391846015-5589253858ba", "Mexico City financial district"),
 "australia": (15, "Australia", "australia", "04:30", "photo-1506973035872-a4ec16b8e8d9", "Sydney harbour financial district"),
 "south-korea": (16, "South Korea", "south-korea", "04:35", "photo-1538485399081-7191377e8241", "Seoul financial district skyline"),
 "market":  (17, "Market and Trading", "category-market-and-trading", "09:00", "photo-1611974748038-1e8768f0db4a", "Trading screens in a modern dealing room"),
 "macro":   (18, "Economy and Macro Policy", "category-economy-and-macro-policy", "09:05", "photo-1554224155-8d04cb21cd6c", "Official economic statistics documents and charts"),
 "corporate": (19, "Corporate Finance and Industry", "category-corporate-finance-and-industry", "15:45", "photo-1486406146926-c627a92ad1ab", "Modern corporate headquarters offices"),
 "personal": (20, "Personal Finance", "category-personal-finance", "21:00", "photo-1554224155-6726d3519c1d", "Household budget planning with calculator and notes"),
}

# keyword filters for category desks (applied to pooled items)
CATEGORY_FILTERS = {
 "market": ["market", "trading", "exchange", "liquidity", "volatility", "derivatives",
            "equit", "bond", "yield", "fx", "currency", "bitcoin", "crypto", "index",
            "clearing", "settlement", "short selling", "margin", "ipo", "listing",
            "price", "rate", "euro", "dollar", "rupee", "yen", "pound", "commodit",
            "oil", "gold", "securit", "order", "reserve", "benchmark", "futures"],
 "macro": ["inflation", "cpi", "gdp", "growth", "unemployment", "jobs", "employment",
           "trade", "tariff", "deficit", "debt", "policy rate", "repo", "interest rate",
           "quantitative", "fiscal", "budget", "stimulus", "pmi", "retail sales",
           "industrial", "wage", "monetary", "central bank", "economy", "economic",
           "outlook", "statistics", "survey", "consum", "producer", "export", "import",
           "monthly", "quarterly", "annual", "census", "accounts", "fomc", "minutes",
           "commission", "council", "release", "index", "forecast", "bank", "reserve",
           "treasury", "ministry", "federal", "national", "personal income"],
 "corporate": ["corporate", "company", "earnings", "merger", "acquisition", "filing",
               "edgar", "securities", "disclosure", "governance", "capital", "share",
               "dividend", "buyback", "bankrupt", "restructur", "ipo", "issuer",
               "regulation", "enforcement", "fine", "penalty", "commission", "approval",
               "competition", "cartel", "state aid", "business", "industry", "enterprise",
               "firm", "investment", "licence", "license", "sanction", "order",
               "settlement", "insolvency", "bank", "market", "trade"],
 "personal": ["deposit", "savings", "mortgage", "house price", "housing", "rent",
              "pension", "retirement", "insurance", "tax", "payment", "loan", "credit",
              "household", "consumer", "cost", "price", "food", "fuel", "energy",
              "investor", "protection", "compensation", "scam", "fraud", "debt",
              "financial literacy", "wage", "income", "spending", "retail",
              "digital euro", "cash", "citizen", "individual", "family", "student",
              "senior", "cyber", "phishing", "misselling", "mis-selling", "grievance",
              "ombudsman", "advisory", "mutual fund", "provident fund", "small savings",
              "fintech", "upi", "wallet", "microfinance", "banking"],
}

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
# category desks pool from all country sources (with keyword filter)
CATEGORY_DESKS = {"market", "macro", "corporate", "personal"}

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
                      "desc": strip_tags(desc_raw)[:400], "date": date,
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
                i["date"] = dt.date.today() - dt.timedelta(days=1)
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
 "canada": [("CBC Business", "https://www.cbc.ca/webfeed/rss/rss-business", "rss", 1)],
 "mexico": [("Mexico News Daily", "https://mexiconewsdaily.com/feed/", "rss", 1)],
 "germany": [("Deutsche Welle", "https://rss.dw.com/xml/rss-en-all", "rss", 3)],
 "france": [("Le Monde", "https://www.lemonde.fr/en/rss/une.xml", "rss", 2)],
 "india": [("The Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "rss", 2)],
 "brazil": [("ANBA", "https://www.anba.com.br/en/rss", "rss", 1),
           ("The Rio Times", "https://www.riotimesonline.com/feed/", "rss", 1),
           ("MercoPress", "https://en.mercopress.com/rss", "rss", 2)],
 "global": [("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "rss", 2),
            ("France 24 Business", "https://www.france24.com/en/business/rss", "rss", 3)],
 "spain": [("El País (English)", "https://english.elpais.com/arc/outboundfeeds/rss/?outputType=xml", "rss", 1),
           ("The Corner", "https://thecorner.eu/feed/", "rss", 2)],
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

def parse_gnr(xml_text, source):
    """Google News RSS: split 'Headline - Publisher', link straight to publisher."""
    items = parse_rss(xml_text, source)
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        urls = list(ex.map(resolve_url, [i["url"] for i in items[:25]]))
    for i, u in zip(items[:25], urls):
        t = i["title"]
        if " - " in t:
            head, pub = t.rsplit(" - ", 1)
            head, pub = head.strip(), pub.strip()
        else:
            head, pub = t, "Google News"
        if not pub or len(pub) > 40:
            pub = "Google News"
        out.append({"title": head, "url": u, "desc": i["desc"], "date": i["date"],
                    "agency": pub, "prio": source[3], "media": True})
    return out
# own-country relevance hints for media items on country desks
COUNTRY_HINTS = {
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
FINANCE_RE = re.compile(r"\b(rate|inflation|cpi|gdp|growth|recession|econom|market|bank|trade|tariff|"
                        r"tax|budget|deficit|debt|currency|rupee|yen|yuan|euro|dollar|pound|ruble|"
                        r"rouble|won|peso|oil|gas|energy|gold|commodit|pric|merger|acquisition|ipo|"
                        r"earnings|revenue|profit|jobs|employ|unemploy|wage|salary|stimulus|fiscal|"
                        r"monetary|central bank|regulat|securit|bond|equit|stock|share|investor|"
                        r"fund|loan|credit|mortgage|housing|rent|pension|retirement|insurance|"
                        r"consumer|spending|retail|industrial|export|import|compan|corporate|"
                        r"business|industr|sanction|fine|penalt|startup|crypt|bitcoin|wealth|"
                        r"money|cash|payment|income|cost|fee|million|billion|trillion)", re.I)

def fetch_desk_items(desk):
    if desk in CATEGORY_DESKS or desk == "global":
        srcs = [s for d, lst in SOURCES.items() for s in lst] + \
               [s for d, lst in MEDIA.items() for s in lst] + GLOBAL_POOL + GLOBAL_MEDIA
        own_off, own_med = set(), set()
    else:
        off = list(SOURCES.get(desk, []))
        med = list(MEDIA.get(desk, []))
        have = {s[1] for s in off + med}
        srcs = off + med + [s for s in GLOBAL_POOL + GLOBAL_MEDIA if s[1] not in have]
        own_off = {s[0] for s in off}
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

def select_items(all_items, win_start, win_end, desk, target=22, own_off=None, own_med=None):
    own_off = own_off or set()
    own_med = own_med or set()
    lo = win_start.date()
    floor = win_end.date() - dt.timedelta(days=3)   # extend back max 72h when thin
    while True:
        fresh = [i for i in all_items if lo <= i["date"] <= win_end.date()]
        if desk in CATEGORY_DESKS:
            flt = CATEGORY_FILTERS[desk]
            fresh = [i for i in fresh if any(k in i["title"].lower() for k in flt)]
        if len(fresh) >= 15 or lo <= floor:
            break
        lo -= dt.timedelta(days=1)
    hint = HINT_RE.get(desk)
    def score(i):
        s = 100 - i["prio"] * 10
        s += 25 if SALIENT.search(i["title"]) else 0
        if own_off or own_med:
            if i["agency"] in own_off:
                s += 60        # own-country official releases lead
            elif i["agency"] in own_med:
                s += 40        # own-country trusted newsrooms next
                if hint and not hint.search(i["title"]):
                    s -= 50    # own outlet but a foreign story — rank it like context
            else:
                s -= 25        # international context fills
        s += (i["date"] - win_start.date()).days * 2
        return -s
    fresh.sort(key=score)
    agency_count, capped = {}, []
    for i in fresh:
        cap = 12 if i["agency"] in own_off else (8 if i["agency"] in own_med else 5)
        if agency_count.get(i["agency"], 0) >= cap:
            continue
        agency_count[i["agency"]] = agency_count.get(i["agency"], 0) + 1
        capped.append(i)
    fresh = capped
    upcoming = [i for i in all_items
                if i["date"] and win_end.date() < i["date"] <= win_end.date() + dt.timedelta(days=7)][:6]
    return fresh[:target], upcoming, lo

# ---------------------------------------------------------------- composition
def clean_title(t):
    t = re.sub(r"\s+", " ", t).strip(" .:-–|")
    return t

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

def compose_item(it, win_end):
    typ = item_type(it["title"])
    why = WHY[typ][hash(it["title"]) % len(WHY[typ])]
    title = clean_title(it["title"])
    if len(title) > 140:  # trim long official titles at word boundary
        cut = title[:140].rfind(" ")
        title = title[:cut if cut > 60 else 140].rstrip(" ,;:-(") + "…"
    if it["desc"] and len(it["desc"]) > 80:
        desc = it["desc"]
        cut = desc.find(". ", 60)
        if 0 < cut < 320:
            desc = desc[:cut + 1]
    else:
        desc = ""
    day = fmt_day(it["date"]) if it["date"] else "Window"
    etitle, eagency = htmlmod.escape(title), htmlmod.escape(it["agency"])
    core = desc if desc else etitle
    body = f"<strong>{eagency}</strong> — {core}."
    if not desc:
        body = f"<strong>{eagency}</strong> — published {day}: {etitle}."
    body += f" <em>{why}</em>"
    return f'''    <div class="fbk-item">
      <span class="fbk-chip">{day}</span>
      <h3>{etitle}</h3>
      <p>{body}</p>
      <a class="fbk-src" href="{htmlmod.escape(it['url'])}" target="_blank" rel="noopener">{"Source:" if it.get("media") else "Official:"} {eagency}</a>
    </div>'''

# ---------------------------------------------------------------- template
CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fbk_styles.css")).read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fbk_styles.css")) else "/*missing*/"

def desk_title_prefix(desk):
    n, label, slug, slot, _, _ = DESKS[desk]
    if desk == "global":
        return "Global Finance Wire: The Last 24 Hours"
    if desk in CATEGORY_DESKS:
        return f"{label}: The Last 24 Hours"
    return f"{label} Finance News"

def weekday_name(d):
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][d.weekday()]

def build_article(desk, items, upcoming, edition_date, win_start, win_end, fx, related):
    n, label, slug, slot, hero_id, hero_alt = DESKS[desk]
    top = [clean_title(i["title"]) for i in items[:3]]
    headline_bits = "; ".join(top[:2])[:90]
    date_long = f"{weekday_name(edition_date)}, {edition_date.day} {['January','February','March','April','May','June','July','August','September','October','November','December'][edition_date.month-1]} {edition_date.year}"
    win_str = f"{fmt_day(win_start.date())}–{fmt_day(win_end.date())} {win_end.year}"
    span_h = (win_end - win_start).total_seconds() / 3600
    span_txt = "the last 24 hours" if span_h <= 24.5 else f"the last {max(2, round(span_h / 24))} days"
    title = f"{desk_title_prefix(desk)} — {headline_bits} | {edition_date.day} {MONTHS[edition_date.month-1]} {edition_date.year}"
    meta = (f"{desk_title_prefix(desk).lower()}, {span_txt[4:]} only ({win_str}): "
            + "; ".join(t.lower() for t in top[:4])[:280]).strip()

    flag = {"us": "🇺🇸", "china": "🇨🇳", "germany": "🇩🇪", "india": "🇮🇳", "japan": "🇯🇵",
            "uk": "🇬🇧", "france": "🇫🇷", "italy": "🇮🇹", "russia": "🇷🇺", "canada": "🇨🇦",
            "brazil": "🇧🇷", "spain": "🇪🇸", "mexico": "🇲🇽", "australia": "🇦🇺",
            "south-korea": "🇰🇷"}.get(desk, "🌍")
    tag = f"Daily News · {flag} {label} Wire" if desk not in CATEGORY_DESKS else f"Daily News · 📑 {label}"

    hero_url = f"https://images.unsplash.com/{hero_id}?auto=format&fit=crop&w={HERO_W}&h={HERO_H}&q=85"

    # sections: group items into 3 thematic blocks + tape
    third = max(1, len(items) // 3)
    secs = [
        ("01", "The Tape — What Moved and Who Reported It", "Every item below is an official release or reporting from an established, trusted newsroom, inside the window.", items[:third]),
        ("02", "Policy, Data and the Official Record", "Central banks, ministries and statistics offices — the primary releases.", items[third:2*third]),
        ("03", "Regulation, Markets and the Small Print", "Circulars, filings, enforcement and market plumbing.", items[2*third:]),
    ]
    sections_html = ""
    for num, name, sub, its in secs:
        if not its:
            continue
        sections_html += f'\n    <h2 class="fbk-h2"><b>{num}</b> {name}</h2>\n    <p class="fbk-sub">{sub}</p>'
        for it in its:
            sections_html += "\n" + compose_item(it, win_end)

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
      <p><strong>Related reading on Finance by CA Kushal:</strong></p>{links}
    </div>'''

    signoff = f'''
    <div class="fbk-signoff">
      <span class="fbk-script">Read it? Question it. &#9999;</span>
      <p>Every item above happened inside {span_txt} ({win_str}). Where an item refers to an earlier fact, it is marked as background. The Week Ahead section looks forward only. Every item links to a genuine, trustworthy source — official or an established newsroom.</p>
      <p><strong>Education only, not personalised investment advice.</strong> This is not a recommendation or a promise of profit.</p>
      <p>Financial education, not personalised advice. Figures as reported {win_str} by the trusted sources linked above.</p>
    </div>'''

    body = f'''<div class="fbk-wrap">
  <figure class="fbk-hero"><img src="{hero_url}" alt="{hero_alt}" width="{HERO_W}" height="{HERO_H}" loading="eager" decoding="async" fetchpriority="high" style="display:block;width:100%;height:auto;max-width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:14px"></figure>

  <style>{CSS}</style>

  <div class="fbk-kicker">
    <span class="fbk-tag">{tag}</span>
    <span class="fbk-date">{date_long} · IST</span>
  </div>

  <h1 class="fbk-h1">{htmlmod.escape(desk_title_prefix(desk))}: {htmlmod.escape(headline_bits)}</h1>
  <p class="fbk-lede">{len(items)} official items from the {label} desk, all inside {span_txt} — the primary releases, the reference levels, and what they mean. Read the source, not the noise.</p>
  <div class="fbk-byline"><strong>By CA Kushal K. Daga</strong> · Published {date_long} · Last reviewed {date_long} · IST</div>
  <p class="fbk-note">Recency rule: every item below is news of <strong>{win_str}</strong> (or weekend trading inside that window). Levels from before the window appear only as labelled last-close references. Events before the window appear only in the Week Ahead, marked as background. Every item links to a <em>genuine, trustworthy source</em> — official releases from central banks, ministries, statistical offices, regulators and exchanges, plus reporting from established, reputable newsrooms.</p>
{sections_html}
{fx_html}
{week_html}
{related_html}
{signoff}
</div>'''

    canonical = "https://dailyyield.blogspot.com/PLACEHOLDER-CANONICAL"
    jsonld = {
        "@context": "https://schema.org", "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": canonical}, "@id": canonical,
        "headline": title[:110], "description": meta, "inLanguage": "en",
        "datePublished": f"{edition_date.isoformat()}T{slot}:00+05:30",
        "dateModified": f"{edition_date.isoformat()}T{slot}:00+05:30",
        "author": {"@type": "Person", "name": "CA Kushal K. Daga",
                   "url": f"{BLOG}/p/about.html"},
        "publisher": {"@type": "Organization", "name": "Finance by CA Kushal",
                      "url": BLOG + "/"},
        "about": {"@type": "Place", "name": label} if desk not in CATEGORY_DESKS | {"global"} else {"@type": "Thing", "name": label},
        "keywords": f"{label.lower()} finance news today, {span_txt[4:]}, trusted sources, {', '.join(t.lower() for t in top[:4])[:150]}, {edition_date.day} {MONTHS[edition_date.month-1]} {edition_date.year}",
    }
    full_html = body + f'''
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'''

    return {"title": title, "slug": f"{slug}-{edition_date.isoformat()}",
            "meta": meta, "labels": ["News", label], "html": full_html,
            "canonical": canonical, "n_items": len(items)}

# ---------------------------------------------------------------- related links
def fetch_related(desk, prev_url):
    rel = []
    if prev_url:
        rel.append((f"Yesterday's {DESKS[desk][1]} Wire — the previous 24 hours", prev_url))
    try:
        feed = json.loads(http_get(f"{BLOG}/feeds/posts/default?alt=json&max-results=25"))
        kws = {"market": ["market", "invest", "trading"], "macro": ["inflation", "economy", "recession", "gdp"],
               "corporate": ["corporate", "business", "company"], "personal": ["money", "budget", "savings", "emergency", "salary"]}.get(desk, [])
        label = DESKS[desk][1].lower()
        for e in feed["feed"]["entry"]:
            if any(c["term"] == "News" for c in e.get("category", [])):
                continue
            t = e["title"]["$t"]
            link = [l["href"] for l in e["link"] if l["rel"] == "alternate"][0]
            tl = t.lower()
            if (desk not in CATEGORY_DESKS and label.split()[0] in tl) or any(k in tl for k in kws):
                rel.append((t, link))
            if len(rel) >= 3:
                break
    except Exception:
        pass
    return rel[:3]

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
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def publish_post(art, token, dry=False):
    if dry:
        print(f"    [DRY] would publish: '{art['title'][:80]}' slug={art['slug']} labels={art['labels']}")
        return None
    # pass 1: draft with slug-title (Blogger derives permalink from it)
    draft = blogger_call("/posts/", token, "POST", {
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

def run_desk(desk, tracker, dry=False, token=None):
    n, label, slug, slot, _, _ = DESKS[desk]
    now = dt.datetime.now(IST)
    hh, mm = map(int, slot.split(":"))
    slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    prev = tracker["desks"].get(desk, {})
    if prev.get("edition") == now.date().isoformat():
        print(f"  [{desk}] already published today ({prev.get('url','?')}) — skip")
        return False
    # rolling window: previous edition end -> now (24h on first run)
    win_end = now
    win_start = dt.datetime.fromisoformat(prev["window_end"]) if prev.get("window_end") \
        else now - dt.timedelta(hours=24)
    if win_start.tzinfo is None:
        win_start = win_start.replace(tzinfo=IST)
    edition_date = now.date()
    print(f"  [{desk}] window {win_start:%d %b %H:%M} -> {win_end:%d %b %H:%M} IST")

    items_raw, own_off, own_med = fetch_desk_items(desk)
    items, upcoming, eff_lo = select_items(items_raw, win_start, win_end, desk,
                                           own_off=own_off, own_med=own_med)
    eff_start = dt.datetime.combine(eff_lo, dt.time.min, IST)
    span_h = (win_end - eff_start).total_seconds() / 3600
    print(f"  [{desk}] {len(items_raw)} raw items -> {len(items)} selected "
          f"({len(upcoming)} upcoming, window extended to {span_h:.0f}h)" if span_h > 25 else
          f"  [{desk}] {len(items_raw)} raw items -> {len(items)} selected ({len(upcoming)} upcoming)")
    if len(items) < 8:
        print(f"  [{desk}] ONLY {len(items)} ITEMS — below safety floor, edition SKIPPED")
        return False
    fx = ecb_reference_rates()
    related = fetch_related(desk, prev.get("url"))
    art = build_article(desk, items, upcoming, edition_date, eff_start, win_end, fx, related)
    print(f"  [{desk}] article built: {art['n_items']} items, '{art['title'][:70]}…'")
    url = publish_post(art, token, dry)
    if url or dry:
        if not dry:
            tracker["desks"][desk] = {"edition": edition_date.isoformat(),
                                      "window_end": win_end.isoformat(),
                                      "url": url or prev.get("url", "")}
            save_tracker(tracker)
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
        if slot_dt <= now + dt.timedelta(minutes=45):
            due.append(desk)  # due now or missed earlier today -> catch-up
    return due

LAUNCH_DATE = dt.date(2026, 9, 25)   # news section starts Sept 25 (user instruction)

def main():
    args = sys.argv[1:]
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
    token = None
    if not dry:
        token = blogger_token()
    ok, fail = 0, 0
    for desk in desks:
        desk = desk.strip()
        if desk not in DESKS:
            print(f"  ?? unknown desk '{desk}'"); fail += 1; continue
        try:
            if run_desk(desk, tracker, dry, token):
                ok += 1
        except Exception as e:
            print(f"  [{desk}] ERROR: {e}")
            fail += 1
    print(f"\nNews wires: {ok} published, {fail} failed" + (" (DRY RUN)" if dry else ""))
    if fail:
        sys.exit(1)

if __name__ == "__main__":
    main()
