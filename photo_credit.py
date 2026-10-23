#!/usr/bin/env python3
"""The one place a photograph's on-page credit line is worked out, for every writer and repairer.

Why this file exists. On 22-23 October 2026 three Master articles went live with two of their three
photographs carrying a credit line that was empty: an anchor with a source address inside it and no
words at all. The rights data was never missing - ``PHOTO_USAGE_REGISTRY.json`` recorded the creator,
the licence and the licence URL for all nine pictures - and the article builder did write the caption.
What happened is that the anti-plagiarism repair, which removes a sentence the article has already
used, saw the *licence credit* of photograph 2 and 3 as a repeat of photograph 1's credit (all three
were taken at the same event by the same photographer under the same licence) and deleted the words,
leaving the link behind. An article whose figure credits were blanked then failed the whole-site image
rights audit, the corpus status fell to WARNING, and on 23 October the green operating gate - which is
suppose
d to protect publication - held every news desk and every Master slot for hours.

So the credit is defined here once, and every route that renders a figure calls it: a licence
attribution is functional metadata, it is allowed to repeat, and it is never allowed to be blank.
"""
from __future__ import annotations
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "PHOTO_USAGE_REGISTRY.json"

# A Wikimedia/Unsplash-derived asset is honestly describable even when the pool row that carried its
# creator has been compacted; anything else has to be credited by its own record or not published.
COMMONS_FILE = re.compile(r"/wiki/(?:File|Image):([^/?#]+)", re.I)
TRUSTED_HOSTS = ("commons.wikimedia.org", "upload.wikimedia.org", "unsplash.com", "images.unsplash.com",
                 "blogger.googleusercontent.com", "githubusercontent.com")
_INDEX: dict = {}
_INDEX_STAMP: list = [None]


def _index() -> dict:
    """Map every asset address to the rights row the selector recorded for it."""
    try:
        stamp = REGISTRY.stat().st_mtime_ns
    except OSError:
        return {}
    if _INDEX_STAMP[0] == stamp and _INDEX:
        return _INDEX
    rows: dict[str, dict] = {}
    try:
        items = (json.loads(REGISTRY.read_text(encoding="utf-8")) or {}).get("items") or []
    except (OSError, ValueError):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("url", "original_url", "download_url", "source_page"):
            value = str(item.get(key) or "")
            if value:
                rows.setdefault(value.rstrip("/"), item)
    _INDEX.clear()
    _INDEX.update(rows)
    _INDEX_STAMP[0] = stamp
    return rows


def _pick(record: dict, *keys: str) -> str:
    for key in keys:
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return ""


def rights_for(record: dict) -> dict:
    """Return the rights row for a figure, filling any blank from the photo registry.

    Two field spellings are in circulation: the selector writes ``license``/``license_url`` while the
    prepared pools write ``licence``/``licence_url``. Both are read, and neither is invented.
    """
    record = record or {}
    stored = _index().get(str(record.get("url") or "").rstrip("/")) or {}
    out = {}
    out["creator"] = _pick(record, "creator", "artist") or _pick(stored, "creator", "artist")
    out["license"] = _pick(record, "license", "licence") or _pick(stored, "license", "licence")
    out["license_url"] = _pick(record, "license_url", "licence_url") or _pick(stored, "license_url", "licence_url")
    out["source_page"] = (_pick(record, "source_page") or _pick(stored, "source_page")
                          or _pick(record, "original_url", "descriptionurl") or _pick(stored, "original_url"))
    out["title"] = _pick(record, "source_title", "title") or _pick(stored, "title")
    return out


def commons_page(candidate: str) -> str:
    """The Wikimedia file page for an address, when the address names a file."""
    value = str(candidate or "")
    match = COMMONS_FILE.search(unquote(value))
    if match:
        return "https://commons.wikimedia.org/wiki/File:" + match.group(1)
    if "/commons/" in value:
        name = unquote(value.split("/commons/")[-1]).split("?")[0].rsplit("/", 1)[-1]
        if name:
            return "https://commons.wikimedia.org/wiki/File:" + name
    return ""


def credit_text(rights: dict) -> str:
    """Visible words for the credit. Never empty for a figure we are allowed to publish.

    The order is a chain of honesty, not of convenience: the recorded creator and licence first, then a
    plain statement naming the source record when only its address survived, and nothing at all when
    even that is unknown - the caller then refuses the figure instead of publishing an unattributed
    picture or a caption with no sentence in it.
    """
    creator = rights.get("creator") or ""
    licence = rights.get("license") or ""
    if creator and licence:
        return f"Photo: {creator} / {licence}"
    if creator:
        return f"Photo: {creator} / licence recorded with the source file"
    source = rights.get("source_page") or ""
    host = (urlparse(source).hostname or "").lower()
    if "wikimedia.org" in host:
        return "Editorial image · Wikimedia Commons source and licence record"
    if "unsplash.com" in host:
        return "Editorial photograph · Unsplash source and licence record"
    if source:
        return "Editorial image · credited to the linked source record"
    return ""


def figure_html(rights: dict) -> str:
    """The inner HTML of a figcaption carrying the credit and its links, or "" when unattributable."""
    text = credit_text(rights)
    if not text:
        return ""
    pieces = []
    escaped = html.escape(text, quote=True)
    if rights.get("source_page"):
        pieces.append(f'<a href="{html.escape(rights["source_page"], quote=True)}" rel="noopener" '
                      f'target="_blank">{escaped}</a>')
    else:
        pieces.append(escaped)
    if rights.get("license_url"):
        pieces.append(f'<a href="{html.escape(rights["license_url"], quote=True)}" rel="license noopener" '
                      f'target="_blank">Licence</a>')
    return " · ".join(pieces)


def caption_is_visible(caption_html: str) -> bool:
    """True when a figcaption says something, not merely links somewhere."""
    words = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", caption_html or ""))).strip()
    return len(words) >= 12


__all__ = ["rights_for", "credit_text", "figure_html", "caption_is_visible", "commons_page", "TRUSTED_HOSTS"]
