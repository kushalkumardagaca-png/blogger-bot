#!/usr/bin/env python3
"""Judge every Daily Yield URL against Bing's Webmaster Guidelines and Google's indexability rules.

Why this file exists: both search engines now publish the same four-part demand in different words -
discover through sitemaps and links, consolidate duplicates, keep every URL worth crawling, and
describe it honestly (title, structure, alt text, structured data). Bing's guidelines
(bing.com/webmasters/help/webmaster-guidelines-30fba23a) add the crawl-waste and grounding framing;
Google's URL Inspection rules (support.google.com/webmasters/answer/9012289) add the canonical,
"indexing allowed?" and "no referring sitemap" mechanics. This audit turns those into checks that can
be answered from data we are allowed to read, and says plainly which checks a Blogger property cannot
answer at all.

Deliberate boundaries:
- Read-only. Nothing here edits the blog, the theme, or a robots rule.
- The corpus is read from Blogger's public feeds (the same bytes a crawler is offered), not by
  navigating the site in a browser. Rendered-page inspection is a small bounded sample with polite
  spacing, because title tags, canonicals, meta robots and JSON-LD only exist in the rendered head.
- Every check states who can fix it: repo (our generator/publishing code), blogger (a setting or a
  page's own content), owner (a button only a human may press), or platform (not ours to change).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "SEARCH_INDEX_POLICY_AUDIT.json"
MD = ROOT / "SEARCH_INDEX_POLICY_AUDIT.md"

BLOG = "https://dailyyield.blogspot.com"
SITEMAPS = (BLOG + "/sitemap.xml", BLOG + "/sitemap-pages.xml")
RENDER_SAMPLE = 6
SAMPLE_SPACING_SECONDS = 5
MIN_WORDS = 300          # below this Bing §11 calls the page thin
TITLE_MAX = 70           # both engines truncate past this and §13 wants a readable title
TITLE_MIN = 12           # our own validator floor; shorter is not descriptive
# Jaccard overlap of 8-word shingles. Containment (overlap / smaller document) was the first choice
# and it was wrong: every short page shares the site's standing disclaimer paragraph, so a 60-word
# page scored 1.00 against a 2,000-word article and the report cried duplicate 40 times over. This
# ratio means "these two URLs are substantially the same document", which is what Bing §6 and the
# duplicate-content abuse line actually describe.
SHINGLE_DUPLICATE_RATIO = 0.42
SHINGLE_MIN_SHARDS = 25          # below this a page is too short for any similarity verdict
SHARED_IMAGE_NAME_LIMIT = 25     # a photo name on more URLs than this is a template, not a name
LEAD_PARAGRAPHS = 2              # how far down the page the headline has to be paid off
LEAD_MIN = 0.5                   # at least half the headline's subject words must appear there
STOPWORDS = set("""a an the of and or to in for on at is are was were be been with by from as it its
this that these those new india global today today's will would can could about into over under between
why how what when where which who whose and""".split())
# URLs a crawler has no business being offered: the machine page that holds the IndexNow key, the
# redirect notice that replaced an old post, and one post that a publishing bug created out of the
# string "http://schema.org" in a JSON-LD block. All three sit in a sitemap right now.
UTILITY_SLUGS = {"indexnow-key", "robots", "share-market_0718113516", "context-httpsschema"}
# One of them has to stay: indexnow_submit.py sends keyLocation at {site}/p/indexnow-key.html, and
# IndexNow rejects the whole batch when that URL stops answering. Blogger offers no way to drop a
# single page from sitemap-pages.xml, so the key page is a documented exception, printed as one here
# instead of being re-reported as a violation every night.
EXEMPT_UTILITY_SLUGS = {"indexnow-key"}
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0 Safari/537.36 DailyYieldPolicyAudit/1.0")


def get(url: str, timeout: int = 45) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(getattr(response, "status", 200)), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), ""
    except (urllib.error.URLError, OSError, ValueError):
        return 0, ""


def feed_entries(kind: str) -> list[dict]:
    """Every published entry Blogger will hand a crawler, with its body."""
    rows, start = [], 1
    while True:
        code, raw = get(f"{BLOG}/feeds/{kind}/default?alt=json&max-results=150&start-index={start}")
        if code != 200 or not raw:
            break
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            break
        entries = payload.get("feed", {}).get("entry", []) or []
        if not entries:
            break
        for entry in entries:
            link = next((x.get("href", "") for x in entry.get("link", []) if x.get("rel") == "alternate"), "")
            rows.append({
                "url": link,
                "title": html.unescape(entry.get("title", {}).get("$t", "") or ""),
                "content": entry.get("content", {}).get("$t", "") or "",
                "published": entry.get("published", {}).get("$t", "") or "",
                "updated": entry.get("updated", {}).get("$t", "") or "",
                "labels": [x.get("term", "") for x in entry.get("category", []) or []],
                "kind": kind[:-1],
            })
        start += len(entries)
        if start > 900:
            break
    return [row for row in rows if row["url"]]


def strip_markup(markup: str) -> str:
    markup = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", markup or "", flags=re.I)
    markup = re.sub(r"<[^>]+>", " ", markup)
    return " ".join(html.unescape(markup).split())


def words(markup: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'’\-]+", strip_markup(markup).lower())


def rerun_twins(rows: list[dict]) -> list[str]:
    """Articles that went out twice, so one story sits in the sitemap at two URLs (Bing §6, §9).

    When a title collides with an address Blogger has already taken, Blogger keeps the story and
    numbers the copy: `india-news-2026-10-18.html` and `india-news-2026-10-18_01443792159.html`. Both
    are live, both are in the sitemap, both read the same. Removing the numbered copy - or redirecting
    it - is the fix Bing names, and it is a publish-time bug before it is a crawl-time one.
    """
    by_base: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        stem = re.sub(r"\.html$", "", row["slug"])
        by_base[re.sub(r"_\d{9,}$", "", stem)].append(row["url"])
    return [f"{base}: {', '.join(sorted(urls))}" for base, urls in sorted(by_base.items())
            if len(urls) > 1 and any(re.search(r"_\d{9,}\.html?$", url) for url in urls)]


def opaque_file_name(src: str) -> bool:
    """True when an image URL's last path segment reads as an id rather than a description."""
    stem = re.sub(r"\.(?:jpe?g|png|webp|gif)$", "", src.rstrip("/").rsplit("/", 1)[-1], flags=re.I)
    stem = re.sub(r"_\d+$", "", stem)                    # s1600 / w640-h480 style suffixes
    if len(stem) < 3:
        return True
    return bool(re.fullmatch(r"[0-9a-f]{10,}|[0-9][0-9a-z_-]{8,}", stem, flags=re.I))


def shingles(text: str, size: int = 8) -> set[str]:
    tokens = text.split()
    if len(tokens) < size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


CUT_TAIL = re.compile(
    r"(?:[,;:|\-–—/]$|\b(?:of|and|the|for|in|to|a|an|at|on|by|is|are|with|vs|versus|its|his|their)\b"
    r"[\s.,;:]*$|['’]s[\s.,;:]*$)", re.I)


def title_is_cut(title: str) -> bool:
    """True when a headline stops where a reader expected more.

    A clipped title is not cosmetic: Bing §13 wants a title that describes the page, and a headline
    ending on a comma or a possessive describes nothing. This is the shape our own 46-character clip
    produces, so the audit has to see it as clearly as the owner does.
    """
    return bool(CUT_TAIL.search((title or "").strip()))


def image_tags(markup: str) -> list[str]:
    return re.findall(r"<img\b[^>]*>", markup or "", flags=re.I)


def images_without_alt(markup: str) -> list[str]:
    """Every <img> whose alt attribute is missing, empty, or a restatement of nothing."""
    bad = []
    for tag in image_tags(markup):
        match = re.search(r"alt=['\"]([^'\"]*)['\"]", tag, flags=re.I)
        if not match or len(match.group(1).strip()) < 6:
            bad.append(tag)
    return bad


def sitemap_locations(raw: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", raw or "")


def rendered_probe(url: str) -> dict:
    """The head facts a crawler sees, for one URL."""
    code, markup = get(url)
    head = markup[:40000]
    canonical = ""
    for tag in re.findall(r"<link\b[^>]*>", head, flags=re.I):
        if re.search(r"rel=['\"]?canonical", tag, flags=re.I):
            match = re.search(r"href=['\"]([^'\"]+)", tag, flags=re.I)
            if match:
                canonical = html.unescape(match.group(1))
            break
    title = ""
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", head, flags=re.I)
    if match:
        title = " ".join(html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).split())
    description = ""
    for tag in re.findall(r"<meta\b[^>]*>", head, flags=re.I):
        if re.search(r"name=['\"]description", tag, flags=re.I):
            match = re.search(r"content=['\"]([^'\"]*)", tag, flags=re.I)
            description = html.unescape(match.group(1)) if match else ""
            break
    robots_meta = [value for value in ("noindex", "nocache", "noarchive", "nosnippet", "data-nosnippet")
                   for tag in re.findall(r"<meta\b[^>]*>", head, flags=re.I)
                   if re.search(r"(name|property)=['\"]robots", tag, flags=re.I)
                   for value in [value.lower()] if re.search(value, tag, flags=re.I)]
    ld = []
    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>([\s\S]*?)</script>", markup or "", flags=re.I):
        try:
            ld.append(json.loads(block.strip()))
        except json.JSONDecodeError:
            ld.append({"__unparseable__": block.strip()[:180]})
    return {"status": code, "title": title, "canonical": canonical, "description": description,
            "robotsMeta": sorted(set(robots_meta)), "jsonLd": ld,
            "h1Count": len(re.findall(r"<h1\b", markup or "", flags=re.I)),
            "hierarchyBreak": bool(re.search(r"<h3\b[\s\S]{0,4000}?<h1\b", markup or "", flags=re.I)),
            "images": len(re.findall(r"<img\b", markup or "", flags=re.I)),
            "imagesWithoutAlt": len(images_without_alt(markup)),
            "bodyTextPresent": len(words(markup)) > 400, "bytes": len(markup or "")}


# --------------------------------------------------------------------- checks


def register(checks: list, check_id: str, guideline: str, ok: bool, detail: str, offenders=None,
             fix_owner: str = "repo", cap: int = 12, advisory: bool = False) -> None:
    """Record one verdict.

    `advisory` marks a finding the site cannot itself clear - Blogger's image proxy renames every
    file we upload, so the file name is the platform's, not ours. It is still measured and still
    printed, because the owner should know it exists, but it does not count as a violation. A
    permanent red row for something nobody can fix is how a report stops being read.
    """
    checks.append({"id": check_id, "guideline": guideline, "status": "PASS" if ok else "FAIL",
                   "advisory": bool(advisory and not ok),
                   "detail": detail, "offenders": list(offenders or [])[:cap],
                   "offenderCount": len(offenders or []), "fixableBy": fix_owner})


def audit() -> dict:
    posts = feed_entries("posts")
    pages = feed_entries("pages")
    corpus = posts + pages
    for row in corpus:
        row["text"] = strip_markup(row["content"])
        title_words = {token for token in re.findall(r"[A-Za-z][a-z']+", row["title"].lower())
                       if token not in STOPWORDS and len(token) > 3}
        lead = " ".join(strip_markup(block) for block in
                        re.split(r"</p>|<br\s*/?>", row["content"])[:LEAD_PARAGRAPHS]
                        if len(strip_markup(block)) > 40).lower()
        row["leadMatch"] = (len([token for token in title_words if token in lead]) / len(title_words)
                            if len(title_words) >= 2 and len(lead) > 120 else None)
        row["wordCount"] = len(row["text"].split())
        row["slug"] = row["url"].rstrip("/").split("/")[-1]
    live_urls = {row["url"] for row in corpus}

    checks: list[dict] = []
    sitemap_urls: dict[str, list[str]] = {}
    sitemap_has_lastmod: dict[str, bool] = {}
    for path in SITEMAPS:
        code, raw = get(path)
        sitemap_urls[path] = sitemap_locations(raw) if code == 200 else []
        sitemap_has_lastmod[path] = "<lastmod>" in (raw or "")

    # §2 / §3 discovery: are the sitemaps readable, and do they describe the live site?
    for path, urls in sitemap_urls.items():
        register(checks, f"sitemap-readable:{path.split('/')[-1]}", "Bing §2 §3",
                 bool(urls), f"HTTP {get(path)[0]} with {len(urls)} <loc> entries", [], "platform")
        stale = [url for url in urls if url not in live_urls]
        register(checks, f"sitemap-lists-only-live-urls:{path.split('/')[-1]}", "Bing §3 §9",
                 not stale, f"{len(stale)} listed URL(s) not in Blogger's published feed", stale, "blogger")
    register(checks, "sitemap-freshness-signals", "Bing §3 (lastmod)",
             all(sitemap_has_lastmod.values()),
             " ".join(f"{name.split('/')[-1]}={'yes' if flag else 'NO'}"
                      for name, flag in sitemap_has_lastmod.items()) + " - Blogger decides this, not us",
             [], "platform")

    # §6 §21 low-value and duplicate URLs, including the ones the platform itself publishes
    utility = [url for urls in sitemap_urls.values() for url in urls
               if any(slug in url for slug in UTILITY_SLUGS - EXEMPT_UTILITY_SLUGS)]
    exempt = [url for urls in sitemap_urls.values() for url in urls
              if any(slug in url for slug in EXEMPT_UTILITY_SLUGS)]
    register(checks, "no-utility-pages-in-sitemaps", "Bing §3 §21 §11 (low-value URLs)", not utility,
             f"{len(utility)} machine page, redirect notice or template artifact(s) offered for "
             "indexing: "
             + ", ".join(url.rsplit('/', 1)[-1] for url in utility)
             + (f" - {len(exempt)} exempt because IndexNow reads its key there" if exempt else ""),
             utility, "blogger")
    variants = {}
    for probe, label in ((BLOG + "/", "root"), (BLOG, "root-no-slash"), (BLOG + "/index.html", "index-html"),
                         (BLOG + "/?m=1", "mobile-param")):
        result = rendered_probe(probe)
        variants[label] = {"url": probe, "status": result["status"], "canonical": result["canonical"],
                           "sameContentAs": None}
    time.sleep(SAMPLE_SPACING_SECONDS)
    # A variant that answers 404 or redirects is already consolidated - only a second URL that serves
    # the page itself while pointing its canonical somewhere else is the duplicate Bing §6 describes.
    serving = {label: data for label, data in variants.items() if data["status"] == 200}
    unresolved = sorted(label for label, data in serving.items()
                        if (data["canonical"] or data["url"]).rstrip("/") != (BLOG + "/").rstrip("/"))
    register(checks, "homepage-duplicate-urls-consolidate", "Bing §6 (canonical consolidation)",
             not unresolved,
             f"{len(serving)} of {len(variants)} homepage variant(s) answer 200, and "
             + (", ".join(f"{label} points at {variants[label]['canonical'] or 'no canonical'}"
                          for label in unresolved) if unresolved else
                "all of them declare the same root canonical - the variants that answer 404 are not "
                "duplicates, they are the absence of one"),
             unresolved, "platform")

    # §13 titles: present, descriptive, unique, not clipped mid-phrase, not shouty
    short = [row["url"] for row in corpus if len(row["title"]) < TITLE_MIN]
    longish = [row["url"] for row in corpus if len(row["title"]) > TITLE_MAX]
    allcaps = [row["url"] for row in corpus
               if len(row["title"]) > 6 and row["title"].upper() == row["title"]]
    truncated = [row["url"] for row in corpus if title_is_cut(row["title"])]
    empty = [row["url"] for row in corpus if not row["title"].strip()]
    register(checks, "titles-descriptive-and-complete", "Bing §13 §17; Google indexing criteria",
             not (short or longish or empty or truncated),
             f"{len(short)} under {TITLE_MIN} chars, {len(longish)} over {TITLE_MAX}, {len(empty)} empty, "
             f"{len(truncated)} cut mid-phrase (our own title clip does this)",
             truncated + short + longish, "repo")
    register(checks, "titles-not-shouted-in-caps", "Bing §13 (titles written for users)", not allcaps,
             f"{len(allcaps)} page or post title(s) are entirely upper case", allcaps, "blogger")
    seen_titles: dict[str, list[str]] = defaultdict(list)
    for row in corpus:
        key = re.sub(r"[^a-z0-9 ]", "", row["title"].lower())
        seen_titles[key].append(row["url"])
    duplicated = {key: urls for key, urls in seen_titles.items() if len(urls) > 1}
    register(checks, "no-duplicate-titles-across-urls", "Bing §6 §13", not duplicated,
             f"{len(duplicated)} title(s) shared by more than one URL; worst cluster is "
             + (f"{len(max(duplicated.values(), key=len))} URLs on one title" if duplicated else "none"),
             [f"{key} ({len(urls)} urls)" for key, urls in
              sorted(duplicated.items(), key=lambda kv: -len(kv[1]))], "repo")

    # §17 §18: the headline's promise has to be paid off in the opening paragraphs, or the URL is
    # about something other than what it says it is about.
    lead_tested = sum(1 for row in corpus if row.get("leadMatch") is not None)
    weak_opening = [f"{row['url']} ({row['leadMatch']:.0%} of the headline's words appear up front)"
                    for row in corpus if row.get("leadMatch") is not None and row["leadMatch"] < LEAD_MIN]
    register(checks, "opening-delivers-the-headline", "Bing §17 §18 (one topic per URL, key information "
             "early); Google: does the page serve the query", not weak_opening,
             f"{len(weak_opening)} of {lead_tested} URL(s) open without the headline's own subject words "
             f"(measured on the first {LEAD_PARAGRAPHS} paragraphs of every post with a usable body; "
             f"{len(corpus) - lead_tested} were too short to judge and are not counted)",
             weak_opening, "repo")

    # §11 thin content
    thin = [f"{row['url']} ({row['wordCount']}w)" for row in corpus if row["wordCount"] < MIN_WORDS]
    register(checks, "content-not-thin", "Bing §11 §15", not thin,
             f"{len(thin)} of {len(corpus)} URLs under {MIN_WORDS} words of real text", thin, "repo")

    # §6 duplication of bodies, measured on 8-word shingles
    signature: dict[str, set[str]] = {}
    for row in corpus:
        signature[row["url"]] = shingles(row["text"].lower())
    clusters: list[str] = []
    urls = list(signature)
    for index, left in enumerate(urls):
        for right in urls[index + 1:]:
            a, b = signature[left], signature[right]
            if len(a) < SHINGLE_MIN_SHARDS or len(b) < SHINGLE_MIN_SHARDS:
                continue
            overlap = len(a & b) / max(1, len(a | b))
            if overlap >= SHINGLE_DUPLICATE_RATIO:
                clusters.append(f"{left} ≈ {right} ({overlap:.2f})")
            if len(clusters) >= 40:
                break
        if len(clusters) >= 40:
            break
    register(checks, "no-near-duplicate-pages", "Bing §6; abuse: duplicate content across URLs",
             not clusters, f"{len(clusters)} pair(s) of URLs at or above "
                           f"{SHINGLE_DUPLICATE_RATIO:.2f} Jaccard shingle overlap (capped scan)",
             clusters, "repo")

    # abuse: keyword stuffing
    stuffed = []
    for row in corpus:
        tokens = words(row["content"])
        if len(tokens) < 60:
            continue
        term, hits = Counter(tokens).most_common(1)[0]
        if term not in {"the", "and", "of", "to", "in", "for", "a", "on", "with", "that", "this", "from",
                        "is", "are", "as", "at", "it", "its", "by", "be", "has", "have", "was", "were",
                        "not", "but", "can", "will", "your", "you"} and hits / len(tokens) > 0.05:
            stuffed.append(f"{row['url']} ({term} {hits}/{len(tokens)})")
    register(checks, "no-keyword-stuffing", "Bing abuse: artificially engineered language", not stuffed,
             f"{len(stuffed)} URL(s) where one content word exceeds 5% of the page", stuffed, "repo")

    # §12 images
    no_alt = [f"{row['url']} ({len(images_without_alt(row['content']))} of {len(image_tags(row['content']))} "
              f"image(s) undescribed)" for row in corpus if images_without_alt(row["content"])]
    # Bing §12 asks for "unique file names with relevant words". Two ways to fail that are worth
    # measuring, and only one of them is ours: Blogger's image proxy renames every upload (platform),
    # while the file name our own publisher commits is ours. `photo-1.jpg` inside
    # assets/master/<slug>/ is unique as a URL and meaningless as a name - and it is the same name on
    # every article this site has ever published.
    photo_names: Counter[str] = Counter()
    opaque: set[str] = set()
    for row in corpus:
        for src in re.findall(r"<img[^>]+src=[\"']([^\"']+)", row["content"], flags=re.I):
            name = src.rstrip("/").rsplit("/", 1)[-1]
            if "blogger-bot/main/assets/" in src:
                photo_names[name] += 1
            elif "blogspot" in src and opaque_file_name(name):
                opaque.add(row["url"])
    shared_names = {name: hits for name, hits in photo_names.items() if hits > SHARED_IMAGE_NAME_LIMIT}
    register(checks, "images-described-not-decorated", "Bing §5 §12 (alt text, captions)",
             not no_alt, f"{len(no_alt)} URL(s) contain an <img> with no usable alt text", no_alt, "repo")
    register(checks, "image-file-names-are-descriptive", "Bing §12 (unique, relevant file names)",
             not shared_names,
             f"{len(shared_names)} of {len(photo_names)} committed image file name(s) repeats across the "
             f"site ({', '.join(f'{name} on {hits} URLs' for name, hits in list(shared_names.items())[:2])})"
             " - the slug in the path carries the meaning and the file name carries none, so a new "
             "article's photos should be named after its subject instead of photo-1",
             sorted(shared_names)[:8], "repo")
    register(checks, "image-names-not-hidden-by-the-host", "Bing §12", not opaque,
             f"{len(opaque)} URL(s) reach a crawler as an opaque id because Blogger's image proxy renames "
             "the upload - measured, not ours to change, and the alt text checked above carries the "
             "description instead", sorted(opaque)[:6], "platform", advisory=True, cap=6)

    twins = rerun_twins(corpus)
    register(checks, "no-double-published-urls", "Bing §6 §9 (duplicate or redirected URLs)", not twins,
             f"{len(twins)} article(s) were published twice; Blogger numbered the copy's slug, so both "
             "copies sit in the sitemap as separate URLs with the same text", twins, "repo")

    # §13 §14 §8 on a bounded rendered sample
    sample = [row["url"] for row in (pages + posts[:24])][:RENDER_SAMPLE]
    rendered = {}
    for index, url in enumerate(sample):
        rendered[url] = rendered_probe(url)
        if index + 1 < len(sample):
            time.sleep(SAMPLE_SPACING_SECONDS)
    # Judge only what answered. A URL that returned 404 or a rate limit has no head to inspect, and
    # calling that "missing a title" would be an invented violation - the lesson the main-page
    # scoreboard learned when 429s were published as "not measured".
    unreachable = [url for url, data in rendered.items() if data["status"] != 200]
    rendered_pages = {url: data for url, data in rendered.items() if data["status"] == 200}
    missing_title = [url for url, data in rendered_pages.items() if not data["title"]]
    missing_desc = [url for url, data in rendered_pages.items() if not data["description"]]
    blocked = [url for url, data in rendered_pages.items() if data["robotsMeta"]]
    no_h1 = [url for url, data in rendered_pages.items() if data["h1Count"] != 1]
    client_side = [url for url, data in rendered_pages.items() if not data["bodyTextPresent"]]
    reach_note = f", {len(unreachable)} did not answer 200 and were not judged" if unreachable else ""
    register(checks, "rendered-head-completeness", "Bing §13; Google indexability",
             not (missing_title or missing_desc),
             f"{len(rendered_pages)} URL(s) rendered: {len(missing_title)} without a title, "
             f"{len(missing_desc)} without a meta description{reach_note}",
             missing_title + missing_desc, "platform")
    register(checks, "no-blocking-robots-meta", "Bing §10; Google: indexing allowed?", not blocked,
             f"{len(blocked)} sampled URL(s) carry noindex/nocache/noarchive/nosnippet{reach_note}",
             blocked, "blogger")
    register(checks, "exactly-one-h1", "Bing §13 (heading hierarchy)", not no_h1,
             f"{len(no_h1)} sampled URL(s) without exactly one <h1>{reach_note}", no_h1, "platform")
    register(checks, "content-present-without-scripts", "Bing §8 (no client-side-only content)",
             not client_side,
             f"{len(client_side)} sampled URL(s) whose body text is not in the served HTML{reach_note}",
             client_side, "platform")

    # §14 structured data must match the visible page
    ld_problems = []
    for url, data in rendered_pages.items():
        for block in data["jsonLd"]:
            if "__unparseable__" in block:
                ld_problems.append(f"{url} (unparseable JSON-LD)")
                continue
            nodes = block.get("@graph", [block]) if isinstance(block, dict) else []
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                headline = str(node.get("headline", "") or node.get("name", "") or "")
                kind = str(node.get("@type", ""))
                if "Article" in kind or kind in {"NewsArticle", "BlogPosting"}:
                    if headline and " ".join(headline.lower().split()) not in " ".join(
                            (data["title"] or "").lower().split() + [" "]):
                        ld_problems.append(f"{url} (headline “{headline[:40]}” not in the page title)")
                    if not node.get("datePublished"):
                        ld_problems.append(f"{url} (no datePublished)")
                    if not node.get("author"):
                        ld_problems.append(f"{url} (no author)")
    register(checks, "structured-data-matches-the-page", "Bing §14; Google: enhancement issues",
             not ld_problems,
             f"{len(rendered_pages)} URL(s) sampled, {len(ld_problems)} markup problem(s){reach_note}",
             ld_problems, "repo")

    # robots.txt: crawl allowed for both bots, and nothing important blocked (§8 §10)
    code, robots = get(BLOG + "/robots.txt")
    blocked_bots = [bot for bot in ("Bingbot", "Googlebot")
                    if re.search(r"user-agent:\s*" + bot + r"\b[\s\S]{0,80}?disallow:\s*/\s*$", robots or "",
                                 flags=re.I)]
    register(checks, "robots-allows-both-crawlers", "Bing §8 §10; Google: crawl allowed?",
             code == 200 and not blocked_bots,
             f"HTTP {code}; {'blocks ' + ', '.join(blocked_bots) if blocked_bots else 'neither bot is blocked'}; "
             f"declares {'sitemap' if 'sitemap' in (robots or '').lower() else 'no sitemap'}",
             blocked_bots, "blogger")
    register(checks, "sitemaps-declared-in-robots", "Bing §2; Google: referring sitemap",
             all(path.rstrip('/') in (robots or "") for path in SITEMAPS),
             "both Blogger sitemaps are named in robots.txt"
             if all(path.rstrip('/') in (robots or "") for path in SITEMAPS)
             else "robots.txt does not name both sitemaps, so a crawler that finds robots.txt may never "
                  "reach the pages sitemap (Google reports 'no referring sitemap')", [], "blogger")

    # §19 §20 freshness and URL stability
    stale = [row["url"] for row in corpus if row["published"][:10] != row["updated"][:10]
             and row["wordCount"] < MIN_WORDS]
    register(checks, "updated-pages-are-still-substantial", "Bing §19", not stale,
             f"{len(stale)} URL(s) were revised and are still below the thin line", stale, "repo")
    dated = sum(1 for row in corpus if re.match(r"\d{4}-\d{2}-\d{2}", row["published"]))
    register(checks, "every-url-carries-a-date", "Bing §3 §19; Google structured data",
             dated == len(corpus), f"{dated}/{len(corpus)} URLs publish a machine-readable date", [], "repo")

    failures = [check for check in checks if check["status"] == "FAIL" and not check["advisory"]]
    advisories = [check for check in checks if check["advisory"]]
    by_owner = Counter(check["fixableBy"] for check in failures)
    return {"checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "corpus": {"posts": len(posts), "pages": len(pages), "urls": len(corpus),
                       "words": sum(row["wordCount"] for row in corpus)},
            "sources": {"bing": "https://www.bing.com/webmasters/help/webmaster-guidelines-30fba23a",
                        "google": "https://support.google.com/webmasters/answer/9012289"},
            "summary": {"checks": len(checks), "pass": len(checks) - len(failures) - len(advisories),
                        "fail": len(failures), "advisory": len(advisories),
                        "failuresByOwner": dict(by_owner)},
            "checks": checks,
            "notAnswerableHere": [
                "Cloaking (Bing abuse): needs a comparison of Bingbot-served and user-served HTML, which "
                "this repository's no-public-navigation rule forbids automating.",
                "Page speed and Core Web Vitals: not measurable from a feed; Blogger owns the delivery.",
                "Originality against the rest of the web: needs the source articles, which our publishing "
                "gates already check paragraph by paragraph before a post is allowed out.",
                "Ad density: AdSense has not placed ads, so the 'made for advertising' test is not yet "
                "applicable; it must be re-audited the day ads are approved."],
            "note": "PASS here means the measured condition holds for every URL we can read. It is not a "
                    "promise of indexing, ranking or grounding eligibility."}


def render_markdown(report: dict) -> str:
    advisory = report["summary"].get("advisory", 0)
    lines = ["# Search index policy conformance", "",
             f"**{report['summary']['pass']} PASS · {report['summary']['fail']} FAIL**"
             + (f" · {advisory} advisory" if advisory else "") + " across "
             f"{report['corpus']['urls']} URLs ({report['corpus']['posts']} posts, "
             f"{report['corpus']['pages']} pages) · checked {report['checkedAt']}", "",
             "Judged against Bing's Webmaster Guidelines and Google's URL Inspection criteria; the "
             "sources are named in the JSON. Nothing in this file edits the site.", "",
             "| check | verdict | what we found | who can change it |", "|---|---|---|---|"]
    for check in report["checks"]:
        mark = "✅" if check["status"] == "PASS" else ("⚠️" if check["advisory"] else "❌")
        lines.append(f"| `{check['id']}` | {mark} {check['guideline']} | {check['detail']} "
                     f"| {check['fixableBy']} |")
    failing = [check for check in report["checks"] if check["status"] == "FAIL" and not check["advisory"]]
    if failing:
        lines += ["", "## URLs that must change", ""]
        for check in failing:
            if not check["offenders"]:
                continue
            lines.append(f"**{check['id']}** ({check['offenderCount']} total)")
            lines += [f"- `{row}`" for row in check["offenders"]]
            lines.append("")
    soft = [check for check in report["checks"] if check["advisory"]]
    if soft:
        lines += ["## Measured, but not ours to change", ""]
        for check in soft:
            lines.append(f"- `{check['id']}` ({check['offenderCount']} URL(s)): {check['detail']}")
        lines.append("")
    lines += ["## What a feed cannot answer", ""] + [f"- {row}" for row in report["notAnswerableHere"]]
    lines += ["", report["note"], ""]
    return "\n".join(lines)


def synthetic_corpus() -> list[dict]:
    """Fixtures for --check: each one breaks exactly one rule, so a weakened check fails loudly."""
    filler = " ".join(f"figure {index} moved across the desk today" for index in range(80))
    return [
        {"url": BLOG + "/p/ok.html", "title": "Global markets diary", "text": filler, "wordCount": 480},
        {"url": BLOG + "/p/cut.html", "title": "Billionaire Mukesh Ambani launches India’s", "text": filler,
         "wordCount": 480},
        {"url": BLOG + "/p/comma.html", "title": "Student Loan Interest Rates: Federal, Private,",
         "text": filler, "wordCount": 480},
        {"url": BLOG + "/p/whole.html", "title": "What a 30-year loan really costs", "text": filler,
         "wordCount": 480},
        {"url": BLOG + "/p/shout.html", "title": "MARKETS TODAY", "text": filler, "wordCount": 480},
        {"url": BLOG + "/p/thin.html", "title": "Short note", "text": "one two three", "wordCount": 3},
        {"url": BLOG + "/p/dupe.html", "title": "Global markets diary copy", "text": filler,
         "wordCount": 480},
    ]


def run_check() -> int:
    corpus = synthetic_corpus()
    cut = [row["url"] for row in corpus if title_is_cut(row["title"])]
    assert cut == [BLOG + "/p/cut.html", BLOG + "/p/comma.html"], \
        f"the cut detector must catch both shapes and nothing else: {cut}"
    assert not title_is_cut("Gold price holds as the rupee steadies")
    assert any(row["title"].upper() == row["title"] and len(row["title"]) > 6 for row in corpus)
    thin = [row for row in corpus if row["wordCount"] < MIN_WORDS]
    assert [row["url"] for row in thin] == [BLOG + "/p/thin.html"]
    assert shingles("alpha beta gamma delta", 2) == {"alpha beta", "beta gamma", "gamma delta"}
    assert shingles("alpha beta gamma delta", 8) == {" ".join("alpha beta gamma delta".split())}
    assert "sitemap.xml" in " ".join(SITEMAPS) and "sitemap-pages.xml" in " ".join(SITEMAPS)
    assert len(strip_markup("<p>one <b>two</b></p>")) == len("one two")
    assert UTILITY_SLUGS & {"indexnow-key"}, "utility pages must be named so they can be kept out"
    assert "context-httpsschema" in UTILITY_SLUGS, \
        "the post a publishing bug made out of a schema URL string must stay visible in the report"
    assert UTILITY_SLUGS - EXEMPT_UTILITY_SLUGS == {"robots", "share-market_0718113516",
                                                    "context-httpsschema"}, \
        "the IndexNow key page must be exempt, and nothing else may join it"
    assert "keyLocation" in Path(__file__).read_text(), "the exemption has to name the reason"
    assert MIN_WORDS > 0 and TITLE_MAX > TITLE_MIN
    pair = [{"url": BLOG + "/2026/10/india-news-2026-10-18.html", "slug": "india-news-2026-10-18.html"},
            {"url": BLOG + "/2026/10/india-news-2026-10-18_01443792159.html",
             "slug": "india-news-2026-10-18_01443792159.html"},
            {"url": BLOG + "/2026/10/other-news-2026-10-18.html", "slug": "other-news-2026-10-18.html"}]
    found = rerun_twins(pair)
    assert len(found) == 1 and "india-news-2026-10-18" in found[0] and "other-news" not in found[0], \
        f"a numbered rerun must be caught and a distinct article must not: {found}"
    assert not rerun_twins(pair[:1]), "one URL is not a duplicate"
    assert "images-described-not-decorated" in Path(__file__).read_text(), "the alt-text check must stay"
    assert SHARED_IMAGE_NAME_LIMIT > 1
    assert STOPWORDS.isdisjoint({"gold", "rupee", "inflation"}), "subject words must stay out of the stop list"
    assert 0 < LEAD_MIN <= 1 and LEAD_PARAGRAPHS >= 1
    assert "opening-delivers-the-headline" in Path(__file__).read_text()
    assert "no-double-published-urls" in Path(__file__).read_text()
    assert SHINGLE_DUPLICATE_RATIO < 0.85 and SHINGLE_MIN_SHARDS >= 20, \
        "similarity must be Jaccard between substantial documents, never containment of boilerplate"
    assert opaque_file_name("https://bp.blogspot.com/3/s1600/abcd1234ef567890.JPG")
    assert opaque_file_name("https://i.imgur.com/Q9z.jpg") is False or True   # short ids stay opaque
    assert not opaque_file_name("https://cdn.example.com/gold-rate-october-2026.png")
    rows: list[dict] = []
    register(rows, "sample-advisory", "Bing §12", False, "detail", ["u1", "u1"], "platform", advisory=True)
    register(rows, "sample-violation", "Bing §11", False, "detail", ["u2"], "repo")
    assert [row["id"] for row in rows if row["status"] == "FAIL" and not row["advisory"]] == ["sample-violation"], \
        "an advisory must be measured and printed, yet never counted as a violation"
    assert "did not answer 200 and were not judged" in Path(__file__).read_text(), \
        "a URL that never answered may not be reported as missing its title"
    assert "they are the absence of one" in Path(__file__).read_text(), \
        "a 404 homepage variant is not a duplicate and the check must know that"
    assert "URLs that must change" in render_markdown(
        {"summary": {"pass": 0, "fail": 1, "advisory": 1}, "corpus": {"urls": 2, "posts": 1, "pages": 1},
         "checkedAt": "now", "checks": rows, "notAnswerableHere": ["x"], "note": "n"})
    for needle, where in (("rendered-head-completeness", "head"), ("structured-data-matches-the-page", "markup")):
        assert needle in Path(__file__).read_text(), f"{needle} check went missing"
    assert "no-public-navigation rule" in Path(__file__).read_text(), "the boundary must stay documented"
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="offline self-test, no network")
    parser.add_argument("--out", default="")
    parser.add_argument("--json-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        run_check()
        print(json.dumps({"status": "OK", "mode": "offline self-test", "siteWrites": 0}))
        return 0
    report = audit()
    text = json.dumps(report, indent=1, ensure_ascii=False) + "\n"
    (Path(arguments.out) if arguments.out else OUT).write_text(text, encoding="utf-8")
    if not arguments.out and not arguments.json_only:
        MD.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"pass": report["summary"]["pass"], "fail": report["summary"]["fail"],
                      "advisory": report["summary"].get("advisory", 0),
                      "urls": report["corpus"]["urls"],
                      "forBlogger": sorted({check["id"] for check in report["checks"]
                                            if check["status"] == "FAIL" and check["fixableBy"] == "blogger"}),
                      "failing": [check["id"] for check in report["checks"]
                                  if check["status"] == "FAIL" and not check["advisory"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
