#!/usr/bin/env python3
"""Keep the theme's contact promises identical to the Contact page.

The AdSense review declined the first application under **Dishonest declarations**:
information given to Google and to readers must be materially accurate and
complete, with no misleading omissions. The live theme footer promised replies
"within 24–48 hours" on every page while the Contact page promised "2–3 working
days" — two different answers about the same thing, and the footer also showed a
single address even though the blog is administered from another one.

This module rewrites the theme source so both live surfaces say the same thing and
both monitored addresses are visible everywhere a reader looks for a way to write.
It is repeat-safe: running it again changes nothing.
"""
from __future__ import annotations

import re

PRIMARY_EMAIL = "dailyyield.official@gmail.com"
OWNER_EMAIL = "kushalkumardaga.ca@gmail.com"
REPLY_TIME = "2\u20133 working days"

REPLY_TIME_FIXES = (
    ("Replies usually arrive within 24&#8211;48 hours", f"Replies usually arrive within {REPLY_TIME}"),
    ("Replies usually arrive within 24–48 hours", f"Replies usually arrive within {REPLY_TIME}"),
    ("Replies within 24&#8211;48 hours.", f"Replies usually within {REPLY_TIME}."),
    ("Replies within 24–48 hours.", f"Replies usually within {REPLY_TIME}."),
    ("Usually within 2\u20133 working days.", f"Usually within {REPLY_TIME}."),
)

PRIMARY_ANCHOR = f"<a class='ft-email' href='mailto:{PRIMARY_EMAIL}'>{PRIMARY_EMAIL}</a>"
OWNER_ANCHOR = f"<a class='ft-email' href='mailto:{OWNER_EMAIL}'>{OWNER_EMAIL}</a>"
# One primary address followed by exactly one publisher address, wherever the
# footer contact card appears. Written as a rule rather than a fixed string so
# running the repair twice can never stack copies of the same address.
FOOTER_CONTACT_RE = re.compile(re.escape(PRIMARY_ANCHOR) + r"(?:" + re.escape(OWNER_ANCHOR) + r")*")

DESK_CARD = (f"<strong>Email the editorial desk</strong><small>{PRIMARY_EMAIL}</small>",
             f"<strong>Email the editorial desk</strong><small>{PRIMARY_EMAIL} or {OWNER_EMAIL}</small>")

CORRECTION_ANSWER = (f"Use the Daily Yield Contact desk or email {PRIMARY_EMAIL} with the page URL and the correction details.",
                     f"Use the Daily Yield Contact desk or email {PRIMARY_EMAIL} or {OWNER_EMAIL}; both inboxes are monitored and replies take usually within {REPLY_TIME}.")
CORRECTION_ANSWER_RENDERED = (f"Use the <a href='https://dailyyield.blogspot.com/p/contact-us_01883938366.html'>Contact desk</a> or email <a href='mailto:{PRIMARY_EMAIL}'>{PRIMARY_EMAIL}</a> with the page URL and correction details.",
                              f"Use the <a href='https://dailyyield.blogspot.com/p/contact-us_01883938366.html'>Contact desk</a> or email <a href='mailto:{PRIMARY_EMAIL}'>{PRIMARY_EMAIL}</a> or <a href='mailto:{OWNER_EMAIL}'>{OWNER_EMAIL}</a> with the page URL and correction details.")


def apply(text: str) -> tuple[str, list[str]]:
    """Return the corrected theme source plus a list of the changes made."""
    changes: list[str] = []
    for before, after in REPLY_TIME_FIXES:
        if before in text and before != after:
            text = text.replace(before, after)
            changes.append(f"reply time unified: {before!r} → {after!r}")
    if PRIMARY_ANCHOR in text:
        wanted = PRIMARY_ANCHOR + OWNER_ANCHOR
        fixed, count = FOOTER_CONTACT_RE.subn(wanted, text)
        if fixed != text:
            text = fixed
            changes.append(f"footer contact card set to both monitored addresses ({count} place(s))")
    if DESK_CARD[0] in text and DESK_CARD[0] != DESK_CARD[1]:
        text = text.replace(DESK_CARD[0], DESK_CARD[1])
        changes.append("editorial desk card shows both addresses")
    for before, after in (CORRECTION_ANSWER, CORRECTION_ANSWER_RENDERED):
        if before in text:
            text = text.replace(before, after)
            changes.append("correction instructions show both addresses")
    text, meta_done = apply_meta(text)
    if meta_done:
        changes.append("policy-page descriptions state the correct reply time and both addresses")
    return text, changes


def audit(text: str) -> list[str]:
    """Problems that must not survive into an uploaded theme."""
    issues = []
    # The theme stores the dash as an HTML entity or as the character itself.
    if re.search(r"24\s*(?:&#8211;|&#8212;|[\u2013\u2014-])\s*48\s*hours", text):
        issues.append("theme still promises 24–48 hour replies")
    if OWNER_EMAIL not in text:
        issues.append("theme does not show the publisher's own monitored address")
    if PRIMARY_EMAIL not in text:
        issues.append("theme does not show the publication inbox")
    return issues


# ---------------------------------------------------------------------------
# Meta descriptions.
#
# Blogger stores each Page's "Search description" in the blog itself, and that
# field cannot be written through the Blogger API (the documented customMetaData
# field is ignored for descriptions). The Contact page still carried an older
# search description promising replies "in 24–48 hours", which is exactly the kind
# of contradiction the Dishonest declarations rule is about. The theme can put the
# corrected text first, so a reader, a search engine or a reviewer reads the
# truthful version at the top of the page head whatever the stored field says.
# ---------------------------------------------------------------------------
META_MARKER_START = "<!-- DY_HONEST_META_START -->"
META_MARKER_END = "<!-- DY_HONEST_META_END -->"

PAGE_DESCRIPTIONS = {
    "https://dailyyield.blogspot.com/p/about-us_02080501126.html":
        "Daily Yield is an independent finance publication written and published by Kushal K. Daga. "
        "Contact dailyyield.official@gmail.com or kushalkumardaga.ca@gmail.com.",
    "https://dailyyield.blogspot.com/p/contact-us_01883938366.html":
        "Contact Daily Yield about a report, a correction or a topic request at dailyyield.official@gmail.com "
        "or kushalkumardaga.ca@gmail.com; replies usually within 2–3 working days.",
    "https://dailyyield.blogspot.com/p/privacy-policy.html":
        "How Daily Yield handles cookies, analytics, advertising and reader messages, the choices readers have, "
        "and how to reach a human about privacy.",
    "https://dailyyield.blogspot.com/p/disclaimer.html":
        "Daily Yield publishes general financial education, not personal advice: the source, accuracy and "
        "advertising-independence terms readers are entitled to know.",
    "https://dailyyield.blogspot.com/p/terms-and-conditions.html":
        "The terms for using Daily Yield: acceptable use, original work and sources, third-party services, "
        "availability, liability and how to reach the desk.",
}


def meta_block() -> str:
    lines = [META_MARKER_START]
    for url, description in PAGE_DESCRIPTIONS.items():
        lines.append(f"<b:if cond='data:blog.canonicalUrl == &quot;{url}&quot;'>")
        lines.append(f"  <meta content='{description}' name='description'/>")
        lines.append(f"  <meta content='{description}' property='og:description'/>")
        lines.append(f"  <meta content='{description}' name='twitter:description'/>")
        lines.append("</b:if>")
    lines.append(META_MARKER_END)
    return "\n".join(lines)


def apply_meta(text: str) -> tuple[str, bool]:
    """Put the corrected descriptions ahead of Blogger's own head output."""
    block = meta_block()
    if META_MARKER_START in text:
        replaced = re.sub(re.escape(META_MARKER_START) + r".*?" + re.escape(META_MARKER_END),
                          lambda _m: block, text, flags=re.S)
        return replaced, replaced != text
    anchor = "<b:include data='blog' name='all-head-content'/>"
    if anchor not in text:
        return text, False
    return text.replace(anchor, block + "\n" + anchor, 1), True
