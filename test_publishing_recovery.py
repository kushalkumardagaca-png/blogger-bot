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
   self.assertIn('news-china',keys);self.assertIn('master-evergreen-0',keys)
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
  source='source:2026-10-11:master-trending-0';ledger[source]={'attempts':99,'lastAttempt':now.isoformat(),'revision':revision}
  self.assertTrue(r.may_retry(ledger,source,now+dt.timedelta(minutes=31),revision))
  self.assertFalse(r.may_retry(ledger,source,now+dt.timedelta(minutes=29),revision))
  self.assertTrue(r.may_retry(ledger,key,now+dt.timedelta(minutes=1),'repaired-code'))
  r.mark(ledger,key,now,'repaired-code');self.assertEqual(ledger[key]['attempts'],1);self.assertEqual(ledger[key]['revision'],'repaired-code')
if __name__=='__main__':unittest.main()
