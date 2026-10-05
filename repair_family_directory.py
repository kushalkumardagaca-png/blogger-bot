#!/usr/bin/env python3
"""Restore the canonical Daily Yield family directory in every live Post and Page.

The repair uses the authenticated Blogger API only. It never requests a public
Daily Yield URL, so it creates zero synthetic pageviews. A compressed recovery
backup is written before any update and every changed item is re-read from the
API for exact post-deployment verification.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from page_family import END, START, family_block

BACKUP = Path("FAMILY_DIRECTORY_REPAIR_BACKUP.json.gz")
REPORT_JSON = Path("FAMILY_DIRECTORY_REPAIR_REPORT.json")
REPORT_MD = Path("FAMILY_DIRECTORY_REPAIR_REPORT.md")
REQUIRED_SELECTORS = (
    "#dyPageFamily .dyf-kicker",
    "#dyPageFamily .dyf-grid",
    "#dyPageFamily .dyf-card",
    "#dyPageFamily .dyf-card strong",
    "#dyPageFamily .dyf-card small",
    "#dyPageFamily .dyf-utility",
    "#dyPageFamily .dyf-social-links",
    "#dyPageFamily .dyf-social-links a",
    "#dyPageFamily .dyf-subscribe",
)
FORBIDDEN_JOINED_SELECTORS = tuple(value.replace(" ", "") for value in REQUIRED_SELECTORS)


def auth_headers() -> dict[str, str]:
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ["BLOGGER_CLIENT_ID"],
            "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
            "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    response.raise_for_status()
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def request(method: str, url: str, **kwargs):
    last = None
    for attempt in range(5):
        try:
            response = requests.request(method, url, timeout=120, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"transient Blogger API {response.status_code}", response=response)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = exc
            if attempt < 4:
                time.sleep(2**attempt)
    raise last


def list_all(base: str, kind: str, headers: dict[str, str]) -> list[dict]:
    items, token = [], None
    while True:
        params = {"fetchBodies": "true", "maxResults": "50", "status": "live"}
        if token:
            params["pageToken"] = token
        data = request("GET", f"{base}/{kind}", headers=headers, params=params).json()
        items.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            return items


def item_path(kind: str, item: dict) -> str:
    return urlparse(item.get("url", "")).path if kind == "pages" else ""


def canonical_family(content: str, current_path: str = "") -> str:
    return family_block(current_path, include_follow='<!-- DY_MASTER_V2 -->' not in (content or ''))


def canonicalize(content: str, current_path: str = "") -> str:
    """Replace only the marked family block; preserve all editorial content."""
    block = canonical_family(content, current_path)
    pattern = re.escape(START) + r".*?" + re.escape(END)
    updated, count = re.subn(pattern, lambda _match: block, content or "", flags=re.S)
    if count:
        return updated
    return (content or "").rstrip() + "\n" + block


def block_from(content: str) -> str:
    match = re.search(re.escape(START) + r".*?" + re.escape(END), content or "", re.S)
    return match.group(0) if match else ""


def verify_content(content: str, current_path: str = "") -> list[str]:
    issues = []
    block = block_from(content)
    if content.count(START) != 1 or content.count(END) != 1:
        issues.append("family markers are not unique")
    if content.count('id="dyPageFamily"') != 1:
        issues.append("family directory id is not unique")
    if block != canonical_family(content, current_path):
        issues.append("family block differs from canonical source")
    for selector in REQUIRED_SELECTORS:
        if selector not in block:
            issues.append("missing descendant selector: " + selector)
    for selector in FORBIDDEN_JOINED_SELECTORS:
        if selector in block:
            issues.append("corrupted joined selector: " + selector)
    if block.count('class="dyf-card') != 7:
        issues.append("expected seven family cards")
    expected_socials = 0 if '<!-- DY_MASTER_V2 -->' in (content or '') else 4
    if block.count('aria-label="Follow Daily Yield on ') != expected_socials:
        issues.append(f"expected {expected_socials} family-block social-profile links")
    return issues


def update(base: str, kind: str, item: dict, content: str, headers: dict[str, str]) -> None:
    singular = "post" if kind == "posts" else "page"
    body = {
        "kind": f"blogger#{singular}",
        "id": item["id"],
        "title": item["title"],
        "content": content,
    }
    if kind == "posts":
        body["labels"] = item.get("labels", [])
    request("PUT", f"{base}/{kind}/{item['id']}", headers=headers, json=body)


def main() -> int:
    blog_id = os.environ["BLOGGER_BLOG_ID"]
    base = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}"
    headers = auth_headers()
    inventory = {kind: list_all(base, kind, headers) for kind in ("posts", "pages")}

    with gzip.open(BACKUP, "wt", encoding="utf-8") as archive:
        json.dump({"version": 1, "items": inventory}, archive, ensure_ascii=False)

    changed = []
    for kind, items in inventory.items():
        for item in items:
            path = item_path(kind, item)
            old = item.get("content", "")
            new = canonicalize(old, path)
            if new == old:
                continue
            update(base, kind, item, new, headers)
            changed.append({"kind": kind[:-1], "id": item["id"], "title": item["title"], "url": item.get("url", "")})
            time.sleep(0.08)

    verified = {kind: list_all(base, kind, headers) for kind in ("posts", "pages")}
    failures = []
    for kind, items in verified.items():
        for item in items:
            issues = verify_content(item.get("content", ""), item_path(kind, item))
            if issues:
                failures.append({"kind": kind[:-1], "id": item["id"], "title": item["title"], "issues": issues})

    report = {
        "status": "PASS" if not failures else "FAIL",
        "mode": "AUTHENTICATED_BLOGGER_API_ZERO_VIEW",
        "syntheticViews": 0,
        "postsChecked": len(verified["posts"]),
        "pagesChecked": len(verified["pages"]),
        "itemsChanged": len(changed),
        "changed": changed,
        "failures": failures,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Daily Yield Family Directory Repair",
        "",
        f"- Status: **{report['status']}**",
        f"- Posts checked: **{report['postsChecked']}**",
        f"- Pages checked: **{report['pagesChecked']}**",
        f"- Items changed: **{report['itemsChanged']}**",
        "- Synthetic Daily Yield views: **0**",
        "",
    ]
    if failures:
        lines.extend(f"- ❌ {row['kind']} · {row['title']}: {', '.join(row['issues'])}" for row in failures)
    else:
        lines.append("- ✅ Every live Post and Page contains the exact canonical responsive family directory.")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "postsChecked", "pagesChecked", "itemsChanged", "syntheticViews")}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
