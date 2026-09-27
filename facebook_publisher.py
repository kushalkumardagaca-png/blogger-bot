#!/usr/bin/env python3
"""Daily Yield Facebook Page publisher.

Reads publication candidates only through the authenticated Blogger API. It never
opens, HEADs, or downloads a Daily Yield public URL. Facebook posts are created as
photo posts so Meta fetches an approved third-party editorial image (or we upload a
repository brand image) rather than requesting the article for a link preview.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "1303333369533572")
GRAPH_VERSION = os.environ.get("FACEBOOK_GRAPH_VERSION", "v26.0")
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
TRACKER_PATH = Path(os.environ.get("FACEBOOK_TRACKER", "facebook_tracker.json"))
BRAND_IMAGE = Path("assets/brand/daily-yield-social-banner.png")
MAX_CANDIDATE_AGE_HOURS = 42
TIMEOUT = (15, 75)

HIGH_IMPACT = {
    "breaking": 18, "market": 9, "rates": 11, "inflation": 11,
    "economy": 9, "recession": 12, "budget": 10, "tax": 10,
    "bank": 8, "stocks": 8, "invest": 8, "money": 7,
    "policy": 9, "trade": 8, "oil": 8, "gold": 7,
    "jobs": 8, "earnings": 7, "fund": 6, "debt": 8,
}


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required secret: {name}")
    return value


def request_json(method: str, url: str, *, retries: int = 3, **kwargs) -> dict:
    """Retry only read/token operations. Publishing has separate reconciliation."""
    last = None
    for attempt in range(retries):
        try:
            response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
            if response.status_code >= 500 and attempt + 1 < retries:
                time.sleep(2 ** attempt)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"request failed for {url}: {exc}") from exc
    raise RuntimeError(str(last))


def blogger_access_token() -> str:
    data = {
        "client_id": required_env("BLOGGER_CLIENT_ID"),
        "client_secret": required_env("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required_env("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }
    result = request_json("POST", "https://oauth2.googleapis.com/token", data=data)
    return result["access_token"]


def blogger_candidates(token: str) -> list[dict]:
    # Authenticated API inventory only: never request a Daily Yield public page.
    endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts"
    params = {
        "status": "live",
        "fetchBodies": "true",
        "maxResults": "50",
        "orderBy": "published",
        "fields": "items(id,title,url,published,updated,labels,content)",
    }
    data = request_json(
        "GET", endpoint, params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_CANDIDATE_AGE_HOURS)
    result = []
    for post in data.get("items", []):
        try:
            published = datetime.fromisoformat(post["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if published >= cutoff and post.get("url", "").startswith("https://dailyyield.blogspot.com/"):
            result.append(post)
    return result


def load_tracker() -> dict:
    if TRACKER_PATH.exists():
        data = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
        data.setdefault("published", [])
        data.setdefault("pending", None)
        return data
    return {"version": 1, "page_id": PAGE_ID, "published": [], "pending": None}


def save_tracker(tracker: dict) -> None:
    TRACKER_PATH.write_text(json.dumps(tracker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def clean_text(fragment: str) -> str:
    fragment = re.sub(r"<script\b[^>]*>.*?</script>", " ", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<style\b[^>]*>.*?</style>", " ", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def summary_from_content(content: str, title: str) -> str:
    patterns = [
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
        r"<p\b[^>]*>(.*?)</p>",
    ]
    for pattern in patterns:
        match = re.search(pattern, content or "", flags=re.I | re.S)
        if match:
            text = clean_text(match.group(1))
            if len(text) >= 45 and title.lower() not in text.lower():
                return text[:260].rsplit(" ", 1)[0].rstrip(" ,;:-") + ("…" if len(text) > 260 else "")
    return "Clear context, verified sources and practical implications from Daily Yield."


def image_from_content(content: str) -> str | None:
    for source in re.findall(r'<img\b[^>]+src=["\']([^"\']+)', content or "", flags=re.I):
        source = html.unescape(source)
        host = (urlparse(source).hostname or "").lower()
        # Only third-party editorial imagery is eligible. Never fetch Blogger/blog images.
        if host == "images.unsplash.com" or host.endswith(".images.unsplash.com"):
            return source
    return None


def score(post: dict, now: datetime) -> float:
    published = parse_time(post["published"])
    age_hours = max(0.0, (now - published).total_seconds() / 3600)
    title = post.get("title", "")
    labels = [str(x) for x in post.get("labels", [])]
    haystack = (title + " " + " ".join(labels)).lower()
    value = max(0.0, 50.0 - age_hours)
    if "news" not in {x.lower() for x in labels}:
        value += 30  # Long-form master articles have more durable Facebook value.
    if published.astimezone(IST).date() == now.astimezone(IST).date():
        value += 20
    for keyword, weight in HIGH_IMPACT.items():
        if keyword in haystack:
            value += weight
    if any(x in haystack for x in ("global", "india", "us ", "market", "personal finance")):
        value += 5
    return round(value, 3)


def hashtags(post: dict) -> str:
    text = (post.get("title", "") + " " + " ".join(post.get("labels", []))).lower()
    tags = ["#DailyYield"]
    if any(x in text for x in ("market", "stock", "invest", "fund", "trading")):
        tags.append("#Markets")
    elif any(x in text for x in ("money", "saving", "tax", "debt", "personal")):
        tags.append("#PersonalFinance")
    else:
        tags.append("#Finance")
    if any(x in text for x in ("economy", "inflation", "rates", "policy", "gdp")):
        tags.append("#Economy")
    return " ".join(tags[:3])


def make_caption(post: dict) -> str:
    title = clean_text(post.get("title", "Daily Yield"))
    summary = summary_from_content(post.get("content", ""), title)
    url = post["url"]
    return (
        f"{title}\n\n{summary}\n\n"
        f"Read the full Daily Yield report: {url}\n\n"
        f"By Kushal K. Daga · Markets · Money · Better decisions\n\n"
        f"{hashtags(post)}"
    )


def fingerprint(caption: str) -> str:
    return hashlib.sha256(caption.encode("utf-8")).hexdigest()[:20]


def choose_candidate(posts: list[dict], tracker: dict) -> dict | None:
    seen_ids = {str(x.get("blogger_id")) for x in tracker["published"]}
    seen_urls = {x.get("url", "").rstrip("/") for x in tracker["published"]}
    now = datetime.now(timezone.utc)
    eligible = [p for p in posts if str(p.get("id")) not in seen_ids and p.get("url", "").rstrip("/") not in seen_urls]
    if not eligible:
        return None
    return max(eligible, key=lambda p: (score(p, now), parse_time(p["published"])))


def graph_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error", payload)
        return f"HTTP {response.status_code}: {error.get('message', error)} (code={error.get('code', '?')})"
    except Exception:
        return f"HTTP {response.status_code}: {response.text[:500]}"


def verify_page(access_token: str) -> dict:
    return request_json(
        "GET", f"{GRAPH_ROOT}/{PAGE_ID}",
        params={"fields": "id,name", "access_token": access_token},
    )


def recent_page_posts(access_token: str) -> list[dict]:
    data = request_json(
        "GET", f"{GRAPH_ROOT}/{PAGE_ID}/posts", retries=2,
        params={
            "fields": "id,message,created_time",
            "limit": "25",
            "access_token": access_token,
        },
    )
    return data.get("data", [])


def reconcile(access_token: str, url: str, caption_hash: str) -> dict | None:
    """Find a possibly successful post after an ambiguous network/API response."""
    try:
        for item in recent_page_posts(access_token):
            message = item.get("message", "")
            if url in message and fingerprint(message) == caption_hash:
                return item
    except Exception as exc:
        print(f"Reconciliation read failed: {exc}", file=sys.stderr)
    return None


def publish_photo(post: dict, caption: str, access_token: str) -> dict:
    endpoint = f"{GRAPH_ROOT}/{PAGE_ID}/photos"
    payload = {"message": caption, "published": "true", "access_token": access_token}
    image_url = image_from_content(post.get("content", ""))
    try:
        if image_url:
            response = requests.post(endpoint, data={**payload, "url": image_url}, timeout=TIMEOUT)
        else:
            if not BRAND_IMAGE.exists():
                raise RuntimeError(f"fallback image is missing: {BRAND_IMAGE}")
            with BRAND_IMAGE.open("rb") as image:
                response = requests.post(
                    endpoint, data=payload,
                    files={"source": (BRAND_IMAGE.name, image, "image/png")},
                    timeout=TIMEOUT,
                )
        if response.ok:
            return response.json()
        raise RuntimeError(graph_error(response))
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        # Never blindly retry a write. Check the Page first to prevent duplicates.
        found = reconcile(access_token, post["url"], fingerprint(caption))
        if found:
            return {"post_id": found["id"], "reconciled": True}
        raise RuntimeError(f"Facebook publish failed and no matching post was found: {exc}") from exc


def prune_tracker(tracker: dict) -> None:
    # Keep a durable but bounded audit history.
    tracker["published"] = tracker.get("published", [])[-1000:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    access_token = required_env("FACEBOOK_SYSTEM_USER_TOKEN")
    page = verify_page(access_token)
    if str(page.get("id")) != PAGE_ID:
        raise RuntimeError(f"token resolved unexpected Page: {page}")
    print(f"Facebook authorization verified for {page.get('name')} ({page.get('id')}).")
    if args.verify_only:
        return 0

    blogger_token = blogger_access_token()
    posts = blogger_candidates(blogger_token)
    tracker = load_tracker()
    candidate = choose_candidate(posts, tracker)
    if not candidate:
        print("No unshared current candidate; no Facebook post created.")
        return 0

    caption = make_caption(candidate)
    rank = score(candidate, datetime.now(timezone.utc))
    print(f"Selected score={rank}: {candidate.get('title')} [{candidate.get('id')}]")
    if args.dry_run:
        print(caption)
        return 0

    tracker["pending"] = {
        "blogger_id": candidate["id"], "url": candidate["url"],
        "caption_hash": fingerprint(caption), "selected_at": datetime.now(IST).isoformat(),
    }
    save_tracker(tracker)

    result = publish_photo(candidate, caption, access_token)
    facebook_id = result.get("post_id") or result.get("id")
    if not facebook_id:
        raise RuntimeError(f"Facebook returned no post identifier: {result}")
    tracker["published"].append({
        "blogger_id": candidate["id"],
        "title": candidate.get("title"),
        "url": candidate["url"],
        "facebook_post_id": facebook_id,
        "caption_hash": fingerprint(caption),
        "score": rank,
        "published_at": datetime.now(IST).isoformat(),
        "reconciled": bool(result.get("reconciled")),
    })
    tracker["pending"] = None
    tracker["last_success_at"] = datetime.now(IST).isoformat()
    tracker["last_facebook_post_id"] = facebook_id
    prune_tracker(tracker)
    save_tracker(tracker)
    print(f"Published Facebook post {facebook_id} for Blogger post {candidate['id']}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FACEBOOK_PUBLISHER_ERROR: {exc}", file=sys.stderr)
        raise
