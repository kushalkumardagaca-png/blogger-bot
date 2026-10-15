import datetime as dt,json
import pytest
from content_policy_guard import automation_disclosure
from editorial_integrity import assert_green_operating_state,assert_saved_green,assert_unique_plan,find_duplicate,stamp
from master_v3_generator import STRUCTURE_PROFILES,visuals


def test_daily_plan_rejects_same_subject_with_different_ids():
    plan={'status':'READY','trending':[{'id':'a','title':'Cost of living community cup'}],
          'evergreen':[{'id':'b','title':'Community cup and cost of living'}]}
    try:assert_unique_plan(plan)
    except RuntimeError as exc:assert 'DIVERSITY GATE FAILED' in str(exc)
    else:raise AssertionError('near-duplicate plan was accepted')


def test_live_duplicate_guard_recovers_same_title_or_url():
    posts=[{'id':'1','title':'A practical mortgage decision guide','url':'https://dailyyield.blogspot.com/2026/10/mortgage-guide.html','content':'Evidence '+('bounded context '*80)}]
    found,reason=find_duplicate('A practical mortgage decision guide','Different body',posts)
    assert found['id']=='1' and reason=='same normalized title'
    found,reason=find_duplicate('Another title','Different body',posts,'https://dailyyield.blogspot.com/2026/10/mortgage-guide.html')
    assert found['id']=='1' and reason=='same canonical path'


def test_integrity_stamp_records_topic_content_structure_and_profile():
    value=stamp('<article><section><h2>Evidence</h2><p>Useful prose.</p></section></article>','Useful title','decision-path')
    assert 'DY_EDITORIAL_INTEGRITY_V1' in value
    assert 'topic=' in value and 'content=' in value and 'structure=' in value and 'profile=decision-path' in value


def test_master_visual_profiles_use_distinct_evidence_safe_presentations():
    sources=[{'name':f'Source {i}','title':f'Evidence {i}','text':'A bounded source finding with enough explanatory context for readers.'} for i in range(1,4)]
    sections=[{'heading':f'Section {i}'} for i in range(1,10)]
    kinds=[]
    for profile in STRUCTURE_PROFILES[:4]:kinds.append(tuple(x['type'] for x in visuals(sources,sections,profile)))
    assert len(set(kinds))>=3
    assert all(kind in {'table','cards','matrix','timeline'} for row in kinds for kind in row)


def test_whole_site_green_gate_requires_fresh_passing_corpus_and_policy(tmp_path):
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    (tmp_path/'BLOGGER_CORPUS_POLICY_STATUS.json').write_text(json.dumps({'status':'PASS','checked_at':now,'remaining_live_policy_flags':[],'unsafe_active_links':[],'image_rights_gap_posts':0}))
    (tmp_path/'BLOGGER_POLICY_MONITOR_STATUS.json').write_text(json.dumps({'status':'PASS','checked_at':now,'wording_changed':False}))
    assert assert_green_operating_state(tmp_path)
    (tmp_path/'BLOGGER_POLICY_MONITOR_STATUS.json').write_text(json.dumps({'status':'REVIEW_REQUIRED','checked_at':now,'wording_changed':True}))
    with pytest.raises(RuntimeError,match='official Blogger policy requires review'):assert_green_operating_state(tmp_path)


def test_blogger_stored_post_must_preserve_green_markers_and_alt_text():
    body=stamp('<article><p>A source-bounded explanation with current context for readers.</p><img src="https://example.com/a.jpg" alt="Relevant evidence photograph"></article>','A source bounded decision guide')+automation_disclosure('article')
    post={'status':'LIVE','title':'A source bounded decision guide','url':'https://dailyyield.blogspot.com/2026/10/decision-guide.html','content':body}
    assert assert_saved_green(post)
    post['content']=post['content'].replace(' alt="Relevant evidence photograph"','')
    with pytest.raises(RuntimeError,match='alternative text'):assert_saved_green(post)
