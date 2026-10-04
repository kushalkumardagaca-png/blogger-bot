#!/usr/bin/env python3
"""Shared Bing-safe title, description and image-alt hygiene.

The rules are deterministic so retries and future publications remain stable.
"""
from __future__ import annotations

import html
import re

MAX_TITLE_CHARS = 46  # Leaves room for Blogger's current site-name suffix.
MAX_DESCRIPTION_CHARS = 155

NEWS_PREFIXES = {
    "Corporate Finance and Industry News": "Corporate Finance News",
    "Economy and Macro Policy News": "Macro Policy News",
    "Market and Trading News": "Market News",
    "Global Finance Wire": "Global Finance News",
}


def clean_text(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _word_clip(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    cut = value[: max(1, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;:—–-.·|")
    return (cut or value[: limit - 1]).rstrip() + "…"


def compact_title(title: str, limit: int = MAX_TITLE_CHARS) -> str:
    """Create a useful title that stays below Bing's long-title threshold."""
    title = clean_text(title)
    if not title:
        return "Daily Yield"
    candidate = title
    parts = [part.strip() for part in title.split(" · ")]
    if len(parts) >= 2 and re.search(r"\b20\d{2}\b", parts[1]):
        prefix = NEWS_PREFIXES.get(parts[0], parts[0])
        candidate = f"{prefix} — {parts[1]}"
    # Prefer the main clause over mechanically clipping a subtitle.
    if len(candidate) > limit:
        clauses = re.split(r"\s*[—:]\s+", candidate, maxsplit=1)
        if clauses and 12 <= len(clauses[0]) <= limit:
            candidate = clauses[0]
    return _word_clip(candidate, limit)


def unique_title(base: str, ordinal: int, limit: int = MAX_TITLE_CHARS) -> str:
    if ordinal <= 1:
        return compact_title(base, limit)
    suffix = f" ({ordinal})"
    return _word_clip(compact_title(base, limit), limit - len(suffix)) + suffix


def description_from_content(title: str, content: str) -> str:
    """Build a factual description from the first useful paragraph or title."""
    for pattern in (
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
        r'<p\b[^>]*>(.*?)</p>',
    ):
        for match in re.finditer(pattern, content or "", flags=re.I | re.S):
            value = clean_text(match.group(1))
            if len(value) >= 45 and value.lower() != clean_text(title).lower():
                return _word_clip(value, MAX_DESCRIPTION_CHARS)
    fallback = f"{clean_text(title)} — sourced financial context, practical explanations and clear takeaways from Daily Yield."
    return _word_clip(fallback, MAX_DESCRIPTION_CHARS)


def _markup_parts(content: str) -> list[str]:
    """Split literal markup from executable text that may contain HTML examples.

    Daily Yield's Page applications legitimately contain JavaScript strings and
    regular expressions with text such as ``<img>``. Treating those strings as
    document elements can corrupt the application and creates false accessibility
    failures. Even indexes are literal markup; odd indexes are preserved scripts.
    """
    return re.split(r"(<script\b[^>]*>.*?</script>)", content or "", flags=re.I | re.S)


def repair_image_alts(content: str, title: str) -> tuple[str, int]:
    """Give every literal content image a non-empty, descriptive alt attribute."""
    count = 0
    image_number = 0

    def repair(match: re.Match) -> str:
        nonlocal count, image_number
        tag = match.group(0)
        image_number += 1
        present = re.search(r"\balt\s*=\s*(?:([\"'])(.*?)\1|([^\s>]*))", tag, flags=re.I | re.S)
        present_value = (present.group(2) if present and present.group(1) else (present.group(3) if present else ""))
        if present and clean_text(present_value):
            return tag
        label = clean_text(title)
        label += " — editorial photograph" if image_number == 1 else f" — supporting image {image_number}"
        label = _word_clip(label, 145)
        escaped = html.escape(label, quote=True)
        if present:
            updated = tag[:present.start()] + f'alt="{escaped}"' + tag[present.end():]
        else:
            close = "/>" if tag.rstrip().endswith("/>") else ">"
            body = tag.rstrip()[:-len(close)].rstrip()
            updated = f'{body} alt="{escaped}"{close}'
        count += 1
        return updated

    parts = _markup_parts(content)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(r"<img\b[^>]*>", repair, parts[index], flags=re.I | re.S)
    return "".join(parts), count


def image_alt_failures(content: str) -> int:
    failures = 0
    parts = _markup_parts(content)
    literal_markup = "".join(parts[::2])
    for tag in re.findall(r"<img\b[^>]*>", literal_markup, flags=re.I | re.S):
        match = re.search(r"\balt\s*=\s*(?:([\"'])(.*?)\1|([^\s>]*))", tag, flags=re.I | re.S)
        value = (match.group(2) if match and match.group(1) else (match.group(3) if match else ""))
        if not match or not clean_text(value):
            failures += 1
    return failures
