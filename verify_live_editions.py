#!/usr/bin/env python3
"""Say, in plain words, why a live post does or does not count as a day's edition.

The recovery controller now verifies every record against the live post before it
trusts it. This script runs the same verification and prints the reason for each
desk, so a failing check names its cause instead of hiding behind a boolean.

It reads the blog through the authenticated API only: no public request is made,
so no pageview is added.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import news_pipeline
import publishing_recovery

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "LIVE_EDITION_VERIFICATION.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")


def verify(url: str, token: str, day: dt.date) -> dict:
    """Return the verdict plus the exact reason, mirroring the production check."""
    import urllib.parse
    detail: dict = {"url": url, "day": day.isoformat()}
    try:
        path = urllib.parse.urlparse(url).path
        query = urllib.parse.urlencode({"path": path, "fetchBody": "true",
                                        "fields": "id,url,status,title,content"})
        post = news_pipeline.blogger_call("/posts/bypath?" + query, token)
    except Exception as exc:  # noqa: BLE001
        return {**detail, "ok": False, "reason": f"bypath read failed: {exc}"}
    detail["status"] = post.get("status")
    body = post.get("content", "") or ""
    heading = news_pipeline.headline_of(body, post.get("title", ""))
    declared = [heading]
    for pattern in (r"fbk-date[^>]*>(.*?)<", r"Published\s+([^<\u00b7]{0,60})",
                    r"Last reviewed\s+([^<\u00b7]{0,60})"):
        found = re.search(pattern, body, re.S)
        if found:
            declared.append(news_pipeline.htmlmod.unescape(news_pipeline.strip_tags(found.group(1))))
    detail["declaredLine"] = " | ".join(x.strip() for x in declared if x.strip())[:220]
    expected = [f"{day.day} {day.strftime('%B %Y')}"]
    detail["expectedEditionDate"] = expected[0]
    if not any(marker.casefold() in detail["declaredLine"].casefold() for marker in expected):
        return {**detail, "ok": False, "reason": "the post's own date line is not this edition's date"}
    try:
        news_pipeline.assert_saved_green(post)
    except Exception as exc:  # noqa: BLE001
        return {**detail, "ok": False, "reason": f"green verification: {str(exc)[:220]}"}
    return {**detail, "ok": True, "reason": "live post carries this edition and passes the green checks"}


def main() -> int:
    token = publishing_recovery.live_token()
    if not token:
        OUT.write_text(json.dumps({"status": "NO_CREDENTIALS"}, indent=1) + "\n", encoding="utf-8")
        print("no Blogger credentials in this environment")
        return 0
    day = dt.datetime.now(IST).date()
    tracker = json.loads((ROOT / "news_tracker.json").read_text(encoding="utf-8")).get("desks", {})
    # The recovery controller calls the engine's own function. Print its verdict
    # beside this script's step-by-step verdict so a disagreement is visible.
    disagreements = []
    rows = []
    for desk, row in sorted(tracker.items()):
        url = row.get("url", "")
        if not url:
            continue
        verdict = verify(url, token, day)
        verdict["desk"] = desk
        verdict["engineFunctionSays"] = news_pipeline.live_current_edition(
            url, token, day, alt_dates=(day - dt.timedelta(days=1),))
        if verdict["ok"] != verdict["engineFunctionSays"]:
            disagreements.append(desk)
        verdict["recordedEdition"] = row.get("edition", "")
        rows.append(verdict)
    OUT.write_text(json.dumps({"checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                               "dateIST": day.isoformat(), "rows": rows,
                               "confirmed": sum(1 for r in rows if r["ok"]),
                               "engineFunctionAgrees": not disagreements,
                               "disagreements": disagreements,
                               "syntheticViews": 0, "publicDailyYieldRequests": 0}, indent=1) + "\n",
                   encoding="utf-8")
    for row in rows:
        print(f"{row['desk']:13s} script={'OK' if row['ok'] else 'NO'} engine="
              f"{'OK' if row.get('engineFunctionSays') else 'NO'} | {row['reason'][:95]}")
    if disagreements:
        print(json.dumps({"disagreements": disagreements}))
    print(json.dumps({"confirmed": sum(1 for r in rows if r["ok"]), "checked": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
