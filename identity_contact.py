#!/usr/bin/env python3
"""One source of truth for who publishes Daily Yield and how to reach it.

AdSense declined the first application under **Dishonest declarations**, the rule
that says the information a publisher gives Google and its readers must be
materially accurate and complete, with no misleading omissions. Two things in
the live site could read as incomplete or inconsistent:

* the blog is published from Kushal K. Daga's own Google account, while every
  page pointed only to the Daily Yield inbox — so the person accountable for the
  site and the address shown on the site did not visibly match; and
* the Contact page promised replies in two different time frames.

This module holds the single, honest set of facts. Every page, article footer and
audit reads from here, so the site cannot drift into saying two different things
in two different places. Nothing here is invented: the publication, the operator,
the named author and both monitored inboxes are real, and no postal address is
claimed because none is published.
"""
from __future__ import annotations

import html

PUBLICATION = "Daily Yield"
SITE = "https://dailyyield.blogspot.com"
PUBLISHER_NAME = "Kushal K. Daga"
PUBLISHER_ROLE = "Certified Accountant and the named author of Daily Yield"
OPERATING_FROM = "India"
# The inbox shown on the site for readers, corrections and business enquiries.
PRIMARY_EMAIL = "dailyyield.official@gmail.com"
# The address that belongs to the person who owns and administers the blog and
# the AdSense application. It is monitored as well, so a reader or a reviewer
# who writes to it is not left without an answer.
OWNER_EMAIL = "kushalkumardaga.ca@gmail.com"
RESPONSE_TIME = "usually within 2–3 working days"
SOCIAL = {
    "X (Twitter)": "https://x.com/CAKUSHAL2509",
    "LinkedIn — Daily Yield": "https://www.linkedin.com/company/daily-yield",
    "Mastodon": "https://mastodon.social/@dailyyield",
}

IDENTITY_START = "<!-- DY_IDENTITY_START -->"
IDENTITY_END = "<!-- DY_IDENTITY_END -->"

IDENTITY_STYLE = (
    "<style>"
    ".dy-identity{max-width:1040px;margin:24px auto;padding:22px;border:1px solid #dce7e1;"
    "border-radius:16px;background:#fff;color:#17231d;line-height:1.7}"
    ".dy-identity h2{margin:0 0 10px;color:#073b2b;font-size:clamp(22px,3vw,31px)}"
    ".dy-identity p{margin:9px 0}.dy-identity ul{margin:9px 0 9px 20px}"
    ".dy-identity a{color:#08744f;text-decoration:underline;text-underline-offset:2px}"
    "</style>"
)


def mailto(address: str) -> str:
    return f'<a href="mailto:{address}">{html.escape(address)}</a>'


def contact_sentence() -> str:
    """The one sentence every page and article can carry verbatim."""
    return (f"Contact Daily Yield at {mailto(PRIMARY_EMAIL)} "
            f"(the publication inbox) or {mailto(OWNER_EMAIL)} "
            f"(the publisher's own address); both are monitored, and replies take {RESPONSE_TIME}.")


def identity_block(where: str = "page") -> str:
    """The full, plain-language identity statement, safe to repeat often."""
    return f'''{IDENTITY_START}{IDENTITY_STYLE}<section aria-labelledby="dy-identity" class="dy-identity">
<h2 id="dy-identity">Who publishes Daily Yield, and how to reach us</h2>
<p><strong>{html.escape(PUBLICATION)}</strong> is an independent personal-finance and market-news publication at {html.escape(SITE)}. It is written, edited and published by <strong>{html.escape(PUBLISHER_NAME)}</strong>, {html.escape(PUBLISHER_ROLE)}. The blog is administered from {html.escape(OPERATING_FROM)} on the publisher's own Google account; no postal address is published because the publication is operated online only.</p>
<p>Two monitored inboxes are shown deliberately, so the person accountable for the site and the address a reader writes to are the same people:</p>
<ul>
<li>{mailto(PRIMARY_EMAIL)} — the publication inbox used on the site for reader questions, corrections, topic requests and business enquiries.</li>
<li>{mailto(OWNER_EMAIL)} — the publisher's own address, which also owns and administers the blog and any advertising account applied for on its behalf.</li>
</ul>
<p>Replies take {html.escape(RESPONSE_TIME)}. Corrections to a published report are handled first. Anything raised about advertising, privacy choices or a declaration made in an application is answered from the same two addresses. Messages are read by {html.escape(PUBLISHER_NAME)} and the Daily Yield desk; automated tools help collect sources, draft and publish, and that process is disclosed on the articles themselves.</p>
<p>We publish no claim of membership, registration, office, award or partnership that we do not hold, and no information is hidden or stated differently in different places on this site.</p>
</section>{IDENTITY_END}'''


def disclosure_contact_html() -> str:
    """Short contact routing for article footers."""
    return (f'Report a correction or ask a question at {mailto(PRIMARY_EMAIL)} or '
            f'{mailto(OWNER_EMAIL)}; both inboxes are monitored and replies take {RESPONSE_TIME}.')


def lines() -> dict:
    return {
        "publication": PUBLICATION,
        "site": SITE,
        "publisher": PUBLISHER_NAME,
        "publisher_role": PUBLISHER_ROLE,
        "operating_from": OPERATING_FROM,
        "primary_email": PRIMARY_EMAIL,
        "owner_email": OWNER_EMAIL,
        "response_time": RESPONSE_TIME,
    }
