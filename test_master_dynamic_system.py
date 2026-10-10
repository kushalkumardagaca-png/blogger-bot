import datetime as dt
import os
from pathlib import Path
import pytest
import master_taxonomy as taxonomy
import master_topic_discovery as discovery
os.environ.setdefault('BLOGGER_BLOG_ID','test-blog')
from content_experience_repair import build_article_page


def test_exact_20_category_taxonomy():
    assert len(taxonomy.TRENDING_CATEGORIES) == 5
    assert len(taxonomy.EVERGREEN_CATEGORIES) == 15
    assert len(taxonomy.MASTER_CATEGORIES) == 20
    assert len({x['label'] for x in taxonomy.MASTER_CATEGORIES}) == 20


def test_evergreen_rotation_covers_all_categories_in_three_days():
    start=dt.date(2026,10,10).toordinal()
    # Rotation identity is based on the ordinal modulo three, not a fixed weekday.
    rows=[]
    for offset in range(3):rows.extend(taxonomy.evergreen_rotation(start+offset))
    assert {x['label'] for x in rows} == set(taxonomy.EVERGREEN_LABELS)
    assert len(rows) == 15


def test_page_has_five_trending_then_fifteen_evergreen_shelves():
    page=build_article_page([],{'categories':taxonomy.MASTER_CATEGORIES})
    assert page.count('class="dya-desk"') == 20
    assert page.index('Trending Master Articles') < page.index('Evergreen Master Guides')
    assert '20 topic desks · 5 trending + 15 evergreen' in page
    assert 'row.scrollLeft+=72*dt' in page
    assert 'lostpointercapture' in page


def test_discovery_has_no_csv_topic_dependency():
    source=Path('master_topic_discovery.py').read_text()
    assert '.csv' not in source.casefold()
    assert '500_topics_evenly_mixed' not in source
    assert 'discovered_from_live_internet' in source


def test_evergreen_discovery_excludes_already_published_topic(monkeypatch):
    cat=taxonomy.EVERGREEN_CATEGORIES[0]
    rows=[{'query':'budgeting habits guide','clicks':1,'impressions':200,'position':8},{'query':'lifestyle inflation explained','clicks':0,'impressions':100,'position':12}]
    monkeypatch.setattr(discovery,'gsc_queries',lambda:rows)
    selected=discovery.evergreen_candidates([cat],{discovery.uid(rows[0]['query'])})
    assert selected[0]['title']==rows[1]['query']


def test_trend_scoring_clusters_live_observations():
    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    raw=[
      {'title':'Gold prices surge as rate expectations shift','description':'gold market','url':'https://a.example/x','published':stamp,'source':'one','rank':1,'volume':20000,'forced_category':'Trend · Markets & Assets in Motion'},
      {'title':'Gold price surges after rate outlook changes','description':'gold asset','url':'https://b.example/y','published':stamp,'source':'two','rank':2,'volume':0,'forced_category':'Trend · Markets & Assets in Motion'},
    ]
    rows=discovery.trend_candidates(raw)
    assert rows and rows[0]['category']=='Trend · Markets & Assets in Motion'
    assert rows[0]['recency_score'] > 90
    assert rows[0]['discovered_from_live_internet'] is True


def test_master_social_keys_route_to_exactly_one_platform():
    from social_rotation import make_plan, PLATFORMS
    day='2026-10-10T10:00:00+00:00'
    for kind in ('trending','evergreen'):
        for slot in range(5):
            plan=make_plan(f'master-{kind}-{slot}','https://dailyyield.blogspot.com/2026/10/example.html','post',day,'')
            assert plan['platform'] in PLATFORMS
            assert plan['item_key']==f'master-{kind}-{slot}'


def test_publication_is_fail_closed_by_default(monkeypatch,tmp_path):
    monkeypatch.delenv('MASTER_PUBLICATION_ENABLED',raising=False)
    import master_dynamic_pipeline as pipeline
    with pytest.raises(RuntimeError,match='intentionally paused'):
        pipeline.publish('trending',0)
