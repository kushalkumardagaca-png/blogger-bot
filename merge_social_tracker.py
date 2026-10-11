#!/usr/bin/env python3
"""Semantically merge a publisher's stale checkout into current durable state."""
import json,sys
from pathlib import Path

IDENTIFIERS=('facebook_post_id','bluesky_uri','mastodon_status_id','mastodon_url','tumblr_post_id','tumblr_url')

def identity(row):
    for key in IDENTIFIERS:
        if row.get(key):return key,str(row[key])
    return 'fallback','|'.join(str(row.get(k,'')) for k in ('url','caption_hash','text_hash','published_at'))

def merge(current,incoming):
    result={**current,**incoming}
    combined={}
    order=[]
    for row in list(current.get('published',[]))+list(incoming.get('published',[])):
        key=identity(row)
        if key not in combined:order.append(key);combined[key]=dict(row)
        else:combined[key].update(row)
    rows=[combined[key] for key in order]
    rows.sort(key=lambda row:str(row.get('published_at','')))
    result['published']=rows
    result['last_success_at']=max(str(current.get('last_success_at','')),str(incoming.get('last_success_at','')))
    return result

def main():
    if len(sys.argv)!=4:raise SystemExit('usage: merge_social_tracker.py CURRENT INCOMING OUTPUT')
    current=json.loads(Path(sys.argv[1]).read_text());incoming=json.loads(Path(sys.argv[2]).read_text())
    Path(sys.argv[3]).write_text(json.dumps(merge(current,incoming),indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
