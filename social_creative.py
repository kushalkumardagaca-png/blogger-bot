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
PLATFORM_SIZES = {
    # Taller native feed assets earn more useful screen space without increasing
    # posting frequency. Bluesky retains a wide link-friendly treatment.
    "facebook": (1080, 1350),
    "tumblr": (1080, 1350),
    "mastodon": (1080, 1080),
    "bluesky": (1200, 675),
}
PHOTO_HOSTS = ("images.unsplash.com", "upload.wikimedia.org", "thumb.wikimedia.org", "blogger.googleusercontent.com")

# A broad, verified Unsplash editorial library: people and real life first, with
# homes, pets, banks, work, technology, shops, travel and cities worldwide.
PHOTO_LIBRARY = {
    "people": (
        ("photo-1521737604893-d14cc237f11d", "a diverse young team collaborating"),
        ("photo-1529156069898-49953e39b3ac", "friends sharing a candid moment outdoors"),
        ("photo-1494790108377-be9c29b29330", "a confident young woman in natural light"),
        ("photo-1500648767791-00dcc994a43e", "a young man in a candid portrait"),
        ("photo-1524504388940-b1c1722653e1", "a young woman in a bright editorial portrait"),
        ("photo-1531482615713-2afd69097998", "young professionals collaborating at work"),
    ),
    "family": (
        ("photo-1511895426328-dc8714191300", "a family spending time together at home"),
        ("photo-1506869640319-fe1a24fd76dc", "friends enjoying time together"),
        ("photo-1522202176988-66273c2fd55f", "young people learning and working together"),
    ),
    "pets": (
        ("photo-1517849845537-4d257902454a", "a cheerful dog outdoors"),
        ("photo-1514888286974-6c03e2ca1dba", "a cat in a vivid close-up portrait"),
        ("photo-1601758228041-f3b2795255f1", "a person relaxing with a pet"),
    ),
    "dogs": (
        ("photo-1517849845537-4d257902454a", "a cheerful dog outdoors"),
        ("photo-1552053831-71594a27632d", "a dog looking toward the camera"),
        ("photo-1558788353-f76d92427f16", "a playful dog in natural light"),
    ),
    "cats": (
        ("photo-1514888286974-6c03e2ca1dba", "a cat in a vivid close-up portrait"),
        ("photo-1573865526739-10659fec78a5", "a curious cat in natural light"),
        ("photo-1495360010541-f48722b34f7d", "a relaxed cat at home"),
    ),
    "homes": (
        ("photo-1600585154340-be6161a56a0c", "a contemporary home surrounded by greenery"),
        ("photo-1564013799919-ab600027ffc6", "a welcoming modern family home"),
        ("photo-1600607687939-ce8a6c25118c", "a bright modern home interior"),
    ),
    "banking": (
        ("photo-1541354329998-f4d9a9f9297f", "a monumental bank and civic building"),
        ("photo-1486406146926-c627a92ad1ab", "a global banking and business district"),
        ("photo-1556742049-0cfed4f6a45d", "a person making a digital payment"),
        ("photo-1556740749-887f6717d7e4", "a customer using modern payment technology"),
    ),
    "work": (
        ("photo-1517245386807-bb43f82c33c4", "a creative team working together"),
        ("photo-1497366754035-f200968a6e72", "a bright contemporary workplace"),
        ("photo-1556761175-b413da4baf72", "colleagues in a modern meeting"),
        ("photo-1526304640581-d334cdbbf45e", "a person reviewing money and plans at a desk"),
    ),
    "technology": (
        ("photo-1516321318423-f06f85e504b3", "a laptop and connected digital workspace"),
        ("photo-1518770660439-4636190af475", "technology hardware in a vivid close-up"),
        ("photo-1534723328310-e82dad3ee43f", "a modern digital technology workspace"),
    ),
    "shopping": (
        ("photo-1441986300917-64674bd600d8", "a lively contemporary retail store"),
        ("photo-1556742049-0cfed4f6a45d", "a person completing a cashless purchase"),
        ("photo-1556740749-887f6717d7e4", "a bright modern checkout experience"),
    ),
    "travel": (
        ("photo-1500530855697-b586d89ba3ee", "a person exploring a beautiful landscape"),
        ("photo-1539635278303-d4002c07eae3", "friends travelling through a dramatic landscape"),
        ("photo-1488646953014-85cb44e25828", "a traveller beginning a global journey"),
    ),
    "global": (
        ("photo-1493976040374-85c8e12f0c0e", "Tokyo city life and architecture"),
        ("photo-1502602898657-3e91760cbb34", "Paris and its international cityscape"),
        ("photo-1506973035872-a4ec16b8e8d9", "Sydney harbour and its global skyline"),
        ("photo-1494522855154-9297ac14b55f", "a vibrant Asian financial-city skyline"),
        ("photo-1469571486292-0ba58a3f068b", "people moving through a global city"),
    ),
}
TOPIC_THEMES = {
    "market": ("people", "banking", "technology", "global", "work"),
    "debt": ("people", "banking", "homes", "family", "work"),
    "tax": ("people", "work", "banking", "homes"),
    "saving": ("people", "family", "pets", "homes", "travel", "shopping"),
    "economy": ("people", "global", "banking", "shopping", "work"),
    "news": ("global", "people", "banking", "work", "travel"),
    "page": ("technology", "people", "global", "work"),
    "general": tuple(PHOTO_LIBRARY),
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
    "page": ("A PRACTICAL MONEY RESOURCE", "SAVE FOR YOUR NEXT DECISION", "USE THE TOOL, CHECK THE ASSUMPTIONS", "A USEFUL DAILY YIELD RESOURCE"),
    "news": ("WHAT CHANGED — AND WHAT DID NOT", "THE SOURCE-LED UPDATE", "CURRENT REPORTS, CLEARLY DATED", "THE NEWS BEHIND THE HEADLINE"),
    "market": ("PRICE IS NOT THE WHOLE STORY", "READ THE RISK BEFORE THE RETURN", "WHAT THE NUMBERS CAN SUPPORT", "CONTEXT BEFORE A MARKET DECISION"),
    "debt": ("START WITH THE EFFECTIVE COST", "PUT THE REPAYMENT MATH ON PAPER", "COMPARE THE RATE AND THE CASH BUFFER", "A DEBT DECISION WITH VISIBLE NUMBERS"),
    "tax": ("CHECK THE COUNTRY AND TAX YEAR", "ELIGIBILITY BEFORE THE TAX SAVING", "KEEP THE RECORD, VERIFY THE RULE", "SEPARATE TAX MATH FROM TAX LAW"),
    "saving": ("MAKE THE NEXT STEP MEASURABLE", "TEST THE PLAN WITH REAL CASH FLOW", "SMALL CONTRIBUTIONS, VISIBLE ASSUMPTIONS", "BUILD MARGIN BEFORE CHASING RETURN"),
    "economy": ("CONNECT THE DATA TO THE DECISION", "WHAT THE RELEASE ACTUALLY SAYS", "MACRO DATA WITH LIMITS ATTACHED", "THE HOUSEHOLD QUESTION BEHIND THE NUMBER"),
    "general": ("ONE DECISION, CLEAR ASSUMPTIONS", "CHECK THE DOWNSIDE, NOT JUST THE CLAIM", "A PRACTICAL WAY TO TEST THE IDEA", "PUT THE TRADE-OFFS ON ONE PAGE"),
}

EMOJIS = ("🧾", "📊", "🧠", "⚡", "🔎", "📌", "🧮", "🌐")
QUESTIONS = {
    "market": ("Which assumption would change your view?", "What downside would make this unsuitable for you?"),
    "debt": ("Which balance has the highest effective cost?", "How much cash buffer must the plan preserve?"),
    "tax": ("Which official rule and tax year apply to you?", "What record would you need to support the claim?"),
    "saving": ("What amount can you sustain in a difficult month?", "Which assumption should you stress-test first?"),
    "news": ("Which linked source deserves a closer read?", "Does this report change a decision—or only the context?"),
    "page": ("Which decision will you use this resource for?", "What useful tool should Daily Yield improve next?"),
    "economy": ("Which household decision could this number affect?", "What comparison period would make this clearer?"),
    "general": ("Which number would decide this for you?", "What evidence would make you choose differently?"),
}


def clean(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value or "", flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def topic(item: dict) -> str:
    text = (item.get("title", "") + " " + " ".join(str(x) for x in item.get("labels", []))).lower()
    if item.get("kind") == "page": return "page"
    # Canonical News labels choose the creative treatment while publication
    # timing and one-platform routing remain unchanged.
    if "markets, crypto & commodities" in text: return "market"
    if "economy, trade & jobs" in text: return "economy"
    if "banking, fintech & personal money" in text: return "saving"
    if "companies, ipos & deals" in text: return "general"
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
    content_type = "Source-led news edition" if meta["topic"] == "news" else "Practical decision guide"
    if platform == "facebook":
        details = (
            "Includes visible assumptions, downside analysis and source links.",
            "Use the worked example, then replace it with your own figures.",
            "Read the limitations before applying the conclusion.",
            "A concise framework for testing the decision with real numbers.",
        )
        detail = details[(creative_seed(item, platform) // 41) % len(details)]
        return f"{url}\n\n{title}\n\n{meta['emoji']} {insight}\n{content_type}. {detail}\n\nBy Kushal K. Daga\n{tags}"
    if platform == "bluesky":
        fixed = f"{url}\n\n\n\nBy Kushal K. Daga\n{tags}"
        room = 300 - len(fixed)
        short_title = trim(title, max(35, min(len(title), room // 2)))
        remaining = max(0, 300 - len(fixed) - len(short_title) - 1)
        short_detail = trim(insight, remaining) if remaining >= 25 else ""
        parts = [url, "", short_title]
        if short_detail: parts.extend([short_detail])
        parts.extend(["By Kushal K. Daga", tags])
        return "\n".join(parts)[:300]
    if platform == "mastodon":
        base = f"{url}\n\n{title}\n\n{meta['emoji']} {insight}\n{content_type}.\n\nBy Kushal K. Daga\n{tags}"
        if len(base) <= 500: return base
        fixed = f"{url}\n\n\n\n{content_type}.\n\nBy Kushal K. Daga\n{tags}"
        return fixed.replace("\n\n\n\n", "\n\n" + trim(title, max(45, 500-len(fixed))) + "\n\n")
    return f"{url}\n\n{title}\n{insight}\nBy Kushal K. Daga\n{tags}"


def tumblr_payload(item: dict, summary: str) -> dict:
    meta = creative_meta(item, "tumblr")
    title, url = clean(item.get("title", "Daily Yield")), item["url"]
    insight = first_sentence(summary, 360)
    tags = [x.lstrip("#") for x in hashtag_list(item)] + ["moneyblr"]
    return {
        "content": [
            {"type":"link", "url":url, "title":"Read on Daily Yield", "description":trim(title, 180)},
            {"type":"text", "text":title, "subtype":"heading1"},
            {"type":"image", "media":[{"type":"image/jpeg","identifier":"daily-yield-card","width":PLATFORM_SIZES["tumblr"][0],"height":PLATFORM_SIZES["tumblr"][1]}], "alt_text":image_alt(item, "tumblr")},
            {"type":"text", "text":insight},
            {"type":"text", "text":"By Kushal K. Daga · sourced financial education with visible assumptions and limitations."},
        ],
        "state":"published", "tags":",".join(dict.fromkeys(tags)), "source_url":url,
        "send_to_twitter":False, "interactability_reblog":"everyone",
    }


def image_alt(item: dict, platform: str) -> str:
    meta = creative_meta(item, platform)
    return trim(f"Editorial photograph showing {_photo_alt(item, platform)}. Daily Yield overlay: {meta['hook']}. Headline: {clean(item.get('title','Daily Yield'))}", 950)


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


def _semantic_theme(item: dict, platform: str) -> str:
    text = (item.get("title", "") + " " + " ".join(str(x) for x in item.get("labels", []))).lower()
    explicit = (
        ("dogs", ("dog", "puppy", "canine")),
        ("cats", ("cat", "kitten", "feline")),
        ("pets", ("pet", "animal", "veterinary")),
        ("homes", ("home", "house", "housing", "mortgage", "rent", "property", "real estate")),
        ("family", ("family", "parent", "child", "couple", "wedding", "baby")),
        ("travel", ("travel", "trip", "holiday", "vacation", "flight", "tourism")),
        ("shopping", ("shop", "retail", "grocery", "spending", "consumer", "purchase")),
        ("technology", ("ai", "fintech", "digital", "technology", "crypto", "app")),
        ("global", ("global", "world", "international", "country", "countries", "overseas")),
        ("banking", ("bank", "loan", "credit", "interest rate", "payment", "deposit")),
        ("work", ("career", "salary", "job", "office", "business", "company", "startup")),
    )
    for theme, words in explicit:
        if any(word in text for word in words): return theme
    themes = TOPIC_THEMES[topic(item)]
    return themes[(creative_seed(item, platform) // 53) % len(themes)]


def _curated_entries(item: dict, platform: str) -> list[tuple[str, str]]:
    theme = _semantic_theme(item, platform)
    primary = list(PHOTO_LIBRARY[theme])
    # A second relevant lane gives network retries alternatives without showing
    # the same narrow finance cliché repeatedly.
    lanes = TOPIC_THEMES[topic(item)]
    secondary_theme = lanes[(lanes.index(theme) + 1) % len(lanes)] if theme in lanes else lanes[0]
    secondary = list(PHOTO_LIBRARY[secondary_theme])
    seed = creative_seed(item, platform)
    first = seed % len(primary)
    second = (seed // 101) % len(secondary)
    # Always lead with the semantically selected lane; secondary photos exist
    # only as network-failure fallbacks.
    return primary[first:] + primary[:first] + secondary[second:] + secondary[:second]


def _fallback_photo_urls(item: dict, platform: str) -> list[str]:
    width, height = PLATFORM_SIZES.get(platform, SIZE)
    # Request the intended aspect ratio from the licensed source instead of
    # taking a narrow centre crop from the same landscape asset everywhere.
    request_width = max(1200, width)
    request_height = round(request_width * height / width)
    return [f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w={request_width}&h={request_height}&q=88" for photo_id, _ in _curated_entries(item, platform)]


def _article_photo_alt(item: dict) -> str:
    content = item.get("content", "")
    for match in re.finditer(r'<img\b[^>]*>', content, flags=re.I):
        tag = match.group(0)
        src = re.search(r'src=["\']([^"\']+)', tag, flags=re.I)
        alt = re.search(r'alt=["\']([^"\']+)', tag, flags=re.I)
        if src and _allowed_photo_host(urlparse(html.unescape(src.group(1))).hostname or "") and alt:
            value = clean(alt.group(1))
            if value: return value
    return "the article's editorial scene"


def _photo_alt(item: dict, platform: str) -> str:
    article_photo = _photo_url(item)
    # One quarter reuse the article hero; the rest expand into a much broader,
    # context-aware global lifestyle library.
    if article_photo and creative_seed(item, platform) % 4 == 0:
        return _article_photo_alt(item)
    return _curated_entries(item, platform)[0][1]


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
    curated = _fallback_photo_urls(item, platform)
    # Reuse some article heroes, but deliberately rotate most posts through the
    # broader people/life/world collection so feeds never become one visual genre.
    if article_photo and creative_seed(item, platform) % 4 == 0:
        urls = [article_photo] + curated
    else:
        urls = curated + ([article_photo] if article_photo else [])
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
    size = PLATFORM_SIZES.get(platform, SIZE)
    width, height = size
    sx, sy = width / 1200, height / 630
    canvas = ImageOps.fit(source, size, Image.Resampling.LANCZOS)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.04)
    canvas = ImageEnhance.Color(canvas).enhance(1.14)
    canvas = ImageEnhance.Brightness(canvas).enhance(1.03)

    # A light lower-third gradient protects readability without muting the photo.
    rgba = canvas.convert("RGBA")
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)
    for y in range(height):
        progress = y / (height - 1)
        alpha = int(3 + 145 * (progress ** 3.0))
        shade_draw.line((0, y, SIZE[0], y), fill=(5, 8, 15, alpha))
    rgba = Image.alpha_composite(rgba, shade)
    # Alternate a subtle side vignette so consecutive photographs have editorial variety.
    left_title = meta["layout"] in (0, 2, 4)
    side_shade = Image.new("RGBA", size, (0, 0, 0, 0))
    side_draw = ImageDraw.Draw(side_shade)
    for x in range(width):
        edge = (1 - x / width) if left_title else (x / width)
        alpha = int(32 * (edge ** 2.8))
        side_draw.line((x, 0, x, height), fill=(5, 8, 15, alpha))
    rgba = Image.alpha_composite(rgba, side_shade)
    draw = ImageDraw.Draw(rgba)

    accent = palette["accent"]
    title = clean(item.get("title", "Daily Yield"))
    font_scale = max(.82, min(1.08, sx))
    title_font = _font(int((40 if len(title) < 88 else 34) * font_scale), True)
    text_x = int((58 if left_title else 448) * sx)
    text_width = int((1080 if left_title else 690) * sx)
    lines = _lines(draw, title, title_font, text_width, 3)
    line_height = int((47 if len(title) < 88 else 41) * font_scale)
    title_y = int(height * .87) - line_height * len(lines)

    # A concise decision hook gives the image meaning without using clickbait.
    hook_font = _font(max(12, int(15 * font_scale)), True)
    hook = meta["hook"]
    hook_w = draw.textbbox((0, 0), hook, font=hook_font)[2]
    hook_top = title_y - int(53 * font_scale)
    hook_bottom = title_y - int(17 * font_scale)
    draw.rounded_rectangle((text_x, hook_top, text_x + hook_w + int(34 * font_scale), hook_bottom), radius=int(18 * font_scale), fill=accent)
    draw.text((text_x + int(17 * font_scale), title_y - int(45 * font_scale)), hook, font=hook_font, fill="#11151F")
    for line in lines:
        draw.text((text_x, title_y), line, font=title_font, fill="#FFFFFF", stroke_width=2, stroke_fill=(0, 0, 0, 155))
        title_y += line_height

    # Compact masthead and source credit retain identity without covering the image.
    brand_font = _font(max(15, int(18 * font_scale)), True)
    draw.text((int(58*sx), int(36*sy)), "DAILY YIELD", font=brand_font, fill="#FFFFFF", stroke_width=1, stroke_fill=(0,0,0,125))
    draw.text((int(58*sx), int(61*sy)), platform.upper(), font=_font(max(9, int(10*font_scale)), True), fill=(255, 255, 255, 225))
    credit = _photo_credit(item, photo_url)
    credit_font = _font(max(9, int(10 * font_scale)), True)
    credit_w = draw.textbbox((0, 0), credit, font=credit_font)[2]
    draw.text((width - int(60*sx) - credit_w, height - int(36*sy)), credit, font=credit_font, fill=(255, 255, 255, 190))

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
