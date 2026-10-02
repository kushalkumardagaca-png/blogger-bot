#!/usr/bin/env python3
"""Deterministic, platform-native creative system for Daily Yield social posts.

The module never requests a Daily Yield page. It receives authenticated Blogger
API content, creates a fresh platform/date creative signature, writes distinct
captions and renders one of several accessible 1200x630 editorial card systems.
"""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
SIZE = (1200, 630)
PHOTO_HOSTS = ("images.unsplash.com", "upload.wikimedia.org", "thumb.wikimedia.org", "blogger.googleusercontent.com")

# The same licensed editorial-photo family already used by Daily Yield articles.
PHOTO_POOLS = {
    "market": ("photo-1611974789855-9c2a0a7236a3", "photo-1590283603385-17ffb3a7f29f", "photo-1518186285589-2f7649de83e0"),
    "debt": ("photo-1563013544-824ae1b704d3", "photo-1526304640581-d334cdbbf45e"),
    "tax": ("photo-1554224155-8d04cb21cd6c", "photo-1454165804606-c3d57bc86b40"),
    "saving": ("photo-1579621970563-ebec7560ff3e", "photo-1559526324-4b87b5e36e44"),
    "economy": ("photo-1454165804606-c3d57bc86b40", "photo-1486406146926-c627a92ad1ab"),
    "news": ("photo-1494522855154-9297ac14b55f", "photo-1502602898657-3e91760cbb34", "photo-1506973035872-a4ec16b8e8d9"),
    "page": ("photo-1460925895917-afdab827c52f", "photo-1518770660439-4636190af475"),
    "general": ("photo-1526304640581-d334cdbbf45e", "photo-1507679799987-c73779587ccf"),
}
PHOTO_ALT = {
    "market": "financial market screens and investment analysis",
    "debt": "a card payment and personal finance workspace",
    "tax": "financial documents and a calculator on a desk",
    "saving": "coins and a practical savings plan",
    "economy": "economic analysis at a professional workspace",
    "news": "a contemporary financial district and business activity",
    "page": "a digital financial research and planning workspace",
    "general": "a modern personal-finance planning workspace",
}

PALETTES = (
    {"name":"acid ledger","bg":"#101522","panel":"#D8FF49","ink":"#F7F4EA","panel_ink":"#11151F","accent":"#FF6B6B","muted":"#AFB8C8"},
    {"name":"cobalt pop","bg":"#1557FF","panel":"#FFF4D8","ink":"#FFFFFF","panel_ink":"#111827","accent":"#FF775F","muted":"#CFE0FF"},
    {"name":"violet mint","bg":"#4026A8","panel":"#BDF7D5","ink":"#FFF9EE","panel_ink":"#17231D","accent":"#FFAA3D","muted":"#D9D1FF"},
    {"name":"hot coral","bg":"#FF5D57","panel":"#FFF2E5","ink":"#241610","panel_ink":"#241610","accent":"#7B2CFF","muted":"#5D312A"},
    {"name":"night signal","bg":"#111111","panel":"#F1E9DA","ink":"#FAF6EE","panel_ink":"#151515","accent":"#FFB000","muted":"#BFB8AC"},
    {"name":"teal voltage","bg":"#006B65","panel":"#E5FF71","ink":"#F7FFF8","panel_ink":"#12302D","accent":"#FF8066","muted":"#BCE7DF"},
    {"name":"lavender zine","bg":"#D9CEFF","panel":"#21183C","ink":"#21183C","panel_ink":"#FFF9EF","accent":"#FF6A3D","muted":"#5F537A"},
    {"name":"sky sticker","bg":"#AEE8FF","panel":"#FFFDF4","ink":"#112A38","panel_ink":"#112A38","accent":"#F04475","muted":"#466A7A"},
    {"name":"mango grid","bg":"#FFC93D","panel":"#18243A","ink":"#18243A","panel_ink":"#FFF9E8","accent":"#F24D3D","muted":"#5C4D28"},
    {"name":"rose terminal","bg":"#7B1437","panel":"#FFD5E1","ink":"#FFF6EF","panel_ink":"#3D1020","accent":"#7DFFB2","muted":"#EDB7C7"},
)

HOOKS = {
    "page": ("SAVE THIS MONEY TOOL", "YOUR NEXT SMART TAB", "BOOKMARK ENERGY", "THE USEFUL CORNER OF THE INTERNET"),
    "news": ("THE MONEY UPDATE", "WHAT JUST MOVED", "THE CONTEXT DROP", "TODAY, MINUS THE NOISE"),
    "market": ("THE CHART HAS NOTES", "MARKET MOOD CHECK", "WHAT THE NUMBERS ARE SAYING", "ZOOM OUT BEFORE YOU TAP BUY"),
    "debt": ("DEBT CHECK, NO SHAME", "YOUR APR HAS A PLOT", "THE REPAYMENT REALITY CHECK", "BORROWING MATH, UNFILTERED"),
    "tax": ("TAX, BUT MAKE IT CLEAR", "THE FINE PRINT HAS ENTERED", "KEEP THE RECEIPTS", "YOUR TAX TAB, DECODED"),
    "saving": ("FUTURE-YOU SENT A NOTE", "SMALL MOVE, LONG SHADOW", "THE SAVINGS PLOT TWIST", "MAKE THE MONEY STAY"),
    "economy": ("YOUR WALLET FELT THAT", "THE ECONOMY, IN HUMAN TERMS", "MACRO WITHOUT THE MONOLOGUE", "WHY PRICES ARE ACTING LIKE THAT"),
    "general": ("MONEY, MINUS THE LECTURE", "PAUSE THE SCROLL", "THE RECEIPTS ARE IN", "LET'S DO THE MATH"),
}

EMOJIS = ("🧾", "📊", "🧠", "⚡", "🪩", "🔎", "💸", "📌", "🧮", "🌐")
QUESTIONS = {
    "market": ("What would make you change your view?", "Are you watching the price—or the context?"),
    "debt": ("Which number would you tackle first?", "What would make this repayment plan feel realistic?"),
    "tax": ("Which rule deserves a plain-English explainer next?", "What part of the fine print trips people up most?"),
    "saving": ("What is the smallest version of this move you could start today?", "What helps you make saving automatic?"),
    "news": ("Which development deserves the deeper follow-up?", "What changes your money decision here?"),
    "page": ("Which tool should Daily Yield build next?", "Save it now—which decision will you use it for?"),
    "economy": ("Where are you feeling this most in real life?", "Which number needs more context?"),
    "general": ("What is your take after seeing the numbers?", "What should Daily Yield unpack next?"),
}


def clean(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def topic(item: dict) -> str:
    text = (item.get("title", "") + " " + " ".join(str(x) for x in item.get("labels", []))).lower()
    if item.get("kind") == "page": return "page"
    if "news" in text: return "news"
    if any(x in text for x in ("market", "stock", "share", "gold", "oil", "crypto", "invest", "fund")): return "market"
    if any(x in text for x in ("debt", "loan", "emi", "credit card", "mortgage", "apr")): return "debt"
    if any(x in text for x in ("tax", "deduction", "irs")): return "tax"
    if any(x in text for x in ("saving", "budget", "retirement", "salary", "emergency fund")): return "saving"
    if any(x in text for x in ("economy", "inflation", "rates", "gdp", "jobs", "policy")): return "economy"
    return "general"


def creative_seed(item: dict, platform: str, day: str | None = None) -> int:
    day = day or datetime.now(IST).date().isoformat()
    raw = f"{platform}|{item.get('url','')}|{item.get('id','')}|{day}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16)


def creative_meta(item: dict, platform: str, day: str | None = None) -> dict:
    seed = creative_seed(item, platform, day)
    group = topic(item)
    hooks = HOOKS[group]
    questions = QUESTIONS[group]
    return {
        "seed": f"{seed:016x}", "topic": group,
        "style": PALETTES[seed % len(PALETTES)]["name"],
        "style_index": seed % len(PALETTES),
        "hook": hooks[(seed // 11) % len(hooks)],
        "emoji": EMOJIS[(seed // 17) % len(EMOJIS)],
        "question": questions[(seed // 23) % len(questions)],
        "layout": (seed // 31) % 5,
    }


def first_sentence(summary: str, limit: int = 180) -> str:
    text = clean(summary)
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    result = match.group(1) if match else text
    if len(result) > limit:
        result = result[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return result


def trim(text: str, limit: int) -> str:
    text = clean(text)
    if len(text) <= limit: return text
    cut = text[:max(1, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (cut or text[:limit - 1]) + "…"


def hashtag_list(item: dict) -> list[str]:
    group = topic(item)
    mapping = {"market":"#Markets", "debt":"#Debt", "tax":"#Tax", "saving":"#MoneyTips", "economy":"#Economy", "news":"#FinanceNews", "page":"#MoneyTools", "general":"#PersonalFinance"}
    return ["#DailyYield", mapping[group]]


def build_caption(item: dict, platform: str, summary: str, limit: int | None = None) -> str:
    meta = creative_meta(item, platform)
    title, url = clean(item.get("title", "Daily Yield")), item["url"]
    insight = first_sentence(summary, 210 if platform in ("facebook", "tumblr") else 130)
    tags = " ".join(hashtag_list(item))
    if platform == "facebook":
        ctas = ("Save this for the next money conversation.", "Send this to the group chat that debates everything.", "Read it now; bookmark it for decision day.", "The useful bit is the context—not just the headline.")
        cta = ctas[(creative_seed(item, platform) // 41) % len(ctas)]
        return f"{meta['emoji']} {meta['hook']}\n\n{title}\n\n{insight}\n\n{cta}\n{meta['question']}\n\n{url}\n\nBy Kushal K. Daga · {tags}"
    if platform == "bluesky":
        base = f"{meta['emoji']} {meta['hook']}\n{title}\n{insight}\n{url}\n{tags}"
        if len(base) <= 300: return base
        fixed = f"{meta['emoji']} {meta['hook']}\n\n{url}\n{tags}"
        title_room = max(35, 300 - len(fixed) - 1)
        return f"{meta['emoji']} {meta['hook']}\n{trim(title,title_room)}\n{url}\n{tags}"
    if platform == "mastodon":
        base = f"{meta['emoji']} {meta['hook']}\n\n{title}\n\n{insight}\n\n{meta['question']}\n\n{url}\n\n{tags}\nBy Kushal K. Daga"
        if len(base) <= 500: return base
        fixed = f"{meta['emoji']} {meta['hook']}\n\n\n\n{meta['question']}\n\n{url}\n\n{tags}\nBy Kushal K. Daga"
        return fixed.replace("\n\n\n\n", "\n\n" + trim(title, max(45, 500-len(fixed))) + "\n\n")
    return f"{meta['emoji']} {meta['hook']}\n{title}\n{insight}\n{url}\n{tags}"


def tumblr_payload(item: dict, summary: str) -> dict:
    meta = creative_meta(item, "tumblr")
    title, url = clean(item.get("title", "Daily Yield")), item["url"]
    insight = first_sentence(summary, 360)
    tags = [x.lstrip("#") for x in hashtag_list(item)] + [meta["style"], "moneyblr"]
    return {
        "content": [
            {"type":"text", "text":f"{meta['emoji']} {meta['hook']}", "subtype":"heading1"},
            {"type":"text", "text":title, "subtype":"heading2"},
            {"type":"image", "media":[{"type":"image/jpeg","identifier":"daily-yield-card","width":1200,"height":630}], "alt_text":image_alt(item, "tumblr")},
            {"type":"text", "text":insight},
            {"type":"text", "text":meta["question"], "subtype":"quote"},
            {"type":"link", "url":url, "title":"Open the full Daily Yield story", "description":trim(title, 180)},
            {"type":"text", "text":"By Kushal K. Daga · clear numbers, useful context, zero finance-bro fog."},
        ],
        "state":"published", "tags":",".join(dict.fromkeys(tags)), "source_url":url,
        "send_to_twitter":False, "interactability_reblog":"everyone",
    }


def image_alt(item: dict, platform: str) -> str:
    meta = creative_meta(item, platform)
    return trim(f"Editorial photograph showing {_photo_alt(item)}. Daily Yield overlay: {meta['hook']}. Headline: {clean(item.get('title','Daily Yield'))}", 950)


def _font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        try: return ImageFont.truetype(path, size)
        except OSError: pass
    return ImageFont.load_default()


def _lines(draw, text: str, font, width: int, max_lines: int) -> list[str]:
    words, lines, current = clean(text).split(), [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if draw.textbbox((0,0), trial, font=font)[2] <= width: current = trial
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textbbox((0,0), lines[-1]+"…", font=font)[2] > width:
            lines[-1] = lines[-1].rsplit(" ",1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] = lines[-1].rstrip(".,:;-") + "…"
    return lines


def _allowed_photo_host(host: str) -> bool:
    host = host.lower()
    return host in PHOTO_HOSTS or host.endswith(".bp.blogspot.com")


def _photo_url(item: dict) -> str:
    """Use the hero embedded in authenticated Blogger content whenever possible."""
    for source in re.findall(r'<img\b[^>]+src=["\']([^"\']+)', item.get("content", ""), flags=re.I):
        source = html.unescape(source)
        if _allowed_photo_host(urlparse(source).hostname or ""): return source
    return ""


def _fallback_photo_urls(item: dict, platform: str) -> list[str]:
    pool = PHOTO_POOLS[topic(item)]
    start = creative_seed(item, platform) % len(pool)
    ordered = pool[start:] + pool[:start]
    return [f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1600&h=900&q=88" for photo_id in ordered]


def _photo_alt(item: dict) -> str:
    content = item.get("content", "")
    for match in re.finditer(r'<img\b[^>]*>', content, flags=re.I):
        tag = match.group(0)
        src = re.search(r'src=["\']([^"\']+)', tag, flags=re.I)
        alt = re.search(r'alt=["\']([^"\']+)', tag, flags=re.I)
        if src and _allowed_photo_host(urlparse(html.unescape(src.group(1))).hostname or "") and alt:
            value = clean(alt.group(1))
            if value: return value
    return PHOTO_ALT[topic(item)]


def _photo_credit(item: dict, url: str) -> str:
    match = re.search(r'<figcaption\b[^>]*>(.*?)</figcaption>', item.get("content", ""), flags=re.I | re.S)
    if match and _photo_url(item) == url:
        return trim(clean(match.group(1)), 95).upper()
    host = (urlparse(url).hostname or "").lower()
    if host == "images.unsplash.com": return "EDITORIAL PHOTO · UNSPLASH"
    if "wikimedia.org" in host: return "EDITORIAL PHOTO · WIKIMEDIA COMMONS"
    return "ARTICLE EDITORIAL PHOTOGRAPH"


def _download_photo(url: str) -> Image.Image:
    response = requests.get(url, timeout=(10,35), stream=True, headers={"User-Agent":"DailyYield-SocialCreative/3.0"})
    response.raise_for_status()
    chunks, total = [], 0
    for chunk in response.iter_content(128 * 1024):
        total += len(chunk)
        if total > 12 * 1024 * 1024:
            raise ValueError("editorial image exceeds 12 MB safety limit")
        chunks.append(chunk)
    return Image.open(BytesIO(b"".join(chunks))).convert("RGB")


def _photo(item: dict, platform: str) -> tuple[Image.Image, str]:
    article_photo = _photo_url(item)
    urls = ([article_photo] if article_photo else []) + _fallback_photo_urls(item, platform)
    errors = []
    for url in dict.fromkeys(urls):
        try:
            return _download_photo(url), url
        except Exception as exc:
            errors.append(f"{urlparse(url).hostname}: {exc}")
    # Fail closed: a social post must never regress to a banner-only graphic.
    raise RuntimeError("No licensed editorial photo could be loaded: " + " | ".join(errors))

def render_social_card(item: dict, platform: str, destination: Path, summary: str = "", image_format: str = "JPEG") -> Path:
    """Render a full-bleed editorial photograph with restrained magazine overlays."""
    meta = creative_meta(item, platform)
    palette = PALETTES[meta["style_index"]]
    source, photo_url = _photo(item, platform)
    canvas = ImageOps.fit(source, SIZE, Image.Resampling.LANCZOS)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.09)
    canvas = ImageEnhance.Color(canvas).enhance(0.94)

    # A cinematic gradient protects readability while leaving the photograph dominant.
    rgba = canvas.convert("RGBA")
    shade = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)
    for y in range(SIZE[1]):
        progress = y / (SIZE[1] - 1)
        alpha = int(12 + 210 * (progress ** 2.15))
        shade_draw.line((0, y, SIZE[0], y), fill=(5, 8, 15, alpha))
    rgba = Image.alpha_composite(rgba, shade)
    # Alternate a subtle side vignette so consecutive photographs have editorial variety.
    left_title = meta["layout"] in (0, 2, 4)
    side_shade = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    side_draw = ImageDraw.Draw(side_shade)
    for x in range(SIZE[0]):
        edge = (1 - x / SIZE[0]) if left_title else (x / SIZE[0])
        alpha = int(82 * (edge ** 2.5))
        side_draw.line((x, 0, x, SIZE[1]), fill=(5, 8, 15, alpha))
    rgba = Image.alpha_composite(rgba, side_shade)
    draw = ImageDraw.Draw(rgba)

    accent = palette["accent"]
    title = clean(item.get("title", "Daily Yield"))
    title_font = _font(51 if len(title) < 88 else 44, True)
    text_x = 66 if left_title else 430
    text_width = 1020 if left_title else 704
    lines = _lines(draw, title, title_font, text_width, 4)
    line_height = 59 if len(title) < 88 else 52
    title_y = 545 - line_height * len(lines)

    # Small translucent label—not a banner—then the photographic headline treatment.
    hook_font = _font(14, True)
    hook = meta["hook"]
    hook_w = draw.textbbox((0, 0), hook, font=hook_font)[2]
    draw.rounded_rectangle((text_x, title_y - 55, text_x + hook_w + 32, title_y - 20), radius=16, fill=(8, 10, 15, 185))
    draw.text((text_x + 16, title_y - 47), hook, font=hook_font, fill=accent)
    draw.rectangle((text_x, title_y - 8, text_x + 78, title_y - 2), fill=accent)
    for line in lines:
        # Minimal shadow keeps type readable on detailed photography.
        draw.text((text_x + 2, title_y + 3), line, font=title_font, fill=(0, 0, 0, 150))
        draw.text((text_x, title_y), line, font=title_font, fill="#FFFFFF")
        title_y += line_height

    # Compact masthead and source credit retain identity without covering the image.
    brand_font = _font(22, True)
    draw.text((66, 42), "DAILY YIELD", font=brand_font, fill="#FFFFFF")
    draw.text((66, 72), platform.upper() + " · PHOTO EDITION", font=_font(11, True), fill=(255, 255, 255, 205))
    credit = _photo_credit(item, photo_url)
    credit_font = _font(10, True)
    credit_w = draw.textbbox((0, 0), credit, font=credit_font)[2]
    draw.text((1140 - credit_w, 594), credit, font=credit_font, fill=(255, 255, 255, 190))

    destination.parent.mkdir(parents=True, exist_ok=True)
    final = rgba.convert("RGB")
    fmt = image_format.upper()
    if fmt == "PNG":
        final.save(destination, "PNG", optimize=True)
    else:
        quality = 89
        final.save(destination, "JPEG", quality=quality, optimize=True)
        while destination.stat().st_size > 950_000 and quality > 60:
            quality -= 7
            final.save(destination, "JPEG", quality=quality, optimize=True)
    return destination
