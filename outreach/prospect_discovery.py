#!/usr/bin/env python3
"""Discover only source-verified Daily Yield editorial opportunities.

The crawler uses public search-result RSS, obeys robots.txt, visits only a small
number of official HTTPS pages, and accepts an address only when the same page
both publishes it and explicitly invites a relevant editorial approach. It is
not a general email harvester.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTREACH = ROOT / "outreach"
PROSPECTS = OUTREACH / "prospects.csv"
STATUS = Path(os.environ.get("OUTREACH_DISCOVERY_STATUS", str(OUTREACH / "DISCOVERY_STATUS.json")))
USER_AGENT = "DailyYield-EditorialOpportunityDiscovery/1.0 (+dailyyield.official@gmail.com)"
MAX_RESULT_PAGES = 12
QUERIES = (
    'personal finance publication "send pitches" email',
    'finance magazine "pitch us" email',
    'personal finance podcast "guest pitch" email',
    'financial literacy "contributor guidelines" email',
    'money newsletter "story ideas" email',
    'investing publication "news tips" email',
    'economy publication "freelance pitches" email',
    'personal finance "editorial submissions" email',
)
TOPIC_RE = re.compile(r"\b(personal finance|money|saving|budget|invest|retirement|tax|credit|debt|insurance|econom(?:y|ic)|fintech|financial literacy|career|salary)\b", re.I)
INVITE_RE = re.compile(r"\b(send|submit|email|welcome|accept|invite|looking for|pitch)\b.{0,100}\b(pitch|story idea|news tip|contribut|guest|freelance|submission|expert commentary|podcast guest)\b|\b(pitch|story idea|news tip|contribut|guest|freelance|submission|expert commentary|podcast guest)\b.{0,100}\b(send|submit|email|welcome|accept|invite|looking for)\b", re.I | re.S)
PROHIBITED_RE = re.compile(r"\b(editorial fee|publication fee|sponsored post|paid placement|buy backlinks?|dofollow links?|link insertion|casino|gambling|adult content)\b", re.I)
AI_PROHIBITION_RE = re.compile(r"\b(no|do not|don't|prohibit(?:ed)?)\b.{0,50}\b(AI|artificial intelligence|machine.generated|ChatGPT)\b", re.I)
EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.I)
BLOCKED_HOSTS = {"facebook.com", "linkedin.com", "twitter.com", "x.com", "reddit.com", "youtube.com", "instagram.com", "pinterest.com", "medium.com"}
FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "proton.me", "protonmail.com"}
ROLE_WORDS = {"editor", "editorial", "news", "newsroom", "tips", "pitch", "contribut", "writer", "podcast", "contact", "hello"}
FIELDS = ["prospect_id", "organization", "contact_name", "email", "channel_type", "region", "audience_topics", "permitted_purpose", "eligibility", "automation_mode", "source_url", "source_checked_at", "source_evidence", "notes", "country", "timezone"]


def registrable(host: str) -> str:
    parts = host.lower().strip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "org.au", "co.in", "org.in", "co.nz"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def robots_allowed(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return False


def fetch(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        kind = response.headers.get_content_type()
        if kind not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise ValueError(f"unsupported content type {kind}")
        return response.read(1_500_000).decode(response.headers.get_content_charset() or "utf-8", "replace")


def visible(raw: str) -> str:
    raw = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def search_urls(query: str) -> list[str]:
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "format": "rss"})
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    urls = []
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        parts = urllib.parse.urlsplit(link)
        host = (parts.hostname or "").lower()
        if parts.scheme == "https" and host and registrable(host) not in BLOCKED_HOSTS:
            urls.append(link)
    return urls


def country_timezone(text: str, host: str) -> tuple[str, str]:
    lower = text.lower()
    tld = host.rsplit(".", 1)[-1]
    if tld == "in" or re.search(r"\bindia(n)?\b", lower): return "India", "Asia/Kolkata"
    if tld == "uk" or re.search(r"\bunited kingdom|\bUK\b", text): return "United Kingdom", "Europe/London"
    if tld == "au" or "australia" in lower: return "Australia", "Australia/Sydney"
    if tld == "ca" or "canada" in lower: return "Canada", "America/Toronto"
    if tld == "nz" or "new zealand" in lower: return "New Zealand", "Pacific/Auckland"
    if tld == "sg" or "singapore" in lower: return "Singapore", "Asia/Singapore"
    if tld == "za" or "south africa" in lower: return "South Africa", "Africa/Johannesburg"
    if re.search(r"\bunited states|\bU\.S\.|\bUSA\b", text): return "United States", "America/New_York"
    return "Global", "America/New_York"


def organization(raw: str, host: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    if match:
        title = visible(match.group(1)).split("|")[0].split("—")[0].strip()
        if 2 <= len(title) <= 80: return title
    return host.removeprefix("www.").split(".")[0].replace("-", " ").title()


def classify(url: str, raw: str) -> list[dict]:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    text = visible(raw)
    if not TOPIC_RE.search(text) or not INVITE_RE.search(text) or PROHIBITED_RE.search(text):
        return []
    emails = sorted({m.group(1).lower().rstrip(".") for m in EMAIL_RE.finditer(html.unescape(raw))})
    found = []
    for email in emails:
        local, domain = email.rsplit("@", 1)
        # Automatically discovered addresses must be organizational and tied to
        # the same official site. Curated free-mail contacts remain supported.
        if domain in FREE_MAIL or registrable(domain) != registrable(host):
            continue
        positions = [m.start() for m in re.finditer(re.escape(email), text, re.I)]
        context = " ".join(text[max(0, pos-700):pos+700] for pos in positions)
        if not INVITE_RE.search(context) or not TOPIC_RE.search(context):
            continue
        purpose = "Relevant editorial pitch or contributor proposal"
        channel = "podcast" if "podcast" in context.lower() else "publication"
        if "news tip" in context.lower() or "story idea" in context.lower(): purpose = "Specific sourced finance story idea or news tip"
        elif "podcast" in context.lower(): purpose = "Relevant finance expert or podcast guest proposal"
        elif "freelance" in context.lower(): purpose = "Original freelance finance story pitch"
        elif "contribut" in context.lower() or "guest" in context.lower(): purpose = "Original finance contribution pitch"
        country, tz = country_timezone(text[:20000], host)
        role = "Editorial Team"
        if any(word in local.lower() for word in ROLE_WORDS): role = "Editorial Desk"
        pid = re.sub(r"[^a-z0-9]+", "-", registrable(host).split(".")[0]).strip("-") + "-" + hashlib.sha256(email.encode()).hexdigest()[:8]
        found.append({
            "prospect_id": pid, "organization": organization(raw, host), "contact_name": role,
            "email": email, "channel_type": channel, "region": country,
            "audience_topics": "personal finance,money,investing,economy,financial literacy",
            "permitted_purpose": purpose, "eligibility": "eligible",
            "automation_mode": "human_only" if AI_PROHIBITION_RE.search(text) else "auto_approved",
            "source_url": url, "source_checked_at": datetime.now(timezone.utc).date().isoformat(),
            "source_evidence": "Official page publishes this organizational address and explicitly invites a Daily Yield-relevant editorial approach.",
            "notes": "Automatically discovered under strict same-domain, invitation, topic, fee-exclusion and deduplication rules.",
            "country": country, "timezone": tz,
        })
    return found[:1]  # Never add multiple recipients from one organization page.


def read_rows() -> tuple[list[str], list[dict]]:
    with PROSPECTS.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return list(reader.fieldnames or []), rows


def write_rows(rows: list[dict]) -> None:
    with PROSPECTS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows([{key: row.get(key, "") for key in FIELDS} for row in rows])


def main() -> int:
    _, rows = read_rows()
    known_emails = {row.get("email", "").lower() for row in rows}
    known_domains = {registrable(urllib.parse.urlsplit(row.get("source_url", "")).hostname or "") for row in rows}
    hour = datetime.now(timezone.utc).hour
    selected_queries = [QUERIES[hour % len(QUERIES)], QUERIES[(hour + 3) % len(QUERIES)]]
    candidates, checked, rejected, errors = [], 0, 0, []
    urls = []
    for query in selected_queries:
        try: urls.extend(search_urls(query))
        except Exception as exc: errors.append(f"search:{type(exc).__name__}")
    for url in list(dict.fromkeys(urls))[:MAX_RESULT_PAGES]:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if registrable(host) in known_domains:
            continue
        try:
            if not robots_allowed(url):
                rejected += 1; continue
            raw = fetch(url); checked += 1
            accepted = classify(url, raw)
            if not accepted: rejected += 1; continue
            item = accepted[0]
            if item["email"] in known_emails: rejected += 1; continue
            candidates.append(item); known_emails.add(item["email"]); known_domains.add(registrable(host))
            time.sleep(1)
        except Exception as exc:
            errors.append(f"{host}:{type(exc).__name__}")
    rows.extend(candidates)
    if candidates: write_rows(rows)
    report = {
        "checkedAtUtc": datetime.now(timezone.utc).isoformat(), "queries": selected_queries,
        "resultUrls": len(set(urls)), "officialPagesChecked": checked, "accepted": len(candidates),
        "rejected": rejected, "errors": errors[:20], "totalRegistry": len(rows),
        "policy": "official invitation + Daily Yield topic match + same-domain organizational email; no harvesting",
    }
    STATUS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"PROSPECT_DISCOVERY_ERROR: {exc}", file=sys.stderr); raise SystemExit(1)
