#!/usr/bin/env python3
"""Read the real headline back out of each article, because a 46-character cap cut it off.

Measured on the live feed on 20 October 2026: the newest master article is published as
"Payoneer: How Stablecoin is Scaling in Cross-B" while its own body contains
"Payoneer: How Stablecoin is Scaling in Cross-Border Payments". The cause is in this
repository - ``master_v3_generator.py`` sliced every candidate title at exactly 46
characters - so a whole generation of master articles lost their tail in the title, the
RSS feed, the ``<title>`` tag and the ``<h1>``. Two articles that both lose their tails can
end up sharing one title, which is part of how the duplicate pile was built.

The 46-character ceiling is not this file's to raise: ``master_article_v2.validate()`` refuses any
master title outside 12-46 characters, and publishing stops dead on that rejection - which is what
a 72-character version of this job did on 20 October 2026, leaving master slots unfilled for hours.
So a repaired line is read out of the article's own heading and then trimmed, word by word, until
it both fits inside 46 characters and ends on a complete word: for the Payoneer post the
60-character heading yields "Payoneer: How Stablecoin is Scaling" - grammatical, inside the rule,
and made of no words but the article's. Nothing is padded, and an ellipsis is never used to hide a
truncation.

A heading is required as the witness. A title whose own article shows no corroborating heading is
left alone even if it ends mid-word, because editing a live headline on a guess is how new
duplicates were built in the first place. Like every other live-editing job in this repository, it
reports unless ``--apply`` is given, backs the post up first, and caps how many posts one run
may touch.
"""
from __future__ import annotations

import argparse
import gzip
import html as htmlmod
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
OUT = ROOT / "HEADLINE_REPAIR.json"
MD = ROOT / "HEADLINE_REPAIR.md"
BACKUP = ROOT / "HEADLINE_REPAIR_BACKUP.json.gz"

# 46 is both the cap that caused the damage and the longest repaired title allowed: it is the
# upper bound master_article_v2.validate() accepts (12-46) and the one seo_hygiene keeps for
# Blogger's site-name suffix. A title above it is not "optimised", it is unpublished.
BROKEN_CAP = 46
MIN_TITLE_CHARS, MAX_TITLE_CHARS = 12, 46
MAX_REPAIRED = MAX_TITLE_CHARS
MIN_WORDS = 4
# A wire headline can be truncated in the source too, and "…AI spending ambitions as" ending
# on a small connecting word is the tell. A recovered headline must land on a real word.
DANGLING = {"a","an","and","as","at","but","by","for","from","if","in","into","its","of","on",
            "or","our","per","the","to","vs","with","that","this","these","those","it","its",
            "is","are","was","were","be","been","after","before","over","under","between"}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", re.sub(r"<[^>]+>", " ", str(value or "")).lower())


def plain(value: str) -> str:
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def clipped(title: str) -> bool:
    """True when a title looks like it was cut by the 46-character slice, not written short.

    The warrant is arithmetic: the old code took the first 46 characters and stripped
    separators, so a victim lands between 43 and 47 characters and ends without punctuation.
    A headline written short on purpose sits elsewhere, and this job never touches it - and even
    a title that looks cut requires the article's own heading to show the same words first.
    """
    text = plain(title)
    if not text:
        return False
    if text.endswith("…") or text.endswith("..."):
        return True
    return BROKEN_CAP - 3 <= len(text) <= BROKEN_CAP + 1 and not re.search(r"[.?!:]$", text)


DANGLING_DATE = re.compile(
    r"\b(?:19|20)\d{2}\b|\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)"
    r"?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", re.I)


def heading_candidates(content: str) -> list[str]:
    """Headings the article itself renders that the site would accept as a title."""
    found = []
    for match in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", str(content or ""), flags=re.S | re.I):
        text = plain(match.group(2))
        # A heading carrying a date could never be published as a master title (master titles
        # are undated by policy), so a repair may not offer one as a title either.
        if (MIN_TITLE_CHARS <= len(text) <= MAX_REPAIRED and len(words(text)) >= MIN_WORDS
                and not DANGLING_DATE.search(text)):
            found.append(text)
    return found


def fitted(text: str, limit: int = MAX_TITLE_CHARS) -> str:
    """The article's own words, kept whole, shortened until they fit what the site accepts.

    Words are peeled off the end - never out of the middle - so the result is the longest opening
    clause of the heading that satisfies ``master_article_v2`` (12-46 characters) and does not stop
    on a dangling word such as "in" or "the".
    """
    parts = str(text or "").split()
    while parts:
        candidate = " ".join(parts).strip().strip(" ,;:.!?—–-")
        if len(candidate) > limit:
            parts.pop()
            continue
        if len(candidate) < MIN_TITLE_CHARS:
            return ""
        if candidate.split()[-1].lower().strip(" ,;:.!?-") in DANGLING:
            parts.pop()  # a headline may not end on a preposition either
            continue
        return candidate
    return ""


def recover(post: dict) -> dict:
    """Return the repair for one post, or an empty dict when the article gives no warrant."""
    title = plain(post.get("title") or post.get("name") or "")
    if not clipped(title):
        return {}
    wanted = words(title)
    if not wanted:
        return {}
    stem = wanted[:-1]
    if not stem:
        return {}  # a one-word headline is not a cut sentence
    options = []
    # Any heading the article renders may witness the repair, whatever its length; ``fitted``
    # then decides how much of it the site would actually accept as a title.
    for match in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>",
                             str(post.get("content") or post.get("body") or ""), flags=re.S | re.I):
        heading = plain(match.group(2))
        if len(words(heading)) < MIN_WORDS:
            continue
        have = words(heading)
        if len(have) <= len(stem):
            continue
        # The cut title's last token is a fragment of a word ("Cross-B" from "Cross-Border"),
        # so every word before it must match exactly and the fragment may only be completed by
        # the heading's own word. That is reading the article, not writing a better headline.
        if have[: len(stem)] != stem:
            continue  # not the same sentence, just a similar topic - never guess
        if not have[len(stem)].lower().startswith(wanted[-1].lower()):
            continue
        if have[-1].lower() in DANGLING:
            continue  # this heading is itself cut short; it cannot repair anything
        if DANGLING_DATE.search(heading):
            continue  # master titles are undated by policy; a dated heading may not become one
        after = fitted(heading)
        if after == title or not (MIN_TITLE_CHARS <= len(after) <= MAX_TITLE_CHARS):
            continue  # would change nothing or leave the title outside what the site accepts
        # The longest clean title the article can vouch for wins, so a heading that already fits
        # verbatim is preferred to one that has to lose words.
        options.append({"id": post.get("id"), "url": str(post.get("url") or ""), "before": title,
                        "after": after, "gained": len(after) - len(title),
                        "shortenedToFit": len(after) < len(heading)})
    if options:
        return max(options, key=lambda row: len(row["after"]))
    return {}


def oauth_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["BLOGGER_CLIENT_ID"],
        "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def api(url: str, token: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload) if payload.strip() else {}


def list_posts(token: str) -> list[dict]:
    posts, page_token = [], ""
    for _ in range(40):
        query = urllib.parse.urlencode({"maxResults": "250", "view": "READER", "status": "live",
                                        **({"pageToken": page_token} if page_token else {})})
        payload = api(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts?{query}", token)
        posts.extend(payload.get("items") or [])
        page_token = payload.get("nextPageToken") or ""
        if not page_token:
            break
    return posts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write the recovered headline to Blogger; without this the run only reports")
    parser.add_argument("--max", type=int, default=40, help="how many titles one run may rewrite")
    parser.add_argument("--fixture", default="", help="JSON file of posts, for tests and offline review")
    arguments = parser.parse_args()

    if arguments.fixture:
        posts = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
        token = ""
    else:
        missing = [name for name in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN")
                   if not os.environ.get(name)]
        if missing:
            print(json.dumps({"ok": False, "error": "the headline repair reads the blog through the "
                                                     "authenticated API; no credential is configured"}))
            return 0
        token = oauth_token()
        posts = list_posts(token)

    taken: dict[str, int] = {}
    for post in posts:
        key = " ".join(words(post.get("title") or ""))
        taken[key] = taken.get(key, 0) + 1

    repairs = []
    blocked = 0
    for post in posts:
        one = recover(post)
        if not one:
            continue
        # a repair that would put two live posts under one title is a new duplicate, not a fix
        if taken.get(" ".join(words(one["after"])), 0):
            blocked += 1
            continue
        taken[" ".join(words(one["after"]))] = 1
        taken[" ".join(words(one["before"]))] = max(0, taken.get(" ".join(words(one["before"])), 1) - 1)
        one["id"] = post.get("id")
        repairs.append(one)

    batch = repairs[: max(0, arguments.max)]
    applied, failed = [], []
    if arguments.apply and batch:
        BACKUP.write_bytes(gzip.compress(json.dumps({"capturedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                      "posts": [p for p in posts if p.get("id") in
                                                                  {row["id"] for row in batch}]},
                                                     ensure_ascii=False).encode()))
        for row in batch:
            try:
                api(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/{row['id']}", token,
                    method="PATCH", body={"title": row["after"]})
                applied.append(row)
            except urllib.error.HTTPError as exc:
                failed.append({**row, "error": f"HTTP {exc.code}"})
            except Exception as exc:  # noqa: BLE001
                failed.append({**row, "error": str(exc)[:160]})

    # how many scanned posts already show a heading the site could carry as a title untouched:
    # that is the supply of clean headlines available without inventing anything
    usable = sum(1 for one in posts if heading_candidates(one.get("content") or one.get("body") or ""))
    payload = {"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "mode": "APPLIED" if arguments.apply else "AUDIT_ONLY",
               "postsScanned": len(posts), "clippedTitles": len(repairs) + blocked,
               "headingsUsableAsTitle": usable,
               "repairable": len(repairs), "heldBackCollisions": blocked,
               "selectedThisRun": len(batch), "batchCap": arguments.max, "repaired": applied,
               "failed": failed, "backup": BACKUP.name if applied else "",
               "examples": repairs[:20]}
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    lines = [f"# Headline repair · {payload['checkedAt']}", "",
             f"Mode: **{payload['mode']}**", "",
             f"- live posts scanned: **{payload['postsScanned']}**",
             f"- titles cut off by the old 46-character cap: **{payload['clippedTitles']}**",
             f"- recoverable from the article's own heading: **{payload['repairable']}**",
             f"- held back because the recovered title already exists: **{payload['heldBackCollisions']}**",
             f"- posts showing a heading the site could carry as a title untouched: "
             f"**{payload['headingsUsableAsTitle']}** (a longer heading is trimmed to its longest "
             f"whole-word opening inside 12-{MAX_TITLE_CHARS} characters rather than published as-is)",
             f"- selected for this run: **{payload['selectedThisRun']}** (cap {arguments.max})",
             f"- headlines written back: **{len(applied)}**", ""]
    if repairs:
        lines.append("| article | cut title | recovered headline |")
        lines.append("| --- | --- | --- |")
        for row in repairs[:20]:
            lines.append(f"| {row['url']} | {row['before']} | {row['after']} |")
        lines.append("")
    lines.append("URLs do not change: Blogger keeps the slug it was given, so this only makes the "
                 "headline, the feed entry and the search result say the whole thing.")
    MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({k: payload[k] for k in ("mode", "postsScanned", "clippedTitles", "repairable",
                                              "heldBackCollisions", "selectedThisRun", "repaired")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
