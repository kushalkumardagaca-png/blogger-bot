import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


THEMES = [
    Path("theme/Daily-Yield-Theme-v4-2026-10-01.xml"),
    Path("theme/Daily-Yield-Theme-Subscription.xml"),
]


class ThemeLoadingTests(unittest.TestCase):
    def test_themes_are_valid_xml_with_one_loader(self):
        for path in THEMES:
            ET.parse(path)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("DY_FINANCE_LOADER_START"), 1)
            self.assertEqual(text.count("id='dyPageLoader'"), 1)
            self.assertEqual(text.count("DY_SITE_ENHANCEMENTS_JS_START"), 1)

    def test_finance_loader_is_full_screen_and_dependency_free(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("position:fixed;inset:0", text)
        self.assertIn("class='dy-symbol-field'", text)
        self.assertIn("class='dy-sticker-field'", text)
        self.assertIn("class='dy-load-ring'", text)
        self.assertEqual(text.count("class='dy-sticker'"), 24)
        loader = text.split("DY_FINANCE_LOADER_START", 1)[1].split("DY_FINANCE_LOADER_END", 1)[0]
        self.assertGreaterEqual(loader.count("<span>"), 112)
        self.assertNotIn("fonts.googleapis.com", text)
        self.assertNotIn("fonts.gstatic.com", text)
        self.assertNotIn("data:image/png;base64", text)
        import gzip
        self.assertLess(len(gzip.compress(text.encode("utf-8"), compresslevel=9)), 110_000)

    def test_all_internal_link_directions_are_intercepted_safely(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("D.addEventListener('click'", text)
        self.assertIn("/^dailyyield\\.blogspot\\./i", text)
        self.assertIn("location.assign(u.href)", text)
        self.assertIn("a.target==='_blank'", text)
        self.assertIn("a.hasAttribute('download')", text)

    def test_loader_releases_at_dom_ready_with_accessible_fallbacks(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("DOMContentLoaded',ready", text)
        self.assertIn("setTimeout(ready,1800)", text)
        self.assertIn("prefers-reduced-motion:reduce", text)
        self.assertIn("<noscript><style>#dyPageLoader{display:none!important}</style></noscript>", text)

    def test_loader_has_lightweight_soft_entry_and_exit(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("@keyframes dyLoaderFadeIn{from{opacity:0}to{opacity:1}}", text)
        self.assertIn("transition:opacity .24s ease-out", text)
        self.assertIn("Math.max(0,300-(clock-start))", text)
        self.assertIn("location.assign(u.href);},260)", text)
        self.assertIn("contain:strict", text)
        self.assertNotIn("dyCardEnter", text)
        self.assertNotIn("dyStickersEnter", text)
        self.assertNotIn(".dy-sticker{animation:", text)

    def test_every_label_uses_feed_only_infinite_loading_and_compact_sections(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("blog-pager-older-link", text)
        self.assertIn("className='dy-label-status'", text)
        self.assertIn("data-dy-label-feed','feed-json-infinite'", text)
        self.assertIn("'/feeds/posts/summary/-/'", text)
        self.assertIn("indexPromise=window.DYFeedCache.asset()", text)
        self.assertIn("src=imageIndex[entryId(e)]", text)
        self.assertIn("rootMargin:'700px 0px'", text)
        self.assertIn("max-results='+batch+'&start-index='+start", text)
        self.assertIn("className='dy-country-filter'", text)
        self.assertIn("countrySets={'Global Finance News':allCountries", text)
        self.assertIn("path.map(encodeURIComponent).join('/')", text)
        self.assertIn("grid-template-columns:1fr!important", text)
        self.assertNotIn("fetch(href,{credentials:'same-origin'})", text)
        self.assertIn("var all=parse(j,false);", text)
        self.assertIn("Earlier articles", text)
        self.assertIn("grid-template-columns:repeat(5,minmax(0,1fr))!important", text)
        self.assertIn("class='dy-follow-button'", text)
        self.assertIn("class='dy-follow-popup'", text)
        self.assertIn("https://www.blogger.com/followers/follow/8911514070006792465", text)
        self.assertIn("/^\\/\\d{4}\\/\\d{2}\\/[^/]+\\.html$/.test(location.pathname)", text)
        self.assertIn("progress>=.20", text)
        self.assertIn("dy-google-follow-intent-v1", text)
        self.assertIn("localStorage.setItem(key,'followed')", text)
        self.assertIn("!H.classList.contains('dy-privacy-lock')", text)
        self.assertNotIn("https://api.follow.it/subscribe", text)
        self.assertNotIn("dy-sub-form", text)
        self.assertIn(".kd-eg-row{position:relative;display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))", text)
        self.assertIn(".kd-eg-icon{width:52px;height:52px", text)
        self.assertIn(".kd-eg-icon svg{display:block!important;width:26px!important;height:26px!important", text)

    def test_homepage_uses_one_lightweight_author_feed_and_exact_image_index(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("function articleInventory()", text)
        self.assertIn("/feeds/posts/summary/-/Kushal%20K.%20Daga?alt=json&max-results=16", text)
        self.assertIn("window.DYFeedCache.asset()", text)
        self.assertIn("window.__dyImageIndex=parts[1].images||{}", text)
        self.assertIn("exact=(window.__dyImageIndex||{})[pid]", text)
        self.assertIn("var items=all.slice(0,8)", text)
        self.assertIn("var earlier=all.slice(8,16)", text)
        self.assertIn("function hydrate(items)", text)
        self.assertIn("items.filter(function(it){return !it.img&&it.id;})", text)
        self.assertIn("src=[\"']([^\"']+)[\"']", text)
        self.assertIn("/feeds/posts/default/'+encodeURIComponent(it.id)+'?alt=json", text)
        self.assertIn("/feeds/posts/summary/-/News?alt=json&max-results=15&orderby=published", text)
        self.assertNotIn("/feeds/posts/default/-/News?alt=json&max-results=15", text)
        self.assertNotIn("/feeds/posts/default?alt=json&max-results=25", text)

    def test_mobile_document_is_contained_while_rows_remain_scrollable(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("html,body{max-width:100%;overflow-x:clip}", text)
        self.assertIn(".kd-row,.kd-mqwrap{overflow-x:auto;overscroll-behavior-inline:contain}", text)

    def test_duplicate_default_post_grid_is_hidden_only_on_homepage(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn(".fk-home #Blog1 .blog-posts,.fk-home #blog-pager{display:none!important}", text)
        self.assertNotIn(".fk-rest #Blog1 .blog-posts{display:none", text)
        self.assertNotIn("#Blog1 .blog-posts{display:none!important}", text.replace(".fk-home #Blog1 .blog-posts{display:none!important}", ""))

    def test_news_snapshot_precedes_renderer_and_ready_main_is_deferred(self):
        source = Path("content_experience_repair.py").read_text(encoding="utf-8")
        self.assertIn("c=c[:script_start]+snap+c[script_start:]", source)
        self.assertIn("news_snapshot_at<news_engine_at", source)
        self.assertIn("else{setTimeout(main,0);}", source)
        self.assertIn("DY_AUTHENTICATED_NEWS_FALLBACK_V6_OVERSIZED_LATEST_CARDS", source)
        self.assertIn("function buildShelf(spec,kicker,forced)", source)
        self.assertIn("function buildOrderedShelves(regionAnchor,subjectAnchor)", source)
        self.assertIn("buildOrderedShelves(a,b)", source)
        self.assertLess(source.index("desks.topics.forEach"), source.index("desks.regions.slice(1).forEach"))
        self.assertNotIn("countrySelector(a||b)", source)
        self.assertIn("function wire(row)", source)
        self.assertIn("row.addEventListener('pointermove'", source)
        self.assertIn("row.addEventListener('lostpointercapture'", source)
        self.assertIn("if(e.pointerType==='mouse')hover=true", source)
        self.assertIn("delay(180)", source)
        self.assertIn("row.scrollLeft+=72*dt", source)
        self.assertIn("found.forEach(function(it){row.appendChild(makeCard(it));})", source)
        self.assertIn(".slice(0,8)", source)
        self.assertNotIn("flags=re.S)+snap", source)

    def test_non_home_rotating_rows_resume_after_every_input_mode(self):
        source = Path("continuous_motion.py").read_text(encoding="utf-8")
        self.assertIn("classList.contains('fk-home'))return", source)
        self.assertEqual(source.count(",72,true)"), 5)
        self.assertIn("pointerup',end", source)
        self.assertIn("pointercancel',end", source)
        self.assertIn("lostpointercapture',end", source)
        self.assertIn("addEventListener('blur',end)", source)
        self.assertIn("if(e.pointerType==='mouse')hover=true", source)
        self.assertIn("delay(180)", source)
        self.assertIn("Date.now()>pausedUntil", source)
        workflow = Path(".github/workflows/motion_related_retrofit.yml").read_text(encoding="utf-8")
        self.assertIn("github.event_name == 'push' && 'true'", workflow)

    def test_navigation_creates_no_speculative_document_requests(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("data-dy-navigation-policy','reader-navigation-only'", text)
        self.assertIn("data-dy-synthetic-document-requests','0'", text)
        self.assertNotIn("link.rel='prefetch'", text)
        self.assertNotIn("link.as='document'", text)
        self.assertNotIn("rel='prerender'", text)
        self.assertNotIn("data-dy-prefetched", text)
        self.assertNotIn("requestIdleCallback(drain", text)

    def test_safe_accelerator_caches_only_feed_data_and_assets(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("data-dy-safe-accelerator','feed-and-assets-only'", text)
        self.assertIn("/^\\/feeds\\//.test(u.pathname)", text)
        self.assertIn("document requests prohibited", text)
        self.assertIn("sessionStorage.setItem(key", text)
        self.assertIn("window.DYFeedCache.get('/feeds/posts/summary", text)
        self.assertIn("/feeds/posts/summary/-/News?alt=json&max-results=15", text)
        self.assertIn("window.DYFeedCache.asset()", text)
        self.assertIn("img.decode()", text)
        self.assertNotIn("DYFeedCache.get('/p/", text)
        self.assertNotIn("DYFeedCache.get('/search/", text)

    def test_cookie_dialog_is_centered_and_repeats_on_first_and_every_fifth_page(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("left:50%;top:50%", text)
        self.assertIn("backdrop-filter:blur(16px)", text)
        self.assertIn("A more useful Daily Yield", text)
        self.assertIn("Choose how we improve your experience", text)
        self.assertIn("Allow all cookies", text)
        self.assertIn("Remind me later", text)
        self.assertIn("dy-privacy-lock body::after", text)
        self.assertIn("backdrop-filter:blur(15px)", text)
        self.assertIn("if(mustChoose||(savedConsent!=='all'&&scheduled))setPrivacyOpen(true)", text)
        self.assertIn("mustChoose=savedConsent!=='all'&&savedConsent!=='essential'", text)
        self.assertIn("min-height:68px", text)
        self.assertIn("button:not(.dy-primary){min-height:34px;padding:8px;background:transparent;border:0", text)
        self.assertIn("Close and use essential cookies only", text)
        self.assertIn("privacyPage===1||privacyPage%5===0", text)
        self.assertIn("dy-privacy-session-v1", text)
        self.assertIn("delete x.tabs[tab]", text)
        self.assertIn("analytics_storage:allow?'granted':'denied'", text)
        self.assertIn("ad_personalization:allow?'granted':'denied'", text)

    def test_noncritical_comment_engine_is_loaded_during_idle_time(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("DY_LAZY_COMMENT_LOADER_START", text)
        self.assertIn("requestIdleCallback(load,{timeout:1800})", text)
        self.assertNotIn("<script src='https://www.blogger.com/static", text)

    def test_real_two_second_budget_is_recorded_not_fabricated(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("data-dy-complete-ms", text)
        self.assertIn("data-dy-two-second-budget", text)
        self.assertIn("ms<=2000?'met':'miss'", text)
        self.assertNotIn("animation:pageIn", text)

    def test_real_user_vitals_are_consented_and_not_pageviews(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("data-dy-rum-policy','consent-only-non-pageview'", text)
        self.assertIn("largest-contentful-paint", text)
        self.assertIn("layout-shift", text)
        self.assertIn("durationThreshold:40", text)
        self.assertIn("safeGet('dy-consent')==='all'", text)
        self.assertIn("gtag('event','dy_web_vitals'", text)
        self.assertIn("non_interaction:true", text)
        self.assertNotIn("gtag('event','page_view'", text)


if __name__ == "__main__":
    unittest.main()
