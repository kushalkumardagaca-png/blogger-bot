#!/usr/bin/env python3
"""Independent Daily Yield Bluesky publisher using the official AT Protocol API.

Blogger candidates are read only through the authenticated Blogger API. The
publisher never requests a Daily Yield public URL and maintains its own tracker.
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
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
BSKY_HANDLE = os.environ.get("BLUESKY_HANDLE", "dailyyield.bsky.social").strip().lower()
BSKY_SERVICE = "https://bsky.social"
TRACKER_PATH = Path(os.environ.get("BLUESKY_TRACKER", "bluesky_tracker.json"))
CARD_PATH = Path(os.environ.get("BLUESKY_CARD_PATH", "/tmp/daily-yield-bluesky-card.jpg"))
BRAND_MARK = Path("assets/brand/daily-yield-favicon-512.png")
MAX_AGE_HOURS = 42
TIMEOUT = (15, 75)
PAGE_WINDOWS = ((10 * 60 + 30, 12 * 60), (19 * 60 + 30, 21 * 60 + 30))
LOW_VALUE_PAGES = ("privacy", "terms", "disclaimer", "contact", "correction policy")
PAGE_PRIORITY = {"calculator": 50, "tool": 45, "market": 35, "global": 30, "news": 28, "article": 25, "money": 24, "learn": 20, "resource": 20, "start": 15, "about": 5}
HIGH_IMPACT = {"breaking": 18, "rates": 11, "inflation": 11, "recession": 12, "budget": 10, "tax": 10, "economy": 9, "market": 9, "policy": 9, "trade": 8, "oil": 8, "stocks": 8, "invest": 8, "debt": 8, "gold": 7, "jobs": 8, "earnings": 7}


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required encrypted secret: {name}")
    return value


def api(method: str, endpoint: str, *, token: str = "", retries: int = 3, **kwargs) -> dict:
    if "dailyyield.blogspot.com" in endpoint.lower():
        raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
    headers = dict(kwargs.pop("headers", {}))
    if token:
        headers["Authorization"] = "Bearer " + token
    last = None
    for attempt in range(retries):
        try:
            response = requests.request(method, endpoint, headers=headers, timeout=TIMEOUT, **kwargs)
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
            detail = getattr(getattr(exc, "response", None), "text", "")[:500]
            raise RuntimeError(f"API request failed: {endpoint}: {exc} {detail}") from exc
    raise RuntimeError(str(last))


def create_session() -> dict:
    session = api("POST", BSKY_SERVICE + "/xrpc/com.atproto.server.createSession", retries=2, json={
        "identifier": BSKY_HANDLE,
        "password": required("BLUESKY_APP_PASSWORD"),
    })
    if session.get("handle", "").lower() != BSKY_HANDLE or not session.get("did") or not session.get("accessJwt"):
        raise RuntimeError("Bluesky authenticated an unexpected account")
    return session


def blogger_token() -> str:
    result = api("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    })
    return result["access_token"]


def clean(fragment: str) -> str:
    fragment = re.sub(r"<script\b[^>]*>.*?</script>", " ", fragment or "", flags=re.I | re.S)
    fragment = re.sub(r"<style\b[^>]*>.*?</style>", " ", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def inventory(token: str) -> tuple[list[dict], list[dict]]:
    auth = {"Authorization": "Bearer " + token}
    posts_data = api("GET", f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts", headers=auth, params={
        "status": "live", "fetchBodies": "true", "maxResults": "50", "orderBy": "published",
        "fields": "items(id,title,url,published,updated,labels,content)",
    })
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    posts = []
    for item in posts_data.get("items", []):
        try:
            published = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if published >= cutoff and item.get("url", "").startswith("https://dailyyield.blogspot.com/"):
            item["kind"] = "post"
            posts.append(item)
    page_data = api("GET", f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages", headers=auth, params={
        "status": "live", "fetchBodies": "true", "maxResults": "50",
        "fields": "items(id,title,url,published,updated,content)",
    })
    pages = []
    for item in page_data.get("items", []):
        title, url = clean(item.get("title", "")), item.get("url", "")
        if title and url.startswith("https://dailyyield.blogspot.com/p/") and not any(x in title.lower() for x in LOW_VALUE_PAGES):
            item.update(kind="page", labels=["Daily Yield Resources"])
            pages.append(item)
    pages.append({
        "id": "homepage", "kind": "page", "title": "Daily Yield: Markets, Money and Better Decisions",
        "url": "https://dailyyield.blogspot.com/", "labels": ["Daily Yield"],
        "content": "Explore financial reporting, practical money tools, market context and global News editions from Daily Yield.",
        "updated": datetime.now(IST).isoformat(),
    })
    return posts, pages


def load_tracker() -> dict:
    if TRACKER_PATH.exists():
        data = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
        data.setdefault("published", [])
        data.setdefault("pending", None)
        return data
    return {"version": 1, "handle": BSKY_HANDLE, "published": [], "pending": None}


def save_tracker(data: dict) -> None:
    data["published"] = data.get("published", [])[-1000:]
    TRACKER_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parsed(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def score(item: dict) -> float:
    now = datetime.now(timezone.utc)
    age = max(0.0, (now - parsed(item["published"])).total_seconds() / 3600)
    labels = [str(x).lower() for x in item.get("labels", [])]
    haystack = (item.get("title", "") + " " + " ".join(labels)).lower()
    value = max(0.0, 50 - age) + (30 if "news" not in labels else 0)
    if parsed(item["published"]).astimezone(IST).date() == now.astimezone(IST).date():
        value += 20
    value += sum(weight for term, weight in HIGH_IMPACT.items() if term in haystack)
    return round(value, 3)


def page_score(item: dict) -> int:
    title = item.get("title", "").lower()
    return sum(weight for term, weight in PAGE_PRIORITY.items() if term in title)


def choose(posts: list[dict], pages: list[dict], tracker: dict, mode: str, recent_urls: set[str] | None = None) -> dict | None:
    history = tracker.get("published", [])
    recent_urls = {x.rstrip("/") for x in (recent_urls or set())}
    if mode == "auto":
        now = datetime.now(IST)
        minute = now.hour * 60 + now.minute
        mode = "page" if any(start <= minute <= end for start, end in PAGE_WINDOWS) else "post"
    if mode == "page":
        last = {x.get("url", "").rstrip("/"): x.get("published_at", "") for x in history if x.get("kind") == "page"}
        available_pages = [x for x in pages if x["url"].rstrip("/") not in recent_urls] or pages
        if available_pages:
            return min(available_pages, key=lambda x: (1 if x["url"].rstrip("/") in last else 0, last.get(x["url"].rstrip("/"), ""), -page_score(x), x.get("title", "")))
    seen_ids = {str(x.get("blogger_id")) for x in history if x.get("kind") == "post"}
    seen_urls = {x.get("url", "").rstrip("/") for x in history if x.get("kind") == "post"}
    eligible = [x for x in posts if str(x.get("id")) not in seen_ids and x.get("url", "").rstrip("/") not in seen_urls and x.get("url", "").rstrip("/") not in recent_urls]
    return max(eligible, key=lambda x: (score(x), parsed(x["published"]))) if eligible else None


def summary(item: dict) -> str:
    content, title = item.get("content", ""), clean(item.get("title", ""))
    for pattern in (r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)', r"<p\b[^>]*>(.*?)</p>"):
        match = re.search(pattern, content, flags=re.I | re.S)
        if match:
            value = clean(match.group(1))
            if len(value) >= 35 and title.lower() not in value.lower():
                return value
    return "Clear context and practical implications from Daily Yield."


def post_text(item: dict) -> str:
    url, title = item["url"], clean(item.get("title", "Daily Yield"))
    prefix = "Explore:" if item.get("kind") == "page" else "Read the report:"
    suffix = "By Kushal K. Daga · #DailyYield"
    fixed = f"{url}\n\n{prefix} {title}\n\n\n\n{suffix}"
    room = max(0, 300 - len(fixed))
    body = summary(item).strip()
    if body and body[-1] not in ".!?…":
        body += "."
    if len(body) > room:
        body = body[:max(0, room - 1)].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    text = f"{url}\n\n{prefix} {title}\n\n{body}\n\n{suffix}"
    if len(text) > 300:
        # Preserve link, title, byline and identity if a very long title consumes the limit.
        title_room = max(30, 300 - len(f"{url}\n\n{prefix} \n\n{suffix}") - 1)
        title = title[:title_room].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
        text = f"{url}\n\n{prefix} {title}\n\n{suffix}"
    return text


def richtext_facets(text: str, url: str) -> list[dict]:
    link_start = text.index(url)
    tag = "#DailyYield"
    tag_start = text.rindex(tag)
    return [
        {"index": {"byteStart": len(text[:link_start].encode()), "byteEnd": len(text[:link_start + len(url)].encode())},
         "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]},
        {"index": {"byteStart": len(text[:tag_start].encode()), "byteEnd": len(text[:tag_start + len(tag)].encode())},
         "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "DailyYield"}]},
    ]


def font(size: int, bold: bool = False):
    names = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def generate_card(item: dict) -> Path:
    canvas = Image.new("RGB", (1200, 630), "#FFF8EE")
    draw = ImageDraw.Draw(canvas)
    ink, copper, muted = "#241610", "#C86A3D", "#6E5D4B"
    draw.rectangle((700, 0, 1200, 630), fill="#F4E5D4")
    for x in range(735, 1200, 70): draw.line((x, 0, x, 630), fill="#E8D2BC", width=2)
    for y in range(35, 630, 70): draw.line((700, y, 1200, y), fill="#E8D2BC", width=2)
    draw.line([(735, 510), (820, 465), (900, 480), (985, 355), (1070, 380), (1150, 225)], fill=copper, width=10, joint="curve")
    draw.rounded_rectangle((48, 42, 760, 588), radius=28, fill="#FFF8EE", outline="#E4CDB5", width=2)
    if BRAND_MARK.exists():
        logo = Image.open(BRAND_MARK).convert("RGBA"); logo.thumbnail((84, 84), Image.Resampling.LANCZOS); canvas.paste(logo, (78, 70), logo)
    draw.text((180, 76), "DAILY YIELD", fill=ink, font=font(34, True))
    draw.text((180, 120), "Markets · Money · Better decisions", fill=muted, font=font(17))
    badge = "EXPLORE DAILY YIELD" if item.get("kind") == "page" else "LATEST REPORT"
    draw.rounded_rectangle((78, 180, 355, 222), radius=20, fill=copper); draw.text((98, 191), badge, fill="white", font=font(16, True))
    title = clean(item.get("title", "Daily Yield")); words, lines, current = title.split(), [], ""
    title_font = font(52, True)
    for word in words:
        trial = (current + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=title_font)[2] <= 610: current = trial
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    if len(lines) > 4:
        lines = lines[:4]
        while draw.textbbox((0, 0), lines[-1] + "…", font=title_font)[2] > 610 and " " in lines[-1]: lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] = lines[-1].rstrip(".,:;-") + "…"
    y = 255
    for line in lines: draw.text((78, y), line, fill=ink, font=title_font); y += 63
    draw.line((78, 525, 690, 525), fill="#D9BFA7", width=2)
    draw.text((78, 544), "dailyyield.blogspot.com", fill=muted, font=font(20, True))
    draw.rectangle((0, 615, 1200, 630), fill=ink)
    CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    quality = 88
    canvas.save(CARD_PATH, "JPEG", quality=quality, optimize=True)
    while CARD_PATH.stat().st_size > 950_000 and quality > 55:
        quality -= 8; canvas.save(CARD_PATH, "JPEG", quality=quality, optimize=True)
    if CARD_PATH.stat().st_size > 1_000_000: raise RuntimeError("Bluesky card exceeds image upload limit")
    return CARD_PATH


def recent_records(session: dict) -> list[dict]:
    data = api("GET", BSKY_SERVICE + "/xrpc/app.bsky.feed.getAuthorFeed", token=session["accessJwt"], retries=2, params={"actor": session["did"], "limit": "30", "filter": "posts_no_replies"})
    return data.get("feed", [])


def reconcile(session: dict, url: str, text_hash: str) -> dict | None:
    try:
        for entry in recent_records(session):
            post = entry.get("post", {}); record = post.get("record", {}); text = record.get("text", "")
            if url in text and hashlib.sha256(text.encode()).hexdigest()[:20] == text_hash:
                return {"uri": post.get("uri"), "cid": post.get("cid"), "reconciled": True}
    except Exception as exc:
        print(f"Bluesky reconciliation read failed: {exc}", file=sys.stderr)
    return None


def publish(item: dict, text: str, session: dict) -> dict:
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:20]
    existing = reconcile(session, item["url"], text_hash)
    if existing: return existing
    card = generate_card(item)
    blob = api("POST", BSKY_SERVICE + "/xrpc/com.atproto.repo.uploadBlob", token=session["accessJwt"], retries=2, headers={"Content-Type": "image/jpeg"}, data=card.read_bytes()).get("blob")
    if not blob: raise RuntimeError("Bluesky image upload returned no blob")
    alt = f"Daily Yield branded card for: {clean(item.get('title', 'Daily Yield'))}"[:1000]
    record = {
        "$type": "app.bsky.feed.post", "text": text, "facets": richtext_facets(text, item["url"]),
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "embed": {"$type": "app.bsky.embed.images", "images": [{"alt": alt, "image": blob, "aspectRatio": {"width": 1200, "height": 630}}]},
    }
    try:
        return api("POST", BSKY_SERVICE + "/xrpc/com.atproto.repo.createRecord", token=session["accessJwt"], retries=1, json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record})
    except Exception as exc:
        found = reconcile(session, item["url"], text_hash)
        if found: return found
        raise RuntimeError(f"Bluesky write failed and no matching post was found: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--content-mode", choices=("auto", "post", "page"), default="auto")
    args = parser.parse_args()
    session = create_session()
    print(f"Bluesky account verified: {session['handle']} ({session['did']})")
    if args.verify_only: return 0
    posts, pages = inventory(blogger_token())
    tracker = load_tracker()
    recent_urls = set()
    for entry in recent_records(session):
        text = entry.get("post", {}).get("record", {}).get("text", "")
        recent_urls.update(re.findall(r"https://dailyyield\.blogspot\.com/[^\s]*", text))
    item = choose(posts, pages, tracker, args.content_mode, recent_urls)
    if not item:
        print("No eligible Bluesky destination; no post created."); return 0
    text = post_text(item); rank = score(item) if item.get("kind") == "post" else page_score(item)
    print(f"Selected {item.get('kind')} score={rank}: {item.get('title')} [{item.get('id')}]")
    if args.dry_run:
        print(text); return 0
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:20]
    tracker["pending"] = {"kind": item.get("kind"), "blogger_id": item["id"], "url": item["url"], "text_hash": text_hash, "selected_at": datetime.now(IST).isoformat()}
    save_tracker(tracker)
    result = publish(item, text, session)
    uri = result.get("uri")
    if not uri: raise RuntimeError(f"Bluesky returned no record URI: {result}")
    tracker["published"].append({
        "kind": item.get("kind"), "blogger_id": item["id"], "title": item.get("title"), "url": item["url"],
        "bluesky_uri": uri, "cid": result.get("cid"), "text_hash": text_hash, "score": rank,
        "published_at": datetime.now(IST).isoformat(), "reconciled": bool(result.get("reconciled")),
    })
    tracker["pending"] = None; tracker["last_success_at"] = datetime.now(IST).isoformat(); tracker["last_bluesky_uri"] = uri
    save_tracker(tracker)
    print(f"Published Bluesky record {uri} for Blogger {item.get('kind')} {item['id']}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"BLUESKY_PUBLISHER_ERROR: {exc}", file=sys.stderr)
        raise
