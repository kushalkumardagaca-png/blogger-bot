import social_performance as sp


def test_bluesky_metrics_are_genuine_counts_and_never_invent_impressions(monkeypatch):
    entry = {
        'bluesky_uri': 'at://did:plc:test/app.bsky.feed.post/abc',
        'title': 'A sourced decision guide',
        'url': 'https://dailyyield.blogspot.com/2026/10/guide.html',
        'published_at': '2026-10-03T12:00:00+05:30',
    }
    called = []

    def fake_get(url, **kwargs):
        called.append(url)
        return {'posts': [{
            'uri': entry['bluesky_uri'], 'likeCount': 4, 'repostCount': 2,
            'replyCount': 1, 'quoteCount': 0,
        }]}

    monkeypatch.setattr(sp, 'get_json', fake_get)
    rows, status = sp.bluesky_metrics([entry])
    assert status == 'ok'
    assert rows[0]['metrics'] == {'likes': 4, 'reposts': 2, 'replies': 1, 'quotes': 0}
    assert rows[0]['impressions_available'] is False
    assert all('dailyyield.blogspot.com' not in url for url in called)


def test_facebook_keeps_real_engagement_when_insights_are_unavailable(monkeypatch):
    monkeypatch.setenv('FACEBOOK_SYSTEM_USER_TOKEN', 'test-token')
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith('/1303333369533572'):
            return {'access_token': 'page-token'}
        if url.endswith('/1303333369533572_42'):
            return {'shares': {'count': 2}, 'comments': {'summary': {'total_count': 3}}, 'reactions': {'summary': {'total_count': 5}}}
        if url.endswith('/insights'):
            raise RuntimeError('metric unavailable')
        raise AssertionError(url)

    monkeypatch.setattr(sp, 'get_json', fake_get)
    rows, status = sp.facebook_metrics([{'facebook_post_id': '1303333369533572_42'}])
    assert status == 'ok'
    assert rows[0]['metrics'] == {'shares': 2, 'comments': 3, 'reactions': 5}
    assert rows[0]['impressions_available'] is False


def test_missing_credentials_remain_unavailable_not_zero(monkeypatch):
    monkeypatch.delenv('FACEBOOK_SYSTEM_USER_TOKEN', raising=False)
    monkeypatch.delenv('TUMBLR_CONSUMER_KEY', raising=False)
    facebook, facebook_status = sp.facebook_metrics([])
    tumblr, tumblr_status = sp.tumblr_metrics([])
    assert facebook == [] and facebook_status.startswith('unavailable:')
    assert tumblr == [] and tumblr_status.startswith('unavailable:')
