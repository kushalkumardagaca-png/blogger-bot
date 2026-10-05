import re
from unittest.mock import patch
import pytest
from master_article_v2 import render,validate,words
from publication_preflight import assert_publishable
from prepare_master_article import _visual_number


def package():
    sections=[]
    for i in range(8):
        paragraph=f'Section {i+1} '+('evidence context decision risk alternative source limitation application '*63)+' [[S1|official evidence]].'
        sections.append({'heading':f'Topic-specific section {i+1}','paragraphs':[paragraph]})
    summary=[
        'Summary one '+('evidence context decision limitation '*87),
        'Summary two '+('application alternative risk source '*87),
    ]
    return {
      'title':'Build a Stronger Cash Buffer','meta_description':'A source-led examination of cash reserves, household risk, competing priorities and practical decisions under uncertain income.','sections':sections,'summary':summary,
      'faq':[{'question':f'Question {i}?','answer':'A topic-specific answer based on the evidence and its limitations.'} for i in range(5)],
      'glossary':[{'term':f'Term {i}','definition':'A definition used specifically in this article.'} for i in range(8)],
      'visuals':[{'type':kind,'title':f'Evidence view {i}','caption':'Illustrative sourced comparison.','source':1,'after_section':i+2,'labels':['A','B'],'values':[1,2]} for i,kind in enumerate(('table','pie','line'))],
      'photos':[{'url':f'https://images.example/photo-{i}.jpg','alt':f'Topic-specific financial photograph {i}','caption':'Topic-specific editorial photograph.','width':1600,'height':900} for i in range(3)],
      'sources':[{'name':f'Official source {i}','title':f'Source document {i}','url':f'https://source{i}.gov/document','date':'2026','use':'Evidence'} for i in range(6)],
      'internal_links':[{'title':'Daily Yield Calculators','url':'https://dailyyield.blogspot.com/p/calculator_0908148622.html','relevance':'Model the assumptions.'}],
      'low_view_posts':[{'title':f'Discovery article {i}','url':f'https://dailyyield.blogspot.com/2026/10/article-{i}.html','image':f'https://images.example/card-{i}.jpg','label':'Daily Article'} for i in range(10)]}

def topic():return {'#':'1','Category':'Cash Savings and Emergency Funds','Punchy Title':'Unused'}

def test_master_v2_separates_core_and_summary_word_requirements():
    p=package();metrics=validate(p)
    assert 4000<=metrics['core_words']<=4200
    assert 600<=metrics['summary_words']<=800
    title,slug,meta,labels,body=render(p,topic(),'2026-10-05','08:00')
    assert body.count('class="dy2-photo"')==3
    assert body.count('class="dy2-data dy2-data-')==3
    assert 'dy2-data-table' in body and 'dy2-data-pie' in body and 'dy2-data-line' in body
    assert body.index('<h1>') < body.index('class="dy2-by"') < body.index('class="dy2-photo"')
    assert body.index('class="dy2-summary"')<body.index('class="dy2-faq"')<body.index('class="dy2-glossary"')<body.index('class="dy2-low"')<body.index('class="dy2-follow"')<body.index('DY_PAGE_FAMILY_START')
    assert labels==['Cash Savings and Emergency Funds','Kushal K. Daga']
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
    with pytest.raises(ValueError,match='mismatched labels and values'):render(p,topic(),'2026-10-05','08:00')

def test_visual_number_accepts_single_decorated_number_only():
    assert _visual_number('15%')==15
    assert _visual_number('$100,000')==100000
    with pytest.raises(ValueError):_visual_number('10 to 20')
