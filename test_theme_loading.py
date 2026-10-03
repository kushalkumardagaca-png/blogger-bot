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
        self.assertLess(len(text.encode("utf-8")), 310_000)

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

    def test_gapless_date_ordered_feed_and_compact_sections(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("className='dy-feed-sentinel'", text)
        self.assertIn("rootMargin:'1400px 0px'", text)
        self.assertIn("io.observe(sent);load()", text)
        self.assertIn("setTimeout(load,0)", text)
        self.assertIn("blog-pager-older-link", text)
        self.assertIn("function sortGrid()", text)
        self.assertIn("querySelector('time.published')", text)
        self.assertIn("var all=parse(j,false);", text)
        self.assertIn("Earlier articles", text)
        self.assertIn("grid-template-columns:repeat(5,minmax(0,1fr))!important", text)
        self.assertIn(".dy-sub-grid{grid-template-columns:1.05fr .95fr!important;min-height:0!important}", text)

    def test_homepage_uses_deep_summary_inventory_for_both_article_rows(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("function articleInventory()", text)
        self.assertIn("Promise.all([1,151]", text)
        self.assertIn("max-results=150&orderby=published&start-index=", text)
        self.assertIn("var items=all.slice(0,8)", text)
        self.assertIn("var earlier=all.slice(8,16)", text)
        self.assertIn("e.media$thumbnail&&e.media$thumbnail.url", text)
        self.assertIn("function hydrate(items)", text)
        self.assertIn("/feeds/posts/default/'+encodeURIComponent(it.id)+'?alt=json", text)
        self.assertIn("/feeds/posts/default/-/News?alt=json&max-results=15&orderby=published", text)
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
        self.assertIn("DY_AUTHENTICATED_NEWS_FALLBACK_V3", source)
        self.assertIn("rebuild('Global News'", source)
        self.assertIn("rebuild('Country dispatches'", source)
        self.assertIn("rebuild('Specialty desks'", source)
        self.assertIn("function wire(row)", source)
        self.assertIn("row.addEventListener('pointermove'", source)
        self.assertIn("row.addEventListener('lostpointercapture'", source)
        self.assertIn("if(e.pointerType==='mouse')hover=true", source)
        self.assertIn("delay(180)", source)
        self.assertIn("row.scrollLeft+=72*dt", source)
        self.assertIn("found.forEach(function(it){row.appendChild(makeCard(it));});wire(row)", source)
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


if __name__ == "__main__":
    unittest.main()
