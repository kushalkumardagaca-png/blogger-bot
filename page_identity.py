#!/usr/bin/env python3
"""One place that decides what a page's name and address have to be, so a numbered address cannot come back.

Why this file exists. Five of the site's hub pages live at addresses like
`/p/about-us_02080501126.html`: Blogger writes that `_0123456789` tail itself, and it does so only when a
new page is *created* with a name that is already taken. So the numbered address is not decoration and not
a Blogger quirk to be lived with - it is the fingerprint of a create that should have been an update. The
same rule runs the other way for the daily desk editions, which must carry the day in their name and in
their address, because that is what makes every edition a distinct document instead of a second copy of
yesterday's. Both halves of the rule are functions here, so a test can hold them, and every job that could
create a page is checked by `audit_publishing_automation.py` against this file rather than by memory.
"""
from __future__ import annotations

import datetime as dt
import re

# Blogger's collision tail: an underscore and at least eight digits before `.html`.
NUMBERED_SLUG = re.compile(r"_[0-9]{8,}(?=\.html?$)")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")


def numbered_slug(url: str) -> str:
    """The collision tail inside this address, or an empty string when the address is clean."""
    match = NUMBERED_SLUG.search(url or "")
    return match.group(0) if match else ""


def find_page(pages, title: str = "", path: str = ""):
    """The page that already owns this name or this address, if any.

    Matching is on the address first, because that is what readers and the sitemap use, and on the
    exact title second, because that is what makes Blogger stamp a number on a new page.
    """
    for page in pages or ():
        if path and (page.get("url") or "").endswith(path):
            return page
    want = (title or "").strip().casefold()
    if want:
        for page in pages or ():
            if (page.get("title") or "").strip().casefold() == want:
                return page
    return None


def assert_creatable(pages, title: str, *, allow_numbered: bool = False):
    """Return the page to write to; refuse a create that Blogger would answer with a numbered address.

    The refusal is the point. A caller that finds an existing page must patch it - which keeps the
    address, the inbound links and the index record - and only a genuinely new name may be created.
    `allow_numbered` exists for one purpose: a caller that has already checked with the owner and wants
    the second address anyway still has to say so in code, which is what keeps it visible in a diff.
    """
    existing = find_page(pages, title=title)
    if existing is not None:
        return existing, "update"
    if not allow_numbered:
        return None, "create"
    return None, "create"


def edition_title(prefix: str, day: dt.date) -> str:
    """`Markets Today - 24 October 2026`: the desk's own words, then the day it describes."""
    return f"{prefix} - {day.day} {MONTHS[day.month - 1]} {day.year}"


def slug_for(prefix: str, day: dt.date) -> str:
    """The matching address fragment: lower, hyphenated, ending in the ISO date."""
    stem = re.sub(r"[^a-z0-9]+", "-", (prefix or "").lower()).strip("-")
    return f"{stem}-{day.isoformat()}"


def edition_identity_is_dated(title: str, slug: str, *days) -> bool:
    """True only when both the name and the address carry a day, which is the rule the owner set.

    More than one day may be offered, because the Americas edition is dated with the market day it closed
    while its address keeps the run day: the rule is that the edition says which day it is about, not
    that two different conventions agree with each other.
    """
    days = days or (dt.date.today(),)
    spelled = {f"{day.day} {MONTHS[day.month - 1]} {day.year}" for day in days}
    return any(day in (title or "") for day in spelled) and any(day.isoformat() in (slug or "") for day in days)
