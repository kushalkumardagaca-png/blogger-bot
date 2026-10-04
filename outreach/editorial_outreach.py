#!/usr/bin/env python3
"""Prepare review-only, purpose-matched Daily Yield editorial outreach.

Deliberately contains no SMTP, Gmail API, HTTP request, tracking pixel, or send
function. Public-source verification is human-curated in prospects.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
OUTREACH = ROOT / "outreach"
PROSPECTS = OUTREACH / "prospects.csv"
SUPPRESSIONS = OUTREACH / "suppressions.csv"
INTERACTIONS = OUTREACH / "interactions.csv"
SEND_LOCK = OUTREACH / "send_lock.json"
TRACKER = ROOT / "published_tracker.json"
QUEUE = OUTREACH / "review_queue"
MANIFEST = OUTREACH / "pilot_manifest.json"
EMAIL_HEADER = OUTREACH / "assets" / "daily-yield-email-header.gif"

ALLOWED_ELIGIBILITY = {"eligible", "restricted", "excluded"}
ALLOWED_MODES = {"auto_approved", "review_required", "human_only", "excluded"}
BLOCKING_STATUSES = {
    "reserved", "sent", "replied", "bounced", "suppressed", "unsubscribed",
    "complaint", "needs_review", "blocked_after_reservation",
}
GENERIC_WORDS = {
    "and", "the", "for", "with", "from", "that", "this", "your", "about",
    "publication", "finance", "financial", "original", "article", "pitch",
}
# Editorial angles are reviewed before activation. These hints force the matching
# engine toward the specific Daily Yield work that substantiates each proposal.
MATCH_HINTS = {
    "ft-opinion": "emergency fund size job type income risk",
    "money-newsroom": "emergency fund size job type income risk",
    "forbes-news-tips": "what changed money 2026",
    "fortune-personal-finance": "career break salary",
    "business-insider-personal-finance": "BRRRR ugly months real estate",
    "investopedia-news-tips": "capital gains explained taxes",
    "inc-contributors": "hustles 30 days winner",
    "best-finance-resource": "graduate credit file",
    "finance-care-online": "money constitution couples",
    "financebuzz-contributors": "term whole life insurance",
    "investmentpedia-contributors": "S&P 500 global investing",
    "financeproper-contributors": "AI advisor data fintech",
}


@dataclass(frozen=True)
class Article:
    title: str
    category: str
    url: str
    published_at: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in GENERIC_WORDS}


def email_valid(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value))


def tagged_url(url: str, prospect_id: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({
        "utm_source": "editorial_outreach",
        "utm_medium": "email",
        "utm_campaign": "reviewed_pilot",
        "utm_content": prospect_id,
    })
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def load_articles() -> list[Article]:
    payload = json.loads(TRACKER.read_text(encoding="utf-8"))
    articles = []
    for row in payload.get("published_posts", []):
        if row.get("title") and row.get("blogger_url"):
            articles.append(Article(row["title"], row.get("category", ""), row["blogger_url"], row.get("published_at", "")))
    return articles


def match_article(prospect: dict[str, str], articles: list[Article]) -> tuple[Article, int]:
    target = words(prospect["audience_topics"] + " " + prospect["permitted_purpose"])
    hint = words(MATCH_HINTS.get(prospect["prospect_id"], ""))
    ranked = []
    for article in articles:
        article_words = words(article.title + " " + article.category)
        score = len(target & article_words) * 10 + len(hint & article_words) * 30
        if prospect["region"].lower() == "india" and any(x in article_words for x in {"india", "rupee", "nifty"}):
            score += 5
        ranked.append((score, article.published_at, article))
    if not ranked:
        raise ValueError("published_tracker.json has no usable articles")
    score, _, article = max(ranked, key=lambda x: (x[0], x[1]))
    return article, score


def registry_errors() -> list[str]:
    errors: list[str] = []
    prospects = read_csv(PROSPECTS)
    seen_ids, seen_emails = set(), set()
    required = {
        "prospect_id", "organization", "email", "audience_topics", "permitted_purpose",
        "eligibility", "automation_mode", "source_url", "source_checked_at", "source_evidence",
        "country", "timezone",
    }
    for number, row in enumerate(prospects, 2):
        missing = sorted(key for key in required if not row.get(key))
        if missing:
            errors.append(f"prospects.csv:{number}: missing {', '.join(missing)}")
        pid, email = row.get("prospect_id", ""), row.get("email", "").lower()
        if pid in seen_ids:
            errors.append(f"prospects.csv:{number}: duplicate prospect_id {pid}")
        if email in seen_emails:
            errors.append(f"prospects.csv:{number}: duplicate email {email}")
        seen_ids.add(pid); seen_emails.add(email)
        if not email_valid(email):
            errors.append(f"prospects.csv:{number}: invalid email")
        if row.get("eligibility") not in ALLOWED_ELIGIBILITY:
            errors.append(f"prospects.csv:{number}: invalid eligibility")
        if row.get("automation_mode") not in ALLOWED_MODES:
            errors.append(f"prospects.csv:{number}: invalid automation_mode")
        if row.get("eligibility") != "eligible" and row.get("automation_mode") in {"review_required", "auto_approved"}:
            errors.append(f"prospects.csv:{number}: only eligible contacts may be drafted or auto-approved")
        if not row.get("source_url", "").startswith("https://"):
            errors.append(f"prospects.csv:{number}: source must be official HTTPS")
        try:
            date.fromisoformat(row.get("source_checked_at", ""))
        except ValueError:
            errors.append(f"prospects.csv:{number}: invalid source_checked_at")
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(row.get("timezone", ""))
        except Exception:
            errors.append(f"prospects.csv:{number}: invalid timezone")

    if not EMAIL_HEADER.exists() or not EMAIL_HEADER.read_bytes().startswith(b"GIF89a"):
        errors.append("branded animated email header is missing or invalid")
    lock = json.loads(SEND_LOCK.read_text(encoding="utf-8"))
    if lock.get("tracking_pixels_allowed") is not False or lock.get("synthetic_pageviews_allowed") is not False:
        errors.append("tracking pixels and synthetic pageviews must remain prohibited")
    return errors


def validation_errors() -> list[str]:
    errors = registry_errors()
    lock = json.loads(SEND_LOCK.read_text(encoding="utf-8"))
    for key in ("sending_enabled", "gmail_oauth_configured", "review_approval_required"):
        if not isinstance(lock.get(key), bool):
            errors.append(f"send_lock.json {key} must be boolean")
    if lock.get("sending_enabled") is True and lock.get("gmail_oauth_configured") is not True:
        errors.append("sending cannot be enabled before Gmail OAuth is configured")
    minimum = lock.get("minimum_initial_messages_per_day")
    limit = lock.get("max_initial_messages_per_day")
    if not isinstance(minimum, int) or not 1 <= minimum <= 20:
        errors.append("daily minimum target must be an integer from 1 to 20")
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        errors.append("daily maximum must be an integer from 1 to 20")
    if isinstance(minimum, int) and isinstance(limit, int) and minimum > limit:
        errors.append("daily minimum target cannot exceed daily maximum")
    return errors


def render_html(plain_body: str) -> str:
    """Render a conservative email-client-safe Daily Yield presentation."""
    paragraphs = []
    url_pattern = re.compile(r"(https?://[^\s]+)")
    for paragraph in plain_body.strip().split("\n\n"):
        escaped = html.escape(paragraph).replace("\n", "<br>")
        escaped = url_pattern.sub(
            lambda match: f'<a href="{match.group(1)}" style="color:#9c4522;text-decoration:underline;font-weight:700;">{match.group(1)}</a>',
            escaped,
        )
        paragraphs.append(f'<p style="margin:0 0 17px;line-height:1.65;">{escaped}</p>')
    content = "".join(paragraphs)
    return f'''<!doctype html>
<html><body style="margin:0;padding:0;background:#f8f0e3;color:#2b1d15;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f8f0e3;"><tr><td align="center" style="padding:24px 10px;">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background:#fffdf8;border:1px solid #eadcc8;border-radius:18px;overflow:hidden;">
<tr><td style="padding:0;background:#241610;"><img src="cid:daily-yield-header" width="600" height="150" alt="Daily Yield — Read it. Question it." style="display:block;width:100%;height:auto;border:0;"></td></tr>
<tr><td style="padding:30px 34px 24px;font-size:16px;">{content}</td></tr>
<tr><td style="padding:18px 34px;background:#241610;color:#d9c4a4;font-size:12px;line-height:1.55;">Independent personal-finance analysis by Kushal K. Daga<br><a href="https://dailyyield.blogspot.com/" style="color:#f0b180;text-decoration:none;">Daily Yield</a> · No paid-placement request · No tracking pixel</td></tr>
</table></td></tr></table></body></html>'''


def compose(prospect: dict[str, str], article: Article) -> tuple[str, str]:
    organization = prospect["organization"]
    article_link = tagged_url(article.url, prospect["prospect_id"])
    if prospect["prospect_id"] == "ft-opinion":
        subject = "Opinion proposal: Why emergency funds should be sized by job risk"
        body = f"""Dear Opinion Editor,

I am Kushal K. Daga, founder and author of Daily Yield, an independent personal-finance publication. I would like to propose an original opinion piece arguing that the standard three-to-six-month emergency-fund rule is too blunt: liquidity targets should reflect income volatility, re-employment time and household concentration risk.

The proposed article would be newly reported and written exclusively for the Financial Times, with a global frame and practical examples rather than a republication of existing work. A related Daily Yield article shows the starting point for the argument and my reader-focused approach: “{article.title}” — {article_link}

If the premise is of interest, I can send a concise outline and disclose any relevant interests before drafting. I will not submit the same proposal elsewhere while it is under your consideration.

Thank you for considering it. If this route is not suitable, I will not follow up.

Kind regards,
Kushal K. Daga
Founder and Author, Daily Yield
https://dailyyield.blogspot.com/
dailyyield.official@gmail.com
"""
    elif prospect["prospect_id"] == "money-newsroom":
        subject = f"Coverage idea for Money readers: {article.title}"
        body = f"""Dear Money Newsroom,

I am Kushal K. Daga, founder and author of Daily Yield. Your contact page invites topics readers would like to see covered, so I am writing with one specific idea: how workers can size an emergency fund by job stability and realistic re-employment time instead of relying on a universal three-to-six-month rule.

Daily Yield recently approached the issue in “{article.title}”: {article_link}

The useful reporting question is where standard advice breaks down—for households with one income, variable pay, caregiving obligations or sector-specific layoff risk. If your team covers this topic, I would be glad to share the framework and supporting calculations for independent review and attribution where editorially appropriate. I am not requesting paid placement or advertising.

Thank you for considering the idea. If it is not relevant, no reply is necessary and I will not follow up.

Kind regards,
Kushal K. Daga
Founder and Author, Daily Yield
https://dailyyield.blogspot.com/
dailyyield.official@gmail.com
"""
    elif prospect["prospect_id"] == "forbes-news-tips":
        subject = f"Sourced personal-finance story idea: {article.title}"
        body = f"""Dear Forbes News Tips Desk,

I am Kushal K. Daga, founder and author of Daily Yield, an independent personal-finance publication. Your Editorial Values and Standards page invites specific story ideas or news for possible coverage.

A reader-relevant reporting idea is how standard emergency-fund guidance can fail households with variable income, concentrated household earnings or long sector-specific re-employment periods. The central question is whether liquidity guidance should be tied to measurable income risk rather than a universal number of months.

For context, Daily Yield recently published “{article.title}”: {article_link}

This is a story idea for independent editorial consideration, not a request for advertising, paid placement or a backlink. I can provide the underlying calculations and sources if useful. If it is not relevant, no reply or follow-up is necessary.

Kind regards,
Kushal K. Daga
Founder and Author, Daily Yield
https://dailyyield.blogspot.com/
dailyyield.official@gmail.com
"""
    else:
        contact = prospect.get("contact_name", "Editorial Team")
        purpose = prospect["permitted_purpose"]
        subject = f"Editorial proposal for {organization}: {article.title}"
        body = f"""Dear {contact},

I am Kushal K. Daga, founder and author of Daily Yield, an independent personal-finance publication. Your published editorial guidance invites {purpose.lower()}, so I am contacting you through that designated route with one relevant idea.

I propose an original, evidence-based article that tests common financial guidance against realistic household constraints, using transparent calculations and primary sources. A related Daily Yield article shows the subject area and my reader-focused approach: “{article.title}” — {article_link}

The proposed contribution would be newly written for {organization}, adapted to your audience and editorial requirements; it would not be a republication of the linked article. I am not requesting advertising, paid placement, reciprocal links or guaranteed coverage. If the angle is not suitable, no reply or follow-up is necessary.

Kind regards,
Kushal K. Daga
Founder and Author, Daily Yield
https://dailyyield.blogspot.com/
dailyyield.official@gmail.com
"""
    return subject, body


def draft(limit: int, allowed_prospect_ids: set[str] | None = None) -> int:
    errors = validation_errors()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    prospects = read_csv(PROSPECTS)
    suppressions = {r["email"].lower() for r in read_csv(SUPPRESSIONS) if r.get("email")}
    interactions = read_csv(INTERACTIONS)
    blocked_history = {r["email"].lower() for r in interactions if r.get("status", "").lower() in BLOCKING_STATUSES}
    articles = load_articles()

    if QUEUE.exists():
        shutil.rmtree(QUEUE)
    QUEUE.mkdir(parents=True)
    manifest = {
        "generated_at": date.today().isoformat(),
        "mode": "SOURCE_VERIFIED_RESERVATION_QUEUE",
        "daily_limit": limit,
        "selected": [],
        "blocked": [],
    }
    selected = 0
    for prospect in prospects:
        email = prospect["email"].lower()
        reason = ""
        if allowed_prospect_ids is not None and prospect["prospect_id"] not in allowed_prospect_ids:
            reason = "outside recipient local business-time window"
        elif prospect["eligibility"] != "eligible" or prospect["automation_mode"] not in {"review_required", "auto_approved"}:
            reason = f"classification={prospect['eligibility']}/{prospect['automation_mode']}"
        elif email in suppressions:
            reason = "suppression list"
        elif email in blocked_history:
            reason = "prior interaction blocks a new initial message"
        elif selected >= limit:
            reason = "daily pilot limit"
        if reason:
            manifest["blocked"].append({"prospect_id": prospect["prospect_id"], "reason": reason})
            continue

        article, score = match_article(prospect, articles)
        if score <= 0:
            manifest["blocked"].append({"prospect_id": prospect["prospect_id"], "reason": "no Daily Yield topic match"})
            continue
        subject, body = compose(prospect, article)
        fingerprint = hashlib.sha256((email + "\n" + subject + "\n" + body).encode()).hexdigest()
        message = EmailMessage()
        message["From"] = "Kushal K. Daga <dailyyield.official@gmail.com>"
        message["To"] = f"{prospect['contact_name']} <{prospect['email']}>"
        message["Subject"] = subject
        approved_state = "AUTOMATION-APPROVED-NOT-SENT" if prospect["automation_mode"] == "auto_approved" else "REVIEW-REQUIRED-NOT-SENT"
        message["X-Daily-Yield-State"] = approved_state
        message["X-Daily-Yield-Fingerprint"] = fingerprint
        message.set_content(body)
        message.add_alternative(render_html(body), subtype="html")
        html_part = message.get_payload()[-1]
        html_part.add_related(
            EMAIL_HEADER.read_bytes(), maintype="image", subtype="gif",
            cid="<daily-yield-header>", filename="daily-yield-header.gif",
            disposition="inline",
        )
        path = QUEUE / f"{selected + 1:02d}-{prospect['prospect_id']}.eml"
        path.write_bytes(message.as_bytes())
        manifest["selected"].append({
            "prospect_id": prospect["prospect_id"], "organization": prospect["organization"],
            "email": prospect["email"], "purpose": prospect["permitted_purpose"],
            "official_source": prospect["source_url"], "matched_article": article.title,
            "matched_url": article.url, "relevance_score": score, "fingerprint": fingerprint,
            "draft": str(path.relative_to(ROOT)),
            "state": "AUTOMATION_APPROVED_NOT_SENT" if prospect["automation_mode"] == "auto_approved" else "REVIEW_REQUIRED_NOT_SENT",
        })
        selected += 1

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "blocked": len(manifest["blocked"]), "sent": 0, "manifest": str(MANIFEST.relative_to(ROOT))}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    drafting = sub.add_parser("draft")
    drafting.add_argument("--limit", type=int, default=10, choices=range(1, 13), metavar="1..12")
    args = parser.parse_args()
    if args.command == "validate":
        errors = validation_errors()
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 2
        state = "enabled under fail-closed policy" if json.loads(SEND_LOCK.read_text())["sending_enabled"] else "locked"
        print(f"outreach registry valid; sending {state}; synthetic views prohibited")
        return 0
    return draft(args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
