#!/usr/bin/env python3
"""News edition coverage and reader-priority ordering.

Editorial rules this module enforces (user instruction of 15 October 2026):

* a **country** edition carries at least two items from every sub-section
  (Markets, Economy, Banking, Companies) and never more than ten from one
  sub-section when more news is available;
* a **sub-section** edition carries at least two items from every country it
  covers, never more than ten from one country;
* the **Global** edition is an editor's pick: it may leave countries or
  sub-sections out when the bigger stories deserve the space;
* every edition is ordered for the reader: search demand first, then how big the
  story is, then how much the audience cares about that country and sub-section.

Search demand is a real signal, not a guess: Google's public daily trending feed
is read (India, United States, United Kingdom, Australia) and cached for the day.
If that feed is unavailable the ranking falls back to a fixed finance demand
lexicon, and the report says which of the two was used.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DEMAND_CACHE = ROOT / "SEARCH_DEMAND_TRENDS.json"
COVERAGE_LOG = ROOT / "NEWS_COVERAGE_STATUS.json"

DESK_TOPICS = ("markets", "economy", "banking", "companies")
TOPIC_NAMES = {
    "markets": "Markets, Crypto & Commodities",
    "economy": "Economy, Trade & Jobs",
    "banking": "Banking, Fintech & Personal Money",
    "companies": "Companies, IPOs & Deals",
}
COUNTRIES = ("us", "canada", "mexico", "brazil", "china", "japan", "south-korea",
             "australia", "india", "russia", "uk", "germany", "france", "italy", "spain")
COUNTRY_NAMES = {
    "us": "United States", "canada": "Canada", "mexico": "Mexico", "brazil": "Brazil",
    "china": "China", "japan": "Japan", "south-korea": "South Korea", "australia": "Australia",
    "india": "India", "russia": "Russia", "uk": "United Kingdom", "germany": "Germany",
    "france": "France", "italy": "Italy", "spain": "Spain", "global": "Worldwide",
}
REGION_OF_COUNTRY = {
    "us": "americas", "canada": "americas", "mexico": "americas", "brazil": "americas",
    "japan": "asia-pacific", "south-korea": "asia-pacific", "australia": "asia-pacific",
    "uk": "europe", "germany": "europe", "france": "europe", "italy": "europe", "spain": "europe",
    "china": "china", "india": "india", "russia": "russia",
}
COUNTRY_DESKS = ("china", "india", "russia", "americas", "asia-pacific", "europe")
TOPIC_DESKS = DESK_TOPICS

MIN_PER_BUCKET = 2   # every sub-section of a country desk, every country of a topic desk
MAX_PER_BUCKET = 10  # a single sub-section or country never dominates an edition
EDITION_FLOOR = 24   # smallest edition the existing pipeline already accepts
EDITION_CAP = 40     # pipeline selection cap

# ---------------------------------------------------------------- search demand
DEMAND_LEXICON = (
    "inflation", "interest rate", "rate cut", "rate hike", "cpi", "gdp", "recession",
    "tariff", "trade deal", "jobs", "unemployment", "layoff", "earnings", "results",
    "ipo", "merger", "acquisition", "oil price", "gold price", "bitcoin", "crypto",
    "stock market", "sensex", "nifty", "rupee", "dollar", "tax", "budget", "housing",
    "mortgage", "loan", "emi", "bank", "rbi", "fed", "ecb", "sanction", "electric vehicle",
    "artificial intelligence", "semiconductor", "retail sales", "housing price",
)
TRENDING_GEOS = ("IN", "US", "GB", "AU")


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value).casefold())).strip()


def fetch_trends(geos=TRENDING_GEOS, timeout: int = 20) -> list[str]:
    """Read Google's public daily trending feed; no key, no account, no cookies."""
    terms: list[str] = []
    for geo in geos:
        try:
            request = urllib.request.Request(
                f"https://trends.google.com/trending/rss?geo={geo}",
                headers={"User-Agent": "DailyYieldDesk/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except Exception:
            continue
        for title in re.findall(r"<title>(.*?)</title>", body, re.S)[1:]:
            value = _normalise(re.sub(r"<!\[CDATA\[|\]\]>", "", title))
            if value and len(value) > 2:
                terms.append(value)
    return terms


def search_demand(refresh: bool = False) -> dict:
    """Today's demand signals, cached so every desk in one run agrees."""
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    if not refresh:
        try:
            cached = json.loads(DEMAND_CACHE.read_text(encoding="utf-8"))
            if cached.get("date") == today and cached.get("terms"):
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    trends = fetch_trends()
    document = {
        "date": today,
        "source": "google-trends-rss" if trends else "finance-demand-lexicon",
        "terms": trends,
        "lexicon": list(DEMAND_LEXICON),
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    try:
        DEMAND_CACHE.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass
    return document


def demand_score(item: dict, demand: dict | None = None) -> float:
    """How likely is this headline to be searched for right now?"""
    demand = demand or search_demand()
    text = _normalise(item.get("title", ""))
    words = set(text.split())
    score = 0.0
    for phrase in demand.get("lexicon", []):
        if phrase in text:
            score += 6.0
    for term in demand.get("terms", []):
        if not term:
            continue
        if term in text:
            score += 10.0
            continue
        overlap = set(term.split()) & words
        if len(overlap) >= 2 and len(term.split()) >= 2:
            score += 4.0
    return score


# ---------------------------------------------------------------- importance
AUDIENCE_COUNTRY = {
    "india": 1.25, "us": 1.20, "china": 1.15, "global": 1.12, "uk": 1.10, "germany": 1.08,
    "japan": 1.06, "russia": 1.06, "canada": 1.04, "australia": 1.04, "brazil": 1.03,
    "france": 1.03, "south-korea": 1.03, "mexico": 1.02, "italy": 1.02, "spain": 1.02,
}
AUDIENCE_TOPIC = {"markets": 1.20, "economy": 1.15, "banking": 1.10, "companies": 1.05}
MAGNITUDE_MARKERS = (
    "record", "surge", "plunge", "crash", "halt", "collapse", "crisis", "emergency",
    "billion", "trillion", "all-time", "close", "widest", "highest", "lowest",
    "approve", "ban", "sanction", "rescue", "default", "stimulus", "cut", "hike",
    "acquisition", "merger", "resign", "shutdown", "strike", "miss", "beat",
)
OFFICIAL_PRIORITY = {1: 3.0, 2: 2.4, 3: 1.6, 4: 1.0}


def magnitude_score(item: dict) -> float:
    text = _normalise(item.get("title", ""))
    score = sum(2.0 for marker in MAGNITUDE_MARKERS if marker in text)
    numbers = re.findall(r"\b\d+(?:\.\d+)?\s?(?:%|percent|billion|million|trillion|bps|points)\b", text)
    score += 2.5 * len(numbers)
    return score


def importance(item: dict, demand: dict | None = None) -> float:
    """Reader priority: demand, then size of the story, then audience appetite."""
    country = str(item.get("country") or item.get("region") or "global")
    topic = str(item.get("topic") or "economy")
    score = demand_score(item, demand)
    score += magnitude_score(item)
    score += AUDIENCE_COUNTRY.get(country, 1.0) * 8.0
    score += AUDIENCE_TOPIC.get(topic, 1.0) * 6.0
    score += OFFICIAL_PRIORITY.get(int(item.get("prio") or 4), 1.0)
    if item.get("country_discovery"):
        score += 1.5
    return round(score, 2)


def rank(items: list[dict], demand: dict | None = None) -> list[dict]:
    """Strongest story first; ties keep official sources ahead of secondary ones."""
    demand = demand or search_demand()
    return sorted(items, key=lambda item: (importance(item, demand),
                                           -int(item.get("prio") or 4)), reverse=True)


# ---------------------------------------------------------------- quotas
def _bucket_key(item: dict, desk: str) -> str:
    if desk in TOPIC_DESKS:
        return str(item.get("country") or item.get("region") or "global")
    return str(item.get("topic") or "economy")


def apply_quotas(items: list[dict], desk: str, demand: dict | None = None) -> tuple[list[dict], dict]:
    """Guarantee the coverage minimums, then fill by reader priority."""
    demand = demand or search_demand()
    ranked = rank(items, demand)
    if desk == "global":
        chosen = ranked[:EDITION_CAP]
        return chosen, {"desk": desk, "mode": "editor-pick",
                        "note": "Global edition keeps the strongest headlines and may skip countries or sections",
                        "counts": _counts(chosen, desk), "total": len(chosen)}

    order = DESK_TOPICS if desk in COUNTRY_DESKS else COUNTRIES
    buckets: dict[str, list[dict]] = {key: [] for key in order}
    others: list[dict] = []
    for item in ranked:
        key = _bucket_key(item, desk)
        (buckets[key] if key in buckets else others).append(item)

    chosen: list[dict] = []
    seen: set[str] = set()

    def take(item: dict) -> bool:
        marker = str(item.get("url") or _normalise(item.get("title", "")))
        if marker in seen:
            return False
        seen.add(marker)
        chosen.append(item)
        return True

    shortfalls: dict[str, int] = {}
    # 1. every bucket gets its minimum from its own strongest stories
    for key in order:
        taken = 0
        for item in buckets[key]:
            if taken >= MIN_PER_BUCKET:
                break
            if take(item):
                taken += 1
        if taken < MIN_PER_BUCKET and buckets[key]:
            shortfalls[key] = MIN_PER_BUCKET - taken
    # 2. fill up to the cap, keeping each bucket inside its maximum
    counts = _counts(chosen, desk)
    for item in ranked:
        if len(chosen) >= EDITION_CAP:
            break
        key = _bucket_key(item, desk)
        if counts.get(key, 0) >= MAX_PER_BUCKET:
            continue
        if take(item):
            counts[key] = counts.get(key, 0) + 1
    # 3. only if an edition would fall below the floor, allow a bucket to exceed
    #    its maximum rather than ship a thin edition
    for item in ranked:
        if len(chosen) >= EDITION_FLOOR:
            break
        take(item)

    report = {
        "desk": desk, "mode": "country-desk-topics" if desk in COUNTRY_DESKS else "topic-desk-countries",
        "minimum_per_bucket": MIN_PER_BUCKET, "maximum_per_bucket": MAX_PER_BUCKET,
        "counts": _counts(chosen, desk), "total": len(chosen),
        "buckets_short_of_minimum": shortfalls,
        "buckets_never_covered": [key for key in order if not buckets[key]],
    }
    return chosen, report


def _counts(items: list[dict], desk: str) -> dict:
    counts: dict[str, int] = {}
    for item in items:
        key = _bucket_key(item, desk)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ---------------------------------------------------------------- reader order
def order_for_reader(items: list[dict], desk: str, demand: dict | None = None) -> list[dict]:
    """Sections by strength, stories inside a section strongest first."""
    demand = demand or search_demand()
    if desk in COUNTRY_DESKS:
        sections = DESK_TOPICS
        key_of = lambda item: str(item.get("topic") or "economy")  # noqa: E731
    elif desk == "global":
        return rank(items, demand)
    else:
        sections = COUNTRIES
        key_of = lambda item: str(item.get("country") or item.get("region") or "global")  # noqa: E731
    grouped: dict[str, list[dict]] = {key: [] for key in sections}
    leftover: list[dict] = []
    for item in items:
        key = key_of(item)
        (grouped[key] if key in grouped else leftover).append(item)
    strength = {}
    for key, rows in grouped.items():
        strength[key] = max((importance(row, demand) for row in rows), default=0)
    ordered: list[dict] = []
    for key in sorted(sections, key=lambda k: strength[k], reverse=True):
        ordered.extend(rank(grouped[key], demand))
    ordered.extend(rank(leftover, demand))
    return ordered


def enforce(items: list[dict], desk: str, demand: dict | None = None) -> tuple[list[dict], dict]:
    """One call the pipeline makes: apply the coverage rules, then reader order."""
    demand = demand or search_demand()
    chosen, report = apply_quotas(items, desk, demand)
    ordered = order_for_reader(chosen, desk, demand)
    report["lead_headline"] = ordered[0].get("title", "") if ordered else ""
    report["order_top5"] = [item.get("title", "")[:70] for item in ordered[:5]]
    report["demand_source"] = demand.get("source", "unknown")
    report["generated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        history = json.loads(COVERAGE_LOG.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []
    except (OSError, json.JSONDecodeError):
        history = []
    history = [row for row in history if row.get("desk") != desk][-30:] + [report]
    try:
        COVERAGE_LOG.write_text(json.dumps(history, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass
    return ordered, report


if __name__ == "__main__":
    print(json.dumps(search_demand(), indent=1)[:400])
