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
        self.assertIn("class='dy-load-chart'", text)
        self.assertIn("class='dy-load-coin'", text)
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

    def test_real_two_second_budget_is_recorded_not_fabricated(self):
        text = THEMES[0].read_text(encoding="utf-8")
        self.assertIn("data-dy-complete-ms", text)
        self.assertIn("data-dy-two-second-budget", text)
        self.assertIn("ms<=2000?'met':'miss'", text)
        self.assertNotIn("animation:pageIn", text)


if __name__ == "__main__":
    unittest.main()
