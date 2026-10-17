#!/usr/bin/env python3
"""Ask Bing, in plain words, what it will actually accept — and record the answer.

Submission channels have different rules, and guessing is how URL lists get lost.
This check is read-mostly: it reads the quota, then makes one tiny, real attempt on
each channel so the recorded status is evidence rather than assumption.

It never fetches a Daily Yield page, so no pageview is added, and it never touches
anything the AdSense reviewer can see.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "INDEXING_HEALTH.json"
SITE = "https://dailyyield.blogspot.com/"
SITEMAP = SITE + "sitemap.xml"
API = "https://ssl.bing.com/webmaster/api.svc/json"


def call(operation: str, key: str, params: dict, body: dict | None = None) -> dict:
    query = urllib.parse.urlencode({"apikey": key, **params})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{API}/{operation}?{query}", data=data,
                                     method="POST" if body is not None else "GET",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            return {"ok": True, "code": response.status,
                    "body": json.loads(payload) if payload else {}}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "code": exc.code, "error": exc.read()[:400].decode("utf-8", "replace")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "code": 0, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def newest_sitemap_url() -> str:
    from xml.etree import ElementTree
    with urllib.request.urlopen(SITEMAP, timeout=45) as response:
        tree = ElementTree.fromstring(response.read())
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    rows = []
    for entry in tree.findall(".//s:url", ns):
        rows.append((entry.findtext("s:lastmod", default="", namespaces=ns),
                     entry.findtext("s:loc", default="", namespaces=ns)))
    rows = [r for r in rows if r[1]]
    rows.sort(reverse=True)
    return rows[0][1] if rows else SITE


def main() -> int:
    import os
    key = os.environ.get("BING_WEBMASTER_API_KEY", "").strip()
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(), "site": SITE}
    if not key:
        report["status"] = "NO_KEY"
        report["note"] = "BING_WEBMASTER_API_KEY is not set, so no channel can be tested."
        OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return 0
    quota = call("GetUrlSubmissionQuota", key, {"siteUrl": SITE})
    report["quota"] = quota
    report["sites"] = call("GetUserSites", key, {})
    probe = newest_sitemap_url()
    report["probeUrl"] = probe
    # One URL, one attempt: enough to learn whether this channel works today.
    report["urlSubmission"] = call("SubmitUrlbatch", key, {"siteUrl": SITE},
                                   {"siteUrl": SITE, "urlList": [probe]})
    # Sitemap feed submission is a different channel with its own rules.
    report["feedSubmission"] = call("SubmitFeed", key, {"siteUrl": SITE},
                                    {"siteUrl": SITE, "feedUrl": SITEMAP})
    report["status"] = "MEASURED"
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "sites"})[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
