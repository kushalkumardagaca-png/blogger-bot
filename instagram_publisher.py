#!/usr/bin/env python3
"""Official Instagram publisher for Daily Yield, using Meta's Instagram Platform.

Only the official content-publishing API is used. Instagram grants publishing to
professional accounts (Business or Creator) and nothing else: a personal account has
no posting API at all, and browser automation against the private app API is the exact
behaviour that gets accounts disabled, so neither is implemented here and neither will
be added later.

How a post happens
------------------
1. The article must be proven live from evidence this repository already keeps
   (slot guarantee rows, Master tracker, live edition verification). Nothing is ever
   announced for an article that did not publish.
2. The image is a photograph we already hold and licence: the article's own editorial
   picture, reachable at a public URL that Meta can fetch. Instagram accepts JPEG
   only, so a URL that could negotiate WebP is asked for JPEG explicitly. No new
   image is uploaded and no copy of a photo is kept outside the repository.
3. A media container is created, polled until FINISHED, then published. An
   unpublished container dies after 24 hours, so publishing follows immediately.
4. The account's own quota is read before any write (Meta's guide says 100 posts per
   rolling 24 hours while the endpoint itself has returned 50), and the publisher
   stops short of it instead of collecting error 9 / subcode 2207042.
5. Every publish is recorded in a tracker keyed by the shared social identity, so a
   rerun, a retry or a second dispatch can never post the same article twice.

Daily Yield never opens its own public pages from a job, so this module does not
either: no request is ever made to a dailyyield.blogspot.com URL.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")

MODE = (os.environ.get("INSTAGRAM_API_MODE") or "instagram_login").strip().lower()
HOST = "graph.instagram.com" if MODE != "facebook_login" else "graph.facebook.com"
VERSION = os.environ.get("INSTAGRAM_GRAPH_VERSION", "v26.0")
API = f"https://{HOST}/{VERSION}"
GRAPH = f"https://graph.facebook.com/{VERSION}"

TOKEN_FILE = ROOT / "instagram_token.enc"
STATE = ROOT / "instagram_token_state.json"
TRACKER = ROOT / "instagram_tracker.json"
PLAN = ROOT / "INSTAGRAM_PLAN.json"
STATUS = ROOT / "INSTAGRAM_ROUTE_STATUS.json"
HEALTH = ROOT / "SOCIAL_CREDENTIAL_HEALTH.json"
SLOT_EVIDENCE = ROOT / "SLOT_GUARANTEE_STATUS.json"
EDITIONS = ROOT / "LIVE_EDITION_VERIFICATION.json"
MASTER_TRACKER = ROOT / "MASTER_AUTOMATION_TRACKER.json"

RAW_ASSET_BASE = "https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main"
TIMEOUT = (15, 60)
MAX_CAPTION = 2200          # Instagram caption limit
MAX_HASHTAGS = 30           # more are ignored by Instagram, so they are not written
MAX_MENTIONS = 20
MAX_ALT = 1000              # alt text limit for a single-image post
MIN_SPACING = dt.timedelta(minutes=20)

BRAND_LINES = (
    "Daily Yield · news-led financial education",
    "Sources named in the article",
    "General education only · not personal advice",
)

DEFAULT_PLAN = {
    # Cadence is one editable value, not a code change. The owner set this on 20 Oct 2026:
    # Master articles only, five a day, in a 2 evergreen : 3 trending mix, until said
    # otherwise. Five a day also keeps the account far inside the lowest quota Meta has
    # been returning (50 per 24 hours), which leaves room for retries.
    "postsPerDay": 5,
    "targets": "masters_only",
    "mix": {"evergreen": 2, "trending": 3},
    "minSpacingMinutes": 20,
    "captionHashtags": ["#DailyYield", "#PersonalFinanceIndia", "#FinancialLiteracy"],
}


def clean(value) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def plan() -> dict:
    stored = load(PLAN, {})
    merged = {**DEFAULT_PLAN, **{k: v for k, v in (stored or {}).items() if k in DEFAULT_PLAN}}
    merged["postsPerDay"] = max(1, min(24, int(merged.get("postsPerDay") or 5)))
    merged["minSpacingMinutes"] = max(5, min(180, int(merged.get("minSpacingMinutes") or 20)))
    # A mix can never ask for more than the day holds, and a negative budget would mean
    # "post nothing of this kind", so both ends are clamped rather than trusted.
    mix = merged.get("mix") or {}
    merged["mix"] = {kind: max(0, min(merged["postsPerDay"], int(mix.get(kind) or 0)))
                     for kind in ("evergreen", "trending")}
    return merged


def blocked_url(url: str) -> bool:
    """Zero-view policy: a job of ours must never fetch a public Daily Yield page."""
    return "dailyyield.blogspot.com" in str(url).lower()


# --------------------------------------------------------------------- credentials
def _decrypt(blob: bytes) -> str:
    key = os.environ.get("INSTAGRAM_TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("INSTAGRAM_TOKEN_ENCRYPTION_KEY is required to read the stored token")
    from cryptography.fernet import Fernet
    return Fernet(key.encode()).decrypt(blob).decode().strip()


def access_token() -> str:
    """Read the token, then sanity-check it before anything is sent.

    A paste that was cut short on a phone, or the App Secret in the wrong box, reaches the
    graph host as a string it cannot parse. Instagram then answers "Invalid OAuth access
    token - Cannot parse access token", which reads like a dead login and sends an owner to
    re-authorise from scratch. Naming the shape here is the difference between re-pasting one
    field and rebuilding the whole connection.
    """
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = _decrypt(TOKEN_FILE.read_bytes())
    token = "".join(token.split()).strip("'\"")
    if not token:
        raise RuntimeError(
            "not connected: no INSTAGRAM_ACCESS_TOKEN secret and no instagram_token.enc. In GitHub, "
            "Settings -> Secrets and variables -> Actions, the token must be a SECRET named exactly "
            "INSTAGRAM_ACCESS_TOKEN - a Variable of that name is not read here")
    if len(token) < 40 or "|" in token or not token.isascii():
        raise RuntimeError(
            "the stored INSTAGRAM_ACCESS_TOKEN is not shaped like an Instagram access token: it is too "
            "short, or it holds a pipe or non-ASCII text. That usually means the App Secret was pasted "
            "instead, or the copy was cut off on the way. Re-copy it with the copy button on the "
            "@daily_yield row of the Instagram setup page and overwrite that one secret")
    return token


def ig_user_id() -> str:
    """The professional account's own id.

    With Instagram Login the token can answer this itself, because /me on
    graph.instagram.com returns the Instagram-scoped id of the account that granted it.
    That matters for the owner: pasting one token into GitHub is then the entire
    connection, with no numeric id to hunt for in a dashboard. Under Facebook Login the
    same call would return a person's Facebook id, so that mode still needs the id.
    """
    value = os.environ.get("INSTAGRAM_IG_USER_ID", "").strip()
    if value:
        return value
    state = load(STATE, {})
    if state.get("ig_user_id"):
        return str(state["ig_user_id"])
    if MODE == "facebook_login":
        raise RuntimeError("INSTAGRAM_IG_USER_ID is required when INSTAGRAM_API_MODE=facebook_login "
                           "(the token's /me is a Facebook person, not the professional account)")
    response = request("GET", "/me", params={"fields": "id"})
    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    identifier = str(body.get("id") or "").strip()
    if not response.ok or not identifier:
        error = (body or {}).get("error") or {}
        raise RuntimeError("the token could not identify its own account via /me: "
                           + str(error.get("message") or body or "no id returned")[:300])
    return identifier


def record_health(ok: bool, reason: str) -> None:
    """Visible credential state, in the same file the social guard already reads."""
    data = load(HEALTH, {})
    if not isinstance(data, dict):
        data = {}
    data["instagram"] = {"ok": bool(ok), "reason": clean(reason)[:180],
                        "checkedAt": dt.datetime.now(IST).isoformat()}
    save(HEALTH, data)


def refresh_if_needed() -> dict:
    """Long-lived Instagram tokens die after 60 days; refresh before they expire."""
    state = load(STATE, {})
    expires = state.get("expires_at")
    note = {"refreshed": False, "expiresAt": expires}
    if not expires or MODE == "facebook_login":
        return note
    try:
        remaining = dt.datetime.fromisoformat(str(expires)) - dt.datetime.now(dt.timezone.utc)
    except ValueError:
        return note
    if remaining > dt.timedelta(days=7):
        return note
    app_id = os.environ.get("INSTAGRAM_APP_ID", "").strip()
    app_secret = os.environ.get("INSTAGRAM_APP_SECRET", "").strip()
    if not (app_id and app_secret):
        raise RuntimeError("token expires in less than 7 days but the app id/secret are not stored, "
                           "so it cannot be refreshed; re-run the Instagram OAuth bootstrap")
    response = request("GET", "/refresh_access_token", params={"grant_type": "ig_refresh_token"})
    response.raise_for_status()
    payload = response.json()
    if "access_token" not in payload:
        raise RuntimeError(f"Instagram refused to refresh the token: {payload}")
    blob = base64.urlsafe_b64decode(payload["access_token"] + "=" * (-len(payload["access_token"]) % 4)) \
        if False else payload["access_token"]
    key = os.environ.get("INSTAGRAM_TOKEN_ENCRYPTION_KEY", "").strip()
    if key:
        from cryptography.fernet import Fernet
        TOKEN_FILE.write_bytes(Fernet(key.encode()).encrypt(blob.encode()))
    state.update({"ig_user_id": payload.get("user_id") or state.get("ig_user_id"),
                  "expires_at": (dt.datetime.now(dt.timezone.utc)
                                 + dt.timedelta(seconds=int(payload.get("expires_in") or 5184000))).isoformat(),
                  "refreshed_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    save(STATE, state)
    note.update({"refreshed": True, "expiresAt": state["expires_at"]})
    return note


# ------------------------------------------------------------------------- limits
def quota() -> dict:
    """Read the account's own publishing cap instead of trusting a documentation number."""
    try:
        response = request("GET", f"/{ig_user_id()}/content_publishing_limit")
        if not response.ok:
            return {"known": False, "reason": f"limit read failed ({response.status_code})"}
        row = ((response.json().get("data") or [{}])[0]).get("quota_usage_total") or {}
        used = int(row.get("quota_usage") or 0)
        total = int(row.get("quota_total") or 50)
        return {"known": True, "used": used, "total": total, "remaining": max(0, total - used)}
    except requests.RequestException as exc:
        return {"known": False, "reason": str(exc)[:160]}


# ------------------------------------------------------------------- what is live
def eligible(day: str | None = None) -> list[dict]:
    """Articles this repository can prove are live, with their own licensed image."""
    day = day or dt.datetime.now(IST).strftime("%Y-%m-%d")
    found: dict[str, dict] = {}

    slot = load(SLOT_EVIDENCE, {})
    for row in (slot.get("rows") or []):
        if row.get("live") and (row.get("url") or "").startswith("https://"):
            found.setdefault(row.get("key") or row["url"], {}).update(
                {"key": row.get("key") or row["url"], "url": row["url"],
                 "title": clean(row.get("title") or ""), "state": row.get("state")})

    verified = load(EDITIONS, {})
    for row in (verified.get("rows") or []):
        if row.get("ok") and row.get("day") == day and row.get("url"):
            key = row.get("desk") or row["url"]
            found.setdefault(key, {"key": key, "url": row["url"]})
            found[key]["title"] = clean(row.get("title") or found[key].get("title") or "")

    tracker = load(MASTER_TRACKER, {})
    records = tracker if isinstance(tracker, list) else (tracker.get("records") or tracker.get("articles") or [])
    for row in records:
        if str(row.get("date") or row.get("dateIST") or "") == day and row.get("url") and row.get("status") in (
                "PUBLISHED", "LIVE", None):
            key = row.get("slotKey") or f"{row.get('kind')}-{row.get('slot')}"
            found.setdefault(key, {"key": key, "url": row["url"]})
            found[key]["title"] = clean(row.get("title") or found[key].get("title") or "")
            found[key]["kind"] = row.get("kind") or ""
    # An article URL is evidence and caption text, never something this job fetches:
    # blocked_url guards every request, and public_jpeg refuses a Daily Yield image
    # URL, which is the case that would create a synthetic page view.
    return [row for row in found.values() if row.get("url")]


def slug_of(url: str) -> str:
    match = re.search(r"/([0-9]{4}/[0-9]{2}/)?([a-z0-9][a-z0-9-]{6,})\.html", str(url or ""))
    return (match.group(2) if match else "").strip("-")


def image_for(item: dict) -> dict:
    """The article's own editorial photograph, as a JPEG URL Meta can fetch.

    Master articles keep three licensed photographs in this repository at a public raw
    URL. News editions carry their hero inside the built HTML committed alongside them.
    If neither exists the post is refused: no stock substitution, no invented picture,
    and no second copy of an image just to satisfy a social network.
    """
    slug = slug_of(item.get("url", ""))
    if slug:
        for placement in (1, 2, 3):
            asset = ROOT / "assets" / "master" / slug / f"photo-{placement}.jpg"
            if asset.exists() and asset.stat().st_size > 20_000:
                return {"url": f"{RAW_ASSET_BASE}/assets/master/{slug}/photo-{placement}.jpg",
                        "basis": "repository-asset", "credit": item.get("credit", ""),
                        "bytes": asset.stat().st_size}
        for candidate in sorted((ROOT / "scheduled_ready").glob(f"*{slug}*.html")):
            body = candidate.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"<img[^>]+src=\"([^\"]+)\"", body, re.I)
            if match and not blocked_url(match.group(1)):
                return {"url": public_jpeg(match.group(1)), "basis": "built-edition-hero",
                        "credit": "", "bytes": 0}
    return {"url": "", "basis": "none", "credit": "", "bytes": 0}


def public_jpeg(url: str) -> str:
    """Instagram publishes JPEG only: ask the host for it instead of hoping."""
    url = str(url or "").strip()
    if not url or blocked_url(url):
        return ""
    lowered = url.lower()
    if any(extension in lowered for extension in (".png", ".webp", ".gif", ".avif", ".svg")):
        return ""
    if "unsplash.com" in lowered:
        base, _, query = url.partition("?")
        pairs = dict(pair.split("=", 1) for pair in query.split("&") if "=" in pair)
        pairs.update({"fm": "jpg", "q": "85"})
        return base + "?" + "&".join(f"{key}={value}" for key, value in pairs.items())
    return url


# ------------------------------------------------------------------------ wording
def caption(item: dict, hashtags: list[str] | None = None) -> str:
    title = clean(item.get("title") or "Daily Yield")[:180]
    lines = [title, ""]
    lead = clean(item.get("lead") or "")
    if lead:
        lines.append(lead[:300])
    lines += list(BRAND_LINES)
    body = "\n".join(part for part in lines if part is not None)
    tags = [tag for tag in dict.fromkeys(hashtags or plan()["captionHashtags"])
            if re.fullmatch(r"#[\w.]{2,30}", str(tag))][:MAX_HASHTAGS]
    text = body.rstrip() + ("\n\n" + " ".join(tags) if tags else "")
    text = text[:MAX_CAPTION]
    if text.count("@") > MAX_MENTIONS:
        text = re.sub(r"@\w+", "", text)[:MAX_CAPTION]
    return text


def alt_text(item: dict, image: dict) -> str:
    title = clean(item.get("title") or "Daily Yield article")
    return (f"Educational photograph for the Daily Yield article titled: {title}")[:MAX_ALT]


# ------------------------------------------------------------------- the API calls
# One guarded exit for every Instagram call: the access token is attached here, retries
# back off, and a Daily Yield page URL can never be sent to any service from this job.
def request(method: str, path: str, *, params: dict | None = None, retries: int = 3):
    url = path if path.startswith("https://") else f"{API}{path}"
    if blocked_url(url) or any(blocked_url(str(value)) for value in (params or {}).values()):
        raise RuntimeError("refusing to send a Daily Yield page URL to any service: this job must not "
                           "create page views")
    query = {"access_token": access_token(), **(params or {})}
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.request(method, url, params=query, timeout=TIMEOUT)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                dt.datetime.now()  # back off without hammering a rate-limited API
                import time as _time
                _time.sleep(min(60, 6 * attempt))
                continue
            return response
        except requests.RequestException as exc:
            last = exc
            if attempt == retries:
                raise
            import time as _time
            _time.sleep(min(30, 4 * attempt))
    raise RuntimeError(str(last or "unreachable"))


def publish(item: dict, image: dict, *, dry_run: bool) -> dict:
    text = caption(item)
    alt = alt_text(item, image)
    if dry_run:
        return {"dryRun": True, "wouldPost": True, "captionLength": len(text),
                "imageUrl": image["url"], "altLength": len(alt)}
    created = request("POST", f"/{ig_user_id()}/media",
                      params={"image_url": image["url"], "caption": text, "alt_text": alt})
    body = created.json() if created.headers.get("content-type", "").startswith("application/json") else {}
    if not created.ok:
        error = str(body.get("error", {}))
        raise RuntimeError(f"container rejected: {error[:300]}")
    container = str(body.get("id") or "")
    if not container:
        raise RuntimeError("container creation returned no id")

    status = "FINISHED"
    for _ in range(10):
        check = request("GET", f"/{container}", params={"fields": "status_code"})
        # A single-image container is normally finished on creation. Absence of the
        # field is not an error, and holding a slot for a minute of polling only delays
        # the post and burns runner minutes, so an unknown status is treated as ready.
        status = str((check.json() or {}).get("status_code") or "FINISHED")
        if status in ("FINISHED", "ERROR", "EXPIRED"):
            break
        import time as _time
        _time.sleep(2)
    if status != "FINISHED":
        # Never blindly retry a write: an ERROR container must not become a duplicate
        # post, and the reason has to survive in the status file for the daily report.
        raise RuntimeError(f"media container did not become publishable (status {status})")

    published = request("POST", f"/{ig_user_id()}/media_publish", params={"creation_id": container})
    result = published.json() if published.headers.get("content-type", "").startswith("application/json") else {}
    if not published.ok:
        code = ((result.get("error") or {}).get("code"), (result.get("error") or {}).get("error_subcode"))
        raise RuntimeError(f"publish rejected (code {code[0]}, subcode {code[1]}): "
                           f"{(result.get('error') or {}).get('message', '')[:200]}")
    return {"mediaId": str(result.get("id") or ""), "container": container}


# ------------------------------------------------------------------------- ledger
def identity(row: dict) -> str:
    for key in ("url", "caption_hash", "text_hash", "published_at"):
        if row.get(key):
            return f"{key}:{row[key]}"
    return "fallback|" + "|".join(str(row.get(key, "")) for key in ("url", "caption_hash"))


def already_posted(tracker: dict, url: str) -> bool:
    return any(str(row.get("url")) == url for row in tracker.get("published", []))


def last_post_age(tracker: dict) -> dt.timedelta:
    rows = [row for row in tracker.get("published", []) if row.get("published_at")]
    if not rows:
        return dt.timedelta(days=9)
    try:
        return dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(str(rows[-1]["published_at"]))
    except ValueError:
        return dt.timedelta(days=9)


def posts_today(tracker: dict, day: str) -> int:
    return sum(1 for row in tracker.get("published", []) if str(row.get("published_at", ""))[:10] == day
               or str(row.get("publishedAtIST", ""))[:10] == day)


def _kind_of(row: dict) -> str:
    """Evergreen or trending, read from what the slot system already recorded."""
    text = f"{row.get('kind') or ''} {row.get('key') or ''} {row.get('url') or ''}".lower()
    if "evergreen" in text:
        return "evergreen"
    if "trending" in text:
        return "trending"
    return "other"


def posts_by_kind(tracker: dict, day: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in tracker.get("published", []):
        stamp = str(row.get("publishedAtIST", ""))[:10] or str(row.get("published_at", ""))[:10]
        if stamp == day:
            kind = str(row.get("kind") or "other")
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def day_budgets(configuration: dict, tracker: dict, day: str) -> tuple[dict, int, dict]:
    """What is still owed per kind, how many posts are left today, and what went out."""
    posted = posts_by_kind(tracker, day)
    mix = configuration.get("mix") or {}
    owed = {kind: max(0, int(mix.get(kind) or 0) - posted.get(kind, 0)) for kind in ("evergreen", "trending")}
    remaining = max(0, int(configuration["postsPerDay"]) - posts_today(tracker, day))
    return owed, remaining, posted


def ordered_queue(chosen: list[dict], owed: dict, cap: int, budgets: dict | None = None) -> tuple[list[dict], bool]:
    """Build today's queue in the owner's 2:3 evergreen:trending shape.

    The kind that is furthest below its own share of the day goes first, and a tie goes to
    trending, because a trending article is the one that stops being true by tomorrow. Five
    posts at a 2:3 mix therefore reads trending, evergreen, trending, evergreen, trending
    rather than two same-kind blocks back to back.

    If a pool runs short, the rest of the allowance is filled from what is live and still
    unposted instead of being left empty, and the caller is told the mix was relaxed.
    """
    pools = {kind: sorted([row for row in chosen if _kind_of(row) == kind],
                           key=lambda row: str(row.get("key") or ""))
             for kind in ("evergreen", "trending", "other")}
    balance = {kind: int(owed.get(kind) or 0) for kind in ("evergreen", "trending")}
    wanted = {kind: max(int((budgets or {}).get(kind) or 0), balance[kind]) for kind in balance}

    def behind(kind: str) -> float:
        if wanted[kind] <= 0:
            return 99.0
        return (wanted[kind] - balance[kind]) / wanted[kind]

    queue: list[dict] = []
    relaxed = False
    while len(queue) < cap:
        order = sorted(("trending", "evergreen"), key=lambda kind: (behind(kind), kind != "trending"))
        picked = next((kind for kind in order if balance[kind] > 0 and pools[kind]), None)
        if picked:
            queue.append(pools[picked].pop(0))
            balance[picked] -= 1
            continue
        rest = sorted(pools["evergreen"] + pools["trending"] + pools["other"],
                      key=lambda row: str(row.get("key") or ""))
        if not rest:
            break
        row = rest[0]
        for kind in ("evergreen", "trending", "other"):
            if row in pools[kind]:
                pools[kind].remove(row)
                break
        relaxed = relaxed or balance["evergreen"] > 0 or balance["trending"] > 0
        queue.append(row)
    return queue, relaxed


def masters_only(items: list[dict], include_digest: bool) -> tuple[list[dict], dict | None]:
    chosen = [row for row in items if str(row.get("key", "")).startswith("master-")]
    digest = None
    if include_digest:
        news = [row for row in items if str(row.get("key", "")).startswith("news-")]
        if news:
            lines = [f"{index + 1}. {clean(row.get('title') or row['url'].rstrip('/').rsplit('/', 1)[-1])[:80]}"
                     for index, row in enumerate(news[:11])]
            digest = {"key": "instagram-digest", "title": f"Today on Daily Yield · {dt.datetime.now(IST):%d %B %Y}",
                      "url": news[0]["url"].rsplit("/", 2)[0] + "/", "lead": "\n".join(lines),
                      "digestOf": [row["url"] for row in news]}
    return chosen, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("sweep", "health", "preflight"), default="sweep")
    parser.add_argument("--dry-run", action="store_true",
                        help="build and check the post without creating a container")
    parser.add_argument("--force", action="store_true", help="ignore the spacing pause once")
    arguments = parser.parse_args()

    configuration = plan()
    tracker = load(TRACKER, {"version": 1, "published": [], "skipped": []})
    day_ist = dt.datetime.now(IST)
    report: dict = {"checkedAtIST": day_ist.isoformat(), "apiMode": MODE, "host": HOST,
                    "postsPerDay": configuration["postsPerDay"], "dryRun": bool(arguments.dry_run),
                    "published": [], "skipped": [], "notes": []}

    try:
        token = access_token()
    except RuntimeError as exc:
        record_health(False, str(exc))
        report["status"] = "NOT_CONNECTED"
        report["notes"].append(clean(str(exc)))
        save(STATUS, report)
        print(json.dumps({"status": "NOT_CONNECTED", "reason": clean(str(exc))[:200]}))
        return 0

    try:
        refresh = refresh_if_needed()
        limit = quota()
        identity_row = request("GET", f"/{ig_user_id()}", params={"fields": "id,username,account_type"})
        profile = identity_row.json() if identity_row.ok else {}
        if not identity_row.ok or not profile.get("id"):
            raise RuntimeError(f"identity check failed: {(identity_row.json() or {}).get('error', {})}".replace(
                "{", "").replace("}", "")[:220])
        if str(profile.get("account_type", "")).upper() not in ("BUSINESS", "CREATOR"):
            raise RuntimeError("the connected account is not a Business or Creator account, so Instagram will "
                               "not accept API publishing")
    except Exception as exc:
        record_health(False, str(exc))
        report["status"] = "CHECK_FAILED"
        report["notes"].append(clean(str(exc))[:240])
        save(STATUS, report)
        print(json.dumps({"status": "CHECK_FAILED", "reason": clean(str(exc))[:220]}))
        return 0

    record_health(True, f"connected as @{profile.get('username')} ({profile.get('account_type')})")
    report["account"] = {"username": profile.get("username"), "accountType": profile.get("account_type"),
                         "userId": profile.get("id")}
    report["tokenExpiresAt"] = refresh.get("expiresAt")
    report["tokenRefreshed"] = bool(refresh.get("refreshed"))
    report["quota"] = limit

    if arguments.mode == "health":
        report["status"] = "PASS"
        save(STATUS, report)
        print(json.dumps({key: report[key] for key in ("status", "account", "quota", "tokenExpiresAt")},
                         ensure_ascii=False))
        return 0

    owed, remaining_plan, posted_by_kind = day_budgets(configuration, tracker, str(day_ist.date()))
    used_today = posts_today(tracker, str(day_ist.date()))
    if remaining_plan <= 0:
        report["status"] = "DAY_COMPLETE"
        save(STATUS, report)
        print(json.dumps({"status": "DAY_COMPLETE", "published": used_today,
                          "postsPerDay": configuration["postsPerDay"]}))
        return 0
    if not arguments.force and last_post_age(tracker) < dt.timedelta(minutes=configuration["minSpacingMinutes"]):
        report["status"] = "SPACING_PAUSE"
        save(STATUS, report)
        print(json.dumps({"status": "SPACING_PAUSE",
                          "nextEligibleInMinutes": int((dt.timedelta(minutes=configuration["minSpacingMinutes"])
                                                        - last_post_age(tracker)).total_seconds() // 60)}))
        return 0
    if limit.get("known") and int(limit.get("remaining", 0)) < 2:
        # Two slots are kept free: one for this post and one for a retry of it.
        report["status"] = "QUOTA_PAUSE"
        save(STATUS, report)
        print(json.dumps({"status": "QUOTA_PAUSE", "quota": limit}))
        return 0

    items = eligible()
    targets = str(configuration.get("targets", ""))
    chosen, digest = masters_only(items, targets in ("masters_plus_digest", "digest_only"))
    # Refuse before queueing, never inside the post loop. A candidate that was already posted
    # or has no accepted photograph used to sit in the queue and consume one of the day's five
    # slots, so a run could report success while publishing nothing at all.
    queueable: list[dict] = []
    for row in chosen:
        if already_posted(tracker, row["url"]):
            report["skipped"].append({"key": row.get("key"), "reason": "already posted today or on an earlier day"})
            continue
        image = image_for(row)
        if not image["url"]:
            reason = "no licensed JPEG photograph available for this article"
            report["skipped"].append({"key": row.get("key"), "reason": reason})
            tracker.setdefault("skipped", []).append({"url": row["url"], "key": row.get("key"),
                                                      "reason": reason, "atIST": day_ist.isoformat()})
            continue
        enriched = dict(row)
        enriched["image"] = image
        queueable.append(enriched)
    queue, relaxed = ([], False) if targets == "digest_only" else ordered_queue(
        queueable, owed, remaining_plan, configuration.get("mix"))
    if digest:
        queue = queue + [digest]
    report["liveEligible"] = len(items)
    report["poolAfterRefusals"] = len(queueable)
    report["mix"] = {"wanted": configuration.get("mix"), "stillOwed": owed,
                     "postedTodayByKind": posted_by_kind, "relaxed": relaxed}
    report["queueLength"] = len(queue)

    for item in queue:
        url = item["url"]
        image = item.get("image") or image_for(item)
        if not image["url"]:
            reason = "no licensed JPEG photograph available for this article"
            report["skipped"].append({"key": item.get("key"), "reason": reason})
            tracker.setdefault("skipped", []).append({"url": url, "key": item.get("key"),
                                                      "reason": reason, "atIST": day_ist.isoformat()})
            continue
        try:
            result = publish(item, image, dry_run=arguments.dry_run or arguments.mode == "preflight")
        except Exception as exc:
            report["skipped"].append({"key": item.get("key"), "reason": clean(str(exc))[:200]})
            continue
        row = {"url": url, "key": item.get("key"), "kind": _kind_of(item), "caption_hash": hashlib.sha256(
            caption(item).encode()).hexdigest()[:16], "imageBasis": image["basis"],
            "publishedAtIST": dt.datetime.now(IST).isoformat()}
        if result.get("dryRun"):
            row["dryRun"] = True
            report["published"].append(row)
            continue
        row["instagramMediaId"] = result.get("mediaId")
        row["permalinkCheck"] = "not read (no public Instagram request from a job)"
        tracker["published"].append(row)
        tracker["published"] = tracker["published"][-1000:]
        save(TRACKER, tracker)
        report["published"].append(row)

    report["status"] = ("PREFLIGHT" if arguments.mode == "preflight" else
                        "DRY_RUN" if arguments.dry_run else "PASS")
    report["publishedToday"] = used_today + sum(1 for row in report["published"] if not row.get("dryRun"))
    save(STATUS, report)
    save(TRACKER, tracker)
    print(json.dumps({"status": report["status"], "published": report["publishedToday"],
                      "skipped": len(report["skipped"]), "quota": limit, "mix": report["mix"],
                      "queued": [row.get("key") for row in report["published"]],
                      "account": report["account"]["username"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
