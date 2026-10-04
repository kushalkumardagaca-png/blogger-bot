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
    content = f'''<style>.ar-heading-copy{{flex:1 1 430px;min-width:0;}}.ar-heading h2{{margin:0 0 12px;font-size:30px;}}</style><main id="articleHub">
<script id="ar-config" type="application/json">{json.dumps(cfg)}</script>
<header class="ar-hero"><div class="ar-copy"><h1>Good questions. Better <em>answers.</em></h1></div><aside class="ar-note"><div class="ar-note-sheet">Note</div></aside></header>
<section class="ar-section"><div class="ar-heading-copy"><h2>Contrarian Hooks</h2></div><div class="ar-rowtools"><span class="ar-rowcount"></span></div><div class="ar-viewport"></div></section>
<script>
function norm(v){{return v;}}
function inCategory(post,cat){{return post.labels.indexOf(cat.label)!==-1;}}
function card(post,cat){{var im={{}};im.alt='';im.loading='lazy';}}
requestAnimationFrame(function(){{try{{if(group.getBoundingClientRect().width<=viewport.clientWidth+1)duplicate.hidden=true;}}catch(e){{}}}});
document.querySelectorAll('.ar-viewport').forEach(function(v){{bind(v,null,0,false)}});
var last=0;
function tick(t){{var dt=1;rowStates.forEach(function(s){{s.viewport.scrollLeft+=dt*24;}});requestAnimationFrame(tick);}}requestAnimationFrame(tick);
/* Authenticated snapshot is complete; no slower public-feed replacement. */
</script>
</main>
<!-- DY_CONTENT_EXPERIENCE_REPAIR_START --><style>/* DAILY ARTICLE EXPERIENCE V7 */</style><!-- DY_CONTENT_EXPERIENCE_REPAIR_END -->'''
    return {"id": "page-1", "title": "DAILY ARTICLE", "content": content}, cfg


def post(pid="post-1", labels=None):
    return {"id": pid, "title": "A useful article", "url": "/a", "published": "2026-10-04T00:00:00Z", "labels": labels or ["Contrarian Hooks"], "content": '<img src="photo.jpg"><p>Useful context.</p>'}


def test_article_repair_removes_all_experience_overlays_and_preserves_authored_design():
    page, cfg = sample_page()
    out = repair.repair_article_page(page, [post()], cfg)
    assert "DAILY ARTICLE EXPERIENCE" not in out
    assert repair.START not in out
    assert "DY_ARTICLE_FEATURE_START" not in out
    assert '<header class="ar-hero">' in out
    assert 'class="ar-note"' in out
    assert '<em>answers.</em>' in out
    assert "display:grid!important" not in out
    assert "overflow:visible!important" not in out
    assert ".ar-heading-copy{flex:1 1 430px;min-width:0;text-align:left;}" in out
    assert ".ar-heading h2{margin:0 0 12px;text-align:left;" in out


def test_article_uses_daily_news_wire_motion_verbatim_behaviour():
    page, cfg = sample_page()
    out = repair.repair_article_page(page, [post()], cfg)
    assert out.count(repair.ARTICLE_SCROLL_START) == 1
    assert "view.scrollLeft+=72*dt" in out
    assert "if(view.scrollLeft>=half)view.scrollLeft-=half" in out
    assert "view.setPointerCapture" in out
    assert "view.scrollLeft=drag.left-dx" in out
    assert "delay(180)" in out
    assert "delay(900)" in out
    assert "delay(250)" in out
    assert "pointerenter" in out and "pointerleave" in out
    assert "Auto-scroll is supplied by the Daily News wire motion below." in out
    assert "dt*24" not in out
    assert "dt*58" not in out
    assert "bind(v,null,0,false)" not in out


def test_article_snapshot_excludes_news_and_repair_is_idempotent():
    page, cfg = sample_page()
    posts = [post("article-1"), post("news-1", ["News", "India"])]
    once = repair.repair_article_page(page, posts, cfg)
    twice = repair.repair_article_page({**page, "content": once}, posts, cfg)
    assert "article-1" in twice
    assert "news-1" not in twice
    assert twice.count(repair.ARTICLE_SCROLL_START) == 1
    assert twice.count(repair.ARTICLE_SCROLL_END) == 1
    assert "Daily Yield article photograph" in twice
