#!/usr/bin/env python3
"""
Performance Retrofit — Finance by CA Kushal (2026-09-24)
ZERO VISUAL CHANGES — one surgical, provably-invisible operation:

  Extract base64-embedded photos (>= 20 KB) from stored POST content, upload the
  IDENTICAL image bytes to the public blog-assets repo, verify the jsDelivr CDN
  URL serves them, then swap only the src value. Same pixels, same position,
  same styles — but loaded in parallel from a global CDN instead of inflating
  the HTML document. Adds decoding="async" and fetchpriority="high" (invisible
  browser hints) to the swapped imgs.

  Pages are NOT touched (their weight is genuine visual content: inline SVG art,
  live engines, Blogger's own injected data).

Safety design:
  - An img src is only swapped AFTER the CDN URL is confirmed to serve the asset.
  - First post is patched and re-verified (labels, published date, URL, content);
    any failure aborts the whole run.
  - Idempotent: re-running does nothing (base64 gone, CDN URLs skipped).
"""
import base64
import os
import re
import sys
import time

import requests

BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
ASSETS_PAT = os.environ["ASSETS_PAT"]
ASSETS_REPO = "kushalkumardagaca-png/blog-assets"
CDN_BASE = f"https://cdn.jsdelivr.net/gh/{ASSETS_REPO}@main"
BLOG_URL = "https://financebycakushal.blogspot.com/"

B64_IMG_RE = re.compile(
    r'<img\b[^>]*?\bsrc=(["\'])data:image/(jpeg|png|webp|gif);base64,([A-Za-z0-9+/=]+)\1[^>]*>',
    re.DOTALL,
)
EXT = {"jpeg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}
MIN_EXTRACT_BYTES = 20000  # only extract real photos; tiny inline icons stay put

totals = {"posts_cleaned": 0, "images_extracted": 0, "post_kb_saved": 0,
          "warnings": []}


def blogger_headers():
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ["BLOGGER_CLIENT_ID"],
            "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
            "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def wire_size_kb(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0",
                                       "Accept-Encoding": "gzip"}, timeout=30, stream=True)
        n = 0
        for chunk in r.iter_content(65536):
            n += len(chunk)
        return n // 1024
    except Exception:
        return -1


def gh_ensure_asset(name, data):
    """Upload bytes to blog-assets/heroes/{name}; return CDN URL. Reuses if same size."""
    api = f"https://api.github.com/repos/{ASSETS_REPO}/contents/heroes/{name}"
    h = {"Authorization": f"token {ASSETS_PAT}", "Accept": "application/vnd.github+json"}
    sha = None
    r = requests.get(api, headers=h, timeout=30)
    if r.status_code == 200:
        meta = r.json()
        if meta.get("size") == len(data):
            return f"{CDN_BASE}/heroes/{name}"  # already there, identical
        sha = meta.get("sha")  # different content -> update
    body = {"message": f"hero asset: {name}",
            "content": base64.b64encode(data).decode()}
    if sha:
        body["sha"] = sha
    r = requests.put(api, headers=h, json=body, timeout=120)
    r.raise_for_status()
    return f"{CDN_BASE}/heroes/{name}"


def cdn_serves(url):
    """Confirm the CDN URL is live before we point the blog at it."""
    for _ in range(10):
        try:
            r = requests.head(url, headers={"User-Agent": "Mozilla/5.0"},
                              timeout=20, allow_redirects=True)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def big_base64_imgs(content):
    out = []
    for m in B64_IMG_RE.finditer(content):
        if len(base64.b64decode(m.group(3), validate=False)) >= MIN_EXTRACT_BYTES:
            out.append(m)
    return out


def clean_posts(H):
    print("=" * 70)
    print("Extracting base64 photos from POSTS to CDN (zero visual change)")
    print("=" * 70)
    base = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}"
    items, token = [], None
    while True:
        params = {"maxResults": "50", "status": "live", "fetchBodies": "true"}
        if token:
            params["pageToken"] = token
        r = requests.get(f"{base}/posts", params=params, headers=H, timeout=60)
        r.raise_for_status()
        j = r.json()
        items.extend(j.get("items", []))
        token = j.get("nextPageToken")
        if not token:
            break
    print(f"Posts found: {len(items)}")
    first = True
    for post in items:
        pid, title = post["id"], post.get("title", "?")[:36]
        try:
            content = post.get("content", "")
            orig_len = len(content)
            big = big_base64_imgs(content)
            if not big:
                continue

            parts, last, extracted = [], 0, 0
            for m in big:
                img_tag = m.group(0)
                mime, b64 = m.group(2), m.group(3)
                data = base64.b64decode(b64)
                fname = f"post-{pid}-{extracted}.{EXT[mime]}"
                extracted += 1
                cdn_url = gh_ensure_asset(fname, data)
                if not cdn_serves(cdn_url):
                    print(f"    {fname}: CDN not confirmed — keeping embedded (WARN)")
                    totals["warnings"].append(f"{fname}: CDN unverified, kept base64")
                    continue
                old_src = f'src={m.group(1)}data:image/{mime};base64,{b64}{m.group(1)}'
                new_src = f'src={m.group(1)}{cdn_url}{m.group(1)}'
                new_tag = img_tag.replace(old_src, new_src, 1)
                hints = ""
                if "fetchpriority=" not in new_tag:
                    hints += ' fetchpriority="high"'
                if "decoding=" not in new_tag:
                    hints += ' decoding="async"'
                if hints:
                    if new_tag.endswith("/>"):
                        new_tag = new_tag[:-2].rstrip() + hints + " />"
                    elif new_tag.endswith(">"):
                        new_tag = new_tag[:-1].rstrip() + hints + ">"
                parts.append(content[last:m.start()])
                parts.append(new_tag)
                last = m.end()
            if last == 0:
                print(f"  [{title:36s}] no extractable images — skip")
                continue
            parts.append(content[last:])
            new_content = "".join(parts)
            saved_kb = (orig_len - len(new_content)) // 1024

            # Safety gates
            if len(new_content) < 20000 or orig_len - len(new_content) < 1000:
                print(f"  [{title:36s}] !! size change outside bounds — SKIP")
                totals["warnings"].append(f"{title}: unexpected size delta, skipped")
                continue

            body = dict(post)
            body["content"] = new_content
            upd = requests.put(f"{base}/posts/{pid}", headers=H, json=body, timeout=60)
            if upd.status_code >= 400:
                minimal = {"kind": "blogger#post", "id": pid,
                           "title": post.get("title", ""),
                           "content": new_content,
                           "labels": post.get("labels", []),
                           "published": post.get("published", "")}
                upd = requests.put(f"{base}/posts/{pid}", headers=H, json=minimal,
                                   timeout=60)
            upd.raise_for_status()

            # Verify: labels, published date, url unchanged; big base64 gone
            chk = requests.get(f"{base}/posts/{pid}", params={"fetchBody": "true"},
                               headers=H, timeout=30)
            chk.raise_for_status()
            after = chk.json()
            ok = (after.get("labels") == post.get("labels")
                  and after.get("published") == post.get("published")
                  and after.get("url") == post.get("url")
                  and not big_base64_imgs(after.get("content", "")))
            print(f"  [{title:36s}] {extracted} img(s) -> CDN, {saved_kb} KB saved, "
                  f"verify {'OK' if ok else 'FAILED'}")
            if not ok:
                if first:
                    print("!! First-post verification failed — aborting whole run.")
                    sys.exit(1)
                totals["warnings"].append(f"{title}: post verification failed")
            else:
                totals["posts_cleaned"] += 1
                totals["post_kb_saved"] += saved_kb
                totals["images_extracted"] += extracted
        except SystemExit:
            raise
        except Exception as e:
            print(f"  [{title:36s}] ERROR: {e}")
            if first:
                sys.exit(1)
            totals["warnings"].append(f"{title}: {e}")
        first = False


def main():
    print("Performance retrofit (posts only) — zero visual changes")
    H = blogger_headers()
    print("OAuth token acquired.")
    clean_posts(H)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Posts cleaned:         {totals['posts_cleaned']} "
          f"({totals['post_kb_saved']} KB HTML saved)")
    print(f"Images moved to CDN:   {totals['images_extracted']}")
    if totals["warnings"]:
        print(f"Warnings ({len(totals['warnings'])}):")
        for w in totals["warnings"]:
            print(f"  - {w}")

    print("\nGzip wire sizes (live check):")
    for url in [BLOG_URL + "2026/09/run-recession-checklist-while-employed.html",
                BLOG_URL + "2026/09/what-quiet-rich-people-do-on-payday.html",
                BLOG_URL + "2026/09/find-200month-in-10-minutes.html",
                BLOG_URL]:
        print(f"  {wire_size_kb(url):5d} KB  {url}")

    if totals["warnings"]:
        sys.exit(1)
    print("\nRETROFIT COMPLETE — no warnings.")


if __name__ == "__main__":
    main()
