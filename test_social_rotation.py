import datetime as dt
import unittest
from collections import Counter
from social_rotation import (HEADER_PAGES,NEWS_KEYS,NEWS_PATTERN,DAILY_ARTICLE_KEYS,
 DAILY_PLATFORM_PAIRS,platform_for,platform_pair_for,resource_url,make_plan)

class SocialRotationTests(unittest.TestCase):
 def test_exact_two_network_daily_distribution(self):
  pairs=[platform_pair_for(key) for key in DAILY_ARTICLE_KEYS]
  self.assertEqual(len(pairs),21);self.assertTrue(all(a!=b for a,b in pairs))
  self.assertEqual(Counter(x for pair in pairs for x in pair),{'facebook':13,'bluesky':11,'mastodon':10,'tumblr':8})
 def test_each_article_routes_to_two_distinct_networks(self):
  now=dt.datetime(2026,10,1,5,0,tzinfo=dt.timezone.utc);published=now.isoformat();url='https://dailyyield.blogspot.com/2026/10/india.html'
  first=make_plan('news-india',url,'post',published,'',now=now,route_index=0)
  second=make_plan('news-india',url,'post',published,'',now=now,route_index=1)
  self.assertNotEqual(first['platform'],second['platform']);self.assertEqual(first['delay_seconds'],300);self.assertEqual(second['delay_seconds'],300)
 def test_resources_retain_established_rotation(self):
  day=dt.date(2026,10,1);resources=[f'resource-{i}' for i in range(5)]
  today=[platform_for(k,day) for k in resources];tomorrow=[platform_for(k,day+dt.timedelta(days=1)) for k in resources]
  self.assertNotEqual(today,tomorrow);self.assertEqual(len(today),5)
 def test_homepage_plus_four_distinct_rotating_header_pages(self):
  day=dt.date(2026,10,1);urls=[resource_url(i,day) for i in range(5)]
  self.assertEqual(urls[0],'https://dailyyield.blogspot.com/');self.assertEqual(len(set(urls)),5);self.assertTrue(set(urls[1:]).issubset(set(HEADER_PAGES)))
 def test_rejects_non_official_destination(self):
  with self.assertRaises(ValueError):make_plan('news-india','https://example.com/story','post','','')
if __name__=='__main__':unittest.main()
