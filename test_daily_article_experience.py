import importlib
import json
import os

os.environ.setdefault("BLOGGER_BLOG_ID", "test-blog")
repair = importlib.import_module("content_experience_repair")


def sample_page():
    cfg = {
        "preview": True,
        "blog": "https://dailyyield.blogspot.com",
        "categories": [{"number": 1, "name": "Contrarian Hooks", "label": "Contrarian Hooks", "art": "fallback.jpg"}],
        "snapshotEntries": [],
    }
    content = f'''<main id="articleHub">
<script id="ar-config" type="application/json">{json.dumps(cfg)}</script>
<header class="ar-hero"><div class="ar-copy"><h1>Articles</h1></div><aside class="ar-note"><div class="ar-note-sheet">Note</div></aside></header>
<section class="ar-section"><div class="ar-rowtools"><span class="ar-rowcount"></span></div><div class="ar-viewport"></div></section>
<script>
function norm(v){{return v;}}
function inCategory(post,cat){{return post.labels.indexOf(cat.label)!==-1;}}
function card(post,cat){{var im={{}};im.alt='';im.loading='lazy';}}
var state={{viewport:viewport,group:group,duplicate:duplicate,hover:false,focus:false,touchUntil:0,visible:true}};
viewport.addEventListener('pointerdown',function(){{if(viewport._arState)viewport._arState.touchUntil=Date.now()+8000;}},{{passive:true}});
 viewport.addEventListener('wheel',function(){{if(viewport._arState)viewport._arState.touchUntil=Date.now()+5000;}},{{passive:true}});
function tick(dt,s){{if(!s.visible)return;var w=s.group.getBoundingClientRect().width;if(w<=s.viewport.clientWidth+1){{s.duplicate.hidden=true;return;}}s.duplicate.hidden=false;s.carry=(s.carry||0)+dt*24;}}
/* Authenticated snapshot is complete; no slower public-feed replacement. */
</script>
</main>'''
    return {"id": "page-1", "title": "DAILY ARTICLE", "content": content}, cfg


def test_article_repair_restores_horizontal_carousels_and_controls():
    page, cfg = sample_page()
    post = {"id": "post-1", "title": "A useful article", "url": "https://dailyyield.blogspot.com/2026/10/a.html", "published": "2026-10-04T00:00:00Z", "labels": ["Contrarian Hooks"], "content": '<img src="photo.jpg"><p>Useful context.</p>'}
    out = repair.repair_article_page(page, [post], cfg)
    assert "DAILY ARTICLE EXPERIENCE V7" in out
    assert "DY_ARTICLE_FEATURE_START" not in out
    assert "arNewsGrammar='7'" in out
    assert "#articleHub .ar-note{width:100%;max-width:370px" in out
    assert "#articleHub .ar-heading-copy{display:block!important;width:auto!important;margin:0!important;text-align:left!important}" in out
    assert "#articleHub .ar-heading h2" in out and "text-align:left!important" in out
    assert "#articleHub .ar-track{display:flex!important" in out
    assert "#articleHub .ar-group{display:flex!important" in out
    assert "#articleHub .ar-rowtools{display:flex!important" in out
    assert "#articleHub .ar-duplicate,#articleHub .ar-duplicate[hidden]{display:flex!important" in out
    assert "overflow-x:auto!important" in out
    assert "#articleHub .ar-group{display:grid!important" not in out
    assert "#articleHub .ar-viewport{overflow:visible!important" not in out


def test_article_repair_preserves_real_snapshot_excludes_news_and_improves_motion_alt():
    page, cfg = sample_page()
    posts = [
        {"id": "article-1", "title": "Real article", "url": "/real", "published": "2026-10-04T00:00:00Z", "labels": ["Contrarian Hooks"], "content": '<img src="real.jpg"><p>Original article.</p>'},
        {"id": "news-1", "title": "News item", "url": "/news", "published": "2026-10-04T01:00:00Z", "labels": ["News", "India"], "content": '<img src="news.jpg"><p>News.</p>'},
    ]
    out = repair.repair_article_page(page, posts, cfg)
    assert "article-1" in out
    assert "news-1" not in out
    assert "dt*58" in out
    assert "dt*24" not in out
    assert "s.active" in out
    assert "active:false" in out
    assert "Date.now()+32" in out
    assert "Date.now()+48" in out
    assert "Date.now()+8000" not in out
    assert "Date.now()+5000" not in out
    assert "s.hover||s.focus" not in out
    assert "duplicate.hidden=false" in out
    assert "w<=s.viewport.clientWidth" not in out
    assert "Daily Yield article photograph" in out


def test_article_repair_is_idempotent():
    page, cfg = sample_page()
    post = {"id": "post-1", "title": "A useful article", "url": "/a", "published": "2026-10-04T00:00:00Z", "labels": ["Contrarian Hooks"], "content": '<img src="photo.jpg"><p>Text.</p>'}
    once = repair.repair_article_page(page, [post], cfg)
    twice = repair.repair_article_page({**page, "content": once}, [post], cfg)
    assert twice.count(repair.START) == 1
    assert twice.count("DAILY ARTICLE EXPERIENCE V7") == 1
    assert "DY_ARTICLE_FEATURE_START" not in twice
