#!/usr/bin/env python3
"""Make the machine-assembled parts of an article read like edited prose.

Automated drafting left three marks on published pages that a reader notices
immediately and an advertising reviewer reads as low-value, auto-generated text:

* every supporting link was labelled with the same phrase, so a single article
  could carry forty or ninety anchors reading "documented source evidence" —
  the address was shown but the publication behind it was not named;
* the same link was repeated again and again inside one article, which is link
  clutter rather than sourcing;
* drafting shorthand such as **bold** and ### headings survived into the HTML,
  so asterisks and hashes were visible in the finished page.

This module repairs all three from the finished HTML, deterministically, without
adding or removing a single fact: the link still points at the same address, it
is simply named after the publication that address belongs to and shown once.
Everything here is repeat-safe, so a second pass changes nothing.
"""
from __future__ import annotations

import re
import urllib.parse

# Labels the drafting step used for every link. They name no source, so they are
# replaced by the publication the address itself belongs to.
GENERIC_CITATION_LABELS = (
    "documented source evidence",
    "linked source evidence",
    "source evidence",
    "retrieved evidence",
    "supporting source evidence",
    "cited source evidence",
)

# Publication names for the addresses this publication actually links to. Every
# entry names the owner of the domain, so the anchor text is verifiable from the
# address beside it. Unknown domains fall back to the domain's own name.
HOST_LABELS = {
    "news.google.com": "Google News",
    "google.com": "Google News",
    "doi.org": "the DOI record",
    "dx.doi.org": "the DOI record",
    "hdl.handle.net": "the archived record",
    "zenodo.org": "Zenodo",
    "arxiv.org": "arXiv",
    "ground.news": "Ground News",
    "news.webindia123.com": "WebIndia123",
    "webindia123.com": "WebIndia123",
    "irs.gov": "IRS",
    "sba.gov": "SBA",
    "sec.gov": "SEC",
    "federalreserve.gov": "Federal Reserve",
    "treasury.gov": "US Treasury",
    "europa.eu": "European Commission",
    "ecb.europa.eu": "European Central Bank",
    "imf.org": "IMF",
    "worldbank.org": "World Bank",
    "oecd.org": "OECD",
    "bis.org": "BIS",
    "nber.org": "NBER",
    "bloomberg.com": "Bloomberg",
    "reuters.com": "Reuters",
    "apnews.com": "AP",
    "ft.com": "Financial Times",
    "wsj.com": "The Wall Street Journal",
    "cnbc.com": "CNBC",
    "forbes.com": "Forbes",
    "bbc.com": "BBC",
    "bbc.co.uk": "BBC",
    "theguardian.com": "The Guardian",
    "economist.com": "The Economist",
    "moneycontrol.com": "Moneycontrol",
    "business-standard.com": "Business Standard",
    "economictimes.indiatimes.com": "The Economic Times",
    "livemint.com": "Mint",
    "thehindu.com": "The Hindu",
    "businessinsider.in": "Business Insider",
    "rbi.org.in": "Reserve Bank of India",
    "sebi.gov.in": "SEBI",
    "scholarship.law.wm.edu": "William & Mary Law School",
    "digitalcommons.wpi.edu": "Worcester Polytechnic Institute",
    "digitalcommons.georgiasouthern.edu": "Georgia Southern University",
    "digital.sandiego.edu": "University of San Diego",
    "digitalrepository.unm.edu": "University of New Mexico",
    "cdr.lib.unc.edu": "University of North Carolina",
    "lup.lub.lu.se": "Lund University",
    "rave.ohiolink.edu": "OhioLINK",
    "journals.co.za": "Sabinet African Journals",
    "suerf.org": "SUERF",
    "theseus.fi": "Theseus",
    "dk.um.si": "University of Maribor",
    "saiompublications.com": "SAIOM Publications",
    "article.sciencepublishinggroup.com": "Science Publishing Group",
    "cra2011.cutetax.ca": "CuteTax Canada",
    "dailyyield.blogspot.com": "Daily Yield",
}

# The suffix used when a source is named rather than silently linked, so a
# reader can see where a claim came from without leaving the sentence.
SOURCE_PREFIX = "Source: "
SOURCE_STYLE = "color:#6e5d4b;font-size:13px"
SOURCE_CLASS = "dy-source"

ANCHOR_RE = re.compile(
    r'\s*<a\b[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<text>[^<]{0,64})</a>\s*', re.I)
HEADING_RE = re.compile(r'<h[23][^>]*>(?P<text>.*?)</h[23]>', re.I | re.S)
PARA_RE = re.compile(r'<p\b[^>]*>(?P<body>.*?)</p>', re.I | re.S)
BOLD_RE = re.compile(r'\*\*(?P<text>[^*<>]{1,160}?)\*\*')
OPENING_STRONG_RE = re.compile(r'^\s*<strong>(?P<text>[^<>]{1,200})</strong>\s*:?\s*')
HASH_RE = re.compile(r'(?:^|(?<=[\s>]))#{2,6}\s*')
EMPHASIS_RE = re.compile(r'\*\*')
TAG_RE = re.compile(r'<[^>]+>')

# Research scaffolding that was produced by the drafting step for two dates.
SCAFFOLD_PHRASES = (
    # "Digital USD University of San evidence frames The Troubled Distinction..."
    (re.compile(r'(?P<who>[A-Z][^.<>]{4,90}?) evidence frames (?P<what>[^<>]{6,200}?) through\s*'
                r'(?P<doc>[\u201c"][^\u201d"]{4,300}[\u201d"])'),
     r'A study from \g<who> examines \g<what> in \g<doc>'),
    # "The retrieved record states, in part, “...”"
    (re.compile(r'The retrieved record states, in part,\s*([\u201c"])'),
     r'The record notes, in its own words: \1'),
    (re.compile(r'retrieved record states, in part,\s*([\u201c"])'),
     r'notes, in its own words: \1'),
    # "The Yale Law Journal evidence frames ..." without a document clause
    (re.compile(r'(?P<who>[A-Z][^.<>]{4,90}?)\s+evidence frames\s+(?P<what>[^.<>]{6,200}?)(?=[.,<])'),
     r'A study from \g<who> examines \g<what>'),
    (re.compile(r'\s*documented source evidence\b'), ''),
    (re.compile(r'\s*linked source evidence\b'), ''),
    (re.compile(r'\s*supporting source evidence\b'), ''),
    (re.compile(r'\s*cited source evidence\b'), ''),
)


def is_generic_label(text: str) -> bool:
    """True when an anchor names no source at all, only the act of citing one."""
    return " ".join((text or "").strip().lower().split()) in GENERIC_CITATION_LABELS


def source_label(url: str) -> str:
    """Name the publication an address belongs to, without guessing."""
    host = urllib.parse.urlsplit(url if "//" in url else "https://" + url).netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    bare = host[4:] if host.startswith("www.") else host
    if bare in HOST_LABELS:
        return HOST_LABELS[bare]
    for known, label in HOST_LABELS.items():
        if bare.endswith("." + known):
            return label
    parts = bare.split(".")
    name = parts[-2] if len(parts) > 1 else parts[0]
    return name.replace("-", " ").strip().capitalize() or "the source"


def _plain(text: str) -> str:
    text = TAG_RE.sub(" ", text or "")
    text = text.replace("&amp;", "&").replace("&#8217;", "\u2019").replace("&nbsp;", " ")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def repair_markdown(html: str) -> tuple[str, int]:
    """Turn leftover drafting shorthand into markup a reader should see."""
    fixes = 0
    out, n = BOLD_RE.subn(lambda m: f"<strong>{m.group('text').strip()}</strong>", html)
    fixes += n
    out, n = HASH_RE.subn(" ", out)
    fixes += n
    out, n = EMPHASIS_RE.subn("", out)
    fixes += n
    return out, fixes


def repair_scaffolding(html: str) -> tuple[str, int]:
    """Replace drafting notes with the same facts written as prose."""
    out = html
    fixes = 0
    for pattern, replacement in SCAFFOLD_PHRASES:
        out, n = pattern.subn(replacement, out)
        fixes += n
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out, fixes


def _source_note(match: "re.Match[str]") -> str:
    label = source_label(match.group("url"))
    return (f' <span class="{SOURCE_CLASS}" style="{SOURCE_STYLE}">{SOURCE_PREFIX}'
            f'<a href="{match.group("url")}" rel="noopener" target="_blank">{label}</a></span>')


def repair_source_tokens(text: str, names: dict[str, str]) -> tuple[str, int]:
    """Name a source inside an unassembled package, before it becomes a link."""
    fixes = 0

    def swap(match: "re.Match[str]") -> str:
        nonlocal fixes
        if not is_generic_label(match.group("label")):
            return match.group(0)
        fixes += 1
        return f"[[{match.group('ref')}|{names.get(match.group('ref')) or 'the cited record'}]]"

    out = re.sub(r"\[\[(?P<ref>[SI]\d+)\|(?P<label>[^\]]+)\]\]", swap, text or "")
    return out, fixes


def repair_citations(html: str, keep_per_url: int = 1) -> tuple[str, int]:
    """Name every supporting link after its publication, and show it once."""
    seen: dict[str, int] = {}
    fixes = 0

    def swap(match: "re.Match[str]") -> str:
        nonlocal fixes
        text = (match.group("text") or "").strip().lower()
        if text not in GENERIC_CITATION_LABELS:
            return match.group(0)
        url = match.group("url")
        seen[url] = seen.get(url, 0) + 1
        fixes += 1
        if seen[url] <= keep_per_url:
            return _source_note(match)
        return " "                      # the same source, already named above

    out = ANCHOR_RE.sub(swap, html)
    return out, fixes


def _same_topic(one: str, two: str) -> bool:
    """True when two headings name the same subject, allowing for truncation."""
    first, second = _plain(one), _plain(two)
    if not first or not second:
        return False
    if first == second:
        return True
    shorter, longer = sorted((first, second), key=len)
    return len(shorter) >= 24 and shorter in longer


def repair_duplicate_openings(html: str) -> tuple[str, int]:
    """Drop a paragraph that only repeats the heading printed directly above it."""
    fixes = 0
    out_parts = []
    position = 0
    headings: list[str] = []
    for match in re.finditer(r'<h[23][^>]*>.*?</h[23]>|<p\b[^>]*>.*?</p>', html, re.I | re.S):
        piece = match.group(0)
        out_parts.append(html[position:match.start()])
        position = match.end()
        if piece[:3].lower() in ("<h2", "<h3"):
            headings.append(_plain(piece))
            out_parts.append(piece)
            continue
        body = piece
        text = _plain(body)
        # a paragraph whose whole text repeats the heading above it is noise
        if headings and text and text == headings[-1] and len(text) < 160:
            fixes += 1
            out_parts.append("")
            continue
        # a paragraph that opens with the heading in bold keeps its prose only
        bold = OPENING_STRONG_RE.search(body)
        if headings and bold and _same_topic(bold.group("text"), headings[-1]):
            body = body.replace(bold.group(0), "", 1)
            fixes += 1
        out_parts.append(body)
    out_parts.append(html[position:])
    return "".join(out_parts), fixes


def normalise(html: str) -> tuple[str, int]:
    """Apply every reader-facing repair; safe to run repeatedly."""
    if not html:
        return html, 0
    out, fixes = repair_citations(html)
    out, n = repair_markdown(out)
    fixes += n
    out, n = repair_duplicate_openings(out)
    fixes += n
    out, n = repair_scaffolding(out)
    fixes += n
    return out, (fixes if out != html else 0)


def problems(html: str) -> list[str]:
    """What a finished page must no longer contain, for the audits to assert."""
    found = []
    generic = len(re.findall(
        r'<a\b[^>]*href="[^"]+"[^>]*>(?:' + "|".join(GENERIC_CITATION_LABELS) + r')</a>',
        html or "", re.I))
    if generic:
        found.append(f"{generic} link(s) still labelled with a generic source phrase")
    bold = len(re.findall(r'\*\*', html or ""))
    if bold:
        found.append(f"{bold} leftover markdown bold marker(s)")
    for pattern, _ in SCAFFOLD_PHRASES[:4]:
        hits = len(pattern.findall(html or ""))
        if hits:
            found.append(f"{hits} drafting note(s) left in the text")
    return found
