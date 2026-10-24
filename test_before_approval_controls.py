"""Regression protection for the owner's Table 3 / AdSense-first instructions."""
from __future__ import annotations
import contextlib,datetime as dt,io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import yaml
import site_change_control as freeze
import frozen_hub_refresh as hubs
import index_status_report as index
import adsense_approval_check as approval
import social_dedupe as dupe
import social_guard as guard
from merge_social_tracker import merge

ROOT=Path(__file__).parent

class FreezeTests(unittest.TestCase):
    def test_freeze_is_active_and_has_no_automatic_date_release(self):
        cfg=freeze.policy()
        self.assertIs(cfg['frozen'],True)
        self.assertEqual(len(cfg['releaseRequires']),3)
        self.assertNotIn('unfreezeAt',cfg)
    def test_missing_bad_and_empty_policy_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'policy.json'
            with patch.object(freeze,'POLICY',p):
                self.assertTrue(freeze.is_frozen())
                for text in ('{bad','{}','[]'):
                    p.write_text(text);self.assertTrue(freeze.is_frozen())
    def test_only_explicit_false_in_versioned_policy_releases(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'p.json';p.write_text('{"frozen":false}')
            with patch.object(freeze,'POLICY',p):self.assertFalse(freeze.is_frozen())
    def test_env_and_force_cannot_override_freeze(self):
        with patch.dict(os.environ,{'APPLY':'true','FORCE':'1','SITE_FREEZE':'false'}),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:freeze.stop_if_frozen('test')
            self.assertEqual(raised.exception.code,0)
    def test_every_held_cli_stops_without_any_account_credentials(self):
        for action,name in freeze.policy()['heldCliActions'].items():
            with self.subTest(action=action):
                env={k:v for k,v in os.environ.items() if not any(x in k for x in ('BLOGGER','GSC_','GA4_','BING_'))}
                env.update({'APPLY':'true','APPLY_CORPUS_REMEDIATION':'true'})
                r=subprocess.run([sys.executable,name,'--force','--apply'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=12)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn('HELD_BY_OWNER_FREEZE',r.stdout)
    def test_held_workflows_cannot_start_writer_jobs(self):
        for name in freeze.policy()['heldWorkflows']:
            data=yaml.safe_load((ROOT/'.github/workflows'/name).read_text())
            for job in data['jobs'].values():self.assertEqual(job['if'],'${{ false }}',name)
    def test_live_publishers_and_recovery_are_not_held(self):
        for name in ('daily_news_wires.yml','master_evergreen_writer.yml','master_trending_writer.yml','slot_guarantee.yml','publishing_recovery.yml'):
            self.assertNotIn(name,freeze.policy()['heldWorkflows'])
            data=yaml.safe_load((ROOT/'.github/workflows'/name).read_text())
            self.assertTrue(data.get('on',data.get(True,{})).get('schedule'))
    def test_a_release_names_one_action_one_edit_and_the_owner(self):
        # the difference between a granted correction and a hole in the freeze is the record beside it
        cfg=freeze.policy();released=cfg.get('releasedCorrections') or []
        # Four releases exist now, and the list is still exact: a name appearing in the policy without the
        # owner's sentence beside it fails this test, which is the whole point of keeping it pinned. The
        # fourth is 23 October's twin retirement - clearing the extra copy of an article published twice -
        # granted by the owner in the same breath as the report of it, and no wider.
        self.assertEqual([e.get('action') for e in released],
                         ['search_index_policy_repair','desk_index_redesign','corpus_figure_rights_repair',
                          'duplicate_twin_retirement'])
        for index,entry in enumerate(released):
            for key in ('scope','ownerInstruction','releasedAt','limits'):
                self.assertTrue(str(entry.get(key) or '').strip(),f"releasedCorrections[{index}].{key} is missing")
            self.assertIn('October 2026',entry['ownerInstruction'])
            self.assertIn('Owner,',entry['ownerInstruction'])
        repair=[e for e in released if e['action']=='search_index_policy_repair'][0]
        # The 23 October release is the narrowest the freeze has ever carried: it writes the words inside an
        # existing figure caption and nothing else, and its own forbidden list says so.
        rights=[e for e in released if e['action']=='corpus_figure_rights_repair'][0]
        self.assertIn('figcaption',rights['scope'])
        for forbidden in ('delete','revert to draft','title','labels','schedules'):
            self.assertIn(forbidden,json.dumps(rights['limits']['forbidden']))
        self.assertNotIn('corpus_figure_rights_repair',cfg.get('heldCliActions') or {})
        # Nothing that can now write is still described as audit-only: a file whose own release lets it
        # repair a caption cannot also be listed as never writing, or the list has become decoration.
        self.assertNotIn('harden_live_corpus',cfg.get('auditOnlyActions') or [])
        self.assertIn('frozen',json.dumps(cfg))
        self.assertIs(cfg['frozen'],True,'a release must never unfreeze the site')
        self.assertEqual(repair['limits']['publicDailyYieldRequests'],0)
        self.assertEqual(repair['limits']['maxTakedownsPerRun'],12)
        self.assertIn('title',repair['limits']['allowedFields'])
        self.assertIn('body sentences',repair['limits']['forbidden'])
        self.assertNotIn('desk_index_redesign',cfg['heldCliActions'])
        self.assertNotIn('desk_index_redesign.yml',cfg['heldWorkflows'])
        self.assertNotIn('search_index_policy_repair',cfg['heldCliActions'])
        self.assertNotIn('search_index_policy_repair.yml',cfg['heldWorkflows'])
        self.assertIs(cfg['frozen'],True)
    def test_nothing_else_was_let_go_along_with_it(self):
        held=freeze.policy()['heldCliActions'];workflows=freeze.policy()['heldWorkflows']
        # Exact on purpose: a name leaving this list quietly un-freezes a script that writes the site.
        # 'blogger_duplicate_purge' and 'cleanup_wrong_master_post' were added on 22 October 2026 when
        # the owner ruled that no published article may come down because of a workflow; both can call
        # Blogger's DELETE, so both are now held by the freeze like everything else that writes.
        self.assertEqual(set(held),{'adsense_readiness','blogger_seo_repair','blogger_duplicate_purge',
            'cleanup_wrong_master_post','deploy_blogger_policy_compliance',
            'deploy_global_snapshot','deploy_markets_today','gsc_rebuild','identity_migration',
            'motion_related_retrofit','reader_measurement_retrofit','repair_family_directory',
            'repair_known_external_links','retrofit_live_news','solve_remaining','update_page_family'})
        self.assertEqual(set(workflows), {
            'adsense_readiness.yml', 'blogger_seo_repair.yml', 'blogger_policy_compliance.yml',
            'deploy_global_snapshot.yml', 'deploy_markets_today.yml', 'gsc_rebuild.yml',
            'identity_migration.yml', 'motion_related_retrofit.yml', 'reader_measurement_retrofit.yml',
            'repair_family_directory.yml', 'repair_known_external_links.yml', 'retrofit_live_news.yml',
            'solve_remaining.yml', 'update_page_family.yml'})
    def test_dropping_a_name_from_the_list_unlocks_nothing_without_a_record(self):
        with tempfile.TemporaryDirectory() as td:
            written=Path(td)/'p.json'
            written.write_text(json.dumps({'frozen':True,'heldCliActions':{'other_action':'other.py'}}))
            with patch.object(freeze,'POLICY',written),contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit):freeze.stop_if_frozen('desk_index_redesign')
            self.assertIn('HELD_BY_OWNER_FREEZE',out.getvalue())
    def test_a_released_action_reports_the_scope_it_was_given(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:freeze.stop_if_frozen('desk_index_redesign')
        said=json.loads(out.getvalue())
        self.assertEqual(said['status'],'OWNER_RELEASED_CORRECTION')
        self.assertIn('desk index',said['scope'])
    def test_the_workflow_asks_the_freeze_instead_of_being_switched_off(self):
        text=(ROOT/'.github/workflows/desk_index_redesign.yml').read_text()
        data=yaml.safe_load(text)
        for name,job in data['jobs'].items():self.assertNotIn('if',job,f"{name} is still hard-disabled")
        self.assertIn('--allowed desk_index_redesign',text)
        self.assertIn('.github/desk-index-apply-request',text,'the intent to write is retired after use')
        self.assertIn('DESK_INDEX_BACKUP/',text,'the previous copy travels with the evidence')
    def test_the_released_script_still_refuses_an_unverified_board(self):
        # released or not, the writer refuses a board that lost a link, a number or a glyph
        import desk_index_redesign as dx
        board = {"aria": "a", "eyebrow": "b", "title": "c", "note": "{total} desks, one tape",
                 "chips": [], "labels": {"open": "Open desk"},
                 "groups": [{"name": "G", "items": [{"href": "#x", "num": "01", "title": "T",
                                                      "desc": "d",
                                                      "icon": '<svg viewBox="0 0 24 24"><path d="M4 4 L9 9"></path></svg>'}]}]}
        block = dx.design.render(board)
        current = dx.parse_index("<div>" + block + "</div>")
        self.assertEqual(dx.validate(block, current), [])
        lost_glyph = block.replace('<path d="M4 4 L9 9"></path>', "")
        issues = dx.validate(lost_glyph, current)
        self.assertTrue(any("icon lost" in issue for issue in issues), issues)

    def test_draft_restore_does_not_authenticate(self):
        import draft_inventory_sweep as sweep
        with patch('sys.argv',['draft_inventory_sweep.py','--restore']),patch.object(sweep,'token') as token,contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(sweep.main(),0);token.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())['status'],'RESTORE_RETIRED')

class FrozenHubTests(unittest.TestCase):
    def test_json_data_changes_but_surrounding_code_is_identical(self):
        old='<style>.old{}</style><script>window.ENH_NEWS_SNAPSHOT=[{"x":1}];boot();</script>'
        new,ok=hubs.replace_json_value(old,'window.ENH_NEWS_SNAPSHOT=',[{'x':2}])
        self.assertTrue(ok);self.assertEqual(new,old.replace('{"x":1}','{"x":2}'))
    def test_missing_or_nonliteral_snapshot_is_never_installed(self):
        for old in ('<h1>Old hub</h1>','<script>window.ENH_NEWS_SNAPSHOT=load();</script>'):
            new,ok=hubs.replace_json_value(old,'window.ENH_NEWS_SNAPSHOT=',[{'x':1}])
            self.assertFalse(ok);self.assertEqual(new,old)
    def test_cards_refresh_without_new_sections_styles_or_headings(self):
        old='<style>old-css</style><section id="dya-1"><h2>Existing</h2><div class="dya-tools"><span>0 articles</span></div><div class="dya-set"></div></section><script>oldCode()</script>'
        posts=[{'id':'p','url':'https://dailyyield.blogspot.com/2026/10/test.html','labels':['Saving'],'published':'2026-10-18T10:00:00+05:30'}]
        new,count=hubs.refresh_article_cards(old,posts,[{'number':1,'label':'Saving'}],lambda p,c:'<a href="'+p['url']+'">Card</a>')
        self.assertEqual(count,1);self.assertIn('<h2>Existing</h2>',new)
        self.assertIn('<style>old-css</style>',new);self.assertIn('<script>oldCode()</script>',new)
        self.assertEqual(new.count('<section'),old.count('<section'))
        self.assertIn('1 article',new)
    def test_no_scaffolding_is_added_to_an_empty_fallback(self):
        old='<section id="dya-new"><p>No posts</p></section>'
        new,count=hubs.refresh_article_cards(old,[],[],lambda p,c:'')
        self.assertEqual(new,old);self.assertEqual(count,0)

class IndexTruthTests(unittest.TestCase):
    def test_property_labels_and_external_hosts_are_not_urls(self):
        for u in ('sc-domain:dailyyield.blogspot.com','http://dailyyield.blogspot.com/','https://dailyyield.blogspot.com.evil/','https://user@dailyyield.blogspot.com/'):
            self.assertFalse(index.valid_url(u))
        self.assertTrue(index.valid_url('https://dailyyield.blogspot.com/'))
    def test_invalid_target_never_reaches_google(self):
        with patch.object(index,'fetch') as fetch:
            with self.assertRaises(ValueError):index.inspect('secret','sc-domain:dailyyield.blogspot.com')
            fetch.assert_not_called()
    def test_error_is_unknown_not_unindexed(self):
        r=index.summarise([{'url':'a','verdict':'PASS','coverageState':'Submitted and indexed'},
                           {'url':'b','verdict':'NEUTRAL','coverageState':'Discovered - currently not indexed'},
                           {'url':'c','verdict':'ERROR','httpStatus':403},
                           {'url':'d','verdict':'UNKNOWN'}])
        self.assertEqual((r['indexed'],r['notIndexed'],r['inspectionErrors'],r['unknown']),(1,1,1,1))
        self.assertEqual(r['status'],'PARTIAL')
    def test_all_errors_are_unavailable_not_zero_indexing_proof(self):
        r=index.summarise([{'verdict':'ERROR','httpStatus':403}])
        self.assertEqual(r['status'],'UNAVAILABLE');self.assertEqual(r['notIndexed'],0)

class ApprovalTruthTests(unittest.TestCase):
    def report(self,fail=None,home_extra=''):
        base='Kushal Daga Kushal Kumar Daga short form legal name dailyyield.official@gmail.com kushalkumardaga.ca@gmail.com advertising AdSense third-party vendor aboutads.info'
        feed=json.dumps({'feed':{'entry':[{'title':{'$t':'Article'},'content':{'$t':'<p>Original reporting.</p>'}}]}})
        def get(path,*a,**kw):
            if path==fail:return 0,'TimeoutError'
            if path=='/robots.txt':return 200,'User-agent: *\nDisallow: /search\nAllow: /\nSitemap: https://dailyyield.blogspot.com/sitemap.xml'
            if path=='/ads.txt':return 200,'google.com, pub-1083724733490660, DIRECT, f08c47fec0942fa0'
            if path=='/sitemap.xml':return 200,'<url><loc>https://dailyyield.blogspot.com/</loc></url>'
            if path.startswith('/feeds/'):return 200,feed
            return 200,'<html><body>'+base+home_extra+'</body></html>'
        with patch.object(approval,'get',side_effect=get),patch.object(approval.time,'sleep'),patch.object(approval.reader_prose,'problems',return_value=[]):return approval.check_site()
    def test_verification_code_is_not_called_a_violation(self):
        r=self.report(home_extra='<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1083724733490660"></script>')
        self.assertEqual(r['status'],'PASS');self.assertFalse(any(x['check']=='no ad code before approval' for x in r['checks']))
    def test_wildcard_allow_does_not_need_named_ad_crawler(self):
        r=self.report();check=next(x for x in r['checks'] if x['check']=='AdSense crawler access allowed')
        self.assertIs(check['pass'],True)
    def test_fetch_failure_is_incomplete_not_a_proven_missing_page(self):
        r=self.report('/p/terms-and-conditions.html')
        self.assertEqual(r['status'],'CHECK_INCOMPLETE');self.assertFalse(r['blockingIssues']);self.assertTrue(r['unverifiedChecks'])
    def test_home_fetch_failure_does_not_pass_identity_checks(self):
        r=self.report('/')
        self.assertEqual(r['status'],'CHECK_INCOMPLETE')
        self.assertTrue(any(x['check']=='homepage identity and markup' and x['pass'] is None for x in r['checks']))
    def test_one_transient_404_cannot_be_reported_as_a_blocking_defect(self):
        base = ('Kushal Daga Kushal Kumar Daga short form legal name '
                'dailyyield.official@gmail.com kushalkumardaga.ca@gmail.com '
                'advertising AdSense third-party vendor aboutads.info')
        feed = json.dumps({'feed': {'entry': [{'title': {'$t': 'Article'},
                                               'content': {'$t': '<p>Original reporting.</p>'}}]}})
        robots_reads = []

        def get(path, *a, **kw):
            if path == '/robots.txt':
                robots_reads.append(path)
                if len(robots_reads) == 1:
                    return 404, 'Not Found'
                return 200, 'User-agent: *\nDisallow: /search\nAllow: /\nSitemap: https://dailyyield.blogspot.com/sitemap.xml'
            if path == '/ads.txt':
                return 200, 'google.com, pub-1083724733490660, DIRECT, f08c47fec0942fa0'
            if path == '/sitemap.xml':
                return 200, '<url><loc>https://dailyyield.blogspot.com/</loc></url>'
            if path.startswith('/feeds/'):
                return 200, feed
            return 200, '<html><body>' + base + '</body></html>'

        with patch.object(approval, 'get', side_effect=get), patch.object(approval.time, 'sleep'), \
             patch.object(approval.reader_prose, 'problems', return_value=[]):
            report = approval.check_site()
        row = next(x for x in report['checks'] if x['check'] == 'robots.txt readable')
        self.assertIs(row['pass'], True)
        self.assertIn('the first answer was a 404 that the re-probe disproved', row['detail'])
        self.assertEqual(len(robots_reads), 2)
        self.assertEqual(report['status'], 'PASS')
        self.assertFalse(report['blockingIssues'])

    def test_a_file_that_stays_missing_still_fails(self):
        def get(path, *a, **kw):
            if path == "/ads.txt":
                return 404, "Not Found"
            if path == "/robots.txt":
                return 200, "User-agent: *\nAllow: /\nSitemap: https://dailyyield.blogspot.com/sitemap.xml"
            if path == "/sitemap.xml":
                return 200, "<url><loc>https://dailyyield.blogspot.com/</loc></url>"
            if path.startswith("/feeds/"):
                return 200, json.dumps({"feed": {"entry": []}})
            return 200, "<html><body>ok</body></html>"

        with patch.object(approval, "get", side_effect=get), patch.object(approval.time, "sleep"), \
             patch.object(approval.reader_prose, "problems", return_value=[]):
            report = approval.check_site()
        ads = next(row for row in report["checks"] if row["check"] == "ads.txt matches the recorded publisher")
        self.assertIs(ads["pass"], False)
        self.assertIn("3 reads", ads["detail"])
        self.assertEqual(report["status"], "FAIL")

    def test_robots_default_indexing_is_not_a_failure(self):
        r=self.report();self.assertEqual(r['status'],'PASS')
    def test_old_forced_resubmit_and_name_match_instructions_are_gone(self):
        r=self.report();instructions=' '.join(r['manualStepsRequired'])
        self.assertIn('do not remove and resubmit',instructions)
        self.assertNotIn('exactly as they appear on About',instructions)

class SocialSafetyTests(unittest.TestCase):
    def test_tracking_failure_raises_instead_of_allowing_a_post(self):
        with patch.object(dupe,'fresh_tracker',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):dupe.already_posted('tumblr','https://dailyyield.blogspot.com/a')
    def test_article_query_variants_do_not_bypass_dedupe(self):
        d={'published':[{'url':'https://dailyyield.blogspot.com/a.html','kind':'post'}]}
        with patch.object(dupe,'fresh_tracker',return_value=d):self.assertTrue(dupe.already_posted('tumblr','https://dailyyield.blogspot.com/a.html?m=1#x'))
    def test_yesterdays_resource_does_not_cancel_todays_rotation(self):
        d={'published':[{'url':'https://dailyyield.blogspot.com/p/article.html','kind':'page','published_at':'2026-10-17T12:00:00+05:30'}]}
        now=dt.datetime(2026,10,18,12,tzinfo=dupe.IST)
        with patch.object(dupe,'fresh_tracker',return_value=d):self.assertFalse(dupe.already_posted('tumblr',d['published'][0]['url'],'page',now))
    def test_today_resource_is_skipped(self):
        d={'published':[{'url':'https://dailyyield.blogspot.com/p/article.html','kind':'page','published_at':'2026-10-18T11:00:00+05:30'}]}
        now=dt.datetime(2026,10,18,12,tzinfo=dupe.IST)
        with patch.object(dupe,'fresh_tracker',return_value=d):self.assertTrue(dupe.already_posted('tumblr',d['published'][0]['url'],'page',now))
    def test_provider_id_duplicates_are_counted_once(self):
        row={'url':'https://dailyyield.blogspot.com/a','tumblr_post_id':'same-id'}
        self.assertEqual(guard.covered_by({'url':row['url']},{'tumblr':[row,dict(row)]}),{'tumblr':1})
    def test_deleted_provider_post_cannot_be_resurrected_by_stale_state(self):
        row={'url':'https://dailyyield.blogspot.com/a','tumblr_post_id':'duplicate'}
        current={'published':[],'deleted':[dict(row,reason='confirmed duplicate')]}
        result=merge(current,{'published':[row]})
        self.assertEqual(result['published'],[]);self.assertEqual(len(result['deleted']),1)
    def test_workflow_outputs_are_not_accidentally_quoted(self):
        text=(ROOT/'.github/workflows/coordinated_social_publish.yml').read_text()
        self.assertNotIn('already="yes"',text);self.assertEqual(text.count("echo 'already=yes'"),3)
        # two per channel now: the dedupe guard's exit and the publish block's own exit, so a
        # network that fails is still a failed step and recovery keeps trying. Three live networks
        # after Tumblr's removal on 21 October 2026, so six of them.
        self.assertEqual(text.count('exit "$code"'),6)
    def test_each_network_publishes_one_destination_at_a_time(self):
        # The group is scoped to the network, not to network+destination: Facebook rotates a single
        # OAuth refresh token per job, so two parallel jobs for two articles invalidated each other's
        # token on 19 October. Tumblr left automation on 21 October 2026, so three networks remain.
        data=yaml.safe_load((ROOT/'.github/workflows/coordinated_social_publish.yml').read_text())
        self.assertEqual(tuple(data['jobs'][1:] if False else [k for k in data['jobs'] if k!='plan']),
                         ('facebook','bluesky','mastodon'))
        for platform in ('facebook','bluesky','mastodon'):
            group=data['jobs'][platform]['concurrency']['group']
            self.assertEqual(group,f'social-{platform}')
            self.assertNotIn('target_url',group)
            self.assertIs(data['jobs'][platform]['concurrency']['cancel-in-progress'],False)

if __name__=='__main__':unittest.main()
