import unittest
from merge_master_state import merge
class MergeMasterStateTests(unittest.TestCase):
 def test_concurrent_slots_survive_and_duplicate_topic_merges(self):
  a={'version':1,'published':[{'topic_id':'a','url':'u1','date':'2026-10-11'}]}
  b={'publication_enabled':True,'published':[{'topic_id':'b','url':'u2','date':'2026-10-11'},{'topic_id':'a','url':'u1','title':'updated','date':'2026-10-11'}]}
  out=merge(a,b,'published');self.assertEqual({x['topic_id'] for x in out['published']},{'a','b'});self.assertEqual(next(x for x in out['published'] if x['topic_id']=='a')['title'],'updated');self.assertTrue(out['publication_enabled'])
 def test_same_revalidated_topic_survives_on_distinct_dates(self):
  old={'published':[{'topic_id':'same','url':'old','date':'2026-10-11'}]}
  new={'published':[{'topic_id':'same','url':'new','date':'2026-10-14'}]}
  out=merge(old,new,'published')
  self.assertEqual([(x['date'],x['url']) for x in out['published']],[('2026-10-11','old'),('2026-10-14','new')])
if __name__=='__main__':unittest.main()
