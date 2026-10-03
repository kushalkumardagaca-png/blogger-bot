
from PIL import Image, ImageDraw
import io
import base64

import io
import base64
import urllib.request
from PIL import Image, ImageOps
from image_safety import FALLBACK_MARKET, safe_image

CATEGORY_PHOTOS = {
    "Contrarian Hooks": "photo-1518186285589-2f7649de83e0",
    "Age and Wealth Milestones": "photo-1434030216411-0b793f4b4173",
    "Passive Income Reality": "photo-1486406146926-c627a92ad1ab",
    "Middle Class Survival": "photo-1526304640581-d334cdbbf45e",
    "Money Audits and Case Studies": "photo-1454165804606-c3d57bc86b40",
    "Housing Cars and Big Buys": "photo-1503376780353-7e6692767b70",
    "Automation and Money Systems": "photo-1518770660439-4636190af475",
    "Credit Debt and Optimization": "photo-1563013544-824ae1b704d3",
    "AI Fintech and Future Money": "photo-1618005182384-a83a8bd57fbe",
    "Money Psychology and Mindset": "photo-1506126613408-eca07ce68773",
    "Investing Strategies": "photo-1611974789855-9c2a0a7236a3",
    "Retirement Pensions and FIRE": "photo-1532619675605-1ede6c2ed2b0",
    "Taxes and Account Optimization": "photo-1554224155-8d04cb21cd6c",
    "Career Salary and Raises": "photo-1573496359142-b8d87734a5a2",
    "Side Hustles That Work": "photo-1522202176988-66273c2fd55f",
    "Insurance and Protection": "photo-1450133064473-71024230f91b",
    "Couples Family and Kids": "photo-1516589178581-6cd7833ae3b2",
    "Starters Students and First Jobs": "photo-1523240795612-9a054b0db644",
    "Spending Lifestyle and Frugality": "photo-1559526324-4b87b5e36e44",
    "Rich Habits vs Broke Habits": "photo-1507679799987-c73779587ccf",
    "Recessions Crashes and Defense": "photo-1590283603385-17ffb3a7f29f",
    "Cash Savings and Emergency Funds": "photo-1579621970563-ebec7560ff3e",
    "Real Estate Investing": "photo-1560518883-ce09059eeffa",
    "Myths Scams and Bad Advice": "photo-1563986768609-322da13575f3",
    "2026 Money Moves": "photo-1460925895917-afdab827c52f"
}

def generate_hero_image_figure(title, category):
    # Performance: direct Unsplash CDN URL (same photo, same 900x506 crop, q=85).
    # No download/PIL re-encode/base64 embedding — keeps article HTML ~100 KB lighter
    # and lets the hero load in parallel from Unsplash's global image CDN.
    photo_id = CATEGORY_PHOTOS.get(category, "photo-1611974789855-9c2a0a7236a3")
    candidate = f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=900&h=506&q=85"
    fallback = FALLBACK_MARKET.replace('w=1600&h=900', 'w=900&h=506')
    img_src = safe_image(candidate, fallback)

    return f"""  <figure class="kushal-hero-figure" style="margin: 24px 0 32px; text-align: center;">
    <img src="{img_src}" alt="Figure 1.0: Editorial Photography — {title}" width="900" height="506" loading="eager" decoding="async" fetchpriority="high" style="width: 100%; max-width: 100%; height: auto; border-radius: 8px; border: 1px solid #EADCC8; box-shadow: 0 16px 36px -16px rgba(36,22,16,0.3);" />
    <figcaption style="font-size: 12.5px; color: #7A6A58; margin-top: 10px; font-style: italic;">Figure 1.0: Editorial Photography — Forensic Strategic Framework for {title}</figcaption>
  </figure>"""

import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from contextual_links import STYLE as CONTEXT_STYLE, card as contextual_card
from continuous_motion import ensure as ensure_continuous_motion
from related_articles import ensure as ensure_related_articles, fetch_public_posts
from publication_preflight import assert_publishable
from page_family import ensure_family
from seo_hygiene import compact_title, repair_image_alts
from seo_meta import ensure_seo_meta
from reader_value_article import build as build_reader_value_article

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

# Blogger Blog ID for "Daily Yield"
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
TRACKER_FILE = "published_tracker.json"
SOCIAL_EVENTS_FILE = "social_events.json"
CSV_FILE = "500_topics_evenly_mixed.csv"

# Permanent entity SEO map. Topic intent remains primary; these variants identify
# the same publication/person without changing the visible author byline.
SEO_QUERY_TERMS = ["Daily Yield", "Kushal Daga", "CA Kushal", "Kushal Jain",
                   "Kushal K. Daga", "Finance", "Finance by Kushal"]
PERSON_ALIASES = ["Kushal Daga", "CA Kushal", "Kushal Jain", "Finance by Kushal"]

# Exact 25 Master Categories Taxonomy (No commas within categories)
CATEGORIES_25 = [
    "Contrarian Hooks", "Age and Wealth Milestones", "Passive Income Reality",
    "Middle Class Survival", "Money Audits and Case Studies", "Housing Cars and Big Buys",
    "Automation and Money Systems", "Credit Debt and Optimization", "AI Fintech and Future Money",
    "Money Psychology and Mindset", "Investing Strategies", "Retirement Pensions and FIRE",
    "Taxes and Account Optimization", "Career Salary and Raises", "Side Hustles That Work",
    "Insurance and Protection", "Couples Family and Kids", "Starters Students and First Jobs",
    "Spending Lifestyle and Frugality", "Rich Habits vs Broke Habits", "Recessions Crashes and Defense",
    "Cash Savings and Emergency Funds", "Real Estate Investing", "Myths Scams and Bad Advice",
    "2026 Money Moves"
]

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"next_topic_index": 10, "last_published_timestamp": None, "published_posts": []}

def save_tracker(tracker):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2)

def load_topics():
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found!")
        sys.exit(1)
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def clean_slug(title):
    s = title.lower().replace("'", "").replace(":", "").replace("?", "").replace(",", "").replace('"', '').strip()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')

def get_standardized_category(raw_cat):
    clean = re.sub(r"[^a-z0-9]+", " ", raw_cat.lower().replace("&", " and ")).strip()
    for cat in CATEGORIES_25:
        canonical = re.sub(r"[^a-z0-9]+", " ", cat.lower().replace("&", " and ")).strip()
        if canonical == clean or canonical in clean:
            return cat
    raise ValueError(f"Unknown master category: {raw_cat}")

# Master article HTML is built by reader_value_article.build.
# The former fixed cross-topic template was removed to prevent accidental reuse.

def publish_to_blogger(title, content, labels):
    """Publish once, recover safely on retries, and align canonical URLs to Blogger."""
    client_id = os.environ.get("BLOGGER_CLIENT_ID")
    client_secret = os.environ.get("BLOGGER_CLIENT_SECRET")
    refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError("Blogger credentials are absent; tracker will not advance")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(None, refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token", client_id=client_id,
        client_secret=client_secret)
    service = build("blogger", "v3", credentials=creds, cache_discovery=False)

    # If Blogger accepted a prior attempt but the tracker push failed, recover it
    # instead of publishing a duplicate copy.
    found = service.posts().search(blogId=BLOG_ID, q=title, fetchBodies=False).execute()
    for post in found.get("items", []):
        if post.get("title", "").strip() == title.strip():
            print(f"Existing exact-title post recovered; no duplicate published: {post.get('url')}")
            return post

    body = {"kind": "blogger#post", "blog": {"id": BLOG_ID},
            "title": title, "content": content, "labels": labels}
    res = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
    live_url = res.get("url", "")
    # The generated canonical is deterministic, but Blogger can suffix a slug.
    # Patch every predicted post URL to the actual URL after insertion.
    predicted = re.search(r'https://dailyyield\.blogspot\.com/\d{4}/\d{2}/[a-z0-9-]+\.html', content)
    if live_url and predicted and predicted.group(0) != live_url:
        patched = content.replace(predicted.group(0), live_url)
        res = service.posts().update(blogId=BLOG_ID, postId=res["id"], body={
            "kind": "blogger#post", "id": res["id"], "title": title,
            "content": patched, "labels": labels}).execute()
    print(f"Successfully published live to Blogger! Post ID: {res.get('id')} | URL: {res.get('url', live_url)}")
    return res

def main():
    # A workflow consumes only events created by this exact publication run.
    with open(SOCIAL_EVENTS_FILE, "w", encoding="utf-8") as handle:
        json.dump([], handle)
    tracker = load_tracker()
    topics = load_topics()
    
    current_idx = tracker.get("next_topic_index", 10)
    if current_idx >= len(topics):
        print("All 500 topics have been completed!")
        return

    topic = topics[current_idx]
    now = datetime.now(IST)
    pub_date_str = now.strftime("%Y-%m-%d")
    pub_time_str = now.strftime("%H:%M")

    print(f"Processing Topic #{topic['#']} (Index {current_idx}): {topic['Punchy Title']} [{topic['Category']}]")
    category = get_standardized_category(topic["Category"])
    preview_title = compact_title(topic["Punchy Title"])
    hero = generate_hero_image_figure(preview_title, category)
    article_topic = dict(topic)
    article_topic["Category"] = category
    title, slug, meta_desc, labels, html = build_reader_value_article(article_topic, pub_date_str, pub_time_str, hero)
    current_post = {"id": "pending", "title": title, "labels": labels, "content": html}
    html = ensure_related_articles(html, current_post, fetch_public_posts())
    html = ensure_family(html)
    html = ensure_continuous_motion(html)
    assert_publishable(title, html, labels)

    # Always rebuild with the current date, identity and schema. Old precompiled
    # packages are never reused because their dates or branding may be stale.
    os.makedirs("scheduled_ready", exist_ok=True)
    local_path = f"scheduled_ready/topic_{topic['#']}_{slug}.html"
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Built fresh Daily Yield package at {local_path}")

    api_res = publish_to_blogger(title, html, labels)
    if not api_res or not api_res.get("url"):
        raise RuntimeError("Blogger did not return a live URL; tracker will not advance")

    # Update tracker only after Blogger confirms a live or recovered post.
    tracker["next_topic_index"] = current_idx + 1
    tracker["last_published_timestamp"] = f"{pub_date_str} {pub_time_str}"
    tracker["published_posts"].append({
        "topic_id": topic["#"],
        "title": title,
        "slug": slug,
        "category": topic["Category"],
        "published_at": f"{pub_date_str} {pub_time_str}",
        "blogger_url": api_res.get("url") if api_res else f"https://dailyyield.blogspot.com/{pub_date_str[:7].replace('-', '/')}/{slug}.html"
    })
    save_tracker(tracker)
    social_event = {
        "item_key": f"master-{int(topic['#']) % 5}",
        "target_url": api_res["url"],
        "content_mode": "post",
        "published_at": api_res.get("published") or datetime.now(timezone.utc).isoformat(),
    }
    with open(SOCIAL_EVENTS_FILE, "w", encoding="utf-8") as handle:
        json.dump([social_event], handle, indent=2)
    print(f"Tracker successfully updated! Next topic index: {tracker['next_topic_index']}")

if __name__ == "__main__":
    main()
