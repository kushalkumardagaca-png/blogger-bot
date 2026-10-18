import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from master_slot_state import keeper_for_slot,seal_plan,extra_records
from merge_master_preparation import merge_plan
import master_v3_pipeline as pipeline
import news_pipeline

class MasterSlotSealTests(unittest.TestCase):
    def data(self):
        plan={'status':'READY','date':'2026-10-18','trending':[{'id':'replacement','title':'Replacement','category':'Trend · Markets','evergreen_category':'Markets'}],'evergreen':[]}
        records=[{'date':plan['date'],'kind':'trending','topic_id':'first','category':'Trend · Markets','evergreen_category':'Markets','title':'First','url':'https://dailyyield.blogspot.com/2026/10/first.html','published_at':'2026-10-18T01:45:00-07:00'},
                 {'date':plan['date'],'kind':'trending','topic_id':'replacement','category':'Trend · Markets','evergreen_category':'Markets','title':'Replacement','url':'https://dailyyield.blogspot.com/2026/10/replacement.html','published_at':'2026-10-18T01:59:00-07:00'}]
        return plan,records
    def test_first_published_category_slot_is_kept_even_after_topic_change(self):
        plan,rows=self.data();self.assertEqual(keeper_for_slot(plan,rows,'trending',0)['topic_id'],'first')
        self.assertEqual(seal_plan(plan,rows)['trending'][0]['id'],'first')
    def test_extra_stays_visible_not_deleted_or_counted_as_another_slot(self):
        plan,rows=self.data();extras=extra_records(plan,rows)
        self.assertEqual(len(extras),1);self.assertEqual(extras[0]['topic_id'],'replacement')
        self.assertEqual(len(rows),2)
    def test_stale_preparation_cannot_replace_a_published_slot(self):
        plan,rows=self.data();out=merge_plan(plan,copy.deepcopy(plan),{'kind':'trending','slot':0,'topic_id':'replacement'},rows)
        self.assertEqual(out['trending'][0]['id'],'first')
    def test_previous_day_is_not_a_current_slot_completion(self):
        plan,rows=self.data()
        for row in rows:row['date']='2026-10-17'
        self.assertIsNone(keeper_for_slot(plan,rows,'trending',0))
    def test_old_prepare_cannot_roll_current_day_back(self):
        cur={'date':'2026-10-18'};old={'date':'2026-10-17'}
        self.assertEqual(merge_plan(cur,old,{}),cur)
    def test_replay_confirms_existing_article_and_never_generates_or_publishes(self):
        plan,rows=self.data()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);tracker=root/'tracker.json';tracker.write_text(json.dumps({'published':rows}))
            with patch.object(pipeline,'TRACKER',tracker),patch.object(pipeline,'PLAN',root/'plan.json'),patch.object(pipeline,'STATUS',root/'status.json'),patch.object(pipeline,'SOCIAL',root/'social.json'),patch.object(pipeline,'POOL',root/'pool.json'),patch.object(news_pipeline,'blogger_token',return_value='not-a-real-token'),patch.object(news_pipeline,'master_edition_check',return_value=(True,'verified')),patch.object(pipeline,'publish_to_blogger') as publish:
                self.assertTrue(pipeline.reuse_completed_slot(plan,'trending',0,True));publish.assert_not_called()
                social=json.loads((root/'social.json').read_text());self.assertEqual(social[0]['target_url'],rows[0]['url'])
    def test_uncertain_existing_article_defers_instead_of_creating_another(self):
        plan,rows=self.data()
        with tempfile.TemporaryDirectory() as td:
            tracker=Path(td)/'tracker.json';tracker.write_text(json.dumps({'published':rows}))
            with patch.object(pipeline,'TRACKER',tracker),patch.object(news_pipeline,'blogger_token',return_value='not-a-real-token'),patch.object(news_pipeline,'master_edition_check',return_value=(False,'unavailable')):
                with self.assertRaisesRegex(RuntimeError,'defer instead'):pipeline.reuse_completed_slot(plan,'trending',0)
    def test_medal_is_not_a_commodity_story_but_sports_business_is_kept(self):
        self.assertTrue(news_pipeline.nonfinancial_sport({'title':'Korea wins gold medal in baseball at Asian Games'}))
        self.assertFalse(news_pipeline.nonfinancial_sport({'title':'Olympic sponsorship revenue grows after new contract'}))
        self.assertFalse(news_pipeline.nonfinancial_sport({'title':'Gold prices rise as bond yields fall'}))

if __name__=='__main__':unittest.main()

class SocialLiveEvidenceTests(unittest.TestCase):
    def test_extra_and_keeper_have_distinct_records_but_same_approved_route(self):
        import social_guard as sg
        plan,records=MasterSlotSealTests().data()
        def load(path,default):
            if path.name=='news_tracker.json':return {'desks':{}}
            if path.name=='MASTER_AUTOMATION_TRACKER.json':return {'published':records}
            if path.name=='MASTER_DAILY_PLAN.json':return plan
            return default
        with patch.object(sg,'load',side_effect=load):articles=sg.todays_articles(dt.date(2026,10,18))
        self.assertEqual(len(articles),2)
        self.assertEqual(len({x['key'] for x in articles}),2)
        self.assertEqual({x['routingKey'] for x in articles},{'master-trending-0'})
