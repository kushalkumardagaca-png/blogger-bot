from pathlib import Path


def test_authenticated_repair_writes_compact_exact_image_index():
    source = Path("content_experience_repair.py").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/content_experience_repair.yml").read_text(encoding="utf-8")
    assert "LABEL_INDEX=Path('LABEL_FEED_INDEX.json')" in source
    assert "def indexed_images(post):" in source
    assert "(?:thumb|upload)\\.wikimedia\\.org" in source
    assert "pairs={p['id']:indexed_images(p) for p in verified}" in source
    assert "'version':4" in source
    assert "'fallbacks':fallbacks" in source
    assert "separators=(',',':')" in source
    assert "LABEL_FEED_INDEX.json" in workflow
    assert "git add CONTENT_EXPERIENCE_REPAIR_STATUS.json LABEL_FEED_INDEX.json" in workflow


def test_theme_uses_summary_feeds_and_shared_image_index_for_fast_cards():
    text = Path("theme/Daily-Yield-Theme-Subscription.xml").read_text(encoding="utf-8")
    assert "var inlineIndex={\"version\":4,\"generated_at\":" in text
    assert "\"fallbacks\":{" in text
    assert "function asset(){return Promise.resolve(inlineIndex)}" in text
    assert "raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/LABEL_FEED_INDEX.json" not in text
    assert "/feeds/posts/summary/-/Kushal%20K.%20Daga?alt=json&max-results=16" in text
    assert "/feeds/posts/summary/-/News?alt=json&max-results=15" in text
    assert "'/feeds/posts/summary/-/'" in text
    assert "indexPromise=window.DYFeedCache.asset()" in text
    assert "fallbackIndex=x.fallbacks||{}" in text
    assert "data-dy-fallback" in text
    assert "data-dy-fallback-used" in text
    assert "window.__dyImageFallbacks=parts[1].fallbacks||{}" in text
    assert "/feeds/posts/default/-/News?alt=json&max-results=15" not in text


def test_post_images_recover_from_an_existing_photo_in_the_same_article():
    text = Path("theme/Daily-Yield-Theme-Subscription.xml").read_text(encoding="utf-8")
    assert "data-dy-image-recovered" in text
    assert "img.addEventListener('error',recover,{once:true})" in text
    assert "D.querySelectorAll('.item-post .post-body img')" in text
    assert "(?:thumb|upload)\\.wikimedia\\.org" in text


def test_below_fold_sections_are_deferred_without_visual_or_structural_removal():
    text = Path("theme/Daily-Yield-Theme-Subscription.xml").read_text(encoding="utf-8")
    assert ".item-post .dy2>section,.item-post .dy2>figure{content-visibility:auto" in text
    assert ".dya-desk,.dy-auth-desk{content-visibility:auto" in text
    assert ".dy-follow-popup" in text
