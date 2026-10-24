#!/usr/bin/env python3
"""Shrink the desk hub pages by removing what the page does not need, and never a link it does.

Why this file exists. On 24 October 2026 the five hub pages that Google is asked to treat as front pages
measured, as served: `/p/daily-news.html` 941,540 bytes, `/p/article.html` 664,533, `/p/global-snapshot.html`
641,208, `/p/for-corporate_01804417406.html` 620,881, `/p/money-atlas_01486068069.html` 551,474 and
`/p/markets-today.html` 521,256. Opening `/p/daily-news.html` and reading it showed why: 714,032 of its
937,917 bytes are inline scripts, and two of those blocks - 230,192 and 222,800 bytes - hold the *same*
list of stories twice, once as `window.ENH_NEWS_SNAPSHOT` and once as `var items` inside the widget. Only
181 of the page's links are the visible list, so the payload carried the blog's whole corpus of 600-plus
stories for a page that shows a few dozen. A page that heavy is not a front page: Google has to download
and render a megabyte to find nineteen items on it, and that is one measured reason it lists 1 page of 633.

What this controller does, and does not do. It collapses the duplicated payload to one copy, minifies it
the way the rest of the site's data blocks are minified, and keeps only the stories the page itself links
plus the most recent `maxRecent` entries. It never removes an anchor, a heading, a paragraph, a table or a
figure, so nothing a reader or a crawler could follow disappears. Every page is copied exactly as found to
`FRONT_PAGE_BACKUP/` before a single byte is written back, the same copy that travels with the run as an
artefact, and a page is refused - not truncated, not guessed at - if any invariant below fails.
"""
from site_change_control import stop_if_frozen as _dy_stop_if_frozen
if __name__ == "__main__":
    _dy_stop_if_frozen('front_page_compaction')

import argparse, datetime as dt, gzip, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKUP_DIR = ROOT / "FRONT_PAGE_BACKUP"
STATUS = ROOT / "FRONT_PAGE_COMPACTION_STATUS.json"
ACTION = "front_page_compaction"

# The hub pages, addressed the way the sitemap and the navigation address them today. Two of them carry
# Blogger's collision tail because a create took the place of an update years ago; the tail is kept in the
# path on purpose, because changing a live address is not what this job is for.
PAGES = (
    {"key": "daily-news", "path": "/p/daily-news.html"},
    {"key": "markets-today", "path": "/p/markets-today.html"},
    {"key": "global-snapshot", "path": "/p/global-snapshot.html"},
    {"key": "article-hub", "path": "/p/article.html"},
    {"key": "money-atlas", "path": "/p/money-atlas_01486068069.html"},
    {"key": "for-corporate", "path": "/p/for-corporate_01804417406.html"},
)

# One canonical copy of the list is written under this name; the two consumers read it.
CANONICAL = "window.DY_HUB_SNAPSHOT"
PAYLOAD_STARTS = (
    re.compile(r"window\.ENH_NEWS_SNAPSHOT\s*=\s*"),
    re.compile(r"var\s+items\s*=\s*"),
)
URL_KEYS = ("url", "link", "href", "canonicalUrl", "canonical")
DATE_KEYS = ("published", "date", "publishedDate", "updated")
SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
HREF = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.I)
MIN_SAVING = 0.25           # less than this, and the edit is not worth making on a live page
MAX_RECENT_DEFAULT = 30
BLOGGER_LIMIT_NOTE = "Blogger page content is stored as given; nothing here changes that"


def _decoder():
    return json.JSONDecoder()


CANONICAL_PATTERN = re.compile(r"window\.DY_HUB_SNAPSHOT\s*=\s*")


def canonical_payload(document):
    """The one list the rebuilt page carries, read back the way a browser would find it.

    The check has to look for the canonical name rather than re-use the two patterns above, because after
    a successful rebuild the second copy is an alias of the first and no longer holds an array literal - a
    re-scan for the old shapes would report an empty page and refuse every correct edit.
    """
    match = CANONICAL_PATTERN.search(document)
    if not match:
        return None
    try:
        value, _length = _decoder().raw_decode(document[match.end():])
    except ValueError:
        return None
    return value if isinstance(value, list) else None


def payload_spans(document):
    """The (start, end, decoded list) of every inline story list the page carries.

    `raw_decode` is used instead of a bracket count because these arrays contain strings with braces in
    them, and a naive count stops at the wrong brace - which on a live page would have written a broken
    script and taken a desk down.
    """
    out = []
    decoder = _decoder()
    for pattern in PAYLOAD_STARTS:
        cursor = 0
        while True:
            match = pattern.search(document, cursor)
            if not match:
                break
            start = match.end()
            try:
                value, length = decoder.raw_decode(document[start:])
            except ValueError:
                cursor = start
                continue
            cursor = start + length
            if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
                out.append((match.start(), start + length, value))
    out.sort(key=lambda span: span[0])
    return out


def item_url(row):
    for key in URL_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return ""


def item_date(row):
    for key in DATE_KEYS:
        value = row.get(key)
        if isinstance(value, str):
            try:
                return dt.datetime.fromisoformat(value.replace("Z", "+00:00").split(".")[0].split("+")[0]
                                                 .replace("T", "T"))
            except ValueError:
                continue
    return None


def visible_links(document):
    """Every address a reader can actually follow from the page, with the scripts left out."""
    without_scripts = SCRIPT_BLOCK.sub(" ", document)
    return {href.strip() for href in HREF.findall(without_scripts)}


def _normalise(url):
    url = (url or "").strip()
    for prefix in ("https://dailyyield.blogspot.com", "http://dailyyield.blogspot.com"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url or url


def emit(rows):
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return payload


def compact(document, max_recent=MAX_RECENT_DEFAULT):
    """Return (new document, report). A refusal comes back with the original document and a reason."""
    report = {"changed": False, "reason": "", "payloads": 0, "itemsBefore": 0, "itemsAfter": 0,
              "linksBefore": 0, "linksAfter": 0, "bytesBefore": len(document), "bytesAfter": len(document)}
    spans = payload_spans(document)
    report["payloads"] = len(spans)
    if not spans:
        report["reason"] = "no inline story list on this page: nothing to compact"
        return document, report

    # The page's own list of links decides what has to stay reachable from the payload. Anything the page
    # links to is kept; anything it does not link to is kept only while it is inside the recent window,
    # and otherwise dropped from the script while still standing as its own post, in the sitemap.
    linked = {_normalise(href) for href in visible_links(document)}
    report["linksBefore"] = len(linked)
    canonical = None
    for _start, _end, rows in spans:
        if canonical is None or len(rows) > len(canonical):
            canonical = rows
    report["itemsBefore"] = len(canonical)

    kept, dropped = [], []
    ordered = sorted(canonical, key=lambda row: item_date(row) or dt.datetime.min, reverse=True)
    for row in ordered:
        url = _normalise(item_url(row))
        if not url:
            kept.append(row)
            continue
        if url in linked or len(kept) < max_recent:
            kept.append(row)
        else:
            dropped.append(row)
    if not kept:
        report["reason"] = "refusing to write a payload with no items in it"
        return document, report
    report["itemsAfter"] = len(kept)

    payload = emit(kept)
    pieces, last = [], 0
    for index, (start, end, _rows) in enumerate(spans):
        # Only the array literal is replaced; the words on its left are kept exactly as they were, because
        # the widget reads a local `var items` and the enhancer reads `window.ENH_NEWS_SNAPSHOT`. The first
        # copy carries the data and also names it canonically; every later copy becomes a read of that one
        # name, so the page ends up holding one list instead of two and both consumers still find theirs.
        head = document[start:document.index("=", start) + 1]
        pieces.append(document[last:start])
        pieces.append(head + (CANONICAL + "=" + payload if index == 0 else CANONICAL))
        last = end
    pieces.append(document[last:])
    new_document = "".join(pieces)

    for required in ("var items=", "window.ENH_NEWS_SNAPSHOT="):
        if required in document and required not in new_document:
            report["reason"] = f"the widget binding {required[:-1]} would have been lost"
            return document, report

    report["bytesAfter"] = len(new_document)
    # Both measures are recorded and the raw one decides, because what a reader or a crawler pays for here
    # is a document it has to parse: two copies of a 600-story list compress almost as well as one (gzip
    # loves a repeat), so a compressed-size test alone would have thrown away a 45% cut in what the page
    # actually has to carry and render. The compressed figure is kept in the report so nobody has to take
    # that on trust.
    before_gzip = len(gzip.compress(document.encode("utf-8"), 9))
    after_gzip = len(gzip.compress(new_document.encode("utf-8"), 9))
    report.update({"gzipBefore": before_gzip, "gzipAfter": after_gzip})
    saving = 1 - (len(new_document) / max(1, len(document)))
    if saving < MIN_SAVING:
        report["reason"] = (f"only {saving:.0%} smaller after collapsing "
                            f"{len(spans)} payload copies: not worth a live write")
        return document, report
    if after_gzip > before_gzip:
        report["reason"] = "the transfer size rose, so the rebuild is refused"
        return document, report

    # Invariants, measured on the rebuilt page. Any failure returns the original bytes untouched.
    report["linksAfter"] = len({_normalise(href) for href in visible_links(new_document)})
    if report["linksAfter"] != report["linksBefore"]:
        report["reason"] = "a reader link would have been lost"
        return document, report
    rebuilt_balance = balance_report(new_document)
    if not rebuilt_balance["balanceReportOk"]:
        report["reason"] = f"a container tag would have been left unclosed: {rebuilt_balance['unbalancedTags'][:2]}"
        return document, report
    if new_document.lower().count("<script") != document.lower().count("<script"):
        report["reason"] = "the number of script blocks changed"
        return document, report
    if new_document.lower().count("</script") != document.lower().count("</script"):
        report["reason"] = "a closing script tag would have been lost"
        return document, report
    rebuilt = canonical_payload(new_document)
    if rebuilt is None or len(rebuilt) != len(kept):
        report["reason"] = "the rewritten payload does not read back as the list that was built"
        return document, report
    for row in kept:
        url = _normalise(item_url(row))
        if url and url in linked and url not in new_document:
            report["reason"] = "a linked story vanished from the page"
            return document, report

    report.update({"changed": True, "reason": "ok", "bytesSaved": len(document) - len(new_document),
                   "droppedItems": len(dropped)})
    return new_document, report


PAIRS = ("div", "section", "article", "script", "style", "a", "h1", "ul", "li", "table")


def balance_report(document):
    """Whether every container the page opens, it also closes.

    A tag-balance check rather than a full parser, because the content is a Blogger page: the markup is
    deliberately forgiving and a strict parser would report the theme's own optional closers as damage.
    What matters for this job is that a rebuild never drops a closer, so the counts are compared - open
    against close, per container - before a write and again on the bytes that came back afterwards.
    """
    problems = []
    lowered = document.lower()
    for tag in PAIRS:
        opened = len(re.findall(r"<%s(?=[\s>/])" % tag, lowered))
        closed = len(re.findall(r"</%s\s*>" % tag, lowered))
        if opened != closed:
            problems.append({"tag": tag, "opened": opened, "closed": closed})
    return {"balanceReportOk": not problems, "unbalancedTags": problems}


def backup_page(key, document, stamp=None):
    stamp = stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIR / f"{key}-{stamp}.html"
    path.write_text(document, encoding="utf-8")
    if path.read_text(encoding="utf-8") != document:
        raise RuntimeError(f"backup of {key} did not read back byte-for-byte, so nothing will be written")
    return path


# --------------------------------------------------------------------------- Blogger API, only in --apply

def headers():
    import requests
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["BLOGGER_CLIENT_ID"], "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    response.raise_for_status()
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def list_pages(base, auth):
    import requests
    out, token = [], None
    while True:
        params = {"fetchBodies": "true", "maxResults": "50"}
        if token:
            params["pageToken"] = token
        response = requests.get(base + "/pages", headers=auth, params=params, timeout=60)
        response.raise_for_status()
        body = response.json()
        out += body.get("items", [])
        token = body.get("nextPageToken")
        if not token:
            return out


def write_page(base, auth, page_id, title, content):
    import requests
    response = requests.put(f"{base}/pages/{page_id}", headers=auth, timeout=90,
                            json={"kind": "blogger#page", "id": page_id, "title": title, "content": content})
    response.raise_for_status()
    return response.json()


def run(mode="survey", apply_writes=False, max_recent=MAX_RECENT_DEFAULT, local=None, out=None):
    rows = []
    if local:
        document = Path(local).read_text(encoding="utf-8")
        new_document, report = compact(document, max_recent=max_recent)
        report["key"] = Path(local).name
        report["balance"] = balance_report(new_document) if report["changed"] else balance_report(document)
        rows.append(report)
        if out and report["changed"]:
            Path(out).write_text(new_document, encoding="utf-8")
            print(f"  compacted copy written to {out}")
    else:
        import requests
        blog_id = os.environ["BLOGGER_BLOG_ID"]
        base = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}"
        auth = headers()
        pages = list_pages(base, auth)
        for target in PAGES:
            page = next((p for p in pages if (p.get("url") or "").endswith(target["path"])), None)
            row = {"key": target["key"], "path": target["path"]}
            if page is None:
                row.update({"changed": False, "reason": "page not found by address; nothing written"})
                rows.append(row)
                continue
            document = page.get("content", "")
            row["bytesFound"] = len(document)
            new_document, report = compact(document, max_recent=max_recent)
            row.update(report)
            if report["changed"]:
                stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
                row["backup"] = str(backup_page(target["key"], document, stamp).relative_to(ROOT))
                if apply_writes:
                    stored = write_page(base, auth, page["id"], page.get("title", ""), new_document)
                    after = stored.get("content", "")
                    again = payload_spans(after)
                    row["storedBytes"] = len(after)
                    row["verified"] = (len(again) >= 1 and balance_report(after)["balanceReportOk"]
                                       and len(visible_links(after)) == row["linksBefore"])
                    if not row["verified"]:
                        write_page(base, auth, page["id"], page.get("title", ""), document)
                        row.update({"changed": False, "reason": "stored page failed the same checks, "
                                                                "so the backup copy was written back"})
                else:
                    row["reason"] = "dry run: nothing written"
            rows.append(row)

    wrote = sum(1 for row in rows if row.get("changed"))
    status = {"generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "action": ACTION,
              "mode": "apply" if apply_writes else mode, "pagesChecked": len(rows),
              "pagesCompacted": wrote, "siteWrites": wrote if apply_writes else 0,
              "bytesSaved": sum(row.get("bytesSaved", 0) for row in rows),
              "rule": "one payload copy, minified, limited to what the page links plus the recent window; "
                      "no reader link may be lost; backup written before any write",
              "rows": rows}
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", action="store_true", help="measure the pages and write nothing")
    parser.add_argument("--dry-run", action="store_true", help="build the replacement and validate it")
    parser.add_argument("--apply", action="store_true", help="write, after a byte-exact backup of each page")
    parser.add_argument("--max-recent", type=int, default=MAX_RECENT_DEFAULT)
    parser.add_argument("--local-file", help="compact one saved document instead of the live pages")
    parser.add_argument("--out", help="where to write the compacted copy in --local-file mode")
    parser.add_argument("--status-only", action="store_true", help="read the status file and print it")
    arguments = parser.parse_args()

    if arguments.status_only:
        print(STATUS.read_text(encoding="utf-8") if STATUS.exists() else json.dumps({"status": "NOT_RUN"}))
        return 0
    mode = "apply" if arguments.apply else ("dry-run" if arguments.dry_run else "survey")
    status = run(mode=mode, apply_writes=arguments.apply, max_recent=arguments.max_recent,
                 local=arguments.local_file, out=arguments.out)
    if not arguments.local_file:
        STATUS.write_text(json.dumps(status, indent=1), encoding="utf-8")
    for row in status["rows"]:
        print(f"  {row.get('key','?'):16s} {row.get('bytesBefore', row.get('bytesFound', 0)):>9,} -> "
              f"{row.get('bytesAfter', row.get('bytesFound', 0)):>9,} bytes · {row.get('reason', '')}")
    print(json.dumps({k: status[k] for k in ("mode", "pagesChecked", "pagesCompacted", "siteWrites",
                                             "bytesSaved")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
