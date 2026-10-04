import csv
import itertools
import re
from unittest.mock import patch

import pytest

import reader_value_article as rva
from publication_preflight import MASS_TEMPLATE_PHRASES, _plain, _source_domains, assert_publishable
from news_pipeline import DESKS, build_article, compose_item, dedupe_rendered_stories


def topics_by_family():
    with open('500_topics_evenly_mixed.csv', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    first = {}
    for row in rows:
        first.setdefault(row['Category'], row)
    return first


def package(row):
    hero = '<figure><img src="https://images.unsplash.com/test" alt="Topic-specific financial planning notes" width="900" height="506"></figure>'
    title, slug, meta, labels, body = rva.build(row, '2026-10-03', '21:00', hero)
    # The publisher supplies these preserved cross-site packages after body construction.
    body += ('<div class="dy-context">Context</div><div class="dy-related">Related</div>'
             '<div id="dyPageFamily">Directory</div><!-- DY_CONTINUOUS_MOTION_START -->')
    return title, slug, meta, labels, body


def shingles(text, size=5):
    words = re.findall(r'[a-z]+', text.casefold())
    return {' '.join(words[i:i + size]) for i in range(len(words) - size + 1)}


def test_all_25_master_families_are_sourced_specific_and_deep():
    families = topics_by_family()
    assert len(families) == 25
    for category, row in families.items():
        title, slug, meta, labels, body = package(row)
        text = _plain(body)
        assert len(re.findall(r"[A-Za-z][A-Za-z'-]+", text)) >= 900, category
        assert len(_source_domains(body)) >= 3, category
        assert 'Worked example with disclosed assumptions' in body
        assert 'Editorial method' in body
        assert row['Video Description'] in text
        assert row['Video Idea'] in text
        assert labels == [category, 'Kushal K. Daga']
        assert not any(phrase.casefold() in text.casefold() for phrase in MASS_TEMPLATE_PHRASES)
        with patch('publication_preflight.image_works', return_value=True):
            assert assert_publishable(title, body, labels)


def test_category_family_samples_do_not_cross_excessive_similarity_threshold():
    samples = []
    for category, row in topics_by_family().items():
        body = package(row)[4]
        samples.append((category, shingles(_plain(body))))
    worst = max(
        (len(left & right) / len(left | right), a, b)
        for (a, left), (b, right) in itertools.combinations(samples, 2)
    )
    assert worst[0] < 0.80, worst


def test_preflight_rejects_repeated_paragraph_and_unsupported_absolute():
    row = next(iter(topics_by_family().values()))
    title, _, _, labels, body = package(row)
    repeated = '<p>' + ('This documented paragraph is intentionally duplicated for the quality gate. ' * 3) + '</p>'
    with patch('publication_preflight.image_works', return_value=True):
        with pytest.raises(RuntimeError, match='duplicated substantive paragraph'):
            assert_publishable(title, body + repeated + repeated, labels)
        with pytest.raises(RuntimeError, match='unsupported absolute'):
            assert_publishable(title, body + '<p>Guaranteed returns are available.</p>', labels)


def test_all_20_news_desks_build_source_led_transparent_editions():
    import datetime as dt
    end = dt.datetime(2026, 10, 3, 12, tzinfo=dt.timezone.utc)
    start = end - dt.timedelta(hours=24)
    items = [
        {'title': 'Agency publishes scheduled policy update', 'desc': 'The agency published its scheduled policy update with the scope and effective date stated in the linked record', 'agency': 'Official Agency', 'url': 'https://official.example/update', 'date': end.date(), 'media': False, 'background': False},
        {'title': 'Newsroom reports response to official release', 'desc': 'The newsroom reported the response and attributed the reported figures to the official release', 'agency': 'Established Newsroom', 'url': 'https://news.example/report', 'date': end.date(), 'media': True, 'background': False},
        {'title': 'Statistics office releases current data table', 'desc': 'The statistics office released a current table and retained the measurement notes in the source document', 'agency': 'Statistics Office', 'url': 'https://stats.example/table', 'date': end.date(), 'media': False, 'background': False},
    ]
    hero = {'url': 'https://images.unsplash.com/news', 'alt': 'Financial news desk documents', 'credit': 'Editorial photograph · Unsplash', 'source': 'test'}
    with patch('news_pipeline.daily_hero', return_value=hero):
        for desk in DESKS:
            article = build_article(desk, items, [], end.date(), start, end, {'USD': 1.1}, [])
            text = _plain(article['html'])
            assert len(re.findall(r"[A-Za-z][A-Za-z'-]+", text)) >= 350, desk
            assert 'How to Read This' in article['html'], desk
            assert len(_source_domains(article['html'])) >= 3, desk
            assert 'source map, not a prediction' in text, desk
            assert all(item['desc'] in text for item in items), desk


def test_news_visible_paragraph_deduplication_keeps_one_source_record():
    shared = {
        'desc': 'The agency issued the same sufficiently detailed release summary for two syndicated records.',
        'agency': 'Official Agency', 'date': __import__('datetime').date(2026, 10, 4),
        'media': False, 'background': False,
    }
    items = [
        {**shared, 'title': 'First syndication headline', 'url': 'https://official.example/one'},
        {**shared, 'title': 'Second syndication headline', 'url': 'https://official.example/two'},
    ]
    assert dedupe_rendered_stories(items) == [items[0]]


def test_news_item_prose_is_deterministic_and_source_bounded():
    item = {
        'title': 'Central bank publishes October policy decision',
        'desc': 'The central bank kept its policy rate unchanged after the scheduled meeting',
        'agency': 'Example Central Bank',
        'url': 'https://central.example/policy',
        'date': __import__('datetime').date(2026, 10, 3),
        'media': False,
        'background': False,
    }
    first = compose_item(item, None)
    second = compose_item(item, None)
    assert first == second
    assert item['desc'] in first
    assert 'Source:' not in first and 'Official:' in first
    assert 'moves the market' not in first.casefold()
