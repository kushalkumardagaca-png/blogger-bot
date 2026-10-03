#!/usr/bin/env python3
"""Regression tests for varied, deterministic Daily Yield social creatives."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from social_creative import (
    PLATFORM_SIZES, _curated_entries, _photo_url, _semantic_theme, build_caption,
    creative_meta, image_alt, render_social_card, tumblr_payload,
)


def item(n=1, title=None, labels=None, kind="post"):
    return {
        "id": str(n), "kind": kind,
        "url": f"https://dailyyield.blogspot.com/2026/10/story-{n}.html" if kind == "post" else f"https://dailyyield.blogspot.com/p/tool-{n}.html",
        "title": title or f"Money decision {n}: the numbers, trade-offs and context that matter",
        "labels": labels or ["Personal Finance"],
        "content": "<p>A practical breakdown of the numbers, trade-offs and next questions, based on verifiable sources rather than hype.</p>",
    }


def test_authenticated_article_hero_is_selected_before_any_fallback():
    story = item(6)
    hero = "https://images.unsplash.com/photo-123?auto=format&fit=crop&w=900"
    story["content"] = f'<figure><img src="{hero}" alt="Editorial market photograph"></figure>'
    assert _photo_url(story) == hero
    story["content"] = '<img src="https://malicious.example/images.unsplash.com/photo.jpg">'
    assert _photo_url(story) == ""


def test_global_lifestyle_library_routes_explicit_real_life_subjects():
    cases = {
        "dogs": "The real cost of adopting a dog",
        "homes": "Should you rent or buy a home?",
        "banking": "What a bank interest-rate change means",
        "travel": "A budget for your next international trip",
        "shopping": "Why the grocery shop costs more",
        "technology": "The fintech app changing payments",
        "work": "How to negotiate your next salary",
        "family": "A practical family money plan",
    }
    for expected, title in cases.items():
        story = item(70, title, ["Personal Finance"])
        assert _semantic_theme(story, "facebook") == expected
        assert _curated_entries(story, "facebook")[0][1]


def test_signature_is_deterministic_and_platform_specific():
    story = item(7, "How inflation changes a monthly budget", ["Economy"])
    a = creative_meta(story, "facebook", "2026-10-02")
    assert a == creative_meta(story, "facebook", "2026-10-02")
    assert a != creative_meta(story, "bluesky", "2026-10-02")
    assert a != creative_meta(story, "facebook", "2026-10-03")


def test_caption_limits_platform_voice_and_cross_network_difference():
    story = item(8, "Credit card APR: what the minimum payment hides", ["Debt", "Personal Finance"])
    captions = {p: build_caption(story, p, "A clear look at compounding interest and repayment choices.") for p in ("facebook", "bluesky", "mastodon")}
    assert len(captions["bluesky"]) <= 300
    assert len(captions["mastodon"]) <= 500
    assert len(set(captions.values())) == 3
    assert all(story["url"] in text and "#DailyYield" in text for text in captions.values())
    assert all("Read the report" not in text and "Clear context" not in text for text in captions.values())
    assert all("A clear look at compounding interest" in text for text in captions.values())
    assert "?" in captions["facebook"] and "?" in captions["mastodon"]


def test_many_stories_do_not_collapse_to_one_template_or_caption():
    stories = [item(n, labels=[["Markets"], ["Debt"], ["Tax"], ["Economy"], ["News"]][n % 5]) for n in range(1, 51)]
    metas = [creative_meta(story, "facebook", "2026-10-02") for story in stories]
    assert len({m["style"] for m in metas}) >= 8
    assert len({m["layout"] for m in metas}) == 5
    captions = [build_caption(story, "facebook", "Useful source-based context for the decision.") for story in stories]
    assert len(captions) == len(set(captions))


def test_tumblr_is_native_npf_with_conversation_and_descriptive_alt():
    story = item(22, "A tax deduction checklist without the jargon", ["Tax"])
    data = tumblr_payload(story, "A practical checklist for keeping the right records and asking better questions.")
    block_types = [block["type"] for block in data["content"]]
    assert block_types == ["text", "text", "image", "text", "text", "link", "text"]
    assert data["content"][4]["subtype"] == "quote"
    assert story["url"] == data["source_url"] == data["content"][5]["url"]
    assert "Editorial photograph" in data["content"][2]["alt_text"]
    assert "moneyblr" in data["tags"]


def test_cards_are_photo_first_accessible_sized_and_visually_distinct():
    story = item(31, "Gold, rates and the market mood: what to watch", ["Markets"])
    # Keep the unit test offline while exercising the full photographic compositor.
    photo = Image.new("RGB", (1600, 900), "#31546b")
    photo_draw = ImageDraw.Draw(photo)
    for x in range(0, 1600, 80):
        photo_draw.rectangle((x, 180 + x // 8, x + 55, 900), fill=(45 + x % 150, 85, 110))
    with patch("social_creative._photo", return_value=(photo, "https://images.unsplash.com/test")):
        with TemporaryDirectory() as temp:
            paths = []
            for platform in ("facebook", "bluesky", "tumblr", "mastodon"):
                path = Path(temp) / f"{platform}.jpg"
                render_social_card(story, platform, path, "A compact guide to the signals and limits behind today's market move.")
                paths.append(path)
                with Image.open(path) as image:
                    assert image.size == PLATFORM_SIZES[platform]
                assert path.stat().st_size < 1_000_000
                alt = image_alt(story, platform)
                assert story["title"] in alt and "Editorial photograph" in alt
            with Image.open(paths[0]) as first, Image.open(paths[1]) as second:
                assert ImageChops.difference(first.convert("RGB"), second.convert("RGB")).getbbox() is not None
