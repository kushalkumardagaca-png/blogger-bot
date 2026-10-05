import unittest

from page_family import SEO_END, SEO_START, ensure_page_meta, family_block
from repair_family_directory import canonicalize, verify_content


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

    def test_family_directory_preserves_descendant_selector_spaces(self):
        block = family_block('')
        required = (
            '#dyPageFamily .dyf-grid', '#dyPageFamily .dyf-card',
            '#dyPageFamily .dyf-card strong', '#dyPageFamily .dyf-social-links a',
        )
        for selector in required:
            self.assertIn(selector, block)
            self.assertNotIn(selector.replace(' ', ''), block)

    def test_corrupted_family_directory_is_replaced_without_touching_article(self):
        article = '<article><h1>Preserve this exact article</h1><p>Reader content.</p></article>'
        corrupted = family_block('').replace('#dyPageFamily .dyf-card', '#dyPageFamily.dyf-card')
        repaired = canonicalize(article + corrupted)
        self.assertTrue(repaired.startswith(article))
        self.assertEqual(verify_content(repaired), [])
        self.assertEqual(canonicalize(repaired), repaired)


if __name__ == '__main__':
    unittest.main()
