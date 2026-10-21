import datetime as dt
import unittest
from collections import Counter
from publication_timing import NEWS_LIVE,MASTER_LIVE
from social_rotation import RESOURCE_SCHEDULES,PLATFORMS


def minute(value):
 h,m=map(int,value.split(':'));return h*60+m

def ist_minute_from_cron(cron):
 m,h,*_=map(int,cron.split()[:2]);return (h*60+m+330)%1440

class ScheduleCadenceTests(unittest.TestCase):
 def test_articles_preserve_reader_windows_and_six_hour_night_gap(self):
  values=sorted([minute(x) for x in NEWS_LIVE.values()]+[minute(x) for x in MASTER_LIVE.values()])
  self.assertEqual(len(values),21)
  gaps=[b-a for a,b in zip(values,values[1:])]+[1440-values[-1]+values[0]]
  self.assertEqual(Counter(gaps),Counter({60:14,30:5,90:1,360:1}))
  self.assertEqual(values[0],minute('04:15'));self.assertEqual(values[-1],minute('22:15'))
  self.assertLessEqual(max(gaps[:-1]),90)
 def test_page_promotions_cover_global_reader_windows(self):
  values=sorted(ist_minute_from_cron(x) for x in RESOURCE_SCHEDULES)
  self.assertEqual(values,[minute(x) for x in ('04:45','06:45','08:45','10:45','12:00','13:45','15:45','17:00','19:00','20:00','21:30','23:15')])
  self.assertEqual(Counter(p for p,_ in RESOURCE_SCHEDULES.values()),Counter({p:4 for p in PLATFORMS}))
 def test_every_article_keeps_two_distinct_social_routes(self):
  from social_rotation import DAILY_ARTICLE_KEYS,platform_pair_for,IST
  day=dt.datetime.now(IST).date()
  self.assertTrue(all(len(set(platform_pair_for(k,day)))==2 for k in DAILY_ARTICLE_KEYS))

if __name__=='__main__':unittest.main()
