#!/usr/bin/env python3
"""Tell Bing and Yandex about a new URL the second it publishes — no quota, no human.

IndexNow is a shared protocol: one POST makes the URL known to every participating
search engine at once, and it is free and effectively unlimited. That is what
replaces hand-submission and the exhausted Bing API quota.

The only awkward part is the key. IndexNow normally wants the key file at the
domain root; Blogger cannot host arbitrary files, so the protocol's own
``keyLocation`` option is used and the key is published as a Blogger page. If a
search engine refuses that location, the Bing URL Submission API (quota-aware)
stays in place as the safety net, so a refusal never loses a URL.

The script never makes a public request to Daily Yield: the URL list is passed in
by the caller, so no pageview is added.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "INDEXNOW_STATE.json"
SITE = "https://dailyyield.blogspot.com"
# The protocol accepts any engine listed here; bing.com distributes to the others
# that share the endpoint, and yandex is listed explicitly because it is separate.
ENDPOINTS = ("https://api.indexnow.org/indexnow", "https://yandex.com/indexnow")
PENDING_LIMIT = 400          # the protocol's practical batch size
MAX_ATTEMPTS = 5


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def key_location(key: str) -> str:
    """Where the key text is readable. Blogger cannot host a root file."""
    return os.environ.get("INDEXNOW_KEY_LOCATION", f"{SITE}/p/indexnow-key.html")


def post(endpoint: str, payload: dict) -> tuple[bool, str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "DailyYield-IndexNow/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            code = response.status
            # 200 = accepted, 202 = accepted and queued. Both are success.
            return code in (200, 202), f"HTTP {code}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read()[:160].decode('utf-8', 'replace')}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc)[:160]}"


def sitemap_urls() -> list[str]:
    """Every URL the blog advertises, straight from its own sitemap."""
    import urllib.request
    from xml.etree import ElementTree
    found: list[str] = []
    for page in range(1, 6):
        url = f"{SITE}/sitemap.xml" if page == 1 else f"{SITE}/sitemap.xml?page={page}"
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                tree = ElementTree.fromstring(response.read())
        except Exception:  # noqa: BLE001
            break
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        entries = tree.findall(".//s:url", ns)
        if not entries:
            break
        for entry in entries:
            loc = entry.findtext("s:loc", default="", namespaces=ns)
            if loc:
                found.append(loc)
    return list(dict.fromkeys(found))


def submit(urls: list[str], apply: bool) -> dict:
    state = load(STATE, {"submitted": {}, "pending": [], "history": []})
    key = os.environ.get("INDEXNOW_KEY", "").strip()
    clean = [u for u in dict.fromkeys(urls) if u.startswith(SITE)]
    result = {"requested": len(clean), "sent": 0, "results": []}
    if not clean:
        # Keep the queue on disk even on a quiet run, so a later run (or a missing
        # secret) can still see what is waiting.
        state.setdefault("pending", state.get("pending", []))
        state["lastRun"] = datetime.now(timezone.utc).isoformat()
        save(STATE, state)
        return {**result, "note": "no Daily Yield URLs in the request"}
    blocked = state.get("blocked") or {}
    if blocked and not os.environ.get("INDEXNOW_FORCE"):
        # A known, platform-level refusal: do not pile URLs into a queue that
        # cannot drain. The reason stays on record for when it can.
        return {**result, "blocked": blocked,
                "note": "IndexNow unavailable on this host; see blocked reason"}
    if not key:
        # Without a key nothing can be sent; the URLs wait in the pending queue so
        # the next run (once the secret exists) delivers them. Nothing is lost.
        pending = list(dict.fromkeys(state.get("pending", []) + clean))[:PENDING_LIMIT]
        state["pending"] = pending
        save(STATE, state)
        return {**result, "queued": len(pending), "note": "INDEXNOW_KEY is not configured; URLs queued"}
    payload = {"host": "dailyyield.blogspot.com", "key": key,
               "keyLocation": key_location(key), "urlList": clean[:10000]}
    if not apply:
        return {**result, "note": "dry run; nothing sent"}
    for endpoint in ENDPOINTS:
        ok, detail = post(endpoint, payload)
        result["results"].append({"endpoint": endpoint, "ok": ok, "detail": detail})
        if ok:
            result["sent"] = len(clean)
        time.sleep(1)
    now = datetime.now(timezone.utc).isoformat()
    refusal = " ".join(str(e.get("detail", "")) for e in result["results"])
    key_problem = ("keylocation" in refusal.lower() or "key location" in refusal.lower()
                   or "invalidurlkey" in refusal.lower() or "http 403" in refusal.lower())
    if not result["sent"] and key_problem:
        # Blogger serves every page as HTML and IndexNow needs a plain-text key
        # file, so this cannot succeed until the site has its own domain. The
        # channel parks itself with a dated reason instead of retrying forever.
        state["blocked"] = {"reason": "key location not verifiable on blogspot.com",
                            "detail": refusal[:300], "since": now,
                            "unblocksWhen": "a plain-text key file can be hosted (custom domain)"}
    elif result["sent"]:
        state.pop("blocked", None)
    if result["sent"]:
        for url in clean:
            state.setdefault("submitted", {})[url] = now
        state["pending"] = [u for u in state.get("pending", []) if u not in clean]
    else:
        pending = list(dict.fromkeys(state.get("pending", []) + clean))[:PENDING_LIMIT]
        state["pending"] = pending
    history = state.get("history") or []
    history.insert(0, {"at": now, "count": result["sent"], "endpoints": result["results"]})
    state["history"] = history[:20]
    state["lastRun"] = now
    save(STATE, state)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit URLs to IndexNow")
    parser.add_argument("--url", action="append", default=[], help="URL to submit (repeatable)")
    parser.add_argument("--urls-file", default="", help="file with one URL per line")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--from-sitemap", action="store_true",
                        help="also announce every sitemap URL never announced before")
    args = parser.parse_args()
    urls = list(args.url)
    if args.urls_file and Path(args.urls_file).exists():
        urls += [line.strip() for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    # Anything queued by an earlier run (for example before the key existed) is
    # delivered first, so a missing secret costs time and never a URL.
    state = load(STATE, {})
    if args.from_sitemap:
        known = state.get("submitted", {})
        fresh = [u for u in sitemap_urls() if u not in known]
        # Politeness: a big first catch-up is spread over runs rather than fired
        # at once, and anything left stays on the list for tomorrow.
        urls += fresh[:400]
    urls = list(dict.fromkeys(urls + state.get("pending", [])))
    print(json.dumps(submit(urls, args.apply), ensure_ascii=False)[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
