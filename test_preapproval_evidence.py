"""No fake traffic/baselines, no unsafe social deletions, no Blogger write API."""
import datetime as dt,json,unittest
from pathlib import Path
from unittest.mock import patch
from preapproval_audit import BloggerReader
from social_duplicate_cleanup import candidates,carries_url
import growth_control_tower as tower
import slot_guard

class ReadOnlyEvidenceTests(unittest.TestCase):
    def test_unapproved_blogger_paths_never_reach_network(self):
        reader=BloggerReader.__new__(BloggerReader);reader.base='https://www.googleapis.com/blogger/v3/blogs/not-used';reader.headers={};reader.reads=0
        with patch('preapproval_audit.requests.get') as get:
            for path in ('/posts/a/publish','/posts/123/publish','/posts/123/revert','/pages/123?method=DELETE','/settings'):
                with self.subTest(path=path),self.assertRaises(ValueError):reader.get(path)
            get.assert_not_called()
    def test_shortlist_is_fifty_unapproved_proposals_not_a_build(self):
        data=json.loads(Path('GROWTH_PRIORITY_SHORTLIST_PRIVATE.json').read_text())
        self.assertEqual(len(data['items']),50)
        self.assertEqual(len({x['id'] for x in data['items']}),50)
        self.assertTrue(all(not x['buildApproved'] and not x['livePublicationApproved'] for x in data['items']))
        self.assertTrue(all(x['specification'] and x['validationBeforeRelease'] for x in data['items']))
    def test_no_unverified_300_reader_forecast(self):
        with patch.object(tower,'engaged_analytics',return_value={'status':'NOT_CONFIGURED','dau':None}):r=tower.build(dt.date(2026,10,18))
        self.assertIsNone(r['stretchTrajectory']['verifiedBaseline']);self.assertFalse(r['stretchTrajectory']['checkpoints'])
        self.assertNotIn('planningBaselineUnverified',r['stretchTrajectory'])
    def test_resource_promotions_never_become_deletion_candidates(self):
        u='https://dailyyield.blogspot.com/2026/10/x.html'
        rows=[{'kind':'page','url':u,'facebook_post_id':str(i),'published_at':'2026-10-18T12:00:00+05:30'} for i in range(2)]
        self.assertEqual(candidates(rows,'2026-10-17',{u}),[])
    def test_deleted_or_unknown_articles_never_become_cleanup_targets(self):
        u='https://dailyyield.blogspot.com/2026/10/x.html'
        rows=[{'kind':'post','url':u,'facebook_post_id':str(i),'published_at':'2026-10-18T12:00:00+05:30'} for i in range(2)]
        self.assertEqual(candidates(rows,'2026-10-17',set()),[])
        group=candidates(rows,'2026-10-17',{u})
        self.assertEqual(len(group),1);self.assertEqual(group[0][1][0]['facebook_post_id'],'0')
    def test_same_provider_id_is_not_two_deletable_posts(self):
        u='https://dailyyield.blogspot.com/2026/10/x.html'
        row={'kind':'post','url':u,'facebook_post_id':'same','published_at':'2026-10-18T12:00:00+05:30'}
        self.assertEqual(candidates([row,dict(row)],'2026-10-17',{u}),[])
    def test_provider_content_must_carry_the_exact_destination(self):
        u='https://dailyyield.blogspot.com/2026/10/x.html'
        self.assertTrue(carries_url({'message':'Read '+u},u));self.assertFalse(carries_url({'message':'Some other post'},u))
    def test_original_tokens_are_not_rotated_by_cleanup(self):
        text=Path('social_duplicate_cleanup.py').read_text()
        self.assertNotIn('refresh_access()',text)
        workflow=Path('.github/workflows/preapproval_audit.yml').read_text()
        self.assertNotIn('files+=(tumblr_token.enc)',workflow)

class PublicationTimeTruthTests(unittest.TestCase):
    def test_early_outside_tolerance_is_not_on_time(self):
        due=dt.datetime(2026,10,18,13,15,tzinfo=slot_guard.IST)
        self.assertEqual(slot_guard.classify(due,due,due-dt.timedelta(minutes=31)),'early')
        self.assertEqual(slot_guard.classify(due,due,due-dt.timedelta(minutes=30)),'on time')
        self.assertEqual(slot_guard.classify(due,due,due+dt.timedelta(minutes=31)),'late')
    def test_actual_publication_time_beats_source_gathering_time(self):
        due=dt.datetime(2026,10,18,13,15,tzinfo=slot_guard.IST)
        def live(*a,**kw):kw['observed'].update(published=due.isoformat(),confirmed=True);return True
        row={'kind':'news','url':'https://dailyyield.blogspot.com/2026/10/x.html','publishedAt':(due-dt.timedelta(hours=1)).isoformat()}
        with patch.object(slot_guard.news_pipeline,'live_current_edition',side_effect=live):stamp=slot_guard.confirmed_publish_time(row,'not-a-real-token',due.date())
        self.assertEqual(stamp,due)

if __name__=='__main__':unittest.main()
