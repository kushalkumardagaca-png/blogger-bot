#!/usr/bin/env python3
"""Make one brand and one author name findable everywhere, on every page.

The goal is simple and stated plainly: when somebody searches for **Kushal Daga**,
**Daily Yield**, **CA Kushal Daga** or **Kushal Daga website** — or for any of the
longer phrases a reader would naturally type around them — this publication should
be the clearest, most complete answer a search engine can offer.

Search engines do not rank a name because a page repeats it. They rank it because
the same name, the same person and the same publication appear together, in
consistent language, on pages that plainly answer reader questions and link to one
another. So this module does four honest things to every page and article:

* states in visible text who writes Daily Yield and what else the author is known
  as, using the exact phrases readers search for, in a normal sentence;
* carries a short, factual question-and-answer block, because answer engines quote
  plainly written answers;
* puts the same identity into structured data (Person, Organization, WebSite), so
  the entity can be recognised rather than guessed;
* makes the permanent URL, the page title, the description and the image text
  describe the same thing.

Nothing here invents a claim, a figure or a credential, and nothing here repeats a
keyword at a reader's expense. It is repeat-safe: a second pass changes nothing.
"""
from __future__ import annotations

import html
import json
import re

import identity_contact as ident

PUBLICATION = ident.PUBLICATION
SITE = ident.SITE
AUTHOR = ident.BYLINE
LEGAL = ident.LEGAL_NAME

# The four phrases this publication intends to be the best answer for, plus the
# longer phrases a reader or a voice assistant actually types. Everything written
# into a page is phrased so these read naturally.
BRAND_QUERIES = ("Kushal Daga", "Daily Yield", "CA Kushal Daga", "Kushal Daga website")
RELATED_QUERIES = (
    "Daily Yield finance",
    "Daily Yield Kushal Daga",
    "Kushal Daga Daily Yield",
    "Kushal Daga finance writer",
    "Kushal Daga CA",
    "CA Kushal Daga Daily Yield",
    "Kushal Daga website Daily Yield",
    "Daily Yield official website",
    "Daily Yield finance news",
    "Daily Yield market insights",
    "Daily Yield money guides",
    "Kushal Daga market analysis",
    "who is Kushal Daga",
    "who writes Daily Yield",
    "Daily Yield official blog",
)

# The short, honest way to describe the site wherever a description is needed.
BRAND_LINE = (f"Daily Yield is the finance news and money-guide publication written and published "
              f"by Kushal Daga, who also writes as CA Kushal Daga. "
              f"The official Daily Yield website is {SITE}.")
DESCRIPTION_TAIL = "Daily Yield — finance news and money guides by CA Kushal Daga."

MARKER_START = "<!-- DY_BRAND_SEO_START -->"
MARKER_END = "<!-- DY_BRAND_SEO_END -->"

BRAND_STYLE = (
    "<style>"
    ".dy-brand{max-width:960px;margin:44px auto;padding:22px 24px;border:1px solid #eadcc8;"
    "border-radius:14px;background:#fffdf8;color:#3c2a20;font:16px/1.75 Georgia,serif}"
    ".dy-brand h2{margin:0 0 10px;font-family:Arial,sans-serif;color:#512618;"
    "font-size:clamp(20px,3vw,27px)}"
    ".dy-brand h3{margin:20px 0 6px;font-family:Arial,sans-serif;color:#512618;font-size:17px}"
    ".dy-brand a{color:#9c4522;text-decoration-thickness:1px;text-underline-offset:3px}"
    ".dy-brand ul{margin:10px 0 0 20px}.dy-brand li{margin:6px 0}"
    "</style>"
)

# What the publication is for. Written as answers, never as slogans.
TOPICS = (
    "personal finance and household money decisions",
    "market and company news with the arithmetic shown",
    "tax, pension, insurance and credit rules explained plainly",
    "country-by-country finance coverage and global finance editions",
    "calculators, worked examples and transparent assumptions",
)


def keywords() -> str:
    """The keyword line used in page metadata and structured data."""
    return ", ".join(dict.fromkeys(BRAND_QUERIES + RELATED_QUERIES + ident.NAME_ALIASES))


def front_meta(title: str, description: str, limit: int = 158) -> str:
    """A description that keeps the reader's subject first and the brand last."""
    text = re.sub(r"\s+", " ", (description or "").strip())
    if not text:
        text = f"{title} — reported by Daily Yield."
    if "Daily Yield" not in text:
        text = f"{text.rstrip('.')} — {DESCRIPTION_TAIL}"
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def topic_phrase(subject: str) -> str:
    """Turn a page subject into the phrase a reader would search for."""
    words = re.sub(r"[^A-Za-z0-9 ]+", " ", subject or "").split()
    return " ".join(words[:9]).strip() or "personal finance"


def brand_block(subject: str = "", kind: str = "article") -> str:
    """The visible identity block: who writes this, and where else to read it."""
    subject = html.escape(subject or PUBLICATION)
    what = "this page" if kind == "page" else "this article"
    faq = (
        ("Who writes Daily Yield?",
         "Daily Yield is written, edited and published by Kushal Daga, who also writes as "
         "CA Kushal Daga. Kushal Kumar Daga is the publisher's legal name, used on ownership, "
         "payment and platform records. The publisher's professional background is stated on the "
         "Daily Yield about page."),
        ("What is the Daily Yield website?",
         f"The official Daily Yield website is {SITE}. It carries finance news editions, market "
         "insights, money guides and calculators."),
        ("Is Kushal Daga the same as CA Kushal Daga?",
         "Yes. CA Kushal Daga is the same author, written with the CA prefix. Kushal Daga is the "
         "short form of the publisher's legal name, Kushal Kumar Daga."),
        ("How often is Daily Yield published?",
         "Daily Yield publishes news editions every day and long-form money guides across its "
         "evergreen categories, each one linked to the sources it uses."),
    )
    qa = "".join(f"<h3>{html.escape(q)}</h3><p>{html.escape(a)}</p>" for q, a in faq)
    return (
        f'{BRAND_STYLE}<section class="dy-brand" aria-labelledby="dy-brand-heading">'
        f'<h2 id="dy-brand-heading">About {what} — Daily Yield and Kushal Daga</h2>'
        f'<p>{html.escape(BRAND_LINE)} This page, <em>{subject}</em>, is part of that publication.</p>'
        f'<p>Readers reach Daily Yield by searching for Kushal Daga, for Daily Yield, for '
        f'CA Kushal Daga or for the Kushal Daga website. All four lead to the same writer and the '
        f'same publication: {html.escape(AUTHOR)} writes every Daily Yield article, and the '
        f'editorial desk answers corrections at '
        f'{ident.mailto(ident.PRIMARY_EMAIL)}.</p>'
        f'{qa}'
        f'<p><strong>Keep reading:</strong> '
        f'<a href="{SITE}/">Daily Yield home</a> · '
        f'<a href="{SITE}/p/about-us_02080501126.html">Kushal Daga — about the author</a> · '
        f'<a href="{SITE}/p/contact-us_01883938366.html">Contact the Daily Yield desk</a> · '
        f'<a href="{SITE}/p/article.html">All Daily Yield articles</a></p>'
        f'</section>'
    )


def entity_schema(subject: str = "", kind: str = "article", url: str = "") -> str:
    """Structured data that ties the person, the publication and this page together."""
    person = {
        "@type": "Person",
        "@id": f"{SITE}/p/about-us_02080501126.html#person",
        "name": AUTHOR,
        "alternateName": list(dict.fromkeys([LEGAL, "CA Kushal Daga"] + ident.NAME_ALIASES)),
        "jobTitle": "Finance writer and publisher",
        "description": f"{AUTHOR}, who also writes as CA Kushal Daga, is the writer and publisher of Daily Yield.",
        "url": f"{SITE}/p/about-us_02080501126.html",
        "knowsAbout": list(TOPICS) + [topic_phrase(subject)] if subject else list(TOPICS),
        "worksFor": {"@id": f"{SITE}/#organization"},
    }
    organization = {
        "@type": "Organization",
        "@id": f"{SITE}/#organization",
        "name": PUBLICATION,
        "alternateName": ["Daily Yield finance", "Daily Yield official website"],
        "url": SITE + "/",
        "description": BRAND_LINE,
        "founder": {"@id": f"{SITE}/p/about-us_02080501126.html#person"},
        "email": ident.PRIMARY_EMAIL,
    }
    website = {
        "@type": "WebSite",
        "@id": f"{SITE}/#website",
        "name": PUBLICATION,
        "alternateName": list(BRAND_QUERIES),
        "url": SITE + "/",
        "inLanguage": "en",
        "publisher": {"@id": f"{SITE}/#organization"},
        "about": {"@id": f"{SITE}/p/about-us_02080501126.html#person"},
    }
    graph = {"@context": "https://schema.org", "@graph": [person, organization, website]}
    if url and kind != "page":
        graph["@graph"].append({
            "@type": "Article", "@id": url + "#dy-brand-page", "url": url,
            "author": {"@id": f"{SITE}/p/about-us_02080501126.html#person"},
            "publisher": {"@id": f"{SITE}/#organization"}, "inLanguage": "en",
        })
    return ('<script type="application/ld+json">'
            + json.dumps(graph, ensure_ascii=False) + "</script>")


def enrich(text: str, kind: str = "article", title: str = "", url: str = "") -> tuple[str, bool]:
    """Put the identity, the answers and the entity data on a finished page.

    Repeat-safe: the block is replaced by the same block, so running this again
    changes nothing. A page that already carries the current block is left alone.
    """
    if not text:
        return text, False
    out = text
    block = MARKER_START + brand_block(title, kind) + entity_schema(title, kind, url) + MARKER_END
    if MARKER_START in out and MARKER_END in out:
        replaced = re.sub(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
                          lambda _m: block, out, flags=re.S)
        return replaced, replaced != out
    # The block belongs at the end of the article, before Blogger's own footer.
    return out + block, True


def questions(text: str) -> list[str]:
    """Any brand claim that must never appear on a page."""
    return [f"unowned name published: {v}" for v in ident.WRONG_NAME_VARIANTS if v in (text or "")]


def report(text: str) -> dict:
    """What a finished page carries, for the audits to print."""
    return {
        "hasBrandBlock": MARKER_START in (text or ""),
        "mentionsKushalDaga": "Kushal Daga" in (text or ""),
        "mentionsDailyYield": "Daily Yield" in (text or ""),
        "mentionsCaKushalDaga": "CA Kushal Daga" in (text or ""),
        "mentionsWebsitePhrase": "Kushal Daga website" in (text or ""),
        "hasEntitySchema": '"@graph"' in (text or "") and "#organization" in (text or ""),
    }
