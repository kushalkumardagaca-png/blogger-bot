import json,re,unittest
from pathlib import Path
from followup_archive_review import REVIEW,all_item_spans,review_content,verify_reference
from followup_image_review import correct_figures
from licence_evidence import rights_record_complete
from source_photography import photographic_candidate,source_alt
from news_pipeline import obviously_nonfinancial

class ArchiveFollowupTests(unittest.TestCase):
    def test_exact_nine_targets_and_46_reviewed_removals(self):
        self.assertEqual(len(REVIEW),9);self.assertEqual(sum(len(x['drop']) for x in REVIEW.values()),46)
    def test_background_and_nested_items_are_not_skipped(self):
        h='<script>var s="<div class=fbk-item>not markup</div>";</script><div class="fbk-item"><div>Inner</div></div><div class="fbk-item fbk-bg">Background</div>'
        spans=all_item_spans(h);self.assertEqual(len(spans),2);self.assertIn('fbk-bg',h[spans[1]['start']:spans[1]['end']])
    def fixture(self):
        items=[]
        for i in range(1,16):items.append(f'<div class="fbk-item"><h3>Source topic {i}</h3><p>Source publisher {i} gives a separate attributed topic for this historical listing.</p><a class="fbk-src" href="https://example.com/{i}">Source</a></div>')
        items.append('<div class="fbk-item"><h3>EUR/USD 1.1403 · EUR/GBP 0.8605 · EUR/JPY 179.7000 · EUR/CNY 7.6551 · EUR/INR 109.2605 · EUR/BRL 5.9091</h3><p>Old last-close wording.</p><a class="fbk-src" href="https://www.ecb.europa.eu/">ECB</a></div>')
        return '<h1>US Finance News — 27 September 2026</h1><style>old</style><p class="fbk-lede">15 current items.</p><p class="fbk-note">Old note.</p>'+''.join(items)+'<script>sameLogic()</script><script type="application/ld+json">{"@type":"NewsArticle","headline":"Old","datePublished":"2026-09-27T01:00:00Z","dateModified":"old","description":"Old"}</script>'
    def rates(self):return {'2026-09-25':{'USD':'1.1403','GBP':'0.86045','JPY':'179.7','CNY':'7.6551','INR':'109.2605','BRL':'5.9091'}}
    def test_prose_correction_preserves_code_and_original_publication(self):
        before=self.fixture();after,result=review_content('9051696550888128467',before,self.rates())
        self.assertIn('<script>sameLogic()</script>',after);self.assertIn('<style>old</style>',after)
        self.assertIn('2026-09-27T01:00:00Z',after);self.assertNotIn('15 current items.',after)
        self.assertEqual(result['referenceDate'],'2026-09-25')
        self.assertEqual(review_content('9051696550888128467',after,self.rates())[0],after)
    def test_historical_rates_cannot_be_faked_to_pass(self):
        broken=self.fixture().replace('EUR/USD 1.1403','EUR/USD 9.9999')
        with self.assertRaisesRegex(ValueError,'differs'):review_content('9051696550888128467',broken,self.rates())
    def test_clear_ambiguous_word_false_positives_are_not_finance(self):
        for title in ['Giant pandas arrive under a new loan deal','North and South Korea trade accusations over landmines','Minister calls for war in occupied West Bank','Half of Europe witnessed record heat stress']:
            self.assertTrue(obviously_nonfinancial({'title':title}),title)
        for title in ['West Bank businesses receive new credit funding','Panda loan agreement includes million-dollar annual fees','European shares rise as bond yields fall','Heat stress raises insurance costs']:
            self.assertFalse(obviously_nonfinancial({'title':title}),title)

class ImageFollowupTests(unittest.TestCase):
    def record(self):return {'url':'https://raw.githubusercontent.com/example/verified.jpg','actual_subject_verified':True,'actual_subject':'A bank building','creator':'Named photographer','license':'CC BY 4.0','license_url':'https://creativecommons.org/licenses/by/4.0/','source_page':'https://commons.wikimedia.org/wiki/File:Bank.jpg'}
    def test_slot_count_and_financial_prose_are_preserved(self):
        old='<h1>Article</h1><style>same</style><p>Reported profit was 123 in 2026.</p><figure class="same"><img src="https://example.com/old.jpg" alt="Wrong brief" width="1600" height="900"><figcaption>Old credit.</figcaption></figure><script>var hero="https://example.com/old.jpg";sameLogic()</script>'
        new,changes=correct_figures(old,[{'oldSrc':'https://example.com/old.jpg','newPhoto':self.record()}])
        self.assertEqual(new.count('<img'),1);self.assertIn('Reported profit was 123 in 2026.',new)
        self.assertIn('<style>same</style>',new);self.assertIn('sameLogic()',new);self.assertNotIn('Wrong brief',new)
        self.assertIn('Named photographer',new);self.assertEqual(len(changes),1)
    def test_a_different_figure_cannot_be_edited(self):
        with self.assertRaisesRegex(ValueError,'not found'):correct_figures('<figure><img src="https://example.com/other.jpg"></figure>',[{'oldSrc':'https://example.com/old.jpg','newPhoto':self.record()}])
    def test_missing_creator_is_not_a_fake_credit(self):
        photo=self.record();photo['creator']=None;photo['provider']='Unsplash';photo['license']='Unsplash License';photo['license_url']='https://unsplash.com/license'
        old='<figure><img src="https://example.com/old.jpg"><figcaption>Old</figcaption></figure>'
        new,_=correct_figures(old,[{'oldSrc':'https://example.com/old.jpg','newPhoto':photo}])
        self.assertNotIn('Photo: None',new);self.assertIn('creator not identified',new)
    def test_attribution_waiver_needs_primary_verified_terms(self):
        r={'license':'Public domain','license_url':'https://creativecommons.org/publicdomain/mark/1.0/','source_page':'https://commons.wikimedia.org/wiki/File:Old.jpg','creator':None}
        self.assertFalse(rights_record_complete(r))
        r.update(licence_terms_verified=True,asset_verified=True,attribution_required=False,source_reuse_basis='primary_public_domain_declaration')
        self.assertTrue(rights_record_complete(r))
        r['source_page']='https://random.example/';self.assertFalse(rights_record_complete(r))
    def test_standard_unsplash_is_not_a_plus_grant(self):
        r={'license':'Unsplash License','license_url':'https://unsplash.com/license','source_page':'https://images.unsplash.com/photo-123-abc?fm=json','original_url':'https://images.unsplash.com/photo-123-abc','creator':None,'licence_terms_verified':True,'asset_verified':True,'attribution_required':False,'source_reuse_basis':'standard_unsplash_provider_license','assetMetadataSha256':'verified-metadata'}
        self.assertTrue(rights_record_complete(r));r['original_url']='https://plus.unsplash.com/premium_photo-123-abc';self.assertFalse(rights_record_complete(r))
    def test_source_alt_never_invents_the_requested_scene(self):
        r={'alt':'Modern financiers in a boardroom','source_page':'https://commons.wikimedia.org/wiki/File:Historic_Cemetery.jpg'}
        self.assertNotIn('boardroom',source_alt(r));self.assertIn('Historic Cemetery',source_alt(r))
    def test_videos_and_documents_are_not_photographs(self):
        for ext in ['webm','pdf','svg','ogg']:
            self.assertFalse(photographic_candidate({'original_url':'https://example.com/file.'+ext,'title':'Office context'}))
    def test_metaphorical_painting_is_not_an_artwork_medium(self):
        r={'original_url':'https://example.com/factory.jpg','title':'Factory workers','description':'Workers are painting aircraft; this project is painting a vision of the future.'}
        self.assertTrue(photographic_candidate(r));r['description']='Medium: wood engraving on paper.';self.assertFalse(photographic_candidate(r))
    def test_review_scope_and_image_number_are_bounded(self):
        p=json.loads(Path('FOLLOWUP_IMAGE_CORRECTION_PLAN.json').read_text());self.assertEqual(len(p['patches']),44)
        self.assertEqual(sum(x['changeImage'] for x in p['patches']),24)
        self.assertEqual(len({x['newPhoto']['url'] for x in p['patches'] if x['changeImage']}),24)

if __name__=='__main__':unittest.main()

class AttributionNoticeTests(unittest.TestCase):
    def test_functional_image_notice_is_not_financial_analysis(self):
        from content_policy_guard import audit_text
        notice='<figcaption>Used as an illustration, not as evidence of the particular people, organisation or event discussed.</figcaption>'
        self.assertNotIn('repeated substantive sentence within the content',audit_text('Article',notice*2))
        financial='<p>The bank reduced the applicable mortgage interest rate after publishing its latest policy decision.</p>'
        self.assertIn('repeated substantive sentence within the content',audit_text('Article',financial*2))
        harmful='<figcaption>We offer guaranteed profits for every investor buying this product.</figcaption>'
        self.assertIn('deceptive financial or commercial promise',audit_text('Article',harmful))

class PreparedPoolMediaTests(unittest.TestCase):
    def test_pool_does_not_reintroduce_document_or_video_thumbnails(self):
        import photo_library as pool
        base={'title':'Office financial context','description':'Commercial context','width':1800,'height':1000}
        self.assertFalse(pool.subject_ok({**base,'original_url':'https://upload.wikimedia.org/source.pdf'}))
        self.assertFalse(pool.subject_ok({**base,'original_url':'https://upload.wikimedia.org/source.webm'}))
        self.assertTrue(pool.subject_ok({**base,'original_url':'https://upload.wikimedia.org/source.jpg'}))
