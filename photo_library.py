#!/usr/bin/env python3
"""Daily Yield photo library: licensed photographs, prepared before publication.

Two pools are built from keyless, licence-bearing public sources (Wikimedia
Commons and Openverse) so a publication run never has to stop because a
photograph could not be found in time:

* **Master pool** — ten candidates for every evergreen and trending article, built
  from the article's own topic words. The current renderer uses three photos;
  the owner's live-format target is ten, and expansion remains held during the
  AdSense freeze. Ten prepared candidates must not be reported as ten published photos.
* **News pool** — forty to fifty photographs for each News desk (every country
  desk plus the global section), used in strict rotation so consecutive editions
  never repeat a picture.

Every entry records its licence, creator, licence link and source page. Nothing
is used that is not clearly licensed for commercial reuse: no non-commercial, no
no-derivatives, no share-alike, no unlicensed web images. No credentials are
needed and no page views are created.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
import time
import urllib.parse
from pathlib import Path

import requests
from source_photography import photographic_candidate

ROOT = Path(__file__).parent
LIBRARY = ROOT / "photo_library"
MASTER_DIR = LIBRARY / "master"
NEWS_DIR = LIBRARY / "news"
STATUS = ROOT / "PHOTO_LIBRARY_STATUS.json"
UA = "DailyYieldPhotoEditor/1.0 (dailyyield.official@gmail.com)"

ALLOWED_LICENCE = (
    "cc0", "public domain", "pdm", "cc by 2.0", "cc by 2.5", "cc by 3.0", "cc by 4.0",
    "by 2.0", "by 2.5", "by 3.0", "by 4.0",
)
BLOCKED_LICENCE = ("noncommercial", "non-commercial", "nc", "nd", "no derivatives", "share-alike", "sa 4.0", "gfdl")
MINOR_TERMS = re.compile(r"\b(?:child|children|kid|kids|minor|schoolchild|schoolgirl|schoolboy|teenager|young girl|young boy|student|pupil)\b", re.I)
NON_PHOTO_TERMS = re.compile(r"\b(?:chart|diagram|illustration|infographic|logo|coat of arms|flag|map|poster|graph|clipart|drawing|banknote|coin design)\b", re.I)
STOP = set("the and with from into that this photo photograph editorial landscape horizontal realistic without showing financial finance opening context article subject mid later mechanism evidence implications decisions stop maxing how after before measure measuring wide news daily yield 2026".split())

# Words that describe the world a finance desk writes about. They never qualify a
# photograph on their own; they let a clearly relevant picture pass when it also
# carries at least one distinctive topic word.
TOPICAL = set("office business people worker workplace building buildings street city market money bank banking shop store industry factory farm table meeting computer laptop documents storefront family house home hospital train plane truck port energy oil gas power solar wind water construction handshake signature newspaper journal library university laboratory research government parliament exchange trading currency coins investment savings".split())


def clean(value) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def terms(value) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]{3,}", str(value).casefold()) if x not in STOP}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")[:60]


# --------------------------------------------------------------------- sources
def commons(query: str, limit: int = 40) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrlimit": min(50, limit), "gsrsearch": query, "prop": "imageinfo",
        "iiprop": "url|size|extmetadata", "iiurlwidth": 1600,
    }
    try:
        response = requests.get("https://commons.wikimedia.org/w/api.php", params=params,
                                headers={"User-Agent": UA}, timeout=45)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
    except Exception:
        return []
    rows = []
    for page in (pages.values() if isinstance(pages, dict) else pages):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        value = lambda key: clean((meta.get(key) or {}).get("value", ""))
        licence = value("LicenseShortName") or value("UsageTerms")
        licence_url = value("LicenseUrl")
        combined = (licence + " " + licence_url).casefold()
        if not licence_url and "public domain" in combined:
            licence_url = "https://creativecommons.org/publicdomain/mark/1.0/"
        if not licence_url and "cc0" in combined:
            licence_url = "https://creativecommons.org/publicdomain/zero/1.0/"
        rows.append({
            "source_id": "commons:" + str(page.get("pageid")),
            "provider": "Wikimedia Commons",
            "title": clean(str(page.get("title", "")).replace("File:", "")),
            "description": value("ImageDescription"),
            "creator": value("Artist") or clean(info.get("user", "")) or "Unknown creator",
            "licence": licence, "licence_url": licence_url,
            "source_page": info.get("descriptionurl", ""),
            "download_url": info.get("thumburl") or info.get("url", ""),
            "original_url": info.get("url", ""),
            "width": int(info.get("width") or 0), "height": int(info.get("height") or 0),
            "query": query,
        })
    return rows


OPENVERSE_LICENCE_URL = "https://creativecommons.org/licenses/{slug}/{version}/"


def openverse(query: str, limit: int = 30) -> list[dict]:
    params = {"q": query, "license_type": "commercial", "page_size": str(min(20, limit)), "mature": "false"}
    try:
        response = requests.get("https://api.openverse.org/v1/images/", params=params,
                                headers={"User-Agent": UA}, timeout=40)
        if response.status_code == 429:
            return []
        response.raise_for_status()
        results = response.json().get("results", [])
    except Exception:
        return []
    rows = []
    for item in results:
        licence = clean(item.get("license")) or "unknown"
        version = clean(item.get("license_version"))
        licence_url = item.get("license_url") or (OPENVERSE_LICENCE_URL.format(slug=licence, version=version) if version else "")
        rows.append({
            "source_id": "openverse:" + str(item.get("id")),
            "provider": clean(item.get("source")) or "Openverse",
            "title": clean(item.get("title")),
            "description": "",
            "creator": clean(item.get("creator")) or "Unknown creator",
            "licence": (f"cc {licence} {version}").strip(),
            "licence_url": licence_url,
            "source_page": item.get("foreign_landing_url") or item.get("detail_url", ""),
            "download_url": item.get("url", ""),
            "original_url": item.get("url", ""),
            "width": int(item.get("width") or 0), "height": int(item.get("height") or 0),
            "query": query,
        })
    return rows


def licence_ok(entry: dict) -> bool:
    combined = (str(entry.get("licence", "")) + " " + str(entry.get("licence_url", ""))).casefold()
    if any(bad in combined for bad in BLOCKED_LICENCE):
        # "by" is allowed; exclude the true blockers only.
        if not re.search(r"\bcc by (?:2\.0|2\.5|3\.0|4\.0)\b", combined):
            return False
    return any(good in combined for good in ALLOWED_LICENCE)


def subject_ok(entry: dict) -> bool:
    if (entry.get('original_url') or entry.get('source_page')) and not photographic_candidate(entry):
        return False
    text = f"{entry.get('title', '')} {entry.get('description', '')}"
    if MINOR_TERMS.search(text):
        return False
    if NON_PHOTO_TERMS.search(text.casefold()):
        return False
    width, height = int(entry.get("width") or 0), int(entry.get("height") or 0)
    if width < 1200 or height < 640:
        return False
    return width / max(1, height) >= 1.3  # landscape, suitable for the 16:9 frames


def reachable(entry: dict) -> bool:
    url = entry.get("download_url") or ""
    if not url.startswith("https://"):
        return False
    try:
        response = requests.get(url, headers={"User-Agent": UA}, timeout=15, stream=True)
        if response.status_code != 200:
            return False
        if not str(response.headers.get("Content-Type", "")).startswith("image/"):
            return False
        next(response.iter_content(2048), b"")
        response.close()
        return True
    except Exception:
        return False


def match_score(wanted: set[str], entry: dict) -> int:
    have = terms(f"{entry.get('title', '')} {entry.get('description', '')}")
    overlap = wanted & have
    if len(overlap) >= 2:
        return 40 + 8 * len(overlap)
    if len(overlap) >= 1 and len(have & TOPICAL) >= 2:
        return 24
    if len(have & TOPICAL) >= 3:
        return 12
    return 0


# --------------------------------------------------------------------- pool files
def load_pool(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"entries": [], "rotation": 0}


def save_pool(path: Path, pool: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pool, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def used_source_ids() -> set[str]:
    """Nothing in the library may reuse a photograph that an article already ran."""
    used: set[str] = set()
    registry = ROOT / "PHOTO_USAGE_REGISTRY.json"
    try:
        for item in json.loads(registry.read_text()).get("items", []):
            used.add(str(item.get("source_id", "")))
    except (OSError, json.JSONDecodeError):
        pass
    for path in list(MASTER_DIR.glob("*.json")) + list(NEWS_DIR.glob("*.json")):
        for entry in load_pool(path).get("entries", []):
            used.add(str(entry.get("source_id", "")))
    return {x for x in used if x}


def gather(queries: list[str], wanted: set[str], want: int, exclude: set[str]) -> list[dict]:
    """Search both sources, keep only licensed and usable photographs, best first."""
    if want <= 0:
        return []
    seen_ids: set[str] = set()
    candidates: list[dict] = []
    for query in dict.fromkeys(q for q in queries if q.strip()):
        if len(candidates) >= want * 3:
            break
        batch = commons(query, 40) + openverse(query, 20)
        for entry in batch:
            key = entry.get("source_id", "")
            if key in seen_ids or key in exclude:
                continue
            if not licence_ok(entry) or not subject_ok(entry):
                continue
            seen_ids.add(key)
            entry["match"] = match_score(wanted, entry)
            if entry["match"] > 0:
                candidates.append(entry)
        time.sleep(0.4)
    candidates.sort(key=lambda x: (x["match"], min(int(x.get("width") or 0), 5000)), reverse=True)
    kept: list[dict] = []
    seen_titles: set[str] = set()
    # Links are checked side by side: the pools are built nightly and a single
    # desk can offer well over a hundred candidates.
    probe = candidates[: max(want * 4, 24)]
    with ThreadPoolExecutor(max_workers=10) as workers:
        live = dict(zip([str(x.get("source_id")) for x in probe], workers.map(reachable, probe)))
    for entry in candidates:
        title = re.sub(r"[^a-z0-9]+", " ", str(entry.get("title", "")).casefold()).strip()
        if title and title in seen_titles:
            continue
        if not live.get(str(entry.get("source_id")), False):
            continue
        seen_titles.add(title)
        entry.pop("match", None)
        entry["checked_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        kept.append(entry)
        if len(kept) >= want:
            break
    return kept


# --------------------------------------------------------------------- Master pool
MASTER_TARGET = 10
DESK_LEXICON = {
    "retirement": ["retirement pension planning", "older couple financial planning", "workplace pension meeting"],
    "housing": ["residential houses neighbourhood", "home buying documents", "apartment buildings city"],
    "inflation": ["grocery shopping prices", "central bank building", "household budgeting desk"],
    "healthcare": ["hospital building exterior", "medical research laboratory", "health technology office"],
    "cash": ["small business shop owner", "cash register counter", "bookkeeping desk paperwork"],
    "credit": ["payment card terminal", "bank branch interior", "credit paperwork signing"],
    "invest": ["stock exchange trading", "financial district buildings", "investment analysis desk"],
    "tax": ["tax office government building", "tax forms paperwork", "accountant working office"],
    "market": ["stock exchange trading floor", "market data screens office", "financial district skyline"],
    "energy": ["oil refinery industrial", "wind turbines energy", "power station electricity"],
    "trade": ["container port shipping", "cargo train freight", "warehouse logistics"],
    "policy": ["parliament building government", "press conference podium", "official government office"],
    "family": ["multigenerational family home", "family household budgeting", "family house exterior"],
    "business": ["office team meeting", "small business owner shop", "office workers computers"],
    "job": ["office workers meeting", "job interview office", "workplace team discussion"],
    "europe": ["european city financial district", "european parliament building", "european street market"],
    "america": ["united states bank building", "american city skyline street", "american small business"],
    "asia": ["asian city financial district", "asian port shipping terminal", "asian street market vendors"],
    "china": ["china city skyline", "china industrial factory", "china business district street"],
    "india": ["india city street market", "india business district office", "india railway station crowd"],
    "russia": ["russia city street architecture", "russia industrial plant", "russia bank building"],
}


def master_queries(title: str, briefs: list[str] | None = None) -> list[str]:
    text = f"{title} {' '.join(briefs or [])}".casefold()
    words = [x for x in terms(title) if len(x) > 3][:4]
    queries = [" ".join(words[:3])] if words else []
    queries += [" ".join(words[:2] + [extra]) for extra in ("office", "city", "business")] if words else []
    for key, extras in DESK_LEXICON.items():
        if key in text:
            queries.extend(extras)
    queries += ["business meeting office table", "office workers computers finance", "financial district buildings street"]
    return [q for q in dict.fromkeys(queries) if q.strip()]


def build_master_pool(topic_key: str, title: str, briefs: list[str] | None = None, target: int = MASTER_TARGET) -> dict:
    path = MASTER_DIR / f"{slugify(topic_key)}.json"
    pool = load_pool(path)
    have = {str(x.get("source_id")) for x in pool.get("entries", [])}
    exclude = used_source_ids() | have
    wanted = terms(title) | terms(" ".join(briefs or []))
    fresh = [x for x in gather(master_queries(title, briefs), wanted,
                               target - len(pool.get("entries", [])), exclude)
             if str(x.get("source_id")) not in have]
    entries = pool.get("entries", []) + fresh
    pool = {"kind": "master", "topic_key": topic_key, "title": title,
            "target": target, "built_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "entries": entries, "taken": pool.get("taken", [])}
    save_pool(path, pool)
    return pool


def ensure_master_pool(topic_key: str, title: str, briefs: list[str] | None = None,
                       target: int = MASTER_TARGET) -> dict:
    """Guarantee this article has a full pool before its release window."""
    pool = build_master_pool(topic_key, title, briefs, target)
    if len(pool.get("entries", [])) < target:
        # A second, wider attempt: the article's own words plus the desk lexicon
        # and the general finance set, with no relevance threshold left to trip.
        extra = gather(master_queries(title, briefs) + ["business meeting office", "city financial district",
                                                        "office workers computers", "small business shop owner"],
                       terms(title), target - len(pool.get("entries", [])),
                       used_source_ids() | {str(x.get("source_id")) for x in pool.get("entries", [])})
        have = {str(x.get("source_id")) for x in pool.get("entries", [])}
        pool["entries"] = pool.get("entries", []) + [x for x in extra if str(x.get("source_id")) not in have]
        save_pool(MASTER_DIR / f"{slugify(topic_key)}.json", pool)
    return pool


def reserve_master_entry(topic_key: str, title: str, briefs: list[str] | None, placement: int,
                         avoid_ids: set[str] | None = None) -> dict | None:
    """Take the next unused, licence-verified photograph for this placement.

    This is the writer's safety net: a prepared pool means a release never has to
    stop merely because a live search returned nothing for one brief.
    """
    avoid_ids = {str(x) for x in (avoid_ids or set())}
    pool = ensure_master_pool(topic_key, title, briefs)
    taken = {str(x.get("source_id")) for x in pool.get("taken", [])}
    for entry in pool.get("entries", []):
        if str(entry.get("source_id")) in taken or str(entry.get("source_id")) in avoid_ids:
            continue
        entry = dict(entry)
        entry["placement"] = placement
        entry["used_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        pool["taken"] = pool.get("taken", []) + [entry]
        save_pool(MASTER_DIR / f"{slugify(topic_key)}.json", pool)
        return entry
    return None


def next_master_photos(topic_key: str, count: int = 3) -> list[dict]:
    """Take the next unused photographs for this article, best match first."""
    path = MASTER_DIR / f"{slugify(topic_key)}.json"
    pool = load_pool(path)
    entries = pool.get("entries", [])
    taken = {str(x.get("source_id")) for x in pool.get("taken", [])}
    available = [x for x in entries if str(x.get("source_id")) not in taken]
    picked = available[:count]
    if len(picked) < count:
        return []
    pool["taken"] = pool.get("taken", []) + picked
    save_pool(path, pool)
    return picked


# --------------------------------------------------------------------- News pool
NEWS_TARGET = 45
NEWS_MOTIFS = (
    "city skyline financial district", "central bank building", "stock exchange trading",
    "currency coins banknotes", "business people meeting office", "small business shop owner",
    "container port shipping trade", "cargo train logistics warehouse", "farm agriculture field",
    "factory industrial production", "oil refinery energy plant", "wind turbines solar power",
    "supermarket grocery shopping", "market street vendors stalls", "office workers computers",
    "bank branch interior counter", "government parliament building", "university library research",
    "construction site buildings cranes", "airport aircraft terminal", "motorway traffic transport",
    "river bridge infrastructure", "hotel tourism city street", "technology laboratory research",
)
DESK_FOCUS = {
    "asia-pacific": ["singapore skyline marina", "tokyo city street", "sydney harbour city", "jakarta street market"],
    "china": ["shanghai skyline pudong", "beijing city street", "shenzhen industrial district", "china factory worker"],
    "india": ["mumbai city skyline", "delhi street market", "bengaluru technology campus", "india railway station"],
    "russia": ["moscow city skyline", "saint petersburg architecture", "russia industrial plant", "russia rural village"],
    "europe": ["frankfurt financial district", "london city skyline", "paris street architecture", "brussels european quarter"],
    "americas": ["new york city skyline", "chicago financial district", "toronto city skyline", "american small town main street"],
    "economy": ["employment factory workers", "trade port containers", "economic statistics office", "agriculture harvest field"],
    "markets": ["trading floor screens", "stock chart monitor office", "gold bullion bars", "commodities oil barrels"],
    "companies": ["corporate headquarters building", "office team meeting", "industrial manufacturing plant", "startup office workspace"],
    "global": ["world map desk documents", "international airport terminal", "shipping container port global trade", "united nations style conference"],
    "banking": ["bank branch counter interior", "payment card transaction", "savings passbook paperwork", "mobile banking smartphone"],
}


def build_news_pool(desk: str, target: int = NEWS_TARGET) -> dict:
    path = NEWS_DIR / f"{slugify(desk)}.json"
    pool = load_pool(path)
    have = {str(x.get("source_id")) for x in pool.get("entries", [])}
    exclude = used_source_ids() | have
    focus = DESK_FOCUS.get(desk, [])
    queries = list(focus) + [f"{focus[0].split()[0]} {m}" for m in NEWS_MOTIFS[:10]] if focus else list(NEWS_MOTIFS)
    queries += [f"{desk.replace('-', ' ')} {m}" for m in NEWS_MOTIFS[:12]]
    wanted = terms(" ".join(focus)) | terms(desk.replace("-", " ")) | terms("finance market business economy")
    fresh = [x for x in gather(queries, wanted, target - len(pool.get("entries", [])), exclude)
             if str(x.get("source_id")) not in have]
    entries = pool.get("entries", []) + fresh
    pool = {"kind": "news", "desk": desk, "target": target, "rotation": int(pool.get("rotation", 0)),
            "built_at": dt.datetime.now(dt.timezone.utc).isoformat(), "entries": entries}
    save_pool(path, pool)
    return pool


def next_news_photo(desk: str, avoid: set[str] | None = None) -> dict | None:
    """Return the next photograph in rotation, never repeating a recent one."""
    path = NEWS_DIR / f"{slugify(desk)}.json"
    pool = load_pool(path)
    entries = pool.get("entries", [])
    if not entries:
        return None
    avoid = {str(x) for x in (avoid or set())}
    start = int(pool.get("rotation", 0))
    for step in range(len(entries)):
        index = (start + step) % len(entries)
        entry = entries[index]
        if str(entry.get("download_url")) in avoid:
            continue
        pool["rotation"] = (index + 1) % len(entries)
        pool["last_used"] = {"index": index, "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                             "source_id": entry.get("source_id")}
        save_pool(path, pool)
        return entry
    return None


# --------------------------------------------------------------------- reporting
def status() -> dict:
    rows = []
    for path in sorted(MASTER_DIR.glob("*.json")):
        pool = load_pool(path)
        rows.append({"pool": f"master/{path.stem}", "entries": len(pool.get("entries", [])),
                     "used": len(pool.get("taken", [])), "target": pool.get("target", MASTER_TARGET),
                     "title": pool.get("title", "")[:70]})
    for path in sorted(NEWS_DIR.glob("*.json")):
        pool = load_pool(path)
        rows.append({"pool": f"news/{path.stem}", "entries": len(pool.get("entries", [])),
                     "rotation": pool.get("rotation", 0), "target": pool.get("target", NEWS_TARGET)})
    return {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "pools": rows,
            "master_pools": sum(1 for r in rows if r["pool"].startswith("master/")),
            "news_pools": sum(1 for r in rows if r["pool"].startswith("news/")),
            "master_photos": sum(r["entries"] for r in rows if r["pool"].startswith("master/")),
            "news_photos": sum(r["entries"] for r in rows if r["pool"].startswith("news/"))}


if __name__ == "__main__":
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    print(json.dumps(status(), indent=2))
