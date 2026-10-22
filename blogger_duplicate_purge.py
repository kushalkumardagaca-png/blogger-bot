#!/usr/bin/env python3
"""Find - and optionally remove - the duplicate posts that are killing Daily Yield's indexing.

The measured situation on 20 Oct 2026: Search Console has 551 submitted URLs, **1 indexed**,
360 sitting in "discovered - currently not indexed". Inside that pile are Blogger's own
duplicate slugs: publish "Sold property eight different ways to" twice and Blogger creates
"sold-property-eight-different-ways-to.html" and "sold-property-eight-different-ways-to_0586614503.html" -
the same words at two addresses. To a crawler that is the signature of a content farm, and it
is one of the few causes we can actually remove for free.

Safety, because this deletes live blog content:

* **audit is the default.** Nothing is removed unless APPLY=YES is passed explicitly.
* a URL is only a duplicate when the **title matches another post exactly** after normalising.
  Near-misses are left alone.
* any URL that appears in the operation's evidence (slot guarantee, live-edition verification,
  the master tracker, or a social tracker) is **protected** - an article the rest of the system
  points at is never deleted, whatever its title looks like.
* every candidate's full body is archived into ``deleted_posts/`` first, so a removal is
  reversible by re-creating the post, and the evidence for the decision survives.
* a batch cap keeps one run from becoming a catastrophe.
* requests go to the authenticated Blogger API only. This never fetches a public Daily Yield
  page, so it cannot add a view to the blog it is cleaning.
"""
from __future__ import annotations

from site_change_control import stop_if_frozen as _dy_stop_if_frozen
# Owner's instruction of 22 October 2026, enforced here rather than in a workflow file: not one
# published article may go offline because of a workflow - a failed one, a scheduled one, any one. The
# nightly job that maintains this file uses the separate refresh tool and never deletes, but --apply is
# one dispatch away and --delete is one keystroke away, so while the site is frozen the whole program
# stops here, before it reads a single argument, with a held line and exit code 0 (a held action is not
# a failure, and a nightly red for an owner's own freeze is the noise that was retired on 22 October).
# The module's functions stay importable so the tests and an offline review of a saved pile can run.
if __name__ == "__main__":
    _dy_stop_if_frozen("blogger_duplicate_purge")

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

ROOT = Path(__file__).resolve().parent
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
OUT = ROOT / "BLOGGER_DUPLICATE_AUDIT.json"
MD = ROOT / "BLOGGER_DUPLICATE_AUDIT.md"
ARCHIVE = ROOT / "deleted_posts"
# Files whose URLs the rest of the operation depends on. Nothing listed here is deletable.
EVIDENCE_FILES = ("SLOT_GUARANTEE_STATUS.json", "LIVE_EDITION_VERIFICATION.json",
                  "MASTER_AUTOMATION_TRACKER.json", "facebook_tracker.json", "bluesky_tracker.json",
                  "tumblr_tracker.json", "mastodon_tracker.json", "instagram_tracker.json")
DUPLICATE_SLUG = re.compile(r"_\d{6,}\.html?$")
MAX_PER_RUN_DEFAULT = 25
CONFIRM_PHRASE = "DELETE-CONFIRMED-DUPLICATES"   # typed by a person, never by a schedule


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def normalise(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()


def protected_urls() -> set[str]:
    """Every URL that other automation already points at, collected from the evidence files."""
    found: set[str] = set()
    for name in EVIDENCE_FILES:
        text = ""
        path = ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"https://dailyyield\.blogspot\.com/[^\s\"']+", text):
            found.add(match.group(0).rstrip(","))
    return found


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


def api(url: str, token: str, method: str = "GET"):
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body.strip() else {}


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


def public_url(post: dict) -> str:
    return str(post.get("url") or "")


def analyse(posts: list[dict], protected: set[str]) -> dict:
    by_title: dict[str, list[dict]] = {}
    for post in posts:
        key = normalise(post.get("title"))
        if key:
            by_title.setdefault(key, []).append(post)
    groups = []
    for key, rows in sorted(by_title.items()):
        if len(rows) < 2:
            continue
        rows.sort(key=lambda row: (not DUPLICATE_SLUG.search(public_url(row) or ""),
                                   len(str(row.get("body") or ""))))
        keep, copies = rows[-1], rows[:-1]
        deletable, guarded = [], []
        for row in copies:
            entry = {"id": row.get("id"), "url": public_url(row), "title": (row.get("title") or "").strip(),
                     "published": (row.get("published") or "")[:10], "words": len(
                         re.sub(r"<[^>]+>", " ", str(row.get("body") or "")).split())}
            (guarded if entry["url"] in protected else deletable).append(entry)
        groups.append({"title": (keep.get("title") or "").strip(),
                       "keep": {"id": keep.get("id"), "url": public_url(keep),
                                "published": (keep.get("published") or "")[:10]},
                       "deletable": deletable, "protected": guarded})
    groups = [group for group in groups if group["deletable"] or group["protected"]]
    return {"titleGroups": len(groups),
            "duplicateUrls": sum(len(g["deletable"]) + len(g["protected"]) for g in groups),
            "removable": sum(len(g["deletable"]) for g in groups),
            "protectedOnly": sum(len(g["protected"]) for g in groups),
            "postsScanned": len(posts), "groups": groups}


def archive(copies: list[dict], token: str) -> int:
    ARCHIVE.mkdir(exist_ok=True)
    stored = 0
    for entry in copies:
        try:
            full = api(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/{entry['id']}?view=RAW", token)
        except Exception as exc:  # noqa: BLE001
            print(f"could not fetch {entry['id']} for archiving: {exc}", file=sys.stderr)
            continue
        (ARCHIVE / f"{entry['id']}.json").write_text(json.dumps(full, indent=1, ensure_ascii=False))
        stored += 1
    return stored


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="actually delete the duplicates; without this the run only reports")
    parser.add_argument("--max", type=int, default=MAX_PER_RUN_DEFAULT, help="batch cap for one run")
    parser.add_argument("--fixture", default="", help="JSON file of posts, for tests and offline review")
    parser.add_argument("--confirm", default="",
                        help=f"type {CONFIRM_PHRASE} to allow deletions; nothing else does")
    arguments = parser.parse_args()

    # Owner's instruction of 22 October 2026, enforced here rather than in a workflow file: not one
    # published article may go offline because of a workflow - a failed one, a scheduled one, any one.
    # The nightly job that runs this file uses `refresh` and never passes --apply, but --apply is one
    # dispatch away, so deletion now needs the owner's recorded release AND a word no schedule can type.
    if arguments.apply and arguments.confirm != CONFIRM_PHRASE:
            print(json.dumps({"ok": False, "mode": "REFUSED", "siteWrites": 0,
                             "error": f"deleting needs --confirm {CONFIRM_PHRASE}; duplicates are "
                                      "differentiated by the nightly refresh, and nothing is ever "
                                      "deleted by a run that did not have to type the word"}))
            return 0

    if arguments.fixture:
        posts = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
        token = ""
    else:
        for name in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN"):
            if not os.environ.get(name):
                print(json.dumps({"ok": False, "error": f"{name} is not configured; the audit reads the "
                                                        "blog through the authenticated API only"}))
                return 0
        token = oauth_token()
        posts = list_posts(token)

    protected = protected_urls()
    report = analyse(posts, protected)
    removable = [entry for group in report["groups"] for entry in group["deletable"]]
    batch = removable[: max(0, arguments.max)]

    removed, failed, archived = [], [], 0
    if arguments.apply and batch:
        archived = archive(batch, token)
        if archived < len(batch):
            print(json.dumps({"ok": False, "error": "every duplicate must be archived before anything is "
                                                    "deleted; stopping with nothing removed"}))
            return 0
        for entry in batch:
            try:
                api(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/{entry['id']}", token,
                    method="DELETE")
                removed.append(entry)
            except urllib.error.HTTPError as exc:
                failed.append({**entry, "error": f"HTTP {exc.code}"})
            except Exception as exc:  # noqa: BLE001
                failed.append({**entry, "error": clean(str(exc))[:160]})

    payload = {"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "mode": "APPLIED" if arguments.apply else "AUDIT_ONLY",
               "blogId": BLOG_ID, "postsScanned": report["postsScanned"],
               "titleGroups": report["titleGroups"], "duplicateUrls": report["duplicateUrls"],
               "removable": report["removable"], "protectedByEvidence": report["protectedOnly"],
               "batchCap": arguments.max, "selectedThisRun": len(batch),
               "removed": removed, "failed": failed, "archivedTo": str(ARCHIVE.name) if archived else "",
               "groups": report["groups"][:60]}
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    lines = [f"# Duplicate pile audit · {payload['checkedAt']}", "",
             f"Mode: **{payload['mode']}**", "",
             f"- posts scanned: **{report['postsScanned']}**",
             f"- exact-title duplicate groups: **{report['titleGroups']}**",
             f"- duplicate URLs inside them: **{report['duplicateUrls']}**",
             f"- removable (nothing in the evidence files points at them): **{report['removable']}**",
             f"- held back because the operation depends on them: **{report['protectedOnly']}**",
             f"- selected for this run: **{len(batch)}** (cap {arguments.max})",
             f"- actually deleted this run: **{len(removed)}**"
             + (f", failed: {len(failed)}" if failed else ""), ""]
    if payload["mode"] == "AUDIT_ONLY":
        lines.append("Nothing was deleted. Run with `action: apply` to remove the selected duplicates, "
                     "each of which is archived in `deleted_posts/` first.\n")
    for group in report["groups"][:25]:
        lines.append(f"### {group['title']}")
        lines.append(f"- keep `{group['keep']['url']}` (published {group['keep']['published']})")
        for entry in group["deletable"]:
            lines.append(f"- remove `{entry['url']}` ({entry['words']} words, {entry['published']})")
        for entry in group["protected"]:
            lines.append(f"- protected, in use by the operation: `{entry['url']}`")
        lines.append("")
    MD.write_text("\n".join(lines))
    print(json.dumps({key: payload[key] for key in ("mode", "postsScanned", "titleGroups", "duplicateUrls",
                                                    "removable", "protectedByEvidence", "selectedThisRun")},
                     ensure_ascii=False))
    if removed:
        print(json.dumps({"deleted": len(removed), "failed": len(failed)}, ensure_ascii=False))
    return 0


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


if __name__ == "__main__":
    sys.exit(main())
