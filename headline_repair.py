#!/usr/bin/env python3
"""Read the real headline back out of each article, because a 46-character cap cut it off.

Measured on the live feed on 20 October 2026: the newest master article is published as
"Payoneer: How Stablecoin is Scaling in Cross-B" while its own body contains
"Payoneer: How Stablecoin is Scaling in Cross-Border Payments". The cause is in this
repository - ``master_v3_generator.py`` sliced every candidate title at exactly 46
characters - so a whole generation of master articles lost their tail in the title, the
RSS feed, the ``<title>`` tag and the ``<h1>``. Two articles that both lose their tails can
end up sharing one title, which is part of how the duplicate pile was built.

Nothing here invents a headline. A repair only happens when the article already displays a
longer form of its own truncated title as its first heading, the recovered line stays inside
a search-result-safe length, and no other post on the blog would collide with it. Like every
other live-editing job in this repository, it reports unless ``--apply`` is given, backs the
post up first, and caps how many posts one run may touch.
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

# 46 is the cap that caused the damage; 72 is what a headline may grow to. Google writes
# roughly 600px of title before it clips with an ellipsis of its own, which lands near 70
# characters, and Bing starts penalising "too long" titles somewhere past 80.
BROKEN_CAP = 46
MAX_REPAIRED = 72
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
    A headline written short on purpose sits elsewhere, and this job never touches it - the
    article's own longer heading is still required before anything is proposed.
    """
    text = plain(title)
    if not text:
        return False
    if text.endswith("…") or text.endswith("..."):
        return True
    return BROKEN_CAP - 3 <= len(text) <= BROKEN_CAP + 1 and not re.search(r"[.?!:]$", text)


def heading_candidates(content: str) -> list[str]:
    """Headings the article itself renders, longest-first scan order preserved."""
    found = []
    for match in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", str(content or ""), flags=re.S | re.I):
        text = plain(match.group(2))
        if 12 <= len(text) <= MAX_REPAIRED and len(words(text)) >= MIN_WORDS:
            found.append(text)
    return found


def recover(post: dict) -> dict:
    """Return the repair for one post, or an empty dict when the article gives no warrant."""
    title = plain(post.get("title") or post.get("name") or "")
    if not clipped(title):
        return {}
    wanted = words(title)
    if not wanted:
        return {}
    for heading in heading_candidates(post.get("content") or post.get("body") or ""):
        have = words(heading)
        if len(have) <= len(wanted):
            continue
        # The cut title's last token is a fragment of a word ("Cross-B" from "Cross-Border"),
        # so every word before it must match exactly and the fragment may only be completed by
        # the heading's own word. That is reading the article, not writing a better headline.
        if have[: len(wanted) - 1] != wanted[: len(wanted) - 1]:
            continue  # not the same sentence, just a similar topic - never guess
        if wanted and not have[len(wanted) - 1].startswith(wanted[-1]):
            continue
        if have[-1].lower() in DANGLING:
            continue  # this heading is itself cut short; it cannot repair anything
        return {"id": post.get("id"), "url": str(post.get("url") or ""), "before": title,
                "after": heading, "gained": len(heading) - len(title)}
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

    payload = {"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "mode": "APPLIED" if arguments.apply else "AUDIT_ONLY",
               "postsScanned": len(posts), "clippedTitles": len(repairs) + blocked,
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
