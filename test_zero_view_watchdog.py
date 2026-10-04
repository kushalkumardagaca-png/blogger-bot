import re
import unittest

import zero_view_watchdog as watchdog


class ZeroViewWatchdogMarkupTests(unittest.TestCase):
    def test_executable_html_examples_are_not_document_elements(self):
        content = '''
        <main id="real"><h1>Daily Article</h1><a href="/p/article.html">Read</a>
        <img src="literal.jpg" alt="Literal article photograph"></main>
        <script>
        var template='<img src="runtime.jpg"><a href="https://example.com/runtime">runtime</a>';
        var parser=/<img[^>]+src=/;
        </script>
        '''
        markup = watchdog.literal_markup(content)
        self.assertEqual(watchdog.attrs(content, "img", "src"), ["literal.jpg"])
        self.assertEqual(watchdog.attrs(content, "a", "href"), ["/p/article.html"])
        self.assertNotIn("runtime.jpg", markup)
        self.assertEqual(watchdog.plain(content), "Daily Article Read")

    def test_script_only_missing_alt_is_not_an_accessibility_failure(self):
        content = '<img src="real.jpg" alt="Real description"><script>var x="<img src=\\"dynamic.jpg\\">";</script>'
        tags = re.findall(r'<img\b[^>]*>', watchdog.literal_markup(content), re.I)
        self.assertEqual(len(tags), 1)
        self.assertIn('alt="Real description"', tags[0])


if __name__ == "__main__":
    unittest.main()
