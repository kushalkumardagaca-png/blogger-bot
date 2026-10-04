import unittest

from page_family import SEO_END, SEO_START, ensure_page_meta


class PageFamilySeoTests(unittest.TestCase):
    def test_terms_receives_specific_repeat_safe_description(self):
        original = '<main><h1>Terms &amp; Conditions</h1></main>'
        once = ensure_page_meta(original, '/p/terms-and-conditions.html')
        twice = ensure_page_meta(once, '/p/terms-and-conditions.html')
        self.assertEqual(once, twice)
        self.assertEqual(once.count(SEO_START), 1)
        self.assertEqual(once.count(SEO_END), 1)
        self.assertIn('acceptable-use terms governing Daily Yield', once)
        self.assertIn(original, once)

    def test_existing_description_package_is_preserved(self):
        original = '<script>var metaDesc="Existing specific description";</script>'
        self.assertEqual(ensure_page_meta(original, '/p/terms-and-conditions.html'), original)


if __name__ == '__main__':
    unittest.main()
