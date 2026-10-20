#!/usr/bin/env python3
"""Differentiate Blogger's accidental twins instead of deleting them.

Owner rule, 20 October 2026: the site publishes 21 articles a day and that count is maintained.
A duplicate must not be answered by removing pages, so the nightly job does not delete the twin
that Blogger created when the same title went out twice (`...sold-property-eight-different-ways-
to_0586614503.html` beside the original). It makes the twin genuinely *different* instead:

  * a headline that says which edition it is, so two posts no longer share one title;
  * a short visible note at the top that either lists what only this edition says - taken from
    this post's own sentences, never invented - or links forward to the current version.

The URL stays, the images stay, the words stay, the article keeps counting towards the daily
output. Like the rest of the live-editing jobs here it reports unless ``--apply`` is given, backs
up both posts before touching either, caps how many pairs one run may touch, and refuses to write
anything when the backup failed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from blogger_duplicate_purge import analyse, oauth_token, protected_urls

ROOT = Path(__file__).resolve().parent
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
OUT = ROOT / "DUPLICATE_REFRESH.json"
MD = ROOT / "DUPLICATE_REFRESH.md"
ARCHIVE = ROOT / "duplicate_refresh_archive"
API = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}"
MAX_PER_RUN_DEFAULT = 25
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def plain(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def sentences(html: str) -> list[str]:
    text = plain(html)
    parts = [part.strip() for part in SENTENCE.split(text) if len(part.strip()) > 45]
    return parts


def unique_sentences(twin_html: str, survivor_html: str, limit: int = 3) -> list[str]:
    """Sentences this edition carries that the survivor does not - extraction, not writing."""
    seen = {" ".join(row.lower().split()) for row in sentences(survivor_html)}
    out: list[str] = []
    for row in sentences(twin_html):
        key = " ".join(row.lower().split())
        if key in seen or key in {" ".join(o.lower().split()) for o in out}:
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def edition_date(post: dict) -> str:
    stamp = str(post.get("published") or "")[:10]
    try:
        return datetime.strptime(stamp, "%Y-%m-%d").strftime("%d %B %Y")
    except ValueError:
        return ""


def new_title(title: str, post: dict, taken: set[str]) -> str:
    """A headline that names this edition, made unique against every other live title."""
    day = edition_date(post)
    stem = plain(title).rstrip(" .")
    base = f"{stem} — {day} edition" if day else f"{stem} — earlier edition"
    candidate, index = base, 2
    while candidate.lower() in taken:
        candidate = f"{base} ({index})"
        index += 1
    return candidate


def note_block(unique: list[str], survivor_url: str) -> str:
    if unique:
        body = " ".join(row if row.endswith((".", "!", "?")) else row + "." for row in unique)
        return ("<p><strong>What only this edition carries:</strong> " + body + "</p>")
    href = survivor_url or "the current version of this article"
    return ("<p><em>Earlier edition of this article. The current version is at "
            f'<a href="{href}">{plain(survivor_url) or "the live article"}</a>.</em></p>')


def api_call(token: str, url: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload) if payload.strip() else {}


def plan(posts: list[dict], bodies: dict[str, str]) -> dict:
    """Everything this run would do, computed offline from the posts it can see."""
    protected = protected_urls()
    report = analyse(posts, protected)
    titles = {plain(post.get("title")).lower() for post in posts}
    pairs = []
    for group in report["groups"]:
        survivor = group["keep"]
        # the purge may not touch a URL the operation points at, because deleting it breaks the
        # reference; a refresh keeps every URL and only makes the twin say something different, so
        # both lists are candidates here - that is the difference between these two jobs
        for twin in list(group["deletable"]) + list(group.get("protected") or []):
            twin_post = next((post for post in posts if str(post.get("id")) == str(twin["id"])), twin)
            survivor_post = next((post for post in posts if str(post.get("id")) == str(survivor["id"])),
                                 survivor)
            twin_html = str(bodies.get(str(twin["id"])) or twin_post.get("content")
                            or twin_post.get("body") or "")
            survivor_html = str(bodies.get(str(survivor["id"])) or survivor_post.get("content")
                                 or survivor_post.get("body") or "")
            unique = unique_sentences(twin_html, survivor_html)
            title = new_title(plain(twin.get("title") or twin_post.get("title") or ""), twin_post, titles)
            titles.add(title.lower())
            pairs.append({"id": twin["id"], "guarded": twin in (group.get("protected") or []),
                          "url": twin.get("url") or public(twin_post),
                          "survivor": survivor.get("url") or public(survivor_post),
                          "beforeTitle": plain(twin.get("title") or twin_post.get("title") or ""),
                          "afterTitle": title, "uniqueSentences": len(unique),
                                                    "block": note_block(unique, survivor.get("url") or public(survivor_post))})
    return {"titleGroups": report["titleGroups"], "twins": len(pairs), "pairs": pairs}


def public(post: dict) -> str:
    return str(post.get("url") or "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write the differentiated title and note; without this the run only reports")
    parser.add_argument("--max", type=int, default=MAX_PER_RUN_DEFAULT, help="how many pairs one run may touch")
    parser.add_argument("--fixture", default="", help="JSON {posts, bodies} for tests and offline review")
    arguments = parser.parse_args()

    if arguments.fixture:
        payload = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
        posts, bodies, token = payload.get("posts") or [], payload.get("bodies") or {}, ""
    else:
        for name in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN"):
            if not os.environ.get(name):
                print(json.dumps({"ok": False, "error": f"{name} is not configured; the refresh reads the "
                                                        "blog through the authenticated API only"}))
                return 0
        token = oauth_token()
        posts, bodies = [], {}
        page_token = ""
        for _ in range(40):
            query = "maxResults=250&view=READER&status=live"
            if page_token:
                query += "&pageToken=" + urllib.parse.quote(page_token)
            data = api_call(token, f"{API}/posts?{query}")
            posts.extend(data.get("items") or [])
            page_token = data.get("nextPageToken") or ""
            if not page_token:
                break
        for post in posts:
            bodies[str(post.get("id"))] = str(post.get("content") or post.get("body") or "")

    planned = plan(posts, bodies)
    batch = planned["pairs"][: max(0, arguments.max)]
    written, failed, archived, stopped = [], [], 0, ""
    if arguments.apply and batch:
        ARCHIVE.mkdir(exist_ok=True)
        for row in batch:
            try:
                before = api_call(token, f"{API}/posts/{row['id']}?view=RAW")
                (ARCHIVE / f"{row['id']}.json").write_text(json.dumps(before, indent=1, ensure_ascii=False))
                archived += 1
            except Exception as exc:  # noqa: BLE001
                failed.append({**row, "error": "archiving failed: " + str(exc)[:120]})
        if archived < len(batch):
            # the run still has to leave evidence behind: a silent exit would look like a
            # successful night in which nothing was wrong
            stopped = "every post must be archived before it is rewritten; nothing was changed"
            print(json.dumps({"ok": False, "error": stopped}))
            batch = []
        for row in batch:
            try:
                current = json.loads((ARCHIVE / f"{row['id']}.json").read_text(encoding="utf-8"))
                content = row["block"] + str(current.get("content") or "")
                api_call(token, f"{API}/posts/{row['id']}", method="PATCH",
                         body={"title": row["afterTitle"], "content": content})
                written.append({key: row[key] for key in ("id", "url", "beforeTitle", "afterTitle",
                                                          "uniqueSentences", "guarded")})
            except urllib.error.HTTPError as exc:
                failed.append({**row, "error": f"HTTP {exc.code}"})
            except Exception as exc:  # noqa: BLE001
                failed.append({**row, "error": str(exc)[:140]})

    report = {"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "mode": "APPLIED" if arguments.apply else "AUDIT_ONLY",
              "titleGroups": planned["titleGroups"], "twinsFound": len(planned["pairs"]),
              "selectedThisRun": len(batch), "batchCap": arguments.max, "archived": archived,
              "refreshed": written, "failed": failed, "deletions": 0, "stopped": stopped or None,
              "policy": "duplicates are differentiated, never bulk-deleted (owner decision, "
                        "20 October 2026: the 21-a-day output is maintained)",
              "examples": planned["pairs"][:15]}
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    lines = [f"# Duplicate refresh · {report['checkedAt']}", "", f"Mode: **{report['mode']}**", "",
             f"- exact-title groups on the blog: **{report['titleGroups']}**",
             f"- twins to differentiate: **{report['twinsFound']}**",
             f"- selected for this run: **{report['selectedThisRun']}** (cap {arguments.max})",
             f"- backed up before writing: **{archived}**",
             f"- rewritten: **{len(written)}**, failed: **{len(failed)}**, deleted: **0**", ""]
    for row in report["examples"]:
        lines.append(f"- `{row['url']}` → **{row['afterTitle']}** "
                     f"({row['uniqueSentences']} sentence(s) only this edition carries)")
    lines += ["", "Nothing is deleted by this job. The twin keeps its URL and its text; it stops "
                  "being a duplicate by carrying its own headline and its own note."]
    MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({"mode": report["mode"], "titleGroups": report["titleGroups"],
                      "twinsFound": report["twinsFound"], "selectedThisRun": report["selectedThisRun"],
                      "refreshed": len(written), "failed": len(failed), "deletions": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
