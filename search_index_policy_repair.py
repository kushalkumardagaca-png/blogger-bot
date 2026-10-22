#!/usr/bin/env python3
"""Bring every live Post and Page into line with Bing's and Google's indexing rules.

The audit (search_index_policy_audit.py) judged all 597 URLs on 22 October 2026 and returned 11
violations. Most of them sit on content that already exists, so measuring them was half the job; this
file repairs the rest, on the Blogger API, one URL at a time.

Owner instruction, 22 October 2026: "Fix everything in all the current pages and post ... make sure
every page and post complies both the policies page". Nothing is indexed yet, which is the one moment
corrections like these cost nothing in search-result churn. The freeze itself stays on - this action is
released by name, with its scope recorded in SITE_CHANGE_POLICY.json, exactly the way that file says a
release must be recorded.

What it changes:

1. **Titles.** ALL CAPS to sentence case; a headline clipped onto a comma or an apostrophe-s re-cut on
   whole words; the 115-170 character legacy desk titles compacted to the site's own Bing-safe form; a
   title another live URL already carries given the numbered form, so two URLs stop competing for one
   query (Bing §6 §13).
2. **Alt text** on every image that has none (Bing §5 §12), through the seo_hygiene repair the site
   already trusts.
3. **URLs a crawler should never have been offered**: the September posts a bug created out of the
   string "http://schema.org", the redirect-notice page sitting in the sitemap, and any numbered copy
   whose original still carries the same text. These are **unpublished, not deleted** - Blogger's own
   ``unpublish`` call, reversible with ``publish`` - because Bing §9 wants removed content to answer 404
   and Bing §3 wants redirected URLs out of a sitemap.

What it never does: it does not rewrite an article's sentences, does not remove a photo, does not touch
labels beyond resending them, and does not raise the 12-46 character master-title window that
``master_article_v2.validate()`` enforces. A repair that invents copy is not a repair.

Safety: audit is the default and ``--apply`` is explicit; every item's previous title and complete body
are gzipped into a backup before the first write; a batch cap limits one run; the Blogger API is the only
endpoint used, so no public Daily Yield page is fetched and no view is added to the blog being fixed
(the client imported below enforces that); and any URL other automation points at is held back from
being taken down.
"""
from __future__ import annotations

import sys as _sys

from site_change_control import stop_if_frozen as _dy_stop_if_frozen
# The offline self-test writes nothing and reads nothing, so it is allowed to run while the freeze is on.
# Every other path through this file is checked against the owner's release for this action.
if __name__ == "__main__" and "--check" not in _sys.argv:
    _dy_stop_if_frozen('search_index_policy_repair')

import argparse
import gzip
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import index_policy_gate as gate
from seo_hygiene import compact_title, repair_image_alts, unique_title

ROOT = Path(__file__).resolve().parent
BACKUP = ROOT / "SEARCH_INDEX_POLICY_REPAIR_BACKUP.json.gz"
OUT = ROOT / "SEARCH_INDEX_POLICY_REPAIR.json"
MD = ROOT / "SEARCH_INDEX_POLICY_REPAIR.md"
PATCH_SPACING_SECONDS = 1.5
JUNK_SLUG_PREFIXES = ("context-httpsschema",)
REDIRECT_NOTICE_SLUGS = ("share-market_0718113516",)


def title_for(item: dict, taken: set[str], *, page_minimum: int = 4) -> str:
    """The title this URL should carry, or "" when the one it has is already compliant."""
    current = " ".join((item.get("title") or "").split())
    content = item.get("content") or ""
    candidate = current
    if item.get("resource") == "pages":
        # A standing page's title field is the label the site's own navigation shows - "About us",
        # "Contact us", "Privacy policy" - so sentence-casing it fixes the only defect the audit found
        # (all caps) and keeps the title matched to the URL it describes. Borrowing the page's banner
        # instead is what turned "ABOUT US" into "Money, explained with clarity evidence numbers honesty
        # context maths" on the first run of 22 October: the commas in that headline live in markup, and
        # stripping the tags ate them. So the banner is used only when the title field itself is empty or
        # is not a title at all.
        base = gate.sentence_case(current)
        candidate = (base if base and not gate.JUNK_TITLE.search(base)
                     else (gate.page_title(content) or base))
    else:
        # compact_title keeps a desk edition's date and shortens the desk name to fit, which is what
        # stops six editions of one desk publishing under one title.
        candidate = compact_title(current) or current
    floor = page_minimum if item.get("resource") == "pages" else gate.TITLE_MIN
    repaired = gate.publish_title(candidate, set(), minimum=floor)
    if not repaired:
        # Refusing to invent a headline is the correct failure. Fall back to a de-dangled trim of what
        # the site already had, and only then leave the title alone. A standing page gets no padding:
        # "About us at Daily Yield" would be a worse title than "About us", and Bing §13 does not ask
        # for length, it asks for a title that says what the page is.
        trimmed = gate.uncut_title(gate.sentence_case(current))
        if item.get("resource") != "pages" and len(trimmed) < gate.TITLE_MIN and trimmed:
            trimmed = f"{trimmed} at Daily Yield"
        repaired = gate.publish_title(trimmed, set(), minimum=floor) or current
    if gate.key(repaired) in taken:
        for ordinal in range(2, 8):
            attempt = unique_title(repaired, ordinal)
            if gate.key(attempt) not in taken:
                repaired = attempt
                break
    return repaired if repaired and repaired != current else ""


def plan(items: list[dict]) -> list[dict]:
    """Every change this run wants to make, computed from the inventory alone.

    "Taken" is never the full title list: an item may not be told its own title collides with itself,
    and two URLs that today share one title must not be repaired into sharing it again. So the set a row
    is compared against is every title still unprocessed plus every title this run has already assigned -
    which is what makes the second Banking edition come out as "... (2)".
    """
    ordered = sorted(items, key=lambda row: (row.get("published", "") or "", str(row.get("id", ""))))
    pending: Counter[str] = Counter(gate.key(row.get("title") or "") for row in ordered)
    assigned: set[str] = set()
    patches = []
    for item in ordered:
        current = " ".join((item.get("title") or "").split())
        own = gate.key(current)
        pending[own] -= 1
        others = {row for row, hits in pending.items() if hits > 0} | assigned
        title = title_for(item, others)
        reasons = []
        content = item.get("content") or ""
        if title:
            reasons.append(f"title {current!r} -> {title!r}")
            assigned.add(gate.key(title))
        else:
            title = current
        repaired, alts = repair_image_alts(content, title)
        if alts:
            reasons.append(f"{alts} image(s) given alt text")
            content = repaired
        if reasons:
            patches.append({"resource": item["resource"], "id": str(item["id"]), "url": item.get("url", ""),
                            "fromTitle": current, "toTitle": title, "reasons": reasons, "content": content,
                            "labels": item.get("labels") or [], "original": item})
    return patches


def takedowns(items: list[dict], protected: set[str]) -> dict:
    """Junk URLs and exact numbered copies, with the reasons and the holds that stop them."""
    by_base: dict[str, list[dict]] = {}
    for item in items:
        url = item.get("url", "")
        slug = re.sub(r"\.html$", "", url.rstrip("/").rsplit("/", 1)[-1])
        by_base.setdefault(re.sub(r"_\d{9,}$", "", slug), []).append(item)

    removable, held = [], []
    for base, group in sorted(by_base.items()):
        if len(group) < 2:
            continue
        # The copy is the URL Blogger numbered when the title collided - not the later one, and not the
        # shorter one. Publish order proves nothing: a re-run can be timestamped before the original.
        numbered = [row for row in group
                    if re.search(r"_\d{9,}\.html$", row.get("url", ""))]
        originals = [row for row in group if row not in numbered]
        if not originals:
            group.sort(key=lambda row: (row.get("published", "") or "", str(row.get("id", ""))))
            originals, numbered = group[:1], group[1:]
        original = min(originals, key=lambda row: row.get("url", ""))
        for copy in numbered:
            score = gate.similarity(original.get("content") or "", copy.get("content") or "")
            entry = {"resource": copy["resource"], "id": str(copy["id"]), "url": copy.get("url", ""),
                     "title": copy.get("title", ""), "base": base, "similarity": round(score, 2),
                     "original": original.get("url", "")}
            if entry["url"] in protected:
                entry["why"] = "held back: other automation links to this URL, so taking it down would " \
                               "break a live reference"
                held.append(entry)
            elif score < 0.6:
                entry["why"] = f"left alone: the two copies no longer say the same thing ({score:.0%} " \
                               "alike), so this is an edition rather than a duplicate"
                held.append(entry)
            else:
                entry["why"] = "the same article at a second, Blogger-numbered address (Bing §6 §9); the " \
                               "original URL keeps its content and this copy goes quiet"
                removable.append(entry)

    for item in items:
        url = item.get("url", "")
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if not (any(slug.startswith(row) for row in JUNK_SLUG_PREFIXES)
                or any(row in slug for row in REDIRECT_NOTICE_SLUGS)):
            continue
        words = len(gate.prose(gate.strip_markup(item.get("content") or "")).split())
        title = " ".join((item.get("title") or "").split())
        entry = {"resource": item["resource"], "id": str(item["id"]), "url": url, "title": title,
                 "words": words}
        # Slug alone is not evidence. On 22 October the two /2026/09/context-httpsschema* URLs turned out
        # to be "Your Portfolio Does Not Owe You Rent" and "Stop Maxing Your 401(k)" - real articles,
        # 1,900 words each, published under a slug that was left over from the template that made them.
        # Taking those down would have removed content to fix an address. A slug is corrected in Blogger's
        # post settings, which is an owner action, so this holds the URL and says what to change instead.
        if words >= gate.MIN_DOCUMENT_WORDS and not gate.JUNK_TITLE.search(title or "junk"):
            entry["why"] = (f"held back: the slug looks machine-made but the page is a real article of "
                            f"{words} words, so the defect is its permalink - a rename only the owner can "
                            "make in Blogger (Posts → the post → settings → Custom permalink), which would "
                            "need a 301 the platform does not offer on this host")
            held.append(entry)
        elif url in protected:
            entry["why"] = ("held back: other automation links to this URL, so removing it would break a "
                            "live reference")
            held.append(entry)
        else:
            entry["why"] = ("a machine artifact or a redirect notice - Bing §3 keeps sitemaps for pages a "
                            "reader was sent here to find, and this is not one")
            removable.append(entry)
    return {"unpublish": removable, "heldBack": held}


def apply(patches: list[dict], unpublished: list[dict], token: str) -> dict:
    from bing_seo_repair import BLOG_ID, patch_item, request_json   # the zero-view-guarded client

    done, failed = [], []
    for row in patches:
        try:
            patch_item(token, row["original"], row["toTitle"], row["content"])
            done.append({"action": "patch", "resource": row["resource"], "id": row["id"],
                         "url": row["url"], "title": row["toTitle"], "reasons": row["reasons"]})
        except Exception as exc:
            failed.append({"action": "patch", "id": row["id"], "url": row["url"],
                           "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
        time.sleep(PATCH_SPACING_SECONDS)
    for row in unpublished:
        # The API host, not blogger.com: the first run of 22 October sent these to www.blogger.com/v3,
        # which answered with HTML, and the job reported a takedown that had not happened. Verified here
        # by requiring the entry back, so "taken down" can only mean the API said so about this post.
        endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{row['resource']}/{row['id']}/unpublish"
        try:
            answer = request_json(endpoint, method="POST", headers={"Authorization": "Bearer " + token},
                                  body={})
            if str(answer.get("id", "")) != str(row["id"]) or answer.get("status") not in (None, "DRAFT"):
                raise RuntimeError(f"Blogger did not confirm the takedown: {answer.get('status')!r}")
            done.append({"action": "unpublish", "resource": row["resource"], "id": row["id"],
                         "url": row["url"], "reasons": [row["why"]]})
        except Exception as exc:
            failed.append({"action": "unpublish", "id": row["id"], "url": row["url"],
                           "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
        time.sleep(PATCH_SPACING_SECONDS)
    return {"written": len(done), "applied": done, "failed": failed}


def restore_rows(backup: list[dict]) -> list[dict]:
    """What a revert means, item by item: the title and content as they were, and the post made live again.

    Kept apart from the API calls so the rule itself is testable: every entry gets a patch (Blogger has no
    "undo"), and every entry is published afterwards because `unpublish` is part of what a run may have
    done and a patch alone would leave it quiet. Publishing something that is already live is a no-op, so
    applying it to all of them is safer than trying to remember which ones needed it.
    """
    rows = []
    for item in backup:
        rows.append({"resource": item.get("resource", "posts"), "id": str(item.get("id", "")),
                     "url": item.get("url", ""), "title": item.get("title", ""),
                     "content": item.get("content", ""), "publish": True})
    return rows


def read_backup(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(gzip.decompress(path.read_bytes()).decode())


def restore(rows: list[dict], token: str) -> dict:
    """Write the backup back. Reversible by definition, because it restores the previous state."""
    from bing_seo_repair import BLOG_ID, patch_item, request_json   # the zero-view-guarded client

    done, failed = [], []
    for row in rows:
        item = {"id": row["id"], "resource": row["resource"]}
        try:
            patch_item(token, item, row["title"], row["content"])
            if row["publish"]:
                endpoint = (f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{row['resource']}/"
                            f"{row['id']}/publish")
                request_json(endpoint, method="POST", headers={"Authorization": "Bearer " + token},
                             body={})
            done.append({"action": "restore", "resource": row["resource"], "id": row["id"],
                         "url": row["url"], "title": row["title"]})
        except Exception as exc:
            failed.append({"action": "restore", "id": row["id"], "url": row["url"],
                           "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
        time.sleep(PATCH_SPACING_SECONDS)
    return {"written": len(done), "failed": failed, "restored": done[:40]}


def render_markdown(payload: dict) -> str:
    head = (f"{payload['planned']['patches']} title and alt-text repairs planned · "
            f"{payload['planned']['unpublish']} URL(s) to take down · {payload['planned']['heldBack']} "
            "deliberately left alone")
    if payload["mode"] == "RESTORE":
        # A revert report has to be readable on its own: the number of URLs put back is the only thing a
        # person needs to check before they move on.
        head = (f"{payload['inventory']} URL(s) written back to the state the previous run found, with "
                "each one republished in case it had been taken down")
    lines = ["# Search index policy repair", "",
             f"**{payload['mode']}** · inventory {payload['inventory']} live URLs · {head}",
             f"- written this run: **{payload.get('written', 0)}** · failed: "
             f"{len(payload.get('failed', []))} · backup of everything touched: "
             f"`{payload['backup'] or 'none (audit only)'}`", "",
             "| url | why |", "|---|---|"]
    for row in payload["preview"]:
        lines.append(f"| `{row['url']}` | {'; '.join(row['reasons'])[:200]} |")
    if payload["unpublishPreview"]:
        lines += ["", "## URLs to take down", ""]
        lines += [f"- `{row['url']}` — {row['why'][:150]}" for row in payload["unpublishPreview"]]
    if payload["heldPreview"]:
        lines += ["", "## Left alone on purpose", ""]
        lines += [f"- `{row.get('url', '')}` — {row.get('why', '')[:150]}" for row in payload["heldPreview"]]
    if payload.get("alsoTakenDown"):
        lines += ["", "## Titles deliberately not polished first", "",
                  "These URLs are on the takedown list, so no title patch was spent on them: a page a "
                  "crawler is being told to forget does not need a better headline.", ""]
        lines += [f"- `{row}`" for row in payload["alsoTakenDown"][:20]]
    lines += ["", "## The limit of a repair like this", "",
              "Titles, alt attributes and the removal of junk URLs are all mechanical, so they are fixed "
              "here. Two findings in the audit are content decisions and stay with the desk: the country "
              "editions that share one template, and the evergreen library's photo file names. Both have "
              "a gate in `index_policy_gate.py` now, so new posts cannot make the mistake again.", ""]
    if payload.get("applied"):
        lines += ["## Written", ""]
        lines += [f"- {row['action']} `{row['url']}` — {'; '.join(row['reasons'])[:150]}"
                  for row in payload["applied"][:80]]
    return "\n".join(lines)


def self_test() -> dict:
    body = "<p>" + " ".join(f"settlement figure {index} moved on the desk before the bell"
                            for index in range(60)) + "</p>"
    items = [
        {"resource": "posts", "id": "1", "title": "Student Loan Interest Rates: Federal, Private,",
         "content": body, "url": "https://x.blogspot.com/2026/10/one.html",
         "published": "2026-10-20T01:00:00Z"},
        {"resource": "pages", "id": "2", "title": "CALCULATOR",
         "content": '<h2>EMI, SIP and loan calculators</h2>' + body,
         "url": "https://x.blogspot.com/p/calculator.html", "published": "2026-10-01T01:00:00Z"},
        {"resource": "posts", "id": "3", "title": "Gold rate today in India",
         "content": body + '<p><img src="https://bp.blogspot.com/a/photo-1.jpg"></p>',
         "url": "https://x.blogspot.com/2026/10/gold.html", "published": "2026-10-21T01:00:00Z"},
        {"resource": "posts", "id": "4", "title": "Asia Pacific Finance News — 18 October 2026",
         "content": body, "url": "https://x.blogspot.com/2026/10/twin.html",
         "published": "2026-10-18T01:00:00Z"},
        {"resource": "posts", "id": "5", "title": "Asia Pacific Finance News — 18 October 2026",
         "content": body, "url": "https://x.blogspot.com/2026/10/twin_01443792159.html",
         "published": "2026-10-18T02:00:00Z"},
        {"resource": "posts", "id": "6", "title": "http://schema.org", "content": body,
         "url": "https://x.blogspot.com/2026/09/context-httpsschema.html",
         "published": "2026-09-30T01:00:00Z"},
    ]
    patches = plan(items)
    planned = {row["url"]: row for row in patches}
    problems = []
    if "one.html" not in "".join(planned):
        problems.append("a title ending on a comma must be re-cut on whole words")
    if "calculator" not in "".join(planned):
        problems.append("an ALL-CAPS page title must be sentence-cased into the label readers see")
    elif planned["https://x.blogspot.com/p/calculator.html"]["toTitle"] != "Calculator":
        problems.append(f"a page label is sentence-cased, never invented: "
                        f"{planned['https://x.blogspot.com/p/calculator.html']['toTitle']!r}")
    # The page's own heading is borrowed only when there is no usable title to fix. The first run of
    # 22 October took "ABOUT US" from its banner and lost the commas that lived in markup, which read as
    # a word list; a page's own name is the safer title and still satisfies Bing 13.
    blank = plan([{"resource": "pages", "id": "7", "title": "", "labels": [], "status": "LIVE",
                   "content": "<h1>EMI, SIP and loan calculators</h1>" + body,
                   "url": "https://x.blogspot.com/p/blank.html", "published": "2026-10-01T01:00:00Z"}])
    if not blank or "calculators" not in blank[0]["toTitle"]:
        problems.append("a page with no title at all must be named from its own heading")
    if not any("alt text" in " ".join(row["reasons"]) for row in patches):
        problems.append("an image with no alt text must be repaired")
    outcomes = takedowns(items, protected=set())
    down = {row["url"] for row in outcomes["unpublish"]}
    if "https://x.blogspot.com/2026/10/twin_01443792159.html" not in down:
        problems.append("an exact numbered twin must be taken down")
    if "https://x.blogspot.com/2026/10/twin.html" in down:
        problems.append("the original URL is never the one taken down")
    if "https://x.blogspot.com/2026/09/context-httpsschema.html" not in down:
        problems.append("the schema-string post must leave the sitemap")
    held = takedowns(items, protected={"https://x.blogspot.com/2026/10/twin_01443792159.html"})
    if any(row["url"].endswith("twin_01443792159.html") for row in held["unpublish"]):
        problems.append("a URL other automation links to may never be taken down")
    if not any("held back" in row["why"] for row in held["heldBack"]):
        problems.append("the hold has to say why the URL was kept")
    if any(row["toTitle"] == row["fromTitle"] and not any("alt" in reason for reason in row["reasons"])
           for row in patches):
        problems.append("a row that changes neither title nor an image is a needless edit and a needless "
                        "freshened updated timestamp")
    known = [item for item in items if item["id"] not in {"1", "2", "5", "6"}]
    if any(row["toTitle"] != row["fromTitle"] for row in plan(known) if row["fromTitle"] ==
            "Gold rate today in India"):
        problems.append("a compliant title must be left exactly as it is")
    return {"status": "OK" if not problems else "FAIL", "mode": "offline self-test",
            "plannedPatches": len(patches), "unpublish": len(outcomes["unpublish"]),
            "heldBack": len(outcomes["heldBack"]), "problems": problems, "siteWrites": 0,
            "networkRequests": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the plan to Blogger (default: audit)")
    parser.add_argument("--max-patches", type=int, default=150, help="how many URLs one run may rewrite")
    parser.add_argument("--max-unpublish", type=int, default=12, help="how many URLs one run may take down")
    parser.add_argument("--only", default="all", choices=("all", "titles", "alts", "junk"))
    parser.add_argument("--fixture", default="", help="JSON inventory file for tests and offline review")
    parser.add_argument("--check", action="store_true", help="offline self-test: no network, no writes")
    parser.add_argument("--restore", nargs="?", const="auto", default="",
                        help="write BACKUP (or this path) back over the site: the undo of a bad run")
    arguments = parser.parse_args()

    if arguments.check:
        report = self_test()
        print(json.dumps(report))
        return 0 if report["status"] == "OK" else 1

    if arguments.restore != "":
        # The owner's release covers correcting titles, alt text and takedowns; putting those URLs back
        # exactly as the run found them is the same scope run in reverse, and it is the only honest answer
        # to a batch that was applied before it was reviewed.
        source = BACKUP if arguments.restore in ("", "auto") else Path(arguments.restore)
        rows = restore_rows(read_backup(source))
        outcome = {"written": 0, "failed": [], "restored": [], "backup": source.name}
        if rows:
            from bing_seo_repair import oauth
            outcome.update(restore(rows, oauth()))
        payload = {"ranAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "mode": "RESTORE", "inventory": len(rows),
                   "planned": {"patches": len(rows), "unpublish": 0, "heldBack": 0,
                               "titlesOnly": len(rows), "altsOnly": 0},
                   "preview": [{"url": row["url"], "reasons": ["restored from the run's own backup"],
                                "title": row["title"]} for row in outcome.get("restored", [])],
                   "unpublishPreview": [], "heldPreview": [],
                   "gate": "the plan this reverted was a policy repair; the repaired titles are gone",
                   **outcome}
        OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        MD.write_text(render_markdown(payload), encoding="utf-8")
        print(json.dumps({"mode": "RESTORE", "restored": payload["written"],
                          "failed": len(payload["failed"]), "siteWrites": payload["written"]}))
        return 0 if not payload["failed"] else 1

    if arguments.fixture:
        items = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
        token, protected = "", set()
    else:
        from bing_seo_repair import inventory, oauth
        from blogger_duplicate_purge import protected_urls
        token = oauth()
        items = inventory(token)
        protected = protected_urls()

    patches = plan(items)
    outcomes = takedowns(items, protected)
    if arguments.only == "titles":
        patches = [row for row in patches if row["toTitle"] != row["fromTitle"]]
    elif arguments.only == "alts":
        patches = [row for row in patches if any("alt text" in reason for reason in row["reasons"])]
    elif arguments.only == "junk":
        patches = []
    patches = patches[: arguments.max_patches]
    unpublished = (outcomes["unpublish"] if arguments.only in ("all", "junk")
                   else [])[: arguments.max_unpublish]
    going_down = {row["url"] for row in unpublished}
    # No point polishing the title of a URL that is about to answer 404: one write per URL, ever.
    skipped = [row for row in patches if row["url"] in going_down]
    patches = [row for row in patches if row["url"] not in going_down]

    payload = {"ranAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "mode": "APPLY" if arguments.apply else "AUDIT_ONLY",
               "inventory": len(items),
               "planned": {"patches": len(patches), "unpublish": len(unpublished),
                           "heldBack": len(outcomes["heldBack"]),
                           "titlesOnly": sum(1 for row in patches if row["toTitle"] != row["fromTitle"]),
                           "altsOnly": sum(1 for row in patches if row["toTitle"] == row["fromTitle"])},
               "alsoTakenDown": [row["url"] for row in skipped],
               "preview": [{"url": row["url"], "reasons": row["reasons"], "title": row["toTitle"]}
                           for row in patches[:40]],
               "unpublishPreview": unpublished[:20], "heldPreview": outcomes["heldBack"][:20],
               "gate": "index_policy_gate.py keeps every one of these rules on future publications",
               "backup": ""}
    if arguments.apply and (patches or unpublished):
        # The backup is the rollback: every URL this run is about to touch, with the title and the whole
        # body it had beforehand. Only touched items are stored, because a 2.4 MB snapshot of the entire
        # blog committed every run would be a repository of its own, and a restore needs exactly these.
        touched = {row["id"]: row["original"] for row in patches}
        touched.update({row["id"]: next(item for item in items if str(item["id"]) == row["id"])
                        for row in unpublished})
        BACKUP.write_bytes(gzip.compress(json.dumps(
            [{"resource": row["resource"], "id": str(row["id"]), "url": row.get("url", ""),
              "title": row.get("title", ""), "status": row.get("status", "LIVE"),
              "content": row.get("content", "")} for row in touched.values()],
            ensure_ascii=False).encode()))
        payload.update(apply(patches, unpublished, token))
        payload["backup"] = BACKUP.name
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    MD.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"mode": payload["mode"], "planned": payload["planned"],
                      "written": payload.get("written", 0),
                      "failed": len(payload.get("failed", [])), "siteWrites": payload.get("written", 0)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
