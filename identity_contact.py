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
import json
import re

PUBLICATION = "Daily Yield"
SITE = "https://dailyyield.blogspot.com"
# The publisher's full legal name. This is the form that belongs in the AdSense
# account, the payments profile, the bank record and every legal or contractual
# statement, because those must match the person's own identity documents.
LEGAL_NAME = "Kushal Kumar Daga"
# The public author name. This is the name readers see on every article, in the
# masthead, in the footer and on social posts: one name, used everywhere, so that
# the person and the publication are recognisable as the same byline.
BYLINE = "Kushal Daga"
PUBLISHER_NAME = BYLINE          # the name the publication is published under
PUBLISHER_ROLE = "Certified Accountant and the named author of Daily Yield"
# How the two names relate, in one honest sentence. The public name is not a false
# identity: it is the short form of the legal name, and the site says so.
NAME_EXPLAINER = (f"{PUBLICATION} is written and published by {BYLINE}, which is the short form of the "
                  f"publisher's legal name, {LEGAL_NAME}. The legal name is the one used on ownership, "
                  f"payment and platform records.")
# Honest search and entity names for the same person and the same publication.
NAME_ALIASES = [BYLINE, LEGAL_NAME, "CA Kushal", "Finance by Kushal"]
# The byline form that was used before this change. It is retired: an initials
# byline reads as a third, unsearchable person, and the public name is now the
# same one form everywhere. Any page still carrying it is rewritten.
RETIRED_BYLINE = "Kushal K. Daga"
# A name that was previously published as an alias but is not a form of the
# publisher's name. Nothing on the site may claim it, because telling Google or a
# reader that the author is also called by an unrelated surname is exactly the
# kind of inaccurate declaration that stops an advertising approval.
WRONG_NAME_VARIANTS = ("Kushal Jain",)
# The published identity sentences are replaced by these, word for word.
PUBLIC_IDENTITY_SENTENCE = (f"Daily Yield is the finance publication of {BYLINE}. "
                             f"{LEGAL_NAME} is the publisher's legal name, used on ownership, payment "
                             f"and platform records.")
IDENTITY_STATEMENT_FIXES = (
 ("Daily Yield is the finance publication of Kushal Kumar Daga, whose articles carry the abbreviated byline \u201cKushal K. Daga\u201d.",
  PUBLIC_IDENTITY_SENTENCE),
 ("Daily Yield is the finance publication of Kushal K. Daga, also known as Kushal Daga and Kushal Jain.",
  PUBLIC_IDENTITY_SENTENCE),
 ("Daily Yield is the finance publication of Kushal K. Daga, also known as Kushal Daga.",
  PUBLIC_IDENTITY_SENTENCE),
 ("Daily Yield is the finance publication of Kushal Kumar Daga, whose articles carry the abbreviated byline \u201cKushal Daga\u201d.",
  PUBLIC_IDENTITY_SENTENCE),
 ("Published by Kushal Kumar Daga \u2014 \u201cKushal K. Daga\u201d is the abbreviated form of the same name used as the byline.",
  f"Published by {PUBLICATION}. Written by {BYLINE}. {LEGAL_NAME} is the publisher's legal name, used on ownership, payment and platform records."),
 ("Published by Kushal Kumar Daga \u2014 \u201cKushal Daga\u201d is the abbreviated form of the same name used as the byline.",
  f"Published by {PUBLICATION}. Written by {BYLINE}. {LEGAL_NAME} is the publisher's legal name, used on ownership, payment and platform records."),
 ("also known as Kushal Daga and Kushal Jain", f"whose author name is {BYLINE}"),
 ("also known as Kushal Daga", f"whose author name is {BYLINE}"),
 ("\u201cCA Kushal\u201d refers to Certified Accountant Kushal Kumar Daga.",
  f"\u201cCA Kushal\u201d refers to Certified Accountant {BYLINE}."),
 ("\u201cCA Kushal\u201d refers to Certified Accountant Kushal K. Daga.",
  f"\u201cCA Kushal\u201d refers to Certified Accountant {BYLINE}."),
)
# JSON-LD alias lists that must now name the legal person, not an unrelated one.
def alias_list_json(indent: int = 0) -> str:
    """The canonical JSON-LD alias list body for the author."""
    return ", ".join(json.dumps(alias, ensure_ascii=False) for alias in NAME_ALIASES)


STRUCTURED_NAME_FIXES = (
 ('\"alternateName\": [\"Kushal Daga\", \"CA Kushal\", \"Kushal Jain\", \"Finance by Kushal\"]',
  '\"alternateName\": [' + alias_list_json() + ']'),
 ('\"alternateName\": [\"Kushal Kumar Daga\", \"Kushal Daga\", \"Kushal K. Daga\", \"Finance by Kushal\"]',
  '\"alternateName\": [' + alias_list_json() + ']'),
)
# Publishing the corrected packages means the live pass has to run again after
# they change, so the note below is deliberate and repeat-safe.
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
<p><strong>{html.escape(PUBLICATION)}</strong> is an independent personal-finance and market-news publication at {html.escape(SITE)}. It is written, edited and published by <strong>{html.escape(BYLINE)}</strong>, {html.escape(PUBLISHER_ROLE)}. The blog is administered from {html.escape(OPERATING_FROM)} on the publisher's own Google account; no postal address is published because the publication is operated online only.</p>
<p>One name question is answered here rather than left to be discovered: <strong>{html.escape(BYLINE)}</strong> is the author name used on this site, and it is the short form of the publisher's legal name, <strong>{html.escape(LEGAL_NAME)}</strong>. Both refer to the same person. The legal name is the one that appears on ownership, payment and platform records, including any advertising account applied for on the site's behalf.</p>
<p>Two monitored inboxes are shown deliberately, so the person accountable for the site and the address a reader writes to are the same people:</p>
<ul>
<li>{mailto(PRIMARY_EMAIL)} — the publication inbox used on the site for reader questions, corrections, topic requests and business enquiries.</li>
<li>{mailto(OWNER_EMAIL)} — the publisher's own address, which also owns and administers the blog and any advertising account applied for on its behalf.</li>
</ul>
<p>Replies take {html.escape(RESPONSE_TIME)}. Corrections to a published report are handled first. Anything raised about advertising, privacy choices or a declaration made in an application is answered from the same two addresses. Messages are read by {html.escape(BYLINE)} and the Daily Yield desk; automated tools help collect sources, draft and publish, and that process is disclosed on the articles themselves.</p>
<p>We publish no claim of membership, registration, office, award or partnership that we do not hold, and no information is hidden or stated differently in different places on this site. Where a legal, payment or platform record requires the full legal name, {html.escape(LEGAL_NAME)} is the name used.</p>
</section>{IDENTITY_END}'''


def disclosure_contact_html() -> str:
    """Short contact routing for article footers."""
    return (f'Report a correction or ask a question at {mailto(PRIMARY_EMAIL)} or '
            f'{mailto(OWNER_EMAIL)}; both inboxes are monitored and replies take {RESPONSE_TIME}.')


# Structured data is emitted both compactly and pretty-printed, so the alias list
# is matched by shape rather than by one exact string. Any list that names a name
# the publisher does not have is rebuilt from NAME_ALIASES.
ALIAS_LIST_RE = re.compile(r'("alternateName"\s*:\s*\[)([^\[\]]*)(\])')
# The keywords line is one JSON string holding a comma-separated list.
KEYWORDS_RE = re.compile(r'(?P<head>"keywords"\s*:\s*")(?P<value>(?:[^"\\]|\\.)*)"')


def _canonical_aliases(inner: str) -> str | None:
    """Return the honest alias list for a JSON-LD array body, or None when it is fine.

    The list is rebuilt whenever it names something the publisher does not have,
    whenever the retired initials byline is still in it, or whenever it simply
    does not match the canonical set. Lists that belong to something other than
    the author (an organisation, for example) are left untouched.
    """
    found = re.findall(r'"([^"]*)"', inner)
    if not found:
        return None
    canonical = list(dict.fromkeys(NAME_ALIASES))
    if sorted(found) == sorted(canonical):
        return None
    if not any(v in found for v in WRONG_NAME_VARIANTS) and RETIRED_BYLINE not in found \
       and not any(a.startswith("Kushal") for a in found):
        return None
    return ", ".join(json.dumps(alias, ensure_ascii=False) for alias in canonical)


def repair_names(text: str) -> tuple[str, bool]:
    """Replace the retired or inaccurate name claims with the honest ones.

    Order matters: the published sentences are rewritten first, then the retired
    initials byline is swept away wherever it survives, and finally the JSON-LD
    alias lists are rebuilt from NAME_ALIASES. The result is stable, so running
    the repair a second time changes nothing.
    """
    out = text
    # Any variation of the published identity sentence, in any older wording, is
    # replaced by the one honest sentence first, so no two versions can sit side
    # by side on the same page.
    out = re.sub(r"Daily Yield is the finance publication of Kushal(?: K\.| Kumar)? Daga, "
                 r"(?:whose articles carry the abbreviated byline [\u201c\"][^\u201d\"]{0,40}[\u201d\"]"
                 r"|also known as Kushal Daga(?: and Kushal Jain)?)\.", PUBLIC_IDENTITY_SENTENCE, out)
    out = re.sub(r"The publisher's legal name is Kushal Kumar Daga\. Articles and the masthead carry the "
                 r"abbreviated editorial byline [^.]{0,60}?\.", NAME_EXPLAINER, out)
    for before, after in IDENTITY_STATEMENT_FIXES + STRUCTURED_NAME_FIXES:
        out = out.replace(before, after)
    if RETIRED_BYLINE in out:
        out = re.sub(r"Kushal\s+K\.?\s+Daga", BYLINE, out)
    def swap(match: "re.Match[str]") -> str:
        canonical = _canonical_aliases(match.group(2))
        return match.group(0) if canonical is None else f"{match.group(1)}{canonical}{match.group(3)}"

    out = ALIAS_LIST_RE.sub(swap, out)
    # The keyword line is a comma-separated list of names and phrases, so the same
    # cleanup has to be applied inside it: no unowned surname, no retired byline,
    # and no duplicate of a name that is already in the list.
    def clean_keywords(match: "re.Match[str]") -> str:
        terms, seen = [], set()
        for term in match.group("value").split(","):
            term = term.strip()
            if not term or any(v in term for v in WRONG_NAME_VARIANTS):
                continue
            term = re.sub(r"Kushal\s+K\.?\s+Daga", BYLINE, term)
            key = term.casefold()
            if key not in seen:
                seen.add(key); terms.append(term)
        if LEGAL_NAME.casefold() not in seen:
            terms.append(LEGAL_NAME)
        return f'{match.group("head")}{", ".join(terms)}"'

    out = KEYWORDS_RE.sub(clean_keywords, out)
    return out, out != text


def name_problems(text: str) -> list[str]:
    """Any name the public pages must no longer carry."""
    found = [f"inaccurate name claim published: {variant}" for variant in WRONG_NAME_VARIANTS
             if variant in (text or "")]
    if re.search(r"Kushal\s+K\.?\s+Daga", text or ""):
        found.append(f"retired initials byline still published: {RETIRED_BYLINE}")
    return found


def lines() -> dict:
    return {
        "publication": PUBLICATION,
        "site": SITE,
        "publisher": PUBLISHER_NAME,
        "author_name": BYLINE,
        "legal_name": LEGAL_NAME,
        "byline": BYLINE,
        "publisher_role": PUBLISHER_ROLE,
        "operating_from": OPERATING_FROM,
        "primary_email": PRIMARY_EMAIL,
        "owner_email": OWNER_EMAIL,
        "response_time": RESPONSE_TIME,
    }
