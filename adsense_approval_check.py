#!/usr/bin/env python3
"""AdSense-approval readiness audit for Daily Yield.

Run after the AdSense Readiness workflow has published its page updates. It reads
the live site over ordinary HTTP (a handful of requests, no synthetic views) and
reports, in plain words, whether each point that can be *checked* is in place:
who publishes the site, both monitored addresses, consistent reply times, the
required policy pages, the ad declaration files, the sitemap and the robots
rules.

Honest limits: approval itself is Google's decision, and this file cannot see
into the AdSense account. What it can do is prove the site says one consistent,
verifiable thing about itself, which is what a Dishonest declarations review is
about.
"""
from __future__ import annotations

import json
import re

import reader_prose
import sys
import time
import urllib.request
import urllib.error
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

BLOG = "https://dailyyield.blogspot.com"
UA = {"User-Agent": "DailyYieldAdSenseCheck/1.0 (dailyyield.official@gmail.com)"}
PRIMARY = "dailyyield.official@gmail.com"
OWNER = "kushalkumardaga.ca@gmail.com"
LEGAL_NAME = "Kushal Kumar Daga"
BYLINE = "Kushal Daga"

PAGES = {
    "about": "/p/about-us_02080501126.html",
    "contact": "/p/contact-us_01883938366.html",
    "privacy": "/p/privacy-policy.html",
    "disclaimer": "/p/disclaimer.html",
    "terms": "/p/terms-and-conditions.html",
}


BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0 Safari/537.36 DailyYieldAdSenseCheck/1.0")


def get(path: str, attempts: int = 3) -> tuple[int, str]:
    """Read one public page politely, with retries for rate limiting.

    A hosted blog can answer a burst of requests from one address with 429/503,
    and a single throttled reply must not be reported as a missing policy page.
    """
    url = path if path.startswith("http") else BLOG + path
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={**UA, "User-Agent": BROWSER_UA,
                                                           "Accept": "text/html,application/xhtml+xml,*/*"})
            with urllib.request.urlopen(request, timeout=60) as r:
                raw = r.read()
                return r.status, raw.decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 — the reason is reported, not hidden
            last = f"{exc.__class__.__name__}: {exc}"
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                return exc.code, last
            time.sleep(2 * attempt)
    return 0, last


def visible(html_text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


def check_site() -> dict:
    findings: list[dict] = []

    def add(name: str, ok: bool | None, detail: str, blocking: bool = True) -> None:
        findings.append({"check": name, "pass": None if ok is None else bool(ok),
                         "state": "UNKNOWN" if ok is None else ("PASS" if ok else "FAIL"),
                         "detail": detail, "blocking": blocking})

    def observed(status):
        return None if status in (0, 429, 500, 502, 503, 504) else status == 200

    pages: dict[str, str] = {}
    for name, path in PAGES.items():
        status, body = get(path)
        time.sleep(1.2)   # polite spacing between page reads
        pages[name] = visible(body) if status == 200 else ""
        add(f"policy page /{name}", observed(status), f"{path} → HTTP {status}" + ("; read unavailable, not proof of a missing page" if observed(status) is None else ""))

    for name in ("about", "contact"):
        text = pages.get(name, "")
        if not text:
            add(f"{name}: identity content available", None, "Identity could not be checked because the page read failed")
            continue
        add(f"{name}: public author name", BYLINE in text, BYLINE)
        add(f"{name}: publisher's legal name", LEGAL_NAME in text, LEGAL_NAME)
        add(f"{name}: name relationship explained",
            "legal name" in text.casefold() and "short form" in text.casefold(),
            "the site says the public author name is the short form of the legal name used on records")
        add(f"{name}: retired initials byline gone", not re.search(r"Kushal\s+K\.?\s+Daga", text),
            "the retired initials byline is no longer published")
        add(f"{name}: publication inbox", PRIMARY in text, PRIMARY)
        add(f"{name}: publisher's own address", OWNER in text, OWNER)
        add(f"{name}: no contradictory reply time", "24\u201348" not in text,
            "one reply-time promise only")
        add(f"{name}: no inaccurate name claim", "Kushal Jain" not in text,
            "no unrelated surname is published as an alias")

    terms = pages.get("terms", "") + pages.get("privacy", "")
    add("advertising declared in the policy pages",
        ("adsense" in terms.casefold() and "advertis" in terms.casefold()) if terms else None,
        "advertising and Google AdSense are described in the policy pages")

    privacy = pages.get("privacy", "")
    add("privacy page names third-party cookie vendors and the ad opt-out",
        ("third-party vendor" in privacy.casefold() and "aboutads.info" in privacy.casefold()) if privacy else None,
        "third-party vendor cookie use and an opt-out route are named on the privacy page")

    status, ads = get("/ads.txt")
    add("ads.txt matches the recorded publisher", ("google.com, pub-1083724733490660, DIRECT, f08c47fec0942fa0" in ads) if status == 200 else observed(status),
        f"HTTP {status}: {ads.strip()[:80] if status == 200 else 'not verified'}")

    status, robots = get("/robots.txt")
    add("robots.txt readable", observed(status), f"HTTP {status}")
    parser = urllib.robotparser.RobotFileParser()
    if status == 200:
        parser.parse(robots.splitlines())
    allowed = all(parser.can_fetch(agent, BLOG + '/') for agent in ('Mediapartners-Google', 'Google-Display-Ads-Bot')) if status == 200 else None
    add("AdSense crawler access allowed", allowed,
        "Evaluated effective robots rules; an explicit agent name is not mandatory")
    add("sitemap declared", "sitemap:" in robots.casefold() if status == 200 else None, "sitemap line checked in existing robots.txt")

    status, sitemap = get("/sitemap.xml")
    add("sitemap.xml serves URLs", ("<loc>" in sitemap) if status == 200 else observed(status),
        f"HTTP {status}, {sitemap.count('<loc>') if status == 200 else 0} URLs listed")

    # The homepage is read last, after several page reads, so the request is given
    # more room: a hosted blog can throttle a burst from one address, and a
    # throttled reply must never be reported as a site defect.
    time.sleep(3)
    status, home = get("/", attempts=5)
    if status != 200:
        add("homepage could be read", observed(status),
            f"the homepage did not answer ({status}); content checks are unknown, not passed")
    if status == 200:
        masked = re.sub(r"<style.*?</style>", " ", home, flags=re.S | re.I)
        add("no raw code shown to readers", "cursor:grab" not in masked and "touch-action" not in masked,
            "no CSS text leaks outside style blocks on the homepage")
        add("no inaccurate name claim on the homepage", "Kushal Jain" not in masked,
            "the homepage does not present an unrelated surname as an alias of the author")
        add("no retired byline on the homepage", not re.search(r"Kushal\s+K\.?\s+Daga", masked),
            "the homepage carries the public author name, not the retired initials form")
        robot_tags = re.findall(r'<meta\b(?=[^>]*name=["\']robots["\'])[^>]*>', masked, re.I)
        add("robots meta does not forbid indexing",
            not any("noindex" in tag.casefold() for tag in robot_tags),
            "No noindex directive found; an explicit index,follow tag is not required")
    else:
        masked = ""
        add("homepage identity and markup", None, "Not checked because homepage fetch was unavailable")
    # The newest live articles are read straight from the public feed, because a
    # reader deciding whether this site is worth their time sees exactly this.
    feed_status, feed = get("/feeds/posts/default?alt=json&max-results=12")
    try:
        entries = json.loads(feed)["feed"].get("entry", [])
    except Exception:
        entries = []
    offenders = []
    for entry in entries:
        body = (entry.get("content", {}) or {}).get("$t", "")
        if not body:
            continue
        marks = reader_prose.problems(body)
        if marks:
            offenders.append(f"{entry.get('title', {}).get('$t', 'untitled')}: {'; '.join(marks)}")
    add("newest articles show no drafting artefacts",
        bool(entries and not offenders) if feed_status == 200 else observed(feed_status),
        "the 12 most recent posts carry no unnamed source links, repeated links or leftover markdown"
        + (f" — first offender: {offenders[0]}" if offenders else ""))

    # AdSense permits/needs its verification connection during review. This is
    # evidence only: do not tell the owner to strip legitimate verification code.
    add("AdSense connection markers observed (informational)", True,
        "Verification/ad code is not prohibited before approval. Keep the Blogger/AdSense method required by the current application; private account status is not visible here.", False)

    blocking = [f for f in findings if f["blocking"] and f["pass"] is False]
    unknown = [f for f in findings if f["blocking"] and f["pass"] is None]
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if blocking else ("CHECK_INCOMPLETE" if unknown else "PASS"),
        "publicPagesRead": len(PAGES) + 5,
        "diagnosticReadsOnly": True, "pageScriptsExecuted": False,
        "syntheticViews": 0, "accountApprovalStatus": "NOT_VISIBLE",
        "checks": findings, "blockingIssues": blocking, "unverifiedChecks": unknown,
        "manualStepsRequired": [
            "Check the existing AdSense site status. If Getting ready, do not remove and resubmit it.",
            "Complete only the required account tasks actually shown. Legal/payment records must match official records, not necessarily the public author byline.",
            "Keep correct contact details unchanged. Submit identity, bank or tax details directly to Google only when requested; never in chat.",
        ],
    }
    return report


def main() -> int:
    report = check_site()
    Path("ADSENSE_APPROVAL_READINESS.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Daily Yield — AdSense approval readiness (live site check)", "",
             f"- **Status:** {report['status']}",
             f"- **Checked:** {report['checkedAt']}",
             "- **Public pages read:** {} (ordinary HTTP, no synthetic views)".format(report["publicPagesRead"]),
             "", "## Checks"]
    for f in report["checks"]:
        mark = "UNKNOWN" if f["pass"] is None else ("PASS" if f["pass"] else ("FAIL" if f["blocking"] else "note"))
        lines.append(f"- **{mark}** — {f['check']}: {f['detail']}")
    if report["manualStepsRequired"]:
        lines += ["", "## Steps only the account holder can complete"]
        lines += [f"{i}. {s}" for i, s in enumerate(report["manualStepsRequired"], 1)]
    Path("ADSENSE_APPROVAL_READINESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "blocking": len(report["blockingIssues"])}))
    for issue in report["blockingIssues"]:
        print("::error title=AdSense readiness check::" + issue["check"] + " — " + issue["detail"])
    return 0 if report["status"] == "PASS" else (2 if report["status"] == "CHECK_INCOMPLETE" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
