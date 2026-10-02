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

    def test_adaptive_navigation_warming_is_bounded_and_connection_aware(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("link.rel='prefetch'", text)
        self.assertIn("link.as='document'", text)
        self.assertIn("c&&c.saveData", text)
        self.assertIn("data-dy-prefetch-scope", text)
        self.assertIn("path==='/p/article.html'", text)
        self.assertIn("path==='/p/daily-news.html'", text)
        self.assertIn("path.indexOf('/search/label/')===0", text)
        self.assertIn("if(!scope)return", text)
        self.assertIn("limit=52", text)
        self.assertIn("DOMContentLoaded',function(){setTimeout(collect,0)", text)
        self.assertIn("requestIdleCallback(drain,{timeout:1800})", text)
        self.assertIn("data-dy-prefetched", text)
        self.assertNotIn("rel='prerender'", text)

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
