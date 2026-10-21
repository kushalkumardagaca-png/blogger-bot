#!/usr/bin/env python3
"""Remove only provider-verified extra article copies; never resource promotions.

Keeps the earliest provider-confirmed copy for each article/network, retains a
backup, and records durable deletion tombstones. No Blogger writes or new posts.
"""
from __future__ import annotations
import argparse,datetime as dt,html,json,os,re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote,urlparse
import requests
from social_dedupe import fresh_tracker,target_key
from merge_social_tracker import identity
from preapproval_audit import BloggerReader

ROOT=Path(__file__).resolve().parent
# Tumblr is no longer automated, so its posts are not part of a duplicate sweep either; the historical
# tracker stays on disk untouched and only live networks are considered here.
FIELDS={'facebook':'facebook_post_id','bluesky':'bluesky_uri','mastodon':'mastodon_status_id'}
NOW=lambda:dt.datetime.now(dt.timezone.utc).isoformat()


def carries_url(post,url):
    text=html.unescape(unquote(json.dumps(post,ensure_ascii=False)))
    return url in text


def candidates(rows,since,live_urls):
    grouped=defaultdict(dict)
    for row in rows:
        url=row.get('url','')
        if row.get('kind','post')!='post' or not re.fullmatch(r'/20\d\d/\d\d/[^/]+\.html',urlparse(url).path):continue
        if target_key(url) not in live_urls:continue
        grouped[target_key(url)][identity(row)]=row
    return [(url,sorted(group.values(),key=lambda r:r.get('published_at',''))) for url,group in grouped.items()
            if len(group)>1 and any(r.get('published_at','')>=since for r in group.values())]


class Facebook:
    def __init__(self):
        from facebook_publisher import resolve_page_token,GRAPH_ROOT,PAGE_ID
        self.root=GRAPH_ROOT;self.page_id=PAGE_ID
        page,self.access=resolve_page_token(os.environ['FACEBOOK_SYSTEM_USER_TOKEN'])
        if str(page.get('id'))!=str(PAGE_ID):raise RuntimeError('unexpected Facebook owner page')
    def read(self,ident):
        if not str(ident).startswith(str(self.page_id)+'_'):raise RuntimeError('post not on approved Facebook page')
        response=requests.get(self.root+'/'+str(ident),params={'fields':'id,message,created_time','access_token':self.access},timeout=30)
        if not response.ok:raise RuntimeError('Facebook read HTTP '+str(response.status_code))
        return response.json()
    def remove(self,ident):
        response=requests.delete(self.root+'/'+str(ident),params={'access_token':self.access},timeout=30)
        if not response.ok:raise RuntimeError('Facebook delete HTTP '+str(response.status_code))
        data=response.json()
        if data is not True and not (isinstance(data,dict) and data.get('success') is True):raise RuntimeError('Facebook did not acknowledge deletion')




def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--since',default='2026-10-17')
    args=parser.parse_args();reader=BloggerReader()
    live={target_key(p['url']) for p in reader.collect('posts',bodies=False) if p.get('url')}
    result={'checkedAt':NOW(),'apply':args.apply,'scope':'Provider-verified extra copies of live articles since '+args.since,
            'siteWrites':0,'newSocialPosts':0,'kept':[],'deleted':[],'blocked':[],'candidates':0}
    backup={}
    for platform,key in FIELDS.items():
        tracker=fresh_tracker(platform);backup[platform]=json.loads(json.dumps(tracker))
        groups=candidates(tracker.get('published',[]),args.since,live)
        result['candidates']+=sum(len(rows)-1 for _,rows in groups)
        if not groups:continue
        if platform != 'facebook':
            result['blocked'].append({'platform':platform,'reason':'No automatic deletion adapter enabled; preserved all copies.'});continue
        try:provider=Facebook()
        except Exception as exc:
            result['blocked'].append({'platform':platform,'reason':'Provider authorization/read unavailable','errorType':type(exc).__name__});continue
        removed=[]
        for url,rows in groups:
            keep=rows[0];keep_id=keep.get(key)
            try:
                actual=provider.read(keep_id)
                if not carries_url(actual,url):raise RuntimeError('kept provider post does not prove destination')
            except Exception as exc:
                result['blocked'].append({'platform':platform,'url':url,'reason':'Earliest copy not verified','errorType':type(exc).__name__});continue
            result['kept'].append({'platform':platform,'url':url,'id':keep_id})
            for row in rows[1:]:
                ident=row.get(key)
                try:
                    actual=provider.read(ident)
                    if not carries_url(actual,url):raise RuntimeError('duplicate provider post does not prove destination')
                    if not args.apply:continue
                    backup.setdefault('providerPosts', {})[platform+'/'+str(ident)] = actual
                    Path('/tmp/table3-social-cleanup-backup.json').write_text(json.dumps(backup,ensure_ascii=False))
                    provider.remove(ident)
                    tombstone={key:str(ident),'url':url,'kind':'post','deleted_at':NOW(),'kept_id':str(keep_id),
                               'reason':'same live article, same verified owner network, provider-confirmed extra copy'}
                    tracker.setdefault('deleted',[]).append(tombstone);removed.append(str(ident))
                    result['deleted'].append({'platform':platform,'url':url,'id':str(ident),'keptId':str(keep_id),'providerAcknowledged':True})
                except Exception as exc:
                    result['blocked'].append({'platform':platform,'url':url,'id':str(ident),'reason':'Not deleted without successful verification and acknowledgement','errorType':type(exc).__name__})
        if args.apply and removed:
            tracker['published']=[r for r in tracker.get('published',[]) if str(r.get(key)) not in removed]
            (ROOT/(platform+'_tracker.json')).write_text(json.dumps(tracker,indent=2,ensure_ascii=False)+'\n')
    result['status']='CHECKED_WITH_LIMITS' if result['blocked'] else ('REMOVED_VERIFIED_DUPLICATES' if result['deleted'] else 'NO_VERIFIED_DUPLICATES_TO_REMOVE')
    (ROOT/'SOCIAL_DUPLICATE_CLEANUP_STATUS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    # Recovery evidence goes to a retained artifact, not a public website.
    Path('/tmp/table3-social-cleanup-backup.json').write_text(json.dumps(backup,ensure_ascii=False))
    print(json.dumps({'status':result['status'],'candidates':result['candidates'],'deleted':len(result['deleted']),'blocked':len(result['blocked']),'siteWrites':0}))
    return 0

if __name__=='__main__':raise SystemExit(main())
