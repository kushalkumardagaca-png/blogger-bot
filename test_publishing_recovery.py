import datetime as dt,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import publishing_recovery as r
class RecoveryTests(unittest.TestCase):
 def setup(self,root,day):
  (root/'news_tracker.json').write_text(json.dumps({'desks':{'asia-pacific':{'edition':day.isoformat(),'url':'https://dailyyield.blogspot.com/a.html','window_end':day.isoformat()+'T04:15:00+05:30'}}}))
  (root/'MASTER_DAILY_PLAN.json').write_text(json.dumps({'date':day.isoformat(),'trending':[{'id':'t0'}],'evergreen':[{'id':'e0'}]}))
  (root/'MASTER_AUTOMATION_TRACKER.json').write_text(json.dumps({'published':[{'topic_id':'t0','kind':'trending','date':day.isoformat(),'url':'https://dailyyield.blogspot.com/t.html','published_at':day.isoformat()+'T07:45:00+05:30'}]}))
  for p in ('facebook','bluesky','tumblr','mastodon'):(root/f'{p}_tracker.json').write_text('{"published":[]}')
 def test_recovers_missing_sources_and_exact_social_routes(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);day=dt.date(2026,10,14);self.setup(root,day);now=dt.datetime(2026,10,14,10,0,tzinfo=r.IST)
   with patch.object(r,'ROOT',root),patch.object(r,'LEDGER',root/'RECOVERY_LEDGER.json'),patch.object(r,'STATUS',root/'STATUS.json'):
    report=r.reconcile(now,False)
   keys={x['key'] for x in report['actions'] if x['type']=='source_recovery'}
   # Both a late News slot and the Master slot are recovered: nothing is skipped.
   self.assertIn('master-evergreen-0',keys)
   self.assertIn('news-china',keys)
   social=[x for x in report['actions'] if x['type']=='social_replay']
   self.assertEqual(len([x for x in social if x['key']=='news-asia-pacific']),2)
   self.assertEqual(report['syntheticViews'],0)
   self.assertEqual(report['status'],'DEGRADED')
   self.assertIn('news-china',report['overdueMissing'])
 def test_prewarm_recovers_a_missed_future_preparation_cron(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);day=dt.date(2026,10,14);self.setup(root,day);now=dt.datetime(2026,10,14,7,0,tzinfo=r.IST)
   with patch.object(r,'ROOT',root),patch.object(r,'LEDGER',root/'RECOVERY_LEDGER.json'),patch.object(r,'STATUS',root/'STATUS.json'):
    report=r.reconcile(now,False)
   warm=[x for x in report['actions'] if x['type']=='preparation_recovery']
   self.assertEqual([x['key'] for x in warm],['master-evergreen-0'])
 def test_master_recovery_does_not_backfill_12_or_13_october(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);day=dt.date(2026,10,13);self.setup(root,day);now=dt.datetime(2026,10,13,23,30,tzinfo=r.IST)
   with patch.object(r,'ROOT',root),patch.object(r,'LEDGER',root/'RECOVERY_LEDGER.json'),patch.object(r,'STATUS',root/'STATUS.json'):
    report=r.reconcile(now,False)
   assert not any(x.get('key','').startswith('master-') and x.get('type') in ('source_recovery','preparation_recovery') for x in report['actions'])
   assert not any(x.startswith('master-') for x in report['overdueMissing'])
 def test_retry_cap_and_spacing(self):
  now=dt.datetime(2026,10,11,12,0,tzinfo=r.IST);key='x';revision='same-code';ledger={key:{'attempts':1,'lastAttempt':now.isoformat(),'revision':revision}}
  self.assertFalse(r.may_retry(ledger,key,now+dt.timedelta(minutes=30),revision))
  self.assertTrue(r.may_retry(ledger,key,now+dt.timedelta(hours=3),revision))
  ledger[key]['attempts']=3;self.assertFalse(r.may_retry(ledger,key,now+dt.timedelta(days=1),revision))
  # A source retry is spaced ten minutes apart and has no attempt ceiling: an
  # overdue desk is chased all day rather than abandoned.
  source='source:2026-10-11:master-trending-0';ledger[source]={'attempts':99,'lastAttempt':now.isoformat(),'revision':revision}
  self.assertTrue(r.may_retry(ledger,source,now+dt.timedelta(minutes=11),revision))
  self.assertFalse(r.may_retry(ledger,source,now+dt.timedelta(minutes=9),revision))
  self.assertTrue(r.may_retry(ledger,key,now+dt.timedelta(minutes=1),'repaired-code'))
  r.mark(ledger,key,now,'repaired-code');self.assertEqual(ledger[key]['attempts'],1);self.assertEqual(ledger[key]['revision'],'repaired-code')

 def test_a_slot_past_its_window_is_still_published(self):
  # The owner's rule: a late edition is still published, with its social posts.
  # Lateness is reported, never used to cancel the day's article.
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);day=dt.date(2026,10,16);self.setup(root,day);now=dt.datetime(2026,10,16,22,30,tzinfo=r.IST)
   with patch.object(r,'ROOT',root),patch.object(r,'LEDGER',root/'RECOVERY_LEDGER.json'),patch.object(r,'STATUS',root/'STATUS.json'):
    report=r.reconcile(now,False)
   self.assertIn('news-banking',{x['key'] for x in report['actions']})

 def test_a_record_that_the_live_post_does_not_confirm_is_not_trusted(self):
  # news_tracker.json claimed the Banking desk was published on 16 October while
  # the live post still carried an older edition. The record is only a claim.
  rows=[{'key':'news-banking','url':'https://dailyyield.blogspot.com/2026/10/x.html','kind':'news','slot':'banking'}]
  with patch.object(r,'live_token',lambda: 'token'), \
       patch('news_pipeline.live_current_edition',lambda *a,**k: False):
   kept,unverified,note=r.verified_inventory(dt.date(2026,10,16),rows)
  self.assertEqual(kept,[])
  self.assertEqual(unverified,['news-banking'])

if __name__=='__main__':unittest.main()
