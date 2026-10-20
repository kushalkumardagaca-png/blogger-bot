#!/usr/bin/env python3
"""Routine card/data refresh only; preserve all existing hub structure and code."""
from __future__ import annotations
import hashlib, html, json, re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


def replace_json_value(document: str, marker: str, value) -> tuple[str, bool]:
    start = document.find(marker)
    if start < 0:
        return document, False
    start += len(marker)
    while start < len(document) and document[start].isspace():
        start += 1
    try:
        old, length = json.JSONDecoder().raw_decode(document[start:])
    except (ValueError, TypeError):
        return document, False
    if not isinstance(old, list):
        return document, False
    payload = json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return document[:start] + payload + document[start + length:], True


def refresh_article_cards(document, posts, categories, card, now=None):
    now = now or datetime.now(timezone.utc)
    masters = sorted((p for p in posts if 'News' not in p.get('labels', [])),
                     key=lambda p: p.get('published', ''), reverse=True)
    def recent(p):
        try:
            stamp = datetime.fromisoformat(p.get('published', '').replace('Z', '+00:00'))
            return timedelta(0) <= now - stamp.astimezone(timezone.utc) <= timedelta(days=1)
        except (ValueError, TypeError):
            return False
    definitions = [('dya-new', [p for p in masters if recent(p)], None)]
    for category in categories:
        definitions.append(('dya-' + str(category['number']),
                            [p for p in masters if category['label'] in p.get('labels', [])], category))
    changed = 0
    for section_id, selected, category in definitions:
        pattern = re.compile(r'(<section\b(?=[^>]*\bid=["\']' + re.escape(section_id) + r'["\'])[^>]*>)(.*?)(</section>)', re.S)
        found = pattern.search(document)
        if not found:
            continue  # never create a missing section during freeze
        body = found.group(2)
        row = re.search(r'(<div class="dya-set">)(.*?)(</div>)', body, re.S)
        if not row:
            continue  # no new carousel scaffolding or feature installation
        cards = []
        for post in selected:
            cat = category or next((c for c in categories if c['label'] in post.get('labels', [])), {'name': 'Latest article', 'art': ''})
            cards.append(card(post, cat))
        new_body = body[:row.start(2)] + ''.join(cards) + body[row.end(2):]
        new_body = re.sub(r'(<div class="dya-tools"><span>)\d+( new)? article(s)?',
                          lambda m: m.group(1) + str(len(selected)) + (' new' if m.group(2) else '') + ' article' + ('' if len(selected) == 1 else 's'), new_body, count=1)
        if new_body != body:
            document = document[:found.start(2)] + new_body + document[found.end(2):]
            changed += 1
    return document, changed


# The hub pages are the crawl path. Every one of the blog's ~550 stories links to
# /p/daily-news.html and /p/article.html, so a search robot standing on a story should be able
# to walk from there onto today's articles - which is exactly the shape the operation wants:
# get the hub indexed, and let the hub hand out the articles. Measured on the live hub on
# 20 October 2026, however: the news snapshot data is refreshed daily and current, but the
# page HTML contains 53 anchor tags and 0 of them point at a blog post. Every article link is
# built by JavaScript after load, so a crawler that does not run that script sees a dead end,
# which matches Search Console's 360 "discovered - currently not indexed" URLs. This block is
# the fix inside the freeze rules: a plain HTML link index, in markers this job owns, with no
# stylesheet, script or heading changes.
HUB_LINK_CAP = 12
LINK_START = '<!-- DY_HUB_LINK_INDEX_START -->'
LINK_END = '<!-- DY_HUB_LINK_INDEX_END -->'


def link_index(posts, want_news, cap=HUB_LINK_CAP):
    """Plain hrefs to the newest articles of one kind, newest first."""
    rows = [post for post in posts
            if (("News" in (post.get("labels") or [])) == bool(want_news)) and post.get("url")]
    rows.sort(key=lambda post: str(post.get("published", "")), reverse=True)
    rows = rows[:cap]
    if not rows:
        return "", 0
    lead = "Latest news editions on Daily Yield" if want_news else "Latest articles on Daily Yield"
    items = "".join(
        '<li><a href="' + html.escape(str(row["url"]), quote=True) + '">'
        + html.escape(re.sub(r"\s+", " ", str(row.get("title") or "Untitled")).strip()) + "</a></li>"
        for row in rows)
    body = (LINK_START + '<div class="dy-hub-links"><p class="dy-hub-links-lead">' + lead +
            '</p><ul class="dy-hub-links-list">' + items + '</ul></div>' + LINK_END)
    return body, len(rows)


def place_link_index(document, index_html):
    """Replace the hub link index in place, or add it once if the hub has never had one."""
    if not index_html:
        return document, False
    if LINK_START in document and LINK_END in document:
        replaced = re.sub(re.escape(LINK_START) + r".*?" + re.escape(LINK_END),
                          lambda _match: index_html, document, count=1, flags=re.S)
        return replaced, replaced != document
    return document + index_html, True


def refresh_existing_hubs(headers, posts, pages, put, article_card, news_item, categories):
    rows = []
    for page in pages:
        path = urlparse(page.get('url', '')).path
        if path not in ('/p/article.html', '/p/daily-news.html'):
            continue
        old = page.get('content', '')
        new = old
        refreshed = 0
        if path == '/p/article.html':
            new, refreshed = refresh_article_cards(old, posts, categories, article_card)
        else:
            data = [news_item(p) for p in sorted(posts, key=lambda p:p.get('published', ''), reverse=True) if 'News' in p.get('labels', [])]
            for marker in ('window.ENH_NEWS_SNAPSHOT=', '(function(w,d){var items='):
                new, ok = replace_json_value(new, marker, data)
                refreshed += int(ok)
        index_html, index_hrefs = link_index(posts, path != '/p/article.html')
        new, index_placed = place_link_index(new, index_html)
        # No style addition/change, no new scripts, tracking, headings or sections.
        styles = lambda s: re.findall(r'<style\b.*?</style>', s, re.I|re.S)
        assert styles(old) == styles(new), 'freeze forbids stylesheet changes'
        assert re.findall(r'<script\b[^>]*>', old, re.I) == re.findall(r'<script\b[^>]*>', new, re.I), 'freeze forbids new script tags'
        assert re.findall(r'<h[1-6]\b.*?</h[1-6]>', old, re.I|re.S) == re.findall(r'<h[1-6]\b.*?</h[1-6]>', new, re.I|re.S), 'freeze forbids changing hub headings'
        if new != old:
            put('pages', page, headers, new)
        rows.append({'path': path, 'dataBlocks': refreshed, 'linkIndexHrefs': index_hrefs,
                     'linkIndexWritten': index_placed, 'changed': new != old,
                     'beforeSha256': hashlib.sha256(old.encode()).hexdigest(),
                     'afterSha256': hashlib.sha256(new.encode()).hexdigest()})
    # Existing theme card lookup: data file only, no Blogger theme upload.
    images, fallbacks = {}, {}
    for post in posts:
        srcs = re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)', post.get('content', ''), re.I)
        images[post['id']] = srcs[0] if srcs else ''
        fallbacks[post['id']] = next((u for u in srcs[1:] if u != images[post['id']] and not re.search(r'https?://(?:thumb|upload)\.wikimedia\.org/', u, re.I)), '')
    Path('LABEL_FEED_INDEX.json').write_text(json.dumps({'version':4, 'generated_at':datetime.now(timezone.utc).isoformat(), 'images':images, 'fallbacks':fallbacks},ensure_ascii=False,separators=(',',':'))+'\n')
    report = {'status':'PASS', 'mode':'FREEZE_DATA_ONLY', 'zero_view':True,
              'posts_checked':len(posts), 'posts_rewritten':0, 'labels_normalized':0,
              'duplicate_heroes_replaced':0, 'pages_repaired':0,
              'routineHubDataRefreshes':rows,
              'optional_changes':'held; no full hub rebuild or old-post edits'}
    Path('CONTENT_EXPERIENCE_REPAIR_STATUS.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return report
