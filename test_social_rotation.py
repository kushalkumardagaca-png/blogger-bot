import datetime as dt
import unittest
from collections import Counter
from social_rotation import (NEWS_KEYS,NEWS_PATTERN,DAILY_ARTICLE_KEYS,
 DAILY_PLATFORM_PAIRS,PLATFORMS,RESOURCE_DESTINATIONS,RESOURCE_SCHEDULES,
 ROTATION_ANCHOR,rotate_platform,platform_for,platform_pair_for,resource_destination,resource_url,make_plan)

class SocialRotationTests(unittest.TestCase):
 def test_exact_two_network_daily_distribution(self):
  pairs=[platform_pair_for(key,ROTATION_ANCHOR) for key in DAILY_ARTICLE_KEYS]
  self.assertEqual(len(pairs),21);self.assertTrue(all(a!=b for a,b in pairs))
  # Tumblr left automation on 21 October 2026 and its eight slots were redistributed, so each live
  # network carries fourteen of the forty-two assignments: the per-article count never changed.
  self.assertEqual(Counter(x for pair in pairs for x in pair),{'facebook':14,'bluesky':14,'mastodon':14})
 def test_every_article_application_choice_rotates_each_day(self):
  for key in DAILY_ARTICLE_KEYS:
   routes=[platform_pair_for(key,ROTATION_ANCHOR+dt.timedelta(days=i)) for i in range(3)]
   self.assertEqual(len({pair[0] for pair in routes}),3)
   self.assertEqual(len({pair[1] for pair in routes}),3)
   self.assertTrue(all(a!=b for a,b in routes))
 def test_each_article_routes_to_two_distinct_networks(self):
  now=dt.datetime(2026,10,1,5,0,tzinfo=dt.timezone.utc);published=now.isoformat();url='https://dailyyield.blogspot.com/2026/10/india.html'
  first=make_plan('news-india',url,'post',published,'',now=now,route_index=0)
  second=make_plan('news-india',url,'post',published,'',now=now,route_index=1)
  self.assertNotEqual(first['platform'],second['platform']);self.assertEqual(first['delay_seconds'],240);self.assertEqual(second['delay_seconds'],240)
 def test_exactly_three_resource_posts_per_platform_daily(self):
  self.assertEqual(len(RESOURCE_SCHEDULES),12)
  # Twelve windows, four per live network: the three Tumblr held were reassigned, not dropped, so the
  # site still gets twelve resource promotions a day and no window had to move time.
  self.assertEqual(Counter(platform for platform,_ in RESOURCE_SCHEDULES.values()),{p:4 for p in PLATFORMS})
  self.assertTrue(all({position for platform,position in RESOURCE_SCHEDULES.values() if platform==p}=={0,1,2,3} for p in PLATFORMS))
 def test_page_application_choices_rotate_while_preserving_three_each(self):
  for offset in range(4):
   day=ROTATION_ANCHOR+dt.timedelta(days=offset)
   actual=[rotate_platform(platform,day) for platform,_ in RESOURCE_SCHEDULES.values()]
   self.assertEqual(Counter(actual),{p:4 for p in PLATFORMS})
  for platform,_ in RESOURCE_SCHEDULES.values():
   self.assertEqual(len({rotate_platform(platform,ROTATION_ANCHOR+dt.timedelta(days=i)) for i in range(3)}),3)
 def test_each_platform_rotates_all_requested_destinations(self):
  start=dt.date(2026,10,1);expected={row[0] for row in RESOURCE_DESTINATIONS}
  for platform in PLATFORMS:
   daily=[];week=set();previous=set()
   for offset in range(7):
    rows=[resource_destination(platform,pos,start+dt.timedelta(days=offset)) for pos in range(4)]
    keys={row[0] for row in rows}
    self.assertEqual(len(keys),4)
    # Four windows over seven destinations cannot be disjoint day to day - 4+4 is more than 7 - so the
    # rule is the gentlest true one: at most one page repeats from the previous day, and the whole week
    # covers every destination exactly four times. Dropping Tumblr's three windows instead would have
    # kept the old disjointness by promoting the site less.
    if previous:self.assertLessEqual(len(keys & previous),1)
    previous=keys;daily.extend(rows);week.update(keys)
   self.assertEqual(week,expected)
   self.assertEqual(Counter(row[0] for row in daily),{key:4 for key in expected})
 def test_scheduled_plan_uses_exact_platform_and_rotating_page(self):
  now=dt.datetime(2026,10,1,5,0,tzinfo=dt.timezone.utc)
  day=now.astimezone(dt.timezone(dt.timedelta(hours=5,minutes=30))).date()
  for cron,(base_platform,position) in RESOURCE_SCHEDULES.items():
   plan=make_plan('','','page','',cron,now=now)
   platform=rotate_platform(base_platform,day);expected=resource_destination(platform,position,day)
   self.assertEqual(plan['platform'],platform);self.assertEqual(plan['target_url'],expected[2]);self.assertEqual(plan['resource_name'],expected[1])
 def test_rejects_non_official_destination(self):
  with self.assertRaises(ValueError):make_plan('news-india','https://example.com/story','post','','')
if __name__=='__main__':unittest.main()
