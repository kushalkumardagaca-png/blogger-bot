#!/usr/bin/env python3
"""Check what Google News and Discover will actually see, by asking the public site.

Publisher Center does not read the repository - it reads the feed and the pages. So this job
looks at exactly those two things the way their reviewers do, and turns the result into a list of
gaps with the number of affected URLs beside each one. It changes nothing: no request is made to
Google, no post is written, no theme is touched.

Why it matters for the 50,000-readers-a-day target: a blog with one indexed page cannot earn
crawl trust by publishing more, but a source accepted into Google News and Discover is fetched on
its own schedule and shown to people who never searched for it. That is the largest free step left.
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "GOOGLE_NEWS_READINESS.json"
MD = ROOT / "GOOGLE_NEWS_READINESS.md"
FEED = "https://dailyyield.blogspot.com/feeds/posts/default?alt=rss&max-results=25"
UA = {"User-Agent": "Mozilla/5.0 (Daily Yield readiness self-check)"}

GAPS = {
    "truncatedHeadline": "headline ends on a fragment - a headline is what a News reader decides on",
    "headlineTooLong": "headline is over 110 characters and will be cut in the listing",
    "headlineTooShort": "headline is under 20 characters and says nothing",
    "stalePubDate": "no pubDate in the feed entry, so the item cannot be dated",
    "noDescription": "the feed entry carries no summary, so the listing has nothing to show",
    "noAuthor": "no author on the entry - Publisher Center wants a byline for the publication",
    "noCategory": "no label on the entry - labels are how sections are mapped in Publisher Center",
    "nonCanonicalLink": "the feed link is not the clean https URL of the post",
    "noOpenGraphImage": "the page has no og:image, so News and Discover have no picture to show",
    "noHeadDescription": "the page has no meta description in the head, so Google writes its own snippet",
    "titleMismatch": "the page title and the feed title disagree",
}


def fetch(url: str, limit: int = 4_000_000) -> str:
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read(limit).decode("utf-8", "ignore")


def strip(value: str) -> str:
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def headline_is_cut(title: str) -> bool:
    text = strip(title)
    if not text:
        return False
    if text.endswith("…") or text.endswith("..."):
        return True
    if 43 <= len(text) <= 47 and not re.search(r"[.?!:]$", text):
        return True
    return bool(re.search(r"[A-Za-z]-[A-Za-z]{1,2}$", text))


def check_feed(xml: str) -> tuple[list[dict], dict]:
    items = re.findall(r"<item>(.*?)</item>", xml, re.S)
    rows = []
    for raw in items:
        grab = lambda tag: (re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", raw, re.S) or [None, ""])[1]
        title = strip(grab("title"))
        link = grab("link").strip()
        pub = grab("pubDate").strip()
        desc = strip(grab("description"))
        categories = re.findall(r"<category[^>]*>(.*?)</category>", raw, re.S)
        author = strip(grab("author"))
        issues = []
        if headline_is_cut(title):
            issues.append("truncatedHeadline")
        if len(title) > 110:
            issues.append("headlineTooLong")
        if len(title) < 20:
            issues.append("headlineTooShort")
        if not pub:
            issues.append("stalePubDate")
        if len(desc) < 40:
            issues.append("noDescription")
        if not author:
            issues.append("noAuthor")
        if not categories:
            issues.append("noCategory")
        if not re.match(r"^https://dailyyield\.blogspot\.com/(20|p/)[^\?]*\.html$", link):
            issues.append("nonCanonicalLink")
        rows.append({"title": title[:90], "url": link, "published": pub[:31],
                     "labels": len(categories), "issues": issues})
    summary = {"feedItems": len(items), "itemsWithIssues": sum(1 for row in rows if row["issues"]),
               "issueCounts": {key: sum(1 for row in rows if key in row["issues"]) for key in GAPS
                               if any(key in row["issues"] for row in rows)}}
    return rows, summary


def check_pages(urls: list[str], read, limit: int = 6) -> list[dict]:
    """Look at the pages themselves. ``read`` is what makes this testable offline."""
    rows = []
    for index, url in enumerate(urls[:limit], start=1):
        page = read(f"page-{index}.html", url)
        if page is None:      # a fixture that only holds one page is not a site with one page
            continue
        row = {"url": url, "issues": []}
        if not page.strip():
            row["issues"].append("pageUnreadable")
            rows.append(row)
            continue
        if not re.search(r'property=["\']og:image["\'][^>]*content=["\']https?://', page, re.I):
            row["issues"].append("noOpenGraphImage")
        head = page[:page.lower().find("<body") if "<body" in page.lower() else 20000]
        if not re.search(r'name=["\']description["\'][^>]*content=["\'][^"\']{30,}', head, re.I):
            row["issues"].append("noHeadDescription")
        page_title = strip((re.search(r"<title>(.*?)</title>", page, re.S) or [None, ""])[1])
        row["pageTitle"] = page_title[:90]
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", default="", help="directory with feed.xml and page-1.html, for tests")
    arguments = parser.parse_args()
    fixture = Path(arguments.fixture_dir) if arguments.fixture_dir else None

    def read(name: str, live_url: str) -> str | None:
        if fixture:
            path = fixture / name
            return path.read_text(encoding="utf-8") if path.exists() else None
        try:
            return fetch(live_url)
        except Exception as exc:  # noqa: BLE001
            print(f"could not read {live_url}: {exc}", file=sys.stderr)
            return ""

    xml = read("feed.xml", FEED) or ""
    if not xml.strip():
        report = {"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "status": "FEED_UNREADABLE", "note": "the public feed could not be fetched from this "
                                                        "network; nothing is assumed, no gap count is "
                                                        "reported as zero", "feed": {}, "pages": []}
    else:
        rows, feed_summary = check_feed(xml)
        pages = check_pages([row["url"] for row in rows if row["url"]], read)
        page_issues = {key: sum(1 for row in pages if key in row["issues"]) for key in GAPS
                       if any(key in row["issues"] for row in pages)}
        report = {"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "status": "MEASURED", "feedUrl": FEED, "feed": feed_summary,
                  "pages": pages, "pageIssueCounts": page_issues,
                  "items": rows[:12],
                  "blockersForPublisherCenter": [
                      {"gap": key, "meaning": GAPS.get(key, "seen on the page itself"), "urls": count}
                      for key, count in {**feed_summary["issueCounts"], **page_issues}.items()],
                  "policy": "read-only: this job asks the public feed and the public pages, and writes "
                            "nothing to Google, Blogger or the theme"}
        OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

    lines = [f"# Google News and Discover readiness · {report['checkedAt']}", ""]
    if report["status"] != "MEASURED":
        lines += [f"Status: **{report['status']}**", "", report["note"]]
    else:
        feed = report["feed"]
        lines += [f"- feed entries read: **{feed['feedItems']}**, of which **{feed['itemsWithIssues']}** "
                  f"have at least one listing defect",
                  f"- pages inspected: **{len(report['pages'])}**", ""]
        counts = {**feed.get("issueCounts", {}), **report.get("pageIssueCounts", {})}
        if counts:
            lines += ["| what is wrong | how many | why it matters |", "| --- | --- | --- |"]
            for key, count in sorted(counts.items(), key=lambda row: -row[1]):
                lines.append(f"| {key} | {count} | {GAPS.get(key, 'reported by the page itself')} |")
        else:
            lines.append("No listing defects found in what was inspected.")
        lines += ["", "## What to do with this", "",
                  "1. Fix the entries in this repository's own hands first - a headline that ends on a "
                  "fragment is a bug we publish, not a Google decision (headline_repair.py already works "
                  "through the backlog nightly).",
                  "2. Then submit the feed to Publisher Center with the section mapping the labels give us.",
                  "3. Then re-run this file: the gap counts should fall, and that is the proof - not a green "
                  "tick in Actions."]
    MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": report["status"],
                      "feedItems": (report.get("feed") or {}).get("feedItems"),
                      "itemsWithIssues": (report.get("feed") or {}).get("itemsWithIssues"),
                      "blockers": len(report.get("blockersForPublisherCenter") or [])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
