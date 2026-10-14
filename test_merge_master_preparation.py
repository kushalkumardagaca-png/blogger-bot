import unittest
from merge_master_preparation import merge_plan,merge_registry
class PreparationMergeTests(unittest.TestCase):
 def test_only_prepared_slot_overlays_concurrent_plan(self):
  cur={'date':'2026-10-11','trending':[{'id':'a'},{'id':'new1'},{'id':'old2'}],'evergreen':[]}
  inc={'date':'2026-10-11','trending':[{'id':'a'},{'id':'old1'},{'id':'new2'}],'evergreen':[]}
  out=merge_plan(cur,inc,{'kind':'trending','slot':2,'topic_id':'new2'})
  self.assertEqual([x['id'] for x in out['trending']],['a','new1','new2'])
 def test_registry_unions_photos_and_usages(self):
  a={'items':[{'sha256':'a','usages':[{'id':1}]}],'authenticated_items':1}
  b={'items':[{'sha256':'a','usages':[{'id':2}]},{'sha256':'b'}],'authenticated_items':2}
  out=merge_registry(a,b);self.assertEqual({x['sha256'] for x in out['items']},{'a','b'});self.assertEqual(len(out['items'][0]['usages']),2)
 def test_registry_rejects_concurrent_cross_article_photo_reuse(self):
  a={'items':[{'sha256':'same','source_id':'commons:1','article_key':'article-a'}]}
  b={'items':[{'sha256':'same','source_id':'commons:1','article_key':'article-b'}]}
  with self.assertRaisesRegex(RuntimeError,'concurrent photo conflict'):merge_registry(a,b)
 def test_historical_duplicate_snapshot_is_not_a_concurrent_addition(self):
  rows=[{'sha256':'one','source_id':'commons:legacy','article_key':'article-a'},
        {'sha256':'two','source_id':'commons:legacy','article_key':'article-b'}]
  out=merge_registry({'items':rows},{'items':rows+[{'sha256':'new','source_id':'commons:2','article_key':'article-c'}]})
  self.assertEqual({x['sha256'] for x in out['items']},{'one','two','new'})
if __name__=='__main__':unittest.main()
