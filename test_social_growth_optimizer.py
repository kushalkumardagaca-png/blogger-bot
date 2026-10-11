import unittest
from social_growth_optimizer import build
class SocialGrowthOptimizerTests(unittest.TestCase):
 def test_sparse_data_does_not_overfit(self):
  items=[]
  for i in range(8):items.append({'platform':'bluesky','creative':{'topic':'saving','style_index':i%2,'layout':i%5,'hook':'A' if i%2 else 'B'},'published_at':'2026-10-11T10:00:00Z','metrics':{'likes':1 if i==0 else 0}})
  r=build({'items':items});self.assertNotIn('bluesky',r['recommendations']);self.assertEqual(r['syntheticViews'],0)
 def test_sufficient_evidence_creates_guarded_recommendation(self):
  items=[]
  for i in range(16):items.append({'platform':'mastodon','creative':{'topic':'market','style_index':1 if i<8 else 2,'layout':1 if i<8 else 2,'hook':'winner' if i<8 else 'other'},'published_at':'2026-10-11T10:00:00Z','metrics':{'favourites':1 if i<8 else 0}})
  r=build({'items':items});rec=r['recommendations']['mastodon']['market'];self.assertEqual(rec['style_index'],1);self.assertEqual(rec['layout'],1);self.assertEqual(rec['hook'],'winner');self.assertEqual(rec['explorationRate'],.2)
if __name__=='__main__':unittest.main()
