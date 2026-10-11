import unittest
from merge_master_state import merge
class MergeMasterStateTests(unittest.TestCase):
 def test_concurrent_slots_survive_and_duplicate_topic_merges(self):
  a={'version':1,'published':[{'topic_id':'a','url':'u1','date':'2026-10-11'}]}
  b={'publication_enabled':True,'published':[{'topic_id':'b','url':'u2','date':'2026-10-11'},{'topic_id':'a','url':'u1','title':'updated','date':'2026-10-11'}]}
  out=merge(a,b,'published');self.assertEqual({x['topic_id'] for x in out['published']},{'a','b'});self.assertEqual(next(x for x in out['published'] if x['topic_id']=='a')['title'],'updated');self.assertTrue(out['publication_enabled'])
if __name__=='__main__':unittest.main()
