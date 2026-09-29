#!/usr/bin/env python3
"""Install the shared Daily Yield family directory on every active static page."""
from pathlib import Path
import json, os, re, requests
from page_family import ACTIVE_PAGES, BLOG, END, START, ensure_family
from social_identity import SOCIAL_PROFILES

BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
BASE = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}"


def headers():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["BLOGGER_CLIENT_ID"],
        "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def list_pages(h):
    out, token = [], None
    while True:
        params = {"fetchBodies": "true", "maxResults": "50"}
        if token:
            params["pageToken"] = token
        r = requests.get(BASE + "/pages", headers=h, params=params, timeout=90)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            return out


def page_path(page):
    url = page.get("url", "")
    return url[len(BLOG):] if url.startswith(BLOG) else ""


def update(h, page, content):
    body = {"kind": "blogger#page", "id": page["id"], "title": page["title"], "content": content}
    r = requests.put(f"{BASE}/pages/{page['id']}", headers=h, json=body, timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    h = headers()
    pages = list_pages(h)
    by_path = {page_path(p): p for p in pages}
    missing = [path for path in ACTIVE_PAGES if path not in by_path]
    if missing:
        raise RuntimeError("active Blogger pages missing: " + ", ".join(missing))

    backup = []
    for path in ACTIVE_PAGES:
        p = by_path[path]
        backup.append({"id": p["id"], "title": p["title"], "url": p["url"], "content": p.get("content", "")})
    Path("page_family_backup.json").write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")

    changed, unchanged = [], []
    for path in ACTIVE_PAGES:
        p = by_path[path]
        old = p.get("content", "")
        new = ensure_family(old, path)
        if new == old:
            unchanged.append(path)
        else:
            update(h, p, new)
            changed.append(path)

    refreshed = {page_path(p): p for p in list_pages(h)}
    checks = []
    social_urls = [url for _name, url, _handle in SOCIAL_PROFILES]
    for path in ACTIVE_PAGES:
        p = refreshed[path]
        content = p.get("content", "")
        match = re.search(re.escape(START) + r".*?" + re.escape(END), content, re.S)
        managed = match.group(0) if match else ""
        social_counts = {url: managed.count(url) for url in social_urls}
        ok = (content.count(START) == 1 and content.count('id="dyPageFamily"') == 1
              and managed.count('class="dyf-social"') == 1
              and all(count == 1 for count in social_counts.values())
              and "/p/markets-today.html" in managed and "/p/global-snapshot.html" in managed
              and "/p/share-market_0718113516.html" not in managed and "Market Explorer" not in managed)
        checks.append({"path": path, "title": p["title"], "verified": ok,
                       "managed_block_found": bool(match), "social_counts": social_counts})

    verified = all(c["verified"] for c in checks)
    result = {"changed": changed, "unchanged": unchanged, "verified_pages": checks, "verified": verified}
    Path("page_family_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not verified:
        raise RuntimeError("one or more managed family blocks failed verification; inspect page_family_result.json")


if __name__ == "__main__":
    main()
