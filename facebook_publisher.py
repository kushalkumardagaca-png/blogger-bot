#!/usr/bin/env python3
"""Daily Yield Facebook Page publisher.

Reads posts and audience-facing Pages only through the authenticated Blogger API.
It never opens, HEADs, or downloads a Daily Yield public URL. Every Facebook item is
a photo post with a locally rendered branded topic card, a useful description and a
direct website URL. This avoids requesting the article merely to build a link preview.
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
import textwrap

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "1303333369533572")
GRAPH_VERSION = os.environ.get("FACEBOOK_GRAPH_VERSION", "v26.0")
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
TRACKER_PATH = Path(os.environ.get("FACEBOOK_TRACKER", "facebook_tracker.json"))
BRAND_IMAGE = Path("assets/brand/daily-yield-social-banner.png")
BRAND_MARK = Path("assets/brand/daily-yield-favicon-512.png")
CARD_PATH = Path(os.environ.get("FACEBOOK_CARD_PATH", "/tmp/daily-yield-facebook-card.png"))
MAX_CANDIDATE_AGE_HOURS = 42
TIMEOUT = (15, 75)
PAGE_PROMOTION_WINDOWS = ((11 * 60 + 45, 13 * 60 + 30), (19 * 60 + 15, 21 * 60))
LOW_VALUE_PAGE_TERMS = ("privacy", "terms", "disclaimer", "contact", "correction policy")
PAGE_PRIORITY_TERMS = {
    "calculator": 50, "tool": 45, "market": 35, "global": 30,
    "news": 28, "article": 25, "money": 24, "learn": 20,
    "resource": 20, "start": 15, "about": 5,
}

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
    for post in result:
        post["kind"] = "post"
    return result


def blogger_pages(token: str) -> list[dict]:
    """Inventory audience-facing evergreen Pages through Blogger API only."""
    endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages"
    data = request_json(
        "GET", endpoint,
        params={
            "status": "live", "fetchBodies": "true", "maxResults": "50",
            "fields": "items(id,title,url,published,updated,content)",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pages = []
    for page in data.get("items", []):
        title = clean_text(page.get("title", ""))
        url = page.get("url", "")
        if not title or not url.startswith("https://dailyyield.blogspot.com/p/"):
            continue
        if any(term in title.lower() for term in LOW_VALUE_PAGE_TERMS):
            continue
        page["kind"] = "page"
        page["labels"] = ["Daily Yield Resources"]
        pages.append(page)
    # The homepage is an audience destination but is not returned by Blogger Pages API.
    pages.append({
        "id": "homepage", "kind": "page", "title": "Daily Yield: Markets, Money and Better Decisions",
        "url": "https://dailyyield.blogspot.com/", "labels": ["Daily Yield"],
        "content": "Explore Daily Yield's latest financial reporting, practical money tools, market context and global News editions in one place.",
        "published": "2026-09-01T00:00:00+05:30", "updated": datetime.now(IST).isoformat(),
    })
    return pages


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
                if len(text) <= 300:
                    return text
                return text[:300].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return "Clear context, verified sources and practical implications from Daily Yield."


def approved_editorial_image(content: str) -> str | None:
    """Return only an Unsplash image URL already present in API-provided content."""
    for source in re.findall(r'<img\b[^>]+src=["\']([^"\']+)', content or "", flags=re.I):
        source = html.unescape(source)
        if re.match(r"^https://images\.unsplash\.com/", source, flags=re.I):
            return source
    return None


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def content_badge(item: dict) -> str:
    text = item.get("title", "").lower()
    if item.get("kind") == "page":
        if "calculator" in text or "tool" in text:
            return "CALCULATOR & TOOL"
        return "EXPLORE DAILY YIELD"
    if "news" in {str(x).lower() for x in item.get("labels", [])}:
        return "NEWS BRIEFING"
    return "IN-DEPTH ANALYSIS"


def wrap_title(draw: ImageDraw.ImageDraw, title: str, max_width: int, max_lines: int = 4) -> list[str]:
    words = title.split()
    lines, current = [], ""
    title_font = font(56, True)
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=title_font)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while draw.textbbox((0, 0), lines[-1] + "…", font=title_font)[2] > max_width and " " in lines[-1]:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] = lines[-1].rstrip(".,:;-") + "…"
    return lines


def generate_topic_card(item: dict) -> Path:
    """Render a 1200x630 branded image without requesting any Daily Yield URL."""
    width, height = 1200, 630
    cream, ink, copper, muted = "#FFF8EE", "#241610", "#C86A3D", "#6E5D4B"
    canvas = Image.new("RGB", (width, height), cream)

    # Topic imagery comes only from an approved third-party URL found in Blogger API content.
    hero_url = approved_editorial_image(item.get("content", ""))
    if hero_url:
        try:
            response = requests.get(hero_url, timeout=TIMEOUT)
            response.raise_for_status()
            hero = Image.open(BytesIO(response.content)).convert("RGB")
            hero = ImageOps.fit(hero, (500, height), method=Image.Resampling.LANCZOS)
            hero = ImageEnhance.Contrast(hero).enhance(0.9)
            canvas.paste(hero, (700, 0))
            overlay = Image.new("RGBA", (500, height), (36, 22, 16, 75))
            canvas.paste(overlay, (700, 0), overlay)
        except Exception as exc:
            print(f"Editorial image unavailable; using rendered topic motif: {exc}")
            hero_url = None

    draw = ImageDraw.Draw(canvas)
    if not hero_url:
        draw.rectangle((700, 0, width, height), fill="#F4E5D4")
        for x in range(735, 1200, 70):
            draw.line((x, 0, x, height), fill="#E8D2BC", width=2)
        for y in range(35, height, 70):
            draw.line((700, y, width, y), fill="#E8D2BC", width=2)
        points = [(735, 510), (820, 465), (900, 480), (985, 355), (1070, 380), (1150, 225)]
        draw.line(points, fill=copper, width=10, joint="curve")
        draw.line(((1110, 225), (1158, 216), (1148, 267)), fill=copper, width=10, joint="curve")

    # Opaque copy panel means the title remains readable on every photograph.
    draw.rounded_rectangle((48, 42, 760, 588), radius=28, fill=cream, outline="#E4CDB5", width=2)
    if BRAND_MARK.exists():
        logo = Image.open(BRAND_MARK).convert("RGBA")
        logo.thumbnail((84, 84), Image.Resampling.LANCZOS)
        canvas.paste(logo, (78, 70), logo)
    draw.text((180, 76), "DAILY YIELD", fill=ink, font=font(34, True))
    draw.text((180, 120), "Markets · Money · Better decisions", fill=muted, font=font(17))
    draw.rounded_rectangle((78, 180, 340, 222), radius=20, fill=copper)
    draw.text((98, 191), content_badge(item), fill="white", font=font(16, True))

    title = clean_text(item.get("title", "Daily Yield"))
    lines = wrap_title(draw, title, 610)
    y = 255
    for line in lines:
        draw.text((78, y), line, fill=ink, font=font(56, True))
        y += 67
    draw.line((78, 525, 690, 525), fill="#D9BFA7", width=2)
    draw.text((78, 544), "Read, calculate and explore at dailyyield.blogspot.com", fill=muted, font=font(18, True))
    draw.rectangle((0, 615, width, height), fill=ink)
    CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(CARD_PATH, "PNG", optimize=True)
    return CARD_PATH


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


def make_caption(item: dict) -> str:
    title = clean_text(item.get("title", "Daily Yield"))
    summary = summary_from_content(item.get("content", ""), title).strip()
    if summary and summary[-1] not in ".!?…":
        summary += "."
    url = item["url"]
    if item.get("kind") == "page":
        top_link = f"🔗 OPEN THIS DAILY YIELD RESOURCE: {url}"
        value_line = "Use the page, review the supporting guidance and bookmark it for your next decision."
    else:
        top_link = f"🔗 READ THE FULL REPORT: {url}"
        value_line = "Open the report for the evidence, context and practical implications."
    # The destination is intentionally the first line so mobile readers can tap it
    # without expanding or searching through the caption.
    return (
        f"{top_link}\n\n"
        f"{title}\n\n{summary}\n\n{value_line}\n\n"
        f"By Kushal K. Daga · Markets · Money · Better decisions\n\n"
        f"{hashtags(item)}"
    )


def fingerprint(caption: str) -> str:
    return hashlib.sha256(caption.encode("utf-8")).hexdigest()[:20]


def choose_post(posts: list[dict], tracker: dict) -> dict | None:
    seen_ids = {str(x.get("blogger_id")) for x in tracker["published"] if x.get("kind", "post") == "post"}
    seen_urls = {x.get("url", "").rstrip("/") for x in tracker["published"] if x.get("kind", "post") == "post"}
    now = datetime.now(timezone.utc)
    eligible = [p for p in posts if str(p.get("id")) not in seen_ids and p.get("url", "").rstrip("/") not in seen_urls]
    if not eligible:
        return None
    return max(eligible, key=lambda p: (score(p, now), parse_time(p["published"])))


def page_priority(page: dict) -> int:
    title = page.get("title", "").lower()
    return sum(weight for term, weight in PAGE_PRIORITY_TERMS.items() if term in title)


def choose_page(pages: list[dict], tracker: dict) -> dict | None:
    history = {}
    for entry in tracker.get("published", []):
        if entry.get("kind") != "page":
            continue
        when = entry.get("published_at", "1970-01-01T00:00:00+00:00")
        history[entry.get("url", "").rstrip("/")] = max(history.get(entry.get("url", "").rstrip("/"), ""), when)
    if not pages:
        return None
    # Unpromoted destinations first; then least recently promoted. Priority breaks ties.
    return min(
        pages,
        key=lambda p: (
            1 if p["url"].rstrip("/") in history else 0,
            history.get(p["url"].rstrip("/"), ""),
            -page_priority(p),
            p.get("title", ""),
        ),
    )


def is_page_promotion_time(now: datetime) -> bool:
    local = now.astimezone(IST)
    minute = local.hour * 60 + local.minute
    return any(start <= minute <= end for start, end in PAGE_PROMOTION_WINDOWS)


def choose_candidate(posts: list[dict], pages: list[dict], tracker: dict, mode: str = "auto") -> dict | None:
    if mode == "page" or (mode == "auto" and is_page_promotion_time(datetime.now(timezone.utc))):
        selected = choose_page(pages, tracker)
        if selected:
            return selected
    return choose_post(posts, tracker)


def graph_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error", payload)
        return f"HTTP {response.status_code}: {error.get('message', error)} (code={error.get('code', '?')})"
    except Exception:
        return f"HTTP {response.status_code}: {response.text[:500]}"


def resolve_page_token(system_user_token: str) -> tuple[dict, str]:
    """Resolve the Page access token required by Page publishing endpoints."""
    page = request_json(
        "GET", f"{GRAPH_ROOT}/{PAGE_ID}",
        params={"fields": "id,name,access_token", "access_token": system_user_token},
    )
    page_token = page.pop("access_token", "")
    if not page_token:
        raise RuntimeError(
            "Meta verified the Page but did not return a Page access token. "
            "Reassign the Daily Yield Page to the system user and regenerate the "
            "system-user token with pages_manage_posts, pages_show_list and "
            "pages_read_engagement."
        )
    return page, page_token


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


def publish_photo(item: dict, caption: str, access_token: str) -> dict:
    endpoint = f"{GRAPH_ROOT}/{PAGE_ID}/photos"
    payload = {"message": caption, "published": "true", "access_token": access_token}
    card = generate_topic_card(item)
    try:
        with card.open("rb") as image:
            response = requests.post(
                endpoint, data=payload,
                files={"source": (card.name, image, "image/png")},
                timeout=TIMEOUT,
            )
        if response.ok:
            return response.json()
        raise RuntimeError(graph_error(response))
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        # Never blindly retry a write. Check the Page first to prevent duplicates.
        found = reconcile(access_token, item["url"], fingerprint(caption))
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
    parser.add_argument("--content-mode", choices=("auto", "post", "page"), default="auto")
    args = parser.parse_args()

    system_user_token = required_env("FACEBOOK_SYSTEM_USER_TOKEN")
    page, page_access_token = resolve_page_token(system_user_token)
    if str(page.get("id")) != PAGE_ID:
        raise RuntimeError(f"token resolved unexpected Page: {page}")
    print(f"Facebook Page token verified for {page.get('name')} ({page.get('id')}).")
    if args.verify_only:
        return 0

    blogger_token = blogger_access_token()
    posts = blogger_candidates(blogger_token)
    pages = blogger_pages(blogger_token)
    tracker = load_tracker()
    candidate = choose_candidate(posts, pages, tracker, args.content_mode)
    if not candidate:
        print("No eligible website destination; no Facebook post created.")
        return 0

    caption = make_caption(candidate)
    rank = score(candidate, datetime.now(timezone.utc)) if candidate.get("kind") == "post" else page_priority(candidate)
    print(f"Selected {candidate.get('kind')} score={rank}: {candidate.get('title')} [{candidate.get('id')}]")
    if args.dry_run:
        print(caption)
        return 0

    tracker["pending"] = {
        "kind": candidate.get("kind", "post"), "blogger_id": candidate["id"], "url": candidate["url"],
        "caption_hash": fingerprint(caption), "selected_at": datetime.now(IST).isoformat(),
    }
    save_tracker(tracker)

    result = publish_photo(candidate, caption, page_access_token)
    facebook_id = result.get("post_id") or result.get("id")
    if not facebook_id:
        raise RuntimeError(f"Facebook returned no post identifier: {result}")
    tracker["published"].append({
        "kind": candidate.get("kind", "post"),
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
    print(f"Published Facebook post {facebook_id} for Blogger {candidate.get('kind', 'post')} {candidate['id']}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FACEBOOK_PUBLISHER_ERROR: {exc}", file=sys.stderr)
        raise
