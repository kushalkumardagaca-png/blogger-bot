import importlib
import os

os.environ.setdefault("BLOGGER_BLOG_ID", "test-blog")
repair = importlib.import_module("content_experience_repair")


def cfg():
    return {
        "categories": [
            {"number": 1, "name": "Contrarian Hooks", "label": "Contrarian Hooks", "eyebrow": "Question the default", "description": "Test familiar assumptions.", "art": "fallback1.jpg"},
            {"number": 2, "name": "Cash Savings", "label": "Cash Savings", "eyebrow": "Build a buffer", "description": "Give cash a purpose.", "art": "fallback2.jpg"},
        ]
    }


def post(pid, title, label, news=False):
    labels = ["News", label] if news else [label, "Kushal K. Daga"]
    return {"id": pid, "title": title, "url": f"https://dailyyield.blogspot.com/2026/10/{pid}.html", "published": "2026-10-04T00:00:00Z", "labels": labels, "content": f'<img src="https://example.com/{pid}.jpg"><p>Useful article.</p>'}


def test_from_scratch_page_retains_no_legacy_article_application():
    posts = [post("a1", "A useful question", "Contrarian Hooks"), post("a2", "Cash first", "Cash Savings")]
    out = repair.repair_article_page({"content": "BROKEN LEGACY CONTENT"}, posts, cfg())
    assert repair.ARTICLE_SCRATCH_MARK in out
    assert 'id="dyArticle"' in out
    assert 'id="articleHub"' not in out
    assert "BROKEN LEGACY CONTENT" not in out
    assert "DAILY ARTICLE EXPERIENCE" not in out
    assert "Checking the shelves" not in out
    assert "/feeds/posts" not in out
    assert out.count('class="dya-desk"') == 2
    assert 'id="dya-1"' in out and 'id="dya-2"' in out


def test_static_real_cards_are_present_before_javascript_and_news_is_excluded():
    posts = [post("a1", "A useful question", "Contrarian Hooks"), post("a2", "Cash first", "Cash Savings"), post("n1", "Breaking news", "India", True)]
    out = repair.repair_article_page({"content": "ignored"}, posts, cfg())
    assert "A useful question" in out
    assert "Cash first" in out
    assert "Breaking news" not in out
    assert out.count('class="dya-card"') == 2
    assert "https://example.com/a1.jpg" in out
    assert "Daily Yield article photograph" in out


def test_clean_css_uses_descendant_selectors_and_mobile_card_widths():
    out = repair.repair_article_page({"content": "ignored"}, [post("a1", "Question", "Contrarian Hooks"), post("a2", "Cash", "Cash Savings")], cfg())
    assert "#dyArticle .dya-hero{" in out
    assert "#dyArticle .dya-card{" in out
    assert "#dyArticle.dya-hero" not in out
    assert "#dyArticle.dya-card" not in out
    assert "flex-basis:78vw" in out
    assert "text-align:left" in out


def test_news_motion_is_single_continuous_drag_engine():
    out = repair.repair_article_page({"content": "ignored"}, [post("a1", "Question", "Contrarian Hooks"), post("a2", "Cash", "Cash Savings")], cfg())
    assert out.count("function wire(row)") == 1
    assert "row.scrollLeft+=72*dt" in out
    assert "if(row.scrollLeft>=cycle)row.scrollLeft-=cycle" in out
    assert "row.setPointerCapture" in out
    assert "row.scrollLeft=drag.left-dx" in out
    assert "delay(180)" in out and "delay(900)" in out and "delay(250)" in out
    assert "requestAnimationFrame(frame)" in out


def test_rebuild_is_deterministic_and_has_page_family():
    posts = [post("a1", "Question", "Contrarian Hooks"), post("a2", "Cash", "Cash Savings")]
    once = repair.repair_article_page({"content": "first broken version"}, posts, cfg())
    twice = repair.repair_article_page({"content": once}, posts, cfg())
    assert once == twice
    assert once.count(repair.ARTICLE_SCRATCH_MARK) == 1
    assert once.count("DY_PAGE_FAMILY_START") == 1
