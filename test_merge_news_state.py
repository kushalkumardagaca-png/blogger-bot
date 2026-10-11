import unittest
from merge_news_state import merge
class MergeNewsStateTests(unittest.TestCase):
 def test_concurrent_desks_and_latest_same_desk_survive(self):
  a={'desks':{'india':{'edition':'2026-10-11','window_end':'a'},'china':{'edition':'2026-10-10'}}}
  b={'desks':{'europe':{'edition':'2026-10-11'},'china':{'edition':'2026-10-11'}}}
  out=merge(a,b);self.assertEqual(set(out['desks']),{'india','china','europe'});self.assertEqual(out['desks']['china']['edition'],'2026-10-11')
if __name__=='__main__':unittest.main()
