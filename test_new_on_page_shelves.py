import importlib
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("BLOGGER_BLOG_ID", "test-blog")
repair = importlib.import_module("content_experience_repair")


def config():
    return {"categories": [{"number": 1, "name": "Test Desk", "label": "Test Desk", "eyebrow": "Test", "description": "A desk.", "art": "fallback.jpg"}]}


def article(pid, hours):
    return {"id": pid, "title": f"Article {pid}", "url": f"/{pid}", "published": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(), "labels": ["Test Desk", "Kushal K. Daga"], "content": f'<img src="https://example.com/{pid}.jpg">'}


def news(pid, hours):
    return {"id": pid, "title": f"News {pid}", "url": f"/{pid}", "published": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(), "labels": ["News", "US"], "content": f'<img src="https://example.com/{pid}.jpg">'}


def test_article_page_has_first_recent_shelf_and_only_recent_article_cards():
    out = repair.build_article_page([article("fresh", 2), article("old", 30)], config())
    assert "NEW ON THE PAGE" in out
    assert "A ROLLING 24-HOUR WINDOW" in out
    shelf = out.split('id="dya-new"', 1)[1].split('id="dya-1"', 1)[0]
    assert "Article fresh" in shelf
    assert "Article old" not in shelf
    assert out.index('id="dya-new"') < out.index('id="dya-1"')
    assert "age>86400000" in out


def test_article_recent_shelf_remains_visible_when_empty():
    out = repair.build_article_page([article("old", 30)], config())
    assert "NEW ON THE PAGE" in out
    assert "No new articles were published in the last 24 hours" in out


def test_news_fallback_builds_exact_rolling_24_hour_shelf_before_desks():
    out = repair.news_static_fallback([repair.news_item(news("fresh", 2)), repair.news_item(news("old", 30))])
    assert "NEW ON THE PAGE" in out
    assert "age<=86400000" in out
    assert "recentShelf(g||a||b)" in out
    assert "PUBLISHED IN THE LAST 24 HOURS" in out
    assert "dy-auth-recent" in out
    assert "wire(row)" in out
