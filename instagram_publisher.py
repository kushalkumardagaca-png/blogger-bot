#!/usr/bin/env python3
"""Post today's article to Instagram, once, with the article's own photograph.

Instagram is the one audience channel that was never built: it needs the Graph API's two-step
container flow, and it needs the brand account linked to the Facebook Page by the owner. The code is
written here so that the only thing missing is that one connection - when it is absent, this job says
so plainly in INSTAGRAM_STATUS.json and does nothing else, instead of failing noisily every day or
pretending to have posted.

What the job never does: it never reads a public Daily Yield address (the candidate list comes from the
authenticated Blogger API, which creates no page view), it never invents a picture - the caption carries
the article's own approved editorial photograph - it never posts the same article twice, it never
publishes a media container that Instagram has not marked finished, and it never touches, prints or
rotates the token it borrows.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "INSTAGRAM_STATUS.json"
TRACKER_PATH = ROOT / os.environ.get("INSTAGRAM_TRACKER", "instagram_tracker.json")
GRAPH = os.environ.get("GRAPH_API_VERSION", "v23.0")
MAX_CAPTION = 2200                    # Instagram's own caption limit, in characters
MAX_CANDIDATE_AGE_HOURS = 30
POLL_TRIES = 6
POLL_SECONDS = 12
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "")


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def config() -> dict:
    """What the job has and what it still needs - stated as facts, not excuses."""
    account = env("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    token_present = bool(env("FACEBOOK_SYSTEM_USER_TOKEN"))
    missing = []
    if not account:
        missing.append("INSTAGRAM_BUSINESS_ACCOUNT_ID (the Instagram professional account's number)")
    if not token_present:
        missing.append("FACEBOOK_SYSTEM_USER_TOKEN (the same page token the Facebook job already uses)")
    if not missing and not token_present:
        missing.append("the token")
    return {"account": account or None, "tokenAvailable": token_present, "ready": not missing,
            "waitingOnOwner": missing}


def request_json(method: str, url: str, *, retries: int = 3, **kwargs) -> dict:
    data = kwargs.pop("data", None)
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    headers = {"User-Agent": "DailyYield-Instagram/1.0", "Accept": "application/json"}
    for name, value in (kwargs.pop("headers", None) or {}).items():
        headers[name] = value
    last: dict = {}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=45) as reply:
                body = reply.read().decode("utf-8", "replace")
            return json.loads(body or "{}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            last = {"httpError": exc.code, "body": body[:400]}
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            if 400 <= exc.code < 500:
                break                          # a refusal from Instagram is an answer, not a retry
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
    return last


def blogger_token() -> str:
    """Blogger's own access token, through the same helper every publishing job uses."""
    import news_pipeline
    return news_pipeline.blogger_token()


def candidates(token: str) -> list[dict]:
    """Today's live articles, taken from the Blogger API - no public page is requested."""
    if not BLOG_ID:
        return []
    endpoint = (f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts?"
                + urllib.parse.urlencode({"status": "live", "fetchBodies": "true", "maxResults": "50",
                                          "orderBy": "published",
                                          "fields": "items(id,title,url,published,content)"}))
    data = request_json("GET", endpoint, headers={"Authorization": f"Bearer {token}"})
    now = datetime.now(timezone.utc)
    out = []
    for post in data.get("items", []) or []:
        url = str(post.get("url", ""))
        if not url.startswith("https://dailyyield.blogspot.com/"):
            continue
        try:
            published = datetime.fromisoformat(str(post["published"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if (now - published).total_seconds() > MAX_CANDIDATE_AGE_HOURS * 3600:
            continue
        post["url"] = url
        out.append(post)
    return out


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def first_paragraph(content: str) -> str:
    for chunk in re.findall(r"<p[^>]*>(.*?)</p>", str(content or ""), flags=re.S | re.I):
        text = strip_tags(chunk)
        if len(text) > 90:
            return text
    return ""


def editorial_photo(content: str) -> str | None:
    """The article's own approved photograph, already hosted by Blogger - never a substitute image."""
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', str(content or ""), flags=re.I):
        src = match.group(1)
        if src.startswith("https://") and "blogspot" in src or src.startswith("https://lh3.googleusercontent.com"):
            return src
    return None


def caption_for(post: dict, link_note: str) -> str:
    """Plain caption: what the article says, why it matters today, and where to read it."""
    title = strip_tags(post.get("title", ""))[:220]
    lead = first_paragraph(post.get("content", ""))[:600]
    body = f"{title}\n\n{lead}".strip()
    tail = f"\n\nRead the full article: {link_note}"
    if len(body) + len(tail) > MAX_CAPTION:
        body = body[:MAX_CAPTION - len(tail)].rsplit(" ", 1)[0]
    return (body + tail)[:MAX_CAPTION]


def fingerprint(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def load_tracker() -> dict:
    try:
        return json.loads(TRACKER_PATH.read_text())
    except (OSError, ValueError):
        return {"posted": {}, "attempts": []}


def save_tracker(tracker: dict) -> None:
    TRACKER_PATH.write_text(json.dumps(tracker, indent=1, sort_keys=True) + "\n")


def choose_post(posts: list[dict], tracker: dict) -> dict | None:
    posted = tracker.get("posted") or {}
    fresh = [p for p in posts if fingerprint(str(p.get("url", ""))) not in posted]
    return fresh[0] if fresh else None


def graph(graph_call, account: str, token: str, post: dict, image: str, tracker: dict) -> dict:
    """The two-step Instagram flow: build a container, wait for it, then publish that container once."""
    caption = caption_for(post, "link in bio")        # Instagram does not make a caption link clickable
    created = graph_call(f"/{account}/media", {"caption": caption, "image_url": image,
                                               "is_comment_enabled": "true"})
    container = str(created.get("id", ""))
    if not container:
        return {"status": "FAILED", "stage": "container", "reason": str(created)[:300]}
    ready = False
    for _ in range(POLL_TRIES):
        state = graph_call(f"/{container}", {"fields": "status_code,status_message"})
        code = str(state.get("status_code", "")).upper()
        if code == "FINISHED":
            ready = True
            break
        if code in ("ERROR", "EXPIRED"):
            return {"status": "FAILED", "stage": "container", "container": container,
                    "reason": str(state.get("status_message") or code)[:300]}
        time.sleep(POLL_SECONDS)
    if not ready:
        return {"status": "FAILED", "stage": "containerNotReady", "container": container,
                "reason": f"Instagram had not finished the image in {POLL_TRIES * POLL_SECONDS} seconds"}
    published = graph_call(f"/{account}/media_publish", {"creation_id": container})
    media_id = str(published.get("id", ""))
    if not media_id:
        return {"status": "FAILED", "stage": "publish", "container": container, "reason": str(published)[:300]}
    record = {"status": "PUBLISHED", "container": container, "mediaId": media_id,
              "url": post.get("url"), "title": strip_tags(post.get("title", ""))[:200],
              "at": datetime.now(timezone.utc).isoformat()}
    tracker.setdefault("posted", {})[fingerprint(str(post.get("url", "")))] = record
    return record


def run(now=None, token_provider=blogger_token, graph_call=None) -> dict:
    settings = config()
    report = {"generatedAt": (now or datetime.now(timezone.utc)).isoformat(), "channel": "Instagram",
              "config": settings, "status": "NOT_CONFIGURED", "attempted": 0, "posted": 0, "rows": []}
    if not settings["ready"]:
        report["note"] = ("Instagram is wired but not armed: the account number and the page token are the "
                          "owner's to connect, and the schedule stays off until they are. No failure is "
                          "claimed and nothing is pretended.")
        return report
    token = token_provider()
    posts = candidates(token)
    tracker = load_tracker()
    if graph_call is None:
        def graph_call(path, params):       # noqa: F811 - the real network call, replaced in tests
            url = f"https://graph.facebook.com/{GRAPH}{path}"
            return request_json("POST" if path.endswith("/media") or path.endswith("/media_publish") else "GET",
                                url, data={**params, "access_token": env("FACEBOOK_SYSTEM_USER_TOKEN")})
    for _ in range(2):                        # at most two articles per run, never a flood
        post = choose_post(posts, tracker)
        if not post:
            break
        report["attempted"] += 1
        image = editorial_photo(post.get("content", ""))
        if not image:
            row = {"status": "SKIPPED", "reason": "no approved photograph on the article to carry the post",
                   "url": post.get("url")}
        else:
            row = graph(graph_call, settings["account"], env("FACEBOOK_SYSTEM_USER_TOKEN"), post, image, tracker)
        report["rows"].append(row)
        if row.get("status") == "PUBLISHED":
            report["posted"] += 1
        else:
            tracker.setdefault("attempts", []).append({**row, "at": datetime.now(timezone.utc).isoformat()})
            break
    save_tracker(tracker)
    statuses = [r.get("status") for r in report["rows"]]
    report["status"] = ("PUBLISHED" if report["posted"] else
                        "NOTHING_DUE" if not statuses else "ATTACHED_BUT_NOT_PUBLISHED")
    return report


def main() -> int:
    report = run()
    STATUS_PATH.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"status": report["status"], "posted": report["posted"],
                      "waitingOn": report["config"]["waitingOnOwner"][:1]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
