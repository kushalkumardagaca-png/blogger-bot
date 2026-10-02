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
PHOTO_HOSTS = ("images.unsplash.com", "upload.wikimedia.org")

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
    return trim(f"Daily Yield {meta['style']} editorial card. {meta['hook']}. Headline: {clean(item.get('title','Daily Yield'))}", 950)


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


def _photo_url(item: dict) -> str:
    for source in re.findall(r'<img\b[^>]+src=["\']([^"\']+)', item.get("content", ""), flags=re.I):
        source = html.unescape(source)
        host = (urlparse(source).hostname or "").lower()
        if host in PHOTO_HOSTS: return source
    return ""


def _photo(item: dict) -> Image.Image | None:
    url = _photo_url(item)
    if not url: return None
    try:
        response = requests.get(url, timeout=(10,35), stream=True, headers={"User-Agent":"DailyYield-SocialCreative/2.0"})
        response.raise_for_status()
        chunks, total = [], 0
        for chunk in response.iter_content(128 * 1024):
            total += len(chunk)
            if total > 12 * 1024 * 1024:
                raise ValueError("editorial image exceeds 12 MB safety limit")
            chunks.append(chunk)
        return Image.open(BytesIO(b"".join(chunks))).convert("RGB")
    except Exception as exc:
        print(f"Creative photo unavailable; using original graphic system: {exc}")
        return None


def render_social_card(item: dict, platform: str, destination: Path, summary: str = "", image_format: str = "JPEG") -> Path:
    meta = creative_meta(item, platform); palette = PALETTES[meta["style_index"]]
    canvas = Image.new("RGB", SIZE, palette["bg"]); draw = ImageDraw.Draw(canvas)
    seed, layout = int(meta["seed"],16), meta["layout"]
    photo = _photo(item)
    if photo:
        photo = ImageOps.fit(photo, (500,630), Image.Resampling.LANCZOS)
        photo = ImageEnhance.Contrast(photo).enhance(1.08)
        photo = photo.filter(ImageFilter.GaussianBlur(.15))
        photo = Image.blend(photo, Image.new("RGB", photo.size, palette["bg"]), 0.16)
        side = 0 if layout in (1,3) else 700
        canvas.paste(photo, (side, 0))
    # Grid, stickers and oversized index create variation without sacrificing legibility.
    if layout in (0,2,4):
        for x in range(0,1200,72): draw.line((x,0,x,630),fill=palette["muted"],width=1)
        for y in range(0,630,72): draw.line((0,y,1200,y),fill=palette["muted"],width=1)
    panel_x = 55 if layout != 1 else 430
    panel_w = 760 if layout in (0,3) else 690
    if layout == 4: panel_w = 840
    draw.rounded_rectangle((panel_x,45,panel_x+panel_w,585),radius=32,fill=palette["panel"],outline=palette["accent"],width=4)
    # Decorative sticker and issue marker.
    sticker_x = 915 if panel_x < 100 else 85
    draw.ellipse((sticker_x,55,sticker_x+190,245),fill=palette["accent"])
    draw.text((sticker_x+45,105),f"{seed%97+1:02d}",fill=palette["bg"],font=_font(56,True))
    draw.rounded_rectangle((panel_x+34,76,panel_x+360,120),radius=18,fill=palette["accent"])
    draw.text((panel_x+54,87),meta["hook"][:30],fill=palette["bg"],font=_font(15,True))
    title = clean(item.get("title","Daily Yield")); title_font=_font(49 if len(title)<90 else 42,True)
    lines=_lines(draw,title,title_font,panel_w-75,5); y=154
    for line in lines:
        draw.text((panel_x+38,y),line,fill=palette["panel_ink"],font=title_font);y+=58 if len(title)<90 else 51
    micro = first_sentence(summary or clean(item.get("content","")),105)
    if micro:
        draw.line((panel_x+38,500,panel_x+panel_w-38,500),fill=palette["accent"],width=4)
        micro_font = _font(16)
        micro_line = _lines(draw, micro, micro_font, panel_w-76, 1)[0]
        draw.text((panel_x+38,516),micro_line,fill=palette["panel_ink"],font=micro_font)
    # Brand is present but subordinate to the story and always outside its panel.
    brand_x = 960 if panel_x < 100 else 72
    draw.text((brand_x,510),"DAILY",fill=palette["ink"],font=_font(34,True));draw.text((brand_x,548),"YIELD",fill=palette["ink"],font=_font(34,True))
    draw.text((brand_x,590),platform.upper()+" EDITION",fill=palette["ink"],font=_font(13,True))
    deco_x = 840 if panel_x < 100 else 65
    for n,symbol in enumerate(("+","↗","₹","$")):
        x=deco_x+(n%2)*230;y0=280+(n//2)*100;draw.text((x,y0),symbol,fill=palette["accent"],font=_font(48,True))
    destination.parent.mkdir(parents=True,exist_ok=True)
    fmt=image_format.upper()
    if fmt=="PNG": canvas.save(destination,"PNG",optimize=True)
    else:
        quality=89;canvas.save(destination,"JPEG",quality=quality,optimize=True)
        while destination.stat().st_size>950_000 and quality>60:
            quality-=7;canvas.save(destination,"JPEG",quality=quality,optimize=True)
    return destination
