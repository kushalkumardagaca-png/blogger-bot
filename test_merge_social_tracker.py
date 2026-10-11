from merge_social_tracker import merge


def test_concurrent_social_records_are_union_merged_without_duplicates():
    current={'published':[{'bluesky_uri':'at://one','url':'https://example/one','published_at':'2026-10-11T01:00:00Z'}],'last_success_at':'2026-10-11T01:00:00Z'}
    stale={'published':[{'bluesky_uri':'at://two','url':'https://example/two','published_at':'2026-10-11T01:00:01Z'},{'bluesky_uri':'at://one','url':'https://example/one','published_at':'2026-10-11T01:00:00Z','reconciled':True}],'last_success_at':'2026-10-11T01:00:01Z'}
    result=merge(current,stale)
    assert [x['bluesky_uri'] for x in result['published']]==['at://one','at://two']
    assert result['published'][0]['reconciled'] is True
    assert result['last_success_at']=='2026-10-11T01:00:01Z'
