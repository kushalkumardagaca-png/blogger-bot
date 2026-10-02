#!/usr/bin/env python3
"""One-time and repeat-safe Bing SEO repair for every live Blogger Post and Page.

Uses only authenticated Blogger API calls. It never requests a public Daily
Yield URL and writes a complete pre-change backup before applying updates.
"""
from __future__ import annotations

import gzip
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from seo_hygiene import (
    MAX_TITLE_CHARS, compact_title, description_from_content,
    image_alt_failures, repair_image_alts, unique_title,
)
from seo_meta import ensure_seo_meta

BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
BACKUP = Path("BING_SEO_REPAIR_BACKUP.json.gz")
REPORT_JSON = Path("BING_SEO_REPAIR_REPORT.json")
REPORT_MD = Path("BING_SEO_REPAIR_REPORT.md")


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required secret: {name}")
    return value


def request_json(url: str, *, method="GET", headers=None, body=None) -> dict:
    if "dailyyield.blogspot.com" in url.lower():
        raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
    data = json.dumps(body).encode() if body is not None else None
    merged = {"User-Agent": "DailyYield-BingSEORepair/1.0", **(headers or {})}
    if body is not None:
        merged["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=merged, method=method)
    with urllib.request.urlopen(request, timeout=75) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def oauth() -> str:
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def inventory(token: str) -> list[dict]:
    headers = {"Authorization": "Bearer " + token}
    items = []
    for resource in ("pages", "posts"):
        page_token = ""
        while True:
            fields = "id,title,url,content,published,updated,status"
            if resource == "posts":
                fields += ",labels"
            params = {"status": "live", "fetchBodies": "true", "maxResults": "50", "fields": f"items({fields}),nextPageToken"}
            if page_token:
                params["pageToken"] = page_token
            data = request_json(
                f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{resource}?{urllib.parse.urlencode(params)}",
                headers=headers,
            )
            for item in data.get("items", []):
                item["resource"] = resource
                items.append(item)
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
    return items


def desired_titles(items: list[dict]) -> dict[str, str]:
    """Compact titles and retain deterministic uniqueness after compaction."""
    result, counts = {}, {}
    ordered = sorted(items, key=lambda x: (x.get("published", ""), x.get("id", "")))
    for item in ordered:
        base = compact_title(item.get("title", ""))
        key = (item["resource"], base.casefold())
        counts[key] = counts.get(key, 0) + 1
        result[f"{item['resource']}:{item['id']}"] = unique_title(base, counts[key])
    return result


def patch_item(token: str, item: dict, title: str, content: str) -> dict:
    body = {"title": title, "content": content}
    if item["resource"] == "posts":
        body["labels"] = item.get("labels", [])
    endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{item['resource']}/{item['id']}"
    return request_json(endpoint, method="PATCH", headers={"Authorization": "Bearer " + token}, body=body)


def audit(items: list[dict], expected_urls: dict[str, str]) -> list[dict]:
    failures = []
    seen = set()
    for item in items:
        title = item.get("title", "").strip()
        key = (item["resource"], title.casefold())
        if item.get("url", "") != expected_urls.get(f"{item['resource']}:{item['id']}", ""):
            failures.append({"id": item["id"], "issue": "URL changed", "value": item.get("url", "")})
        if len(title) > MAX_TITLE_CHARS:
            failures.append({"id": item["id"], "issue": "title too long", "value": title})
        if key in seen:
            failures.append({"id": item["id"], "issue": "duplicate compact title", "value": title})
        seen.add(key)
        missing = image_alt_failures(item.get("content", ""))
        if missing:
            failures.append({"id": item["id"], "issue": f"{missing} image alt value(s) missing", "value": title})
        if "DY_SEO_META_START" not in item.get("content", ""):
            failures.append({"id": item["id"], "issue": "SEO description package missing", "value": title})
    return failures


def main() -> int:
    token = oauth()
    before = inventory(token)
    with gzip.open(BACKUP, "wt", encoding="utf-8") as archive:
        json.dump({"capturedAt": datetime.now(timezone.utc).isoformat(), "items": before}, archive, ensure_ascii=False)

    titles = desired_titles(before)
    rows = []
    for number, item in enumerate(before, 1):
        old_title = item.get("title", "").strip()
        new_title = titles[f"{item['resource']}:{item['id']}"]
        content, alt_repairs = repair_image_alts(item.get("content", ""), new_title)
        description = description_from_content(new_title, content)
        content = ensure_seo_meta(content, new_title, description)
        changed = old_title != new_title or content != item.get("content", "")
        if changed:
            patch_item(token, item, new_title, content)
            time.sleep(0.08)
        rows.append({
            "kind": item["resource"][:-1], "id": item["id"], "url": item.get("url", ""),
            "oldTitle": old_title, "newTitle": new_title,
            "titleChanged": old_title != new_title, "altRepairs": alt_repairs,
            "descriptionLength": len(description), "updated": changed,
        })
        if number % 25 == 0:
            print(f"Processed {number}/{len(before)} authenticated items")

    after = inventory(token)
    failures = audit(after, {f"{item['resource']}:{item['id']}": item.get("url", "") for item in before})
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "AUTHENTICATED_BLOGGER_API_ZERO_PUBLIC_VIEWS",
        "syntheticViews": 0,
        "inventory": {"total": len(after), "posts": sum(x["resource"] == "posts" for x in after), "pages": sum(x["resource"] == "pages" for x in after)},
        "updatedItems": sum(row["updated"] for row in rows),
        "titlesChanged": sum(row["titleChanged"] for row in rows),
        "imageAltsRepaired": sum(row["altRepairs"] for row in rows),
        "descriptionPackagesPresent": sum("DY_SEO_META_START" in x.get("content", "") for x in after),
        "failures": failures,
        "items": rows,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = [
        "# Bing SEO Full-Inventory Repair", "",
        f"- Inventory: **{report['inventory']['total']}** ({report['inventory']['posts']} Posts · {report['inventory']['pages']} Pages)",
        f"- Updated items: **{report['updatedItems']}**",
        f"- Titles shortened: **{report['titlesChanged']}**",
        f"- Empty/missing image alts repaired: **{report['imageAltsRepaired']}**",
        f"- SEO description packages: **{report['descriptionPackagesPresent']}/{report['inventory']['total']}**",
        f"- Remaining failures: **{len(failures)}**", "- Synthetic Daily Yield views: **0**", "",
    ]
    for failure in failures:
        lines.append(f"- ❌ {failure['id']} · {failure['issue']} · {failure['value']}")
    REPORT_MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({key: report[key] for key in ("inventory", "updatedItems", "titlesChanged", "imageAltsRepaired", "descriptionPackagesPresent")}, indent=2))
    if failures:
        raise RuntimeError(f"Bing SEO repair left {len(failures)} authenticated inventory failure(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
