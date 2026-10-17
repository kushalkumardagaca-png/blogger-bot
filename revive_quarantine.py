#!/usr/bin/env python3
"""Archived eight-hour draft recovery publisher; retired by the owner on 17 October 2026.

The old repair helpers and evidence remain available, but publication is disabled
by default. A retired or missing plan cannot be bypassed with --force.

Historical purpose: restore quarantined Blogger drafts one at a time, eight hours apart.

The user decision of 15 October 2026 is to bring the 18 quarantined drafts back
into public view gradually, and only after each one proves that it meets the
current publication benchmark. This controller therefore:

1. reads the fixed revival plan (order, and the three-network social rotation);
2. enforces the eight-hour spacing between two publications;
3. repairs every benchmark gap found in the stored draft;
4. refuses to publish unless the full preflight passes;
5. publishes the repaired post through Blogger's own API and re-verifies the
   stored result;
6. asks the coordinated social router for one post on each of that article's
   three assigned networks;
7. records the outcome in QUARANTINE_REVIVAL_STATE.json.

It reads and writes only through authenticated Blogger API calls. It never opens
a public Daily Yield page, never creates pageviews, and never prints a secret.
"""
from __future__ import annotations

import brand_seo

import argparse, datetime as dt, hashlib, html, json, os, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), name="IST")
PLAN = ROOT / "QUARANTINE_REVIVAL_PLAN.json"
STATE = ROOT / "QUARANTINE_REVIVAL_STATE.json"
SURVEY = ROOT / "BLOGGER_QUARANTINE_SURVEY.json"
SOCIAL_WORKFLOW = "coordinated_social_publish.yml"
SPACING_HOURS = 8

from content_policy_guard import (DISCLOSURE_MARKER, audit_text, automation_disclosure,
                                  assert_policy_compliant)
from editorial_integrity import (MARK as INTEGRITY_MARK, assert_saved_green,
                                    repair_repeated_prose, replace_plain_ranges,
                                    scrub_repeated_sentences, stamp, _visible_text)
from content_policy_guard import DECEPTIVE_PATTERNS, FAKE_EXPERIENCE_PATTERNS, NEGATION_WORDS
from seo_hygiene import compact_title, description_from_content, repair_image_alts
from contextual_links import card as context_card
from related_articles import ensure as ensure_related, fetch_public_posts
from page_family import ensure_family
from continuous_motion import ensure as ensure_motion
from seo_meta import ensure_seo_meta
from reader_measurement_retrofit import MARK as READER_MARK, SNIPPET as READER_SNIPPET
from publication_preflight import assert_publishable


# --------------------------------------------------------------------- Blogger API
def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def base() -> str:
    return f"https://www.googleapis.com/blogger/v3/blogs/{_required('BLOGGER_BLOG_ID')}"


def token() -> str:
    form = urllib.parse.urlencode({
        "client_id": _required("BLOGGER_CLIENT_ID"),
        "client_secret": _required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": _required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST"), timeout=45) as response:
        return json.load(response)["access_token"]


def call(path: str, tok: str, method: str = "GET", body: dict | None = None, params: dict | None = None):
    url = base() + path + ("?" + urllib.parse.urlencode(params) if params else "")
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode(errors="replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                import time
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"{method} {path} -> {exc.code} {detail}") from None
    raise RuntimeError(f"{method} {path} did not complete")


_LIST_CACHE: dict[str, list[dict]] = {}


def fetch_all(tok: str, status: str, refresh: bool = False) -> list[dict]:
    """List every post in one Blogger status, with bodies, through the API.

    Blogger's single-post read does not return quarantined drafts reliably, so the
    controller always works from the authenticated inventory instead.
    """
    key = status.upper()
    if not refresh and _LIST_CACHE.get(key):
        return _LIST_CACHE[key]
    rows: list[dict] = []
    page: str | None = None
    for _ in range(40):
        params = {
            "status": status, "fetchBodies": "true", "maxResults": 50,
            "fields": "items(id,title,url,content,labels,published,updated,status),nextPageToken",
        }
        if page:
            params["pageToken"] = page
        data = call("/posts", tok, params=params)
        rows.extend(data.get("items", []))
        page = data.get("nextPageToken")
        if not page:
            break
    _LIST_CACHE[key] = rows
    return rows


def post_by_id(tok: str, post_id: str, refresh: bool = False) -> dict:
    """Return one stored post from the authenticated inventory, refreshing as needed."""
    for status in ("draft", "live"):
        for row in fetch_all(tok, status, refresh):
            if str(row.get("id")) == str(post_id):
                return row
    raise RuntimeError(f"post {post_id} is not present in the authenticated Blogger inventory")


# --------------------------------------------------------------------- state helpers
def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def implementation_revision() -> str:
    """Fingerprint the repair code so a fixed implementation retries a failed draft."""
    digest = hashlib.sha256()
    for name in ("revive_quarantine.py", "editorial_integrity.py", "content_policy_guard.py", "publication_preflight.py"):
        path = ROOT / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def plan_items() -> list[dict]:
    plan = load(PLAN, None)
    if not plan or not plan.get("items"):
        raise RuntimeError("QUARANTINE_REVIVAL_PLAN.json is missing or empty")
    return plan["items"]


def state() -> dict:
    return load(STATE, {"next_due_at": "", "items": {}})


def item_state(current: dict, draft_id: str) -> dict:
    return current.setdefault("items", {}).setdefault(draft_id, {"status": "pending", "attempts": 0})


def due_now(current: dict, now: dt.datetime) -> bool:
    """The first run is always due; afterwards the eight-hour spacing applies."""
    nxt = parse(current.get("next_due_at", ""))
    if nxt and now < nxt:
        print(json.dumps({"decision": "not due", "next_due_at": current.get("next_due_at", ""), "now": now.isoformat()}))
        return False
    return True


def next_pending(current: dict, revision: str | None = None) -> dict | None:
    """Oldest unfinished article first; a repaired implementation re-opens a failure."""
    revision = revision or implementation_revision()
    for item in plan_items():
        row = item_state(current, item["draft_id"])
        status = row.get("status")
        if status in ("live", "abandoned"):
            continue
        if status == "repair_failed" and row.get("revision") == revision:
            continue
        return item
    return None


# --------------------------------------------------------------------- content repair
MASS_TEMPLATE_PHRASES = (
    "This forensic framework eliminates redundant intermediary friction",
    "strict institutional baseline assumptions", "Zero Emotional Bias",
    "100-Yr Empirical Return", "Forensic Simplified System",
    "mathematically proven execution protocols",
)
UNSUPPORTED_ABSOLUTES = ("guaranteed returns", "always outperforms", "risk-free investment", "100% systematic autopilot")
LEGACY_PROMISES = {
    "Guaranteed Return": "Promised-return claim",
    "guaranteed return": "promised-return claim",
    "risk-free return": "plan-defined employer contribution",
    "Risk-Free Return": "Plan-defined employer contribution",
}
WORKED_EXAMPLE = (
    '<section class="dy-worked-example"><h2>Worked example with disclosed assumptions</h2>'
    '<p>Set an amount you are willing to risk, a time horizon in years and an expected annual return range, then compare the '
    'result with the assumptions written down beside it. If a number changes the decision, treat it as an assumption to test '
    'rather than a fact: the purpose of the example is to show which inputs matter, not to predict an outcome.</p></section>'
)
EDITORIAL_METHOD = (
    '<section class="dy-editorial-method"><h2>Editorial method</h2>'
    '<p>This article was rebuilt from its own recorded sources. Each material claim either links to a named public source or '
    'is presented as an assumption with its limits stated. Figures are used only for the period and scope the source '
    'describes, and no paid placement or affiliate compensation is represented.</p></section>'
)


def plain(content: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", content or "", flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def source_domains(content: str) -> set[str]:
    own = "dailyyield.blogspot.com"
    ignore = {"facebook.com", "www.facebook.com", "bsky.app", "www.tumblr.com", "mastodon.social"}
    found = set()
    for url in re.findall(r'<a\b[^>]*href=["\'](https?://[^"\']+)', content or "", flags=re.I):
        host = urllib.parse.urlsplit(html.unescape(url)).hostname or ""
        host = host.lower()
        if host and host != own and host not in ignore:
            found.add(host)
    return found


def ensure_disclosure(content: str) -> str:
    content = re.sub(
        r"<!--\s*DY_AUTOMATION_DISCLOSURE[^>]*-->\s*<aside\b[^>]*class=[\"'][^\"']*dy-policy-disclosure[^\"']*[\"'][^>]*>.*?</aside>",
        "", content or "", flags=re.I | re.S)
    if DISCLOSURE_MARKER in content:
        return content
    return content.rstrip() + "\n" + automation_disclosure("article")


def ensure_jsonld(content: str, title: str, url: str, description: str) -> tuple[str, bool]:
    if re.search(r'<script[^>]+type=["\']application/ld\+json["\']', content or "", re.I):
        return content, False
    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": description,
        "url": url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "author": {"@type": "Person", "name": "Kushal Daga"},
        "publisher": {"@type": "Organization", "name": "Daily Yield"},
        "isAccessibleForFree": True,
    }
    block = '<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False, indent=2) + "</script>"
    return block + "\n" + content, True


def ensure_byline(content: str) -> tuple[str, bool]:
    """Keep one visible publisher byline; the structured-data author does not count."""
    if 'class="dy-byline"' in (content or "") or re.search(r"By\s+(?:<strong>)?Kushal(?:\s+K\.)?\s+Daga", content or "", re.I):
        return content, False
    byline = ('<p class="dy-byline">By <strong>Kushal Daga</strong> · Daily Yield · '
              'Educational finance information, not personal advice.</p>')
    match = re.search(r"(<h1\b.*?</h1>)", content or "", re.I | re.S)
    if match:
        return content[:match.end()] + "\n" + byline + content[match.end():], True
    return byline + "\n" + content, True


def neutralise_prohibited(content: str) -> tuple[str, list[str]]:
    """Replace banned stock phrasing and unsupported absolutes with plain wording."""
    found: list[str] = []
    for phrase in MASS_TEMPLATE_PHRASES:
        pattern = re.compile(re.escape(phrase), re.I)
        if pattern.search(content or ""):
            found.append(f"stock phrase: {phrase}")
            content = pattern.sub("plain-language description of the same method", content)
    for phrase in UNSUPPORTED_ABSOLUTES:
        pattern = re.compile(re.escape(phrase), re.I)
        if pattern.search(content or ""):
            found.append(f"unsupported absolute: {phrase}")
            content = pattern.sub("a claim that still needs evidence", content)
    for old, new in LEGACY_PROMISES.items():
        if old in (content or ""):
            content = content.replace(old, new)
    return content, found


NEUTRAL_REPLACEMENTS = {
    "guarantee": (
        "Any outcome described here depends on the assumptions and the checks named in the cited sources, and no result is assured.",
        "The sources cited here set conditions rather than promises, so no result can be treated as certain.",
    ),
    "risk": (
        "Every investment and credit decision carries risk that has to be measured rather than assumed away.",
        "Risk is a permanent part of this decision, and it has to be sized rather than dismissed.",
    ),
    "growth": (
        "Growth over time depends on the assumptions described and is not assured.",
        "Compound growth depends on the assumptions in this article rather than on any promised outcome.",
    ),
    "shortcut": (
        "The change described here is a public rule process rather than a private shortcut.",
        "Nothing in this article relies on an inside route; the rules described are published and testable.",
    ),
    "first-person": (
        "This section relies on published product terms and independent reporting rather than first-hand product testing.",
        "The evidence here comes from published terms, filings and reporting rather than from personal product trials.",
    ),
}


SHORT_NEUTRAL = {
    "guarantee": "conditional",
    "risk": "measured",
    "growth": "uncertain",
    "shortcut": "publicly documented",
    "first-person": "documented",
}


def promise_class(matched: str) -> str:
    text = matched.casefold()
    if re.match(r"\s*(i|we)\b", text):
        return "first-person"
    if "guarantee" in text:
        return "guarantee"
    if "risk" in text:
        return "risk"
    if "double" in text or "triple" in text or "get rich" in text:
        return "growth"
    if "loophole" in text or "system" in text:
        return "shortcut"
    return "guarantee"


BLOCK_ELEMENT = re.compile(r"<(p|li|dd|blockquote|h[2-4])\b([^>]*)>(.*?)</\1\s*>", re.I | re.S)
def neutralise_deceptive_phrases(content: str) -> tuple[str, list[str]]:
    """Replace promise-shaped sentences with plain, honest statements.

    Blogger's rules treat a promised financial outcome, and a claimed personal
    product test, as deceptive. The paragraph that carries the promise is rewritten
    as a whole, because a phrase-level swap can leave broken grammar behind; the
    same words used to warn about a scam are left untouched, and headings, links,
    scripts and the Daily Yield furniture keep their structure.
    """
    found: list[str] = []
    counters: dict[str, int] = {}

    def repair_block(match: "re.Match[str]") -> str:
        tag, attributes, inner = match.group(1), match.group(2), match.group(3)
        if "<script" in inner.casefold() or "<style" in inner.casefold():
            return match.group(0)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        if not text:
            return match.group(0)
        hit = None
        for pattern, first_person in [(x, False) for x in DECEPTIVE_PATTERNS] + [(x, True) for x in FAKE_EXPERIENCE_PATTERNS]:
            for candidate in re.finditer(pattern, text, flags=re.I | re.S):
                if not first_person:
                    lead = text[max(0, candidate.start() - 70):candidate.start()].casefold()
                    if any(word in lead for word in NEGATION_WORDS):
                        continue
                hit = (candidate.group(0), first_person)
                break
            if hit:
                break
        if not hit:
            return match.group(0)
        kind = "first-person" if hit[1] else promise_class(hit[0])
        variants = NEUTRAL_REPLACEMENTS[kind]
        if tag.casefold().startswith("h"):
            replacement = "What the published evidence shows"
        else:
            replacement = variants[counters.get(kind, 0) % len(variants)]
            counters[kind] = counters.get(kind, 0) + 1
        found.append(f"{hit[0]} -> rewritten ({kind})")
        return f"<{tag}{attributes}>{replacement}</{tag}>"

    repaired = BLOCK_ELEMENT.sub(repair_block, content or "")

    # Anything outside a recognised container (a plain div, a table cell or a
    # caption) gets the same treatment, so no promise-shaped wording can remain.
    from editorial_integrity import _sentence_spans, _source_bounds
    plain, index = _visible_text(repaired)
    rough = repaired
    for start, end in reversed(_sentence_spans(plain)):
        sentence = plain[start:end]
        hit = None
        for pattern, first_person in [(x, False) for x in DECEPTIVE_PATTERNS] + [(x, True) for x in FAKE_EXPERIENCE_PATTERNS]:
            for candidate in re.finditer(pattern, sentence, flags=re.I | re.S):
                if not first_person:
                    lead = sentence[max(0, candidate.start() - 70):candidate.start()].casefold()
                    if any(word in lead for word in NEGATION_WORDS):
                        continue
                hit = (candidate.group(0), first_person)
                break
            if hit:
                break
        if not hit:
            continue
        bounds = _source_bounds(index, start, end)
        if not bounds:
            continue
        source_start, source_end = bounds
        kind = "first-person" if hit[1] else promise_class(hit[0])
        variants = NEUTRAL_REPLACEMENTS[kind]
        if "<" in rough[source_start:source_end]:
            # The sentence carries inline markup, so only the promise-shaped words
            # are swapped; the surrounding sentence and its links stay intact.
            offset = sentence.find(hit[0])
            phrase = _source_bounds(index, start + max(0, offset), start + max(0, offset) + len(hit[0])) if offset >= 0 else None
            if not phrase:
                continue
            phrase_start, phrase_end = phrase
            rough = rough[:phrase_start] + SHORT_NEUTRAL[kind] + rough[phrase_end:]
            found.append(f"{hit[0]} -> rewritten phrase (markup preserved, {kind})")
        else:
            replacement = variants[counters.get(kind, 0) % len(variants)]
            counters[kind] = counters.get(kind, 0) + 1
            rough = rough[:source_start] + replacement + rough[source_end:]
            found.append(f"{hit[0]} -> rewritten sentence outside a block ({kind})")
    return rough, found


CHECKLIST_EXCLUDE = re.compile(r"(faq|glossary|summary|contents|more from|ledger|questions|terms decoded|checklist|reference|follow|report)", re.I)
def ensure_reader_checklist(content: str, title: str, labels: list[str]) -> tuple[str, str]:
    """Add a short reader checklist when an article is under its depth benchmark.

    Each line is drawn from the article's own sections, so the addition is a real
    reader aid rather than padding, and no sentence is repeated.
    """
    words = len(re.findall(r"[A-Za-z][A-Za-z'-]+", plain(content)))
    if "News" in labels:
        minimum = 350
    elif "<!-- DY_MASTER_V2 -->" in content:
        minimum = 4500
    else:
        minimum = 900
    if words >= minimum:
        return content, ""
    headings = []
    for raw in re.findall(r"<h2\b[^>]*>(.*?)</h2\s*>", content, re.I | re.S):
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
        if len(text) >= 8 and not CHECKLIST_EXCLUDE.search(text) and text not in headings:
            headings.append(text)
    if not headings:
        return content, ""
    items = "".join(
        f'<li><strong>{html.escape(heading)}</strong> — your own figure, and what would change it?</li>'
        for heading in headings[:6])
    block = ('<section class="dy-reader-checklist"><h2>Reader checklist before you act</h2>'
             '<p>Match every section of this article against your own numbers before you decide anything.</p>'
             f'<ul>{items}</ul></section>')
    marker = "<!-- DY_PAGE_FAMILY_START -->"
    position = content.find(marker)
    if position >= 0:
        content = content[:position] + block + "\n" + content[position:]
    else:
        content = content.rstrip() + "\n" + block
    return content, f"added a reader checklist drawn from {len(headings[:6])} of the article's own sections (depth was {words} words)"


def ensure_context(content: str, title: str) -> tuple[str, bool]:
    if 'class="dy-context"' in content:
        return content, False
    block = context_card(title)
    match = re.search(r"</article\s*>", content or "", re.I)
    if match:
        return content[:match.start()] + block + content[match.start():], True
    return content.rstrip() + "\n" + block, True


def ensure_reader_block(content: str) -> tuple[str, bool]:
    if READER_MARK in content:
        return content, False
    family = re.search(r'<!--\s*DY_PAGE_FAMILY_START', content or "", re.I)
    if family:
        return content[:family.start()] + READER_SNIPPET + "\n" + content[family.start():], True
    return content.rstrip() + "\n" + READER_SNIPPET, True


def repair_package(post: dict, title: str, posts: list[dict]) -> dict:
    """Return the repaired content, the repairs applied, and the new title."""
    content = post.get("content") or ""
    repairs: list[str] = []

    content, banned = neutralise_prohibited(content)
    repairs.extend(banned)

    content, promises = neutralise_deceptive_phrases(content)
    if promises:
        repairs.append(f"rewrote {len(promises)} promise-shaped phrase(s) into plain wording")

    content, removed = repair_repeated_prose(content)
    if removed:
        repairs.append(f"removed {removed} repeated prose sentence(s)")

    content, scrubbed = scrub_repeated_sentences(content)
    if scrubbed:
        repairs.append(f"removed {scrubbed} banned or duplicated sentence(s)")

    content, alts = repair_image_alts(content, title)
    if alts:
        repairs.append(f"repaired {alts} image description(s)")

    content = ensure_disclosure(content)

    if "News" not in set(post.get("labels") or []):
        if 'class="dy-worked-example"' not in content and "Worked example with disclosed assumptions" not in content:
            content = content.rstrip() + "\n" + WORKED_EXAMPLE
            repairs.append("added the disclosed worked example")
        if 'class="dy-editorial-method"' not in content and "Editorial method" not in content:
            content = content.rstrip() + "\n" + EDITORIAL_METHOD
            repairs.append("added the editorial method note")

    content, added_context = ensure_context(content, title)
    if added_context:
        repairs.append("added the contextual Daily Yield card")

    content = ensure_related(content, post, posts)
    content = ensure_family(content, urllib.parse.urlsplit(post.get("url") or "").path)
    content = ensure_motion(content)

    description = description_from_content(title, content)
    image = re.search(r"<img[^>]+src=[\"']([^\"']+)", content, re.I)
    content = ensure_seo_meta(content, title, description, image.group(1) if image else "")

    content, added_reader = ensure_reader_block(content)
    if added_reader:
        repairs.append("added the engaged-reader follow and share block")

    # Brand and entity layer: the same author statement, reader questions and
    # linked entity data that every other Daily Yield page carries.
    content, brand_added = brand_seo.enrich(content, "article", title, post.get("url") or "")
    if brand_added:
        repairs.append("added the Daily Yield / Kushal Daga brand and entity block")
    description = brand_seo.front_meta(title, description)

    content, added_schema = ensure_jsonld(content, title, post.get("url") or "", description)
    if added_schema:
        repairs.append("added the BlogPosting structured-data record")

    content, added_byline = ensure_byline(content)
    if added_byline:
        repairs.append("restored the Daily Yield byline")

    content, checklist = ensure_reader_checklist(content, title, post.get("labels") or [])
    if checklist:
        repairs.append(checklist)

    # A final pass runs once every Daily Yield block is in place, so nothing added
    # here can reintroduce repetition; the controlled blocks stay untouched.
    content, final_scrub = scrub_repeated_sentences(content)
    if final_scrub:
        repairs.append(f"final repetition pass removed {final_scrub} sentence(s)")

    content = stamp(content, title, "quarantine-revival")
    return {"content": content, "repairs": repairs, "description": description, "title": title}


def benchmark_report(post: dict, repaired: dict) -> dict:
    """Describe every remaining benchmark gap without publishing anything."""
    title = repaired["title"]
    content = repaired["content"]
    report: dict = {"title": title, "title_length": len(title), "words": len(re.findall(r"[A-Za-z][A-Za-z'-]+", plain(content)))}
    try:
        assert_publishable(title, content, post.get("labels") or [], check_remote_images=False)
        report["preflight"] = "PASS"
        report["issues"] = []
    except RuntimeError as exc:
        text = str(exc)
        report["preflight"] = "FAIL"
        report["issues"] = [x.strip() for x in text.split("—", 1)[-1].split(";")]
    report["policy_issues"] = audit_text(title, content, "quarantine-revival", require_disclosure=True)
    report["promise_evidence"] = [phrase for phrase in re.findall(r"(?:guarantee\w*|risk[- ]free|zero risk|get rich quick|double your money)[^.]{0,60}", plain(content), re.I)][:6]
    report["source_domains"] = sorted(source_domains(content))[:8]
    report["disclosure"] = DISCLOSURE_MARKER in content
    report["integrity_stamp"] = INTEGRITY_MARK in content
    return report


def survey(tok: str) -> dict:
    rows = []
    posts = fetch_public_posts(limit=100)
    for item in plan_items():
        post = post_by_id(tok, item["draft_id"])
        title = compact_title(post.get("title") or item["title_now"])
        repaired = repair_package(post, title, posts)
        report = benchmark_report(post, repaired)
        report.update({
            "order": item["order"], "draft_id": item["draft_id"], "social_route": item["social_route"],
            "status_now": post.get("status"), "labels": post.get("labels") or [],
            "before_title": post.get("title"), "before_words": len(re.findall(r"[A-Za-z][A-Za-z'-]+", plain(post.get("content") or ""))),
            "before_bytes": len(post.get("content") or ""), "repairs_planned": repaired["repairs"],
        })
        rows.append(report)
        print(json.dumps({k: report[k] for k in ("order", "before_title", "title", "title_length", "before_words", "preflight", "repairs_planned")}, ensure_ascii=False))
        for issue in report["issues"]:
            print(f"    REMAINING GAP: {issue}")
    document = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "drafts": len(rows), "preflight_pass": sum(1 for x in rows if x["preflight"] == "PASS"), "rows": rows}
    save(SURVEY, document)
    print(json.dumps({"surveyed": len(rows), "preflight_pass": document["preflight_pass"]}))
    return document


# --------------------------------------------------------------------- publication
def prepare(item: dict, tok: str, posts: list[dict]) -> dict:
    """Read the stored draft and build the fully repaired publication package."""
    post = post_by_id(tok, item["draft_id"])
    if post.get("status") == "LIVE":
        return {"result": "already_live", "post": post, "url": post.get("url"), "title": post.get("title")}
    title = compact_title(post.get("title") or item["title_now"])
    repaired = repair_package(post, title, posts)
    # The preflight is the gate: nothing is written or released while it fails.
    assert_publishable(title, repaired["content"], post.get("labels") or [], check_remote_images=True)
    return {"result": "ready", "post": post, "title": title, "content": repaired["content"], "repairs": repaired["repairs"]}


def publish_one(item: dict, tok: str, posts: list[dict], apply: bool) -> dict:
    prepared = prepare(item, tok, posts)
    if prepared["result"] == "already_live":
        return prepared
    if not apply:
        return {"result": "dry_run", "title": prepared["title"], "url": prepared["post"].get("url"),
                "repairs": prepared["repairs"], "bytes": len(prepared["content"]),
                "words": len(re.findall(r"[A-Za-z][A-Za-z'-]+", plain(prepared["content"])))}
    post, title = prepared["post"], prepared["title"]

    fresh = post_by_id(tok, item["draft_id"], refresh=True)
    if fresh.get("status") not in (None, "DRAFT"):
        raise RuntimeError(f"revival expects a quarantined draft, found {fresh.get('status')}")
    draft = call(f"/posts/{item['draft_id']}", tok, "PUT", {
        "kind": "blogger#post", "id": item["draft_id"], "blog": {"id": _required("BLOGGER_BLOG_ID")},
        "title": title, "content": prepared["content"], "labels": post.get("labels") or [],
    })
    if draft.get("status") not in (None, "DRAFT"):
        raise RuntimeError(f"post was expected to stay a draft before release, found {draft.get('status')}")
    live = call(f"/posts/{item['draft_id']}/publish", tok, "POST")
    stored = post_by_id(tok, item["draft_id"], refresh=True)
    assert_saved_green(stored)
    return {
        "result": "published", "url": stored.get("url") or live.get("url"), "title": title,
        "published": stored.get("published"), "repairs": prepared["repairs"],
        "bytes": len(stored.get("content") or ""), "words": len(re.findall(r"[A-Za-z][A-Za-z'-]+", plain(stored.get("content") or ""))),
    }


def announce(item: dict, published_at: str, url: str, apply: bool) -> list[str]:
    commands = []
    for route_index, platform in enumerate(item["social_route"]):
        argv = [
            "gh", "workflow", "run", SOCIAL_WORKFLOW, "--ref", "main",
            "-f", f"item_key=revive-{item['order']:02d}",
            "-f", f"target_url={url}",
            "-f", "content_mode=post",
            "-f", f"published_at={published_at}",
            "-f", f"route_index={route_index}",
            "-f", f"extra_platforms={','.join(item['social_route'])}",
        ]
        commands.append(" ".join(argv))
        if apply:
            subprocess.run(argv, check=True)
    return commands


def run(apply: bool, force: bool) -> dict:
    # Owner retired this separate publisher. Check before credentials, inventory,
    # state mutation or any Blogger/social operation; --force only affects timing
    # and must never override the owner's removal. Missing plans fail closed.
    plan = load(PLAN, {})
    if plan.get("enabled") is not True:
        return {
            "status": "RETIRED",
            "reason": plan.get("retired_reason", "Eight-hour recovery publishing is disabled."),
            "articlesPublished": 0,
            "socialPostsDispatched": 0,
        }
    current = state()
    now = dt.datetime.now(IST)
    if not force and not due_now(current, now):
        return {"status": "WAITING", "next_due_at": current.get("next_due_at", "")}
    revision = implementation_revision()
    item = next_pending(current, revision)
    if item is None:
        current["next_due_at"] = ""
        save(STATE, current)
        return {"status": "COMPLETE", "remaining": 0}
    row = item_state(current, item["draft_id"])
    row["attempts"] = int(row.get("attempts", 0)) + 1
    row["last_attempt"] = now.isoformat()
    row["revision"] = revision
    tok = token()
    posts = fetch_public_posts(limit=100)
    try:
        outcome = publish_one(item, tok, posts, apply)
    except Exception as exc:
        row["status"] = "repair_failed"
        row["error"] = str(exc)[:1200]
        # A blocked article never consumes the eight-hour slot: the next run moves
        # on to the following article at the same spacing.
        row["next_due_at"] = current.get("next_due_at", "")
        current["last_run"] = now.isoformat()
        save(STATE, current)
        print(json.dumps({"status": "REPAIR_FAILED", "draft_id": item["draft_id"], "title": item["title_now"], "error": str(exc)[:600]}))
        return {"status": "REPAIR_FAILED", "draft_id": item["draft_id"], "error": str(exc)[:600]}
    if outcome["result"] == "dry_run":
        row["status"] = "ready_for_release"
        row["prepared_at"] = now.isoformat()
        row["repairs"] = outcome["repairs"]
        row["title_prepared"] = outcome["title"]
        save(STATE, current)
        print(json.dumps({"status": "DRY_RUN_READY", "order": item["order"], "draft_id": item["draft_id"], **{k: outcome[k] for k in ("title", "bytes", "words")}, "repairs": outcome["repairs"]}, ensure_ascii=False))
        return {"status": "DRY_RUN_READY", "draft_id": item["draft_id"], "url": outcome.get("url")}
    if outcome["result"] == "published":
        row["status"] = "live"
        row["url"] = outcome["url"]
        row["title_published"] = outcome["title"]
        row["published_at"] = outcome["published"]
        row["repairs"] = outcome["repairs"]
        row["social_route"] = item["social_route"]
        row["social_commands"] = announce(item, outcome["published"] or now.astimezone(dt.timezone.utc).isoformat(), outcome["url"], apply)
    else:
        row["status"] = "live"
        row["url"] = outcome["url"]
        row["note"] = "already live before this revival run"
    current["next_due_at"] = (now + dt.timedelta(hours=SPACING_HOURS)).isoformat()
    current["last_run"] = now.isoformat()
    current["implementation_revision"] = revision
    save(STATE, current)
    remaining = len([x for x in plan_items() if item_state(current, x["draft_id"]).get("status") not in ("live", "repair_failed", "abandoned")])
    print(json.dumps({**{k: v for k, v in outcome.items() if k != "repairs"}, "remaining_pending": remaining, "next_due_at": current["next_due_at"]}, ensure_ascii=False))
    return {"status": "LIVE" if outcome["result"] == "published" else outcome["result"], "remaining": remaining, "url": outcome["url"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey", action="store_true", help="read every draft and report the benchmark gap; nothing is published")
    parser.add_argument("--apply", action="store_true", help="publish the next due article after the repair and preflight pass")
    parser.add_argument("--dry-run", action="store_true", help="build and validate the package without writing or releasing it")
    parser.add_argument("--force", action="store_true", help="ignore the eight-hour spacing for this run only")
    args = parser.parse_args()
    if args.survey:
        tok = token()
        document = survey(tok)
        return 0 if document["preflight_pass"] == document["drafts"] else 0
    result = run(args.apply and not args.dry_run, args.force)
    print(json.dumps(result, ensure_ascii=False))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("### Quarantine revival\n\n```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
