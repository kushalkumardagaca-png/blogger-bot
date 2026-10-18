"""An essential correction is not permission for a tracking/theme/bulk rewrite."""
from pathlib import Path
import unittest
from content_policy_guard import audit_text
from preapproval_audit import image_key
from preapproval_essential_corrections import (privacy_correction,dedupe_known_stock_em,OLD1,OLD2,OLD3,MARK)

class NarrowCorrectionTests(unittest.TestCase):
    def test_privacy_correction_requires_observed_tag(self):
        with self.assertRaises(RuntimeError):privacy_correction('<p>'+OLD1+'</p>',False)
    def test_privacy_changes_only_text_and_official_help_links(self):
        old='<style>same</style><h1>Privacy</h1><p>'+OLD1+'</p><p>'+OLD2+'</p><p>'+OLD3+'</p><script>same()</script>'
        new,changes=privacy_correction(old,True)
        self.assertTrue(changes);self.assertIn(MARK,new);self.assertIn('<script>same()</script>',new)
        for negative in (OLD1,OLD2,OLD3):self.assertNotIn(negative,new)
        self.assertEqual(privacy_correction(new,True),(new,[]))
    def test_only_extra_known_stock_em_is_removed(self):
        stock="Official releases are the primary record — the market's commentary will follow, this is the source."
        old='<h1>News</h1><p>Profit 100 in 2026.</p><em>'+stock+'</em><a href="https://example.com/source">Source</a><em>'+stock+'</em><script>value=2026</script>'
        new,removed=dedupe_known_stock_em(old)
        self.assertEqual(len(removed),1);self.assertEqual(new.count(stock),1)
        self.assertIn('Profit 100 in 2026.',new);self.assertIn('<a href="https://example.com/source">',new)
        self.assertIn('<script>value=2026</script>',new)
        self.assertEqual(dedupe_known_stock_em(new),(new,[]))
    def test_unrecognised_quotes_and_executable_strings_are_untouched(self):
        stock="Official releases are the primary record — the market's commentary will follow, this is the source."
        quote='<em>A source-specific statement about a bank and its latest reported quarterly performance.</em>'
        old='<script>var example="<em>'+stock+'</em><em>'+stock+'</em>";</script>'+quote+quote
        self.assertEqual(dedupe_known_stock_em(old),(old,[]))
    def test_numeric_or_linked_quotation_is_never_removed(self):
        old='<em><a href="https://example.com">Official releases are the primary record — the market\'s commentary will follow, this is the source.</a></em>'
        self.assertEqual(dedupe_known_stock_em(old+old),(old+old,[]))
    def test_encoded_news_id_is_not_an_affiliate_parameter(self):
        doc='<p>Reporting.</p><a href="https://news.google.com/rss/articles/CBMiaffidXYZ?oc=5">Source</a>'
        self.assertNotIn('undisclosed affiliate or commercial link',audit_text('News',doc))
        self.assertIn('undisclosed affiliate or commercial link',audit_text('News','<a href="https://example.com/?affid=123">Product</a>'))
    def test_functional_background_label_is_not_substantive_repetition(self):
        note='<p>It is separated from the current-period items so its date and role are clear.</p>'
        self.assertNotIn('repeated substantive sentence within the content',audit_text('News',note*3))
        claim='<p>The bank reduced the applicable mortgage interest rate after publishing its latest policy decision.</p>'
        self.assertIn('repeated substantive sentence within the content',audit_text('News',claim*2))
    def test_licence_match_uses_same_commons_file_not_just_a_trusted_host(self):
        a='https://thumb.wikimedia.org/wikipedia/commons/thumb/7/72/SBH_1955_Interiors.jpg/1280px-SBH_1955_Interiors.jpg?x=1'
        b='https://upload.wikimedia.org/wikipedia/commons/7/72/SBH_1955_Interiors.jpg?x=2'
        c='https://commons.wikimedia.org/wiki/File:SBH_1955_Interiors.jpg'
        self.assertEqual(image_key(a),image_key(b));self.assertEqual(image_key(a),image_key(c))
        self.assertNotEqual(image_key(a),image_key('https://upload.wikimedia.org/wikipedia/en/7/72/SBH_1955_Interiors.jpg'))

if __name__=='__main__':unittest.main()
