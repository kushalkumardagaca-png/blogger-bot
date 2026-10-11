import datetime as dt
import unittest
from collections import Counter
from social_rotation import (NEWS_KEYS,NEWS_PATTERN,DAILY_ARTICLE_KEYS,
 DAILY_PLATFORM_PAIRS,PLATFORMS,RESOURCE_DESTINATIONS,RESOURCE_SCHEDULES,
 platform_for,platform_pair_for,resource_destination,resource_url,make_plan)

class SocialRotationTests(unittest.TestCase):
 def test_exact_two_network_daily_distribution(self):
  pairs=[platform_pair_for(key) for key in DAILY_ARTICLE_KEYS]
  self.assertEqual(len(pairs),21);self.assertTrue(all(a!=b for a,b in pairs))
  self.assertEqual(Counter(x for pair in pairs for x in pair),{'facebook':13,'bluesky':11,'mastodon':10,'tumblr':8})
 def test_each_article_routes_to_two_distinct_networks(self):
  now=dt.datetime(2026,10,1,5,0,tzinfo=dt.timezone.utc);published=now.isoformat();url='https://dailyyield.blogspot.com/2026/10/india.html'
  first=make_plan('news-india',url,'post',published,'',now=now,route_index=0)
  second=make_plan('news-india',url,'post',published,'',now=now,route_index=1)
  self.assertNotEqual(first['platform'],second['platform']);self.assertEqual(first['delay_seconds'],240);self.assertEqual(second['delay_seconds'],240)
 def test_exactly_three_resource_posts_per_platform_daily(self):
  self.assertEqual(len(RESOURCE_SCHEDULES),12)
  self.assertEqual(Counter(platform for platform,_ in RESOURCE_SCHEDULES.values()),{p:3 for p in PLATFORMS})
  self.assertTrue(all({position for platform,position in RESOURCE_SCHEDULES.values() if platform==p}=={0,1,2} for p in PLATFORMS))
 def test_each_platform_rotates_all_requested_destinations(self):
  start=dt.date(2026,10,1);expected={row[0] for row in RESOURCE_DESTINATIONS}
  for platform in PLATFORMS:
   daily=[];week=set();previous=set()
   for offset in range(7):
    rows=[resource_destination(platform,pos,start+dt.timedelta(days=offset)) for pos in range(3)]
    keys={row[0] for row in rows}
    self.assertEqual(len(keys),3)
    if previous:self.assertTrue(keys.isdisjoint(previous))
    previous=keys;daily.extend(rows);week.update(keys)
   self.assertEqual(week,expected)
   self.assertEqual(Counter(row[0] for row in daily),{key:3 for key in expected})
 def test_scheduled_plan_uses_exact_platform_and_rotating_page(self):
  now=dt.datetime(2026,10,1,5,0,tzinfo=dt.timezone.utc)
  for cron,(platform,position) in RESOURCE_SCHEDULES.items():
   plan=make_plan('','','page','',cron,now=now)
   expected=resource_destination(platform,position,now.astimezone(dt.timezone(dt.timedelta(hours=5,minutes=30))).date())
   self.assertEqual(plan['platform'],platform);self.assertEqual(plan['target_url'],expected[2]);self.assertEqual(plan['resource_name'],expected[1])
 def test_rejects_non_official_destination(self):
  with self.assertRaises(ValueError):make_plan('news-india','https://example.com/story','post','','')
if __name__=='__main__':unittest.main()
