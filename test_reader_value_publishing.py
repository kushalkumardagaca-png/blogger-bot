import os
import re
from unittest.mock import Mock,patch
import pytest
from master_article_v2 import render,validate,words
from publication_preflight import assert_publishable
from content_policy_guard import POLICY_VERSION
from prepare_master_article import _compact_evidence_packet,_evidence_bridge_section,_visual_number,model_json,normalize_verified_core


def package():
    sections=[]
    for i in range(10):
        # ten sections of 430 words: inside the 400-490 band the compiler enforces per section, over
        # the 4,000-word reading-value floor the renderer needs before it places the third photograph
        paragraph=f'Part {i+1} '+('evidence context decision risk alternative source limitation application '*53)+' [[S1|official evidence]].'
        sections.append({'heading':f'Topic-specific part {i+1}','paragraphs':[paragraph]})
    summary=[
        'Summary one '+('evidence context decision limitation '*87),
        'Summary two '+('application alternative risk source '*87),
    ]
    return {
      'policy_version':POLICY_VERSION,'title':'Build a Stronger Cash Buffer','meta_description':'A source-led examination of cash reserves, household risk, competing priorities and practical decisions under uncertain income.','sections':sections,'summary':summary,
      'faq':[{'question':f'Question {i}?','answer':f'Answer {i} addresses a distinct topic-specific mechanism, its evidence boundary and its practical limitation.'} for i in range(5)],
      'glossary':[{'term':f'Term {i}','definition':f'Definition {i} explains a distinct concept used specifically in this article and its evidence context.'} for i in range(8)],
      'visuals':[{'type':kind,'title':f'Evidence view {i}','caption':'Illustrative sourced comparison.','source':1,'after_section':i+2,'labels':['A','B'],'values':[1,2]} for i,kind in enumerate(('table','pie','line'))],
      'photos':[{'url':f'https://images.example/photo-{i}.jpg','alt':f'Topic-specific financial photograph {i}','caption':'Topic-specific editorial photograph.','width':1600,'height':900,'source_page':f'https://commons.wikimedia.org/{i}','license':'CC BY 4.0','license_url':'https://creativecommons.org/licenses/by/4.0/','creator':'Creator'} for i in range(3)],
      'sources':[{'name':f'Official source {i}','title':f'Source document {i}','url':f'https://source{i}.gov/document','date':'2026','use':'Evidence','retrieved_at':'2026-10-15'} for i in range(6)],
      'internal_links':[{'title':'Daily Yield Calculators','url':'https://dailyyield.blogspot.com/p/calculator_0908148622.html','relevance':'Model the assumptions.'}],
      'low_view_posts':[{'title':f'Discovery article {i}','url':f'https://dailyyield.blogspot.com/2026/10/article-{i}.html','image':f'https://images.example/card-{i}.jpg','label':'Daily Article'} for i in range(10)]}

def topic():return {'#':'1','Category':'Cash Savings and Emergency Funds','Punchy Title':'Unused'}

def test_master_v2_separates_core_and_summary_word_requirements():
    p=package();metrics=validate(p)
    # the contract is per section, so the test states it the same way instead of a magic total
    assert 400*len(p['sections'])<=metrics['core_words']<=490*len(p['sections'])
    assert 600<=metrics['summary_words']<=800
    title,slug,meta,labels,body=render(p,topic(),'2026-10-05','08:00')
    assert body.count('class="dy2-photo"')==3
    assert body.count('class="dy2-data dy2-data-')==3
    assert 'dy2-data-table' in body and 'dy2-data-pie' in body and 'dy2-data-line' in body
    assert body.index('<h1>') < body.index('class="dy2-by"') < body.index('class="dy2-photo"')
    assert body.index('class="dy2-summary"')<body.index('class="dy2-faq"')<body.index('class="dy2-glossary"')<body.index('class="dy2-low"')<body.index('class="dy2-follow"')<body.index('DY_PAGE_FAMILY_START')
    assert labels==['Cash Savings and Emergency Funds','Kushal Daga','Daily Yield']
    assert '#08744f' not in body and '#073b2b' not in body
    assert 'dy2-answer' in body and 'grid-template-rows' in body and 'prefers-reduced-motion' in body
    assert body.count('class="dy2-rail-group"')==2 and body.count('aria-hidden="true"')>=1
    assert 'flex-flow:row nowrap!important' in body and 'pointerdown' in body and 'pointercancel' in body
    assert "if(!drag)x-=" in body  # automatic right-to-left flow resumes after release
    with patch('publication_preflight.image_works',return_value=True):assert assert_publishable(title,body+'<!-- DY_SEO_META_START --><!-- DY_SEO_META_END --><!-- DY_CONTINUOUS_MOTION_START -->',labels)

def test_master_v2_rejects_date_title_and_supporting_word_padding():
    p=package();p['title']='2026 Cash Buffer Guide'
    with pytest.raises(ValueError,match='contains a date'):validate(p)
    p=package();p['sections']=[{'heading':'Short body','paragraphs':['Only a few core words.']}]
    with pytest.raises(ValueError,match='main article'):validate(p)

def test_model_visual_aliases_are_normalized_for_rendering():
    p=package()
    p['visuals'][0]={'type':'chart','title':'Alias view','caption':'Sourced comparison.','source_number':1,'after_section':2,'labels':['A','B'],'numeric_values':[1,2]}
    body=render(p,topic(),'2026-10-05','08:00')[-1]
    assert 'dy2-data-bar' in body and 'Alias view' in body
    p['visuals'][0]['numeric_values']=[1]
    with pytest.raises(ValueError,match='mismatched labels and values'):validate(p)

def test_evidence_table_supports_qualitative_rows():
    p=package();p['visuals'][0]={'type':'table','title':'Choice comparison','caption':'A source-grounded qualitative comparison.','source':1,'after_section':2,'data':[{'Choice':'A','Trade-off':'Lower liquidity'},{'Choice':'B','Trade-off':'Higher liquidity'}]}
    validate(p);body=render(p,topic(),'2026-10-05','08:00')[-1]
    assert 'Lower liquidity' in body and '<thead>' in body

def test_keyless_local_model_precedes_configured_cloud_keys():
    response=Mock();response.raise_for_status.return_value=None;response.json.return_value={'message':{'content':'{"answer":"local"}'}}
    env={'OLLAMA_API_URL':'http://127.0.0.1:11434','OLLAMA_MODEL':'qwen2.5:3b','GEMINI_API_KEY':'must-not-be-used'}
    with patch.dict(os.environ,env,clear=False),patch('prepare_master_article.requests.post',return_value=response) as post:
        assert model_json([{'role':'user','content':'Return JSON'}],100)=={'answer':'local'}
    assert post.call_args.args[0]=='http://127.0.0.1:11434/api/chat'
    assert post.call_args.kwargs['json']['model']=='qwen2.5:3b'

def test_local_evidence_packet_is_bounded_without_losing_attribution():
    rows=[{'name':'Official source','title':'Document','url':'https://example.gov/doc','text':'x'*9000,'score':9}]
    compact=_compact_evidence_packet(rows)
    assert len(compact[0]['text'])==2200
    assert compact[0]['name']=='Official source' and compact[0]['url'].startswith('https://')
    assert 'score' not in compact[0]

def test_omitted_local_section_has_a_bounded_attributed_fallback():
    evidence=[{'name':f'Official source {i}','title':f'Research record {i}','text':('Documented evidence defines scope jurisdiction observation period and uncertainty without making a universal prediction. '*8)} for i in range(1,6)]
    paragraphs=_evidence_bridge_section('Debt trade-offs','how evidence boundaries affect household decisions',evidence)
    assert words(' '.join(paragraphs))>=240
    assert len(paragraphs)==5 and all(f'[[S{i}|' in paragraphs[i-1] for i in range(1,6))
    assert sum('does not by itself establish causation' in p for p in paragraphs)>=4

def test_short_verified_core_has_evidence_only_deterministic_completion():
    draft=package();draft['sections']=[{'heading':s['heading'],'paragraphs':[' '.join(s['paragraphs'][0].split()[:390])]} for s in draft['sections']]
    evidence=[{'name':f'Official source {i}','title':f'Financial evidence {i}','text':('Financial evidence defines market scope jurisdiction observation period and uncertainty without a universal prediction. '*9)} for i in range(1,7)]
    with patch('prepare_master_article.model_json',side_effect=RuntimeError('offline')):
        normalize_verified_core(draft,evidence)
    total=words(' '.join(' '.join(s['paragraphs']) for s in draft['sections']))
    assert 4000<=total<=4200

def test_visual_number_accepts_single_decorated_number_only():
    assert _visual_number('15%')==15
    assert _visual_number('$100,000')==100000
    with pytest.raises(ValueError):_visual_number('10 to 20')
