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
# the limit this blog imposes on its own titles, read from the file that imposes it, so this report
# cannot quietly disagree with the writer
from seo_hygiene import MAX_TITLE_CHARS as CAP

GAPS = {
    "truncatedHeadline": "headline ends on a fragment - a headline is what a News reader decides on",
    "clippedByOurTitleCap": f"headline stops exactly at this blog's own {CAP}-character title limit: "
                            "the limit, not Google, is what shortens it",
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


# A headline that stops on a word which cannot end a sentence is unfinished, whatever its length.
# This list is deliberately small: it holds only words that need something after them.
DANGLING_END = re.compile(
    r"\b(and|or|nor|but|yet|so|the|a|an|of|to|in|on|at|by|for|from|with|without|within|is|are|was|were|"
    r"be|been|being|has|have|had|will|would|can|could|may|might|shall|should|as|if|than|then|that|this|"
    r"which|who|whose|how|when|where|why|what|into|onto|over|under|between|including|excluding|despite|"
    r"while|after|before|during|since|per|via|versus|vs|says|say|said|according|like|unlike|more|less|"
    r"most|its|it|not|about|against|toward|towards|up|down|out|off|both|each|either|neither|another)\b"
    r"[.,;:\-\u2013\u2014]?\s*$", re.I)
TRAILING_PUNCTUATION = re.compile(r"[,;:\-\u2013\u2014]$")
POSSESSIVE_END = re.compile(r"('s|’s)$")
def headline_is_cut(title: str) -> bool:
    """Whether a headline reads as though something was chopped off the end of it.

    The first version of this test judged by length: anything 43 to 47 characters long without terminal
    punctuation was called cut. That counted "Economy, Trade & Jobs News — 21 October 2026" - a complete
    headline - as a defect, while missing "Cost of living protests hit Belgium, Italy," because it was
    only 43 characters. A listing report that miscounts in both directions cannot be used to decide
    whether a feed is ready for a reviewer, so the test now asks the only question that can be answered
    from the text: does it stop somewhere a sentence cannot stop?
    """
    text = strip(title)
    if not text:
        return False
    if text.endswith("…") or text.endswith("..."):
        return True
    if TRAILING_PUNCTUATION.search(text) or POSSESSIVE_END.search(text):
        return True
    if DANGLING_END.search(text):
        return True
    return bool(re.search(r"[A-Za-z]-[A-Za-z]{1,2}$", text))


def clipped_by_our_own_cap(title: str) -> bool:
    """Whether the headline ends exactly where this blog's own title limit falls.

    Titles are written to a 46-character cap (`seo_hygiene.MAX_TITLE_CHARS`), chosen to leave room for
    Blogger's site-name suffix. So a headline that stops at 46 characters was bounded by us, not by
    Google, and it is the population from which every cut headline in the feed has come. It is reported
    separately because a full-length sentence that happens to measure 46 characters is not a defect -
    it is a headline one character from becoming one.
    """
    return len(strip(title)) == CAP


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
        if clipped_by_our_own_cap(title):
            issues.append("clippedByOurTitleCap")
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



def meta_tag(document: str, name: str) -> str:
    """The one <meta> tag that carries this property or name, however its attributes are ordered."""
    for tag in re.finditer(r"<meta\b[^>]*>", document):
        if re.search(r"""(?:property|name)=["']%s["']""" % re.escape(name), tag.group(0)):
            return tag.group(0)
    return ""


def meta_value(document: str, name: str) -> str:
    """The content= of that tag, or an empty string when the page carries no such line."""
    tag = meta_tag(document, name)
    found = re.search(r"""content=["'](.*?)["']""", tag, re.S) if tag else None
    return found.group(1) if found else ""


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
        # Whichever order the two attributes are written in, the tag is the same fact. This was measured
        # wrong until 24 October 2026: the job demanded property= before content=, Blogger writes it the
        # other way round, and six pages that already carried a picture were reported as carrying none.
        image = meta_value(page, "og:image")
        if not image.startswith(("http://", "https://")):
            row["issues"].append("noOpenGraphImage")
        head = page[:page.lower().find("<body") if "<body" in page.lower() else 20000]
        if len(meta_value(head, "description").strip()) < 30:
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
