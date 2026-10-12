#!/usr/bin/env python3
"""Delete one proven-wrong duplicate only after its replacement is live.

Uses the authenticated Blogger API and never opens the public website. The safety
checks make reruns idempotent and prevent deletion when the replacement is absent.
"""
from __future__ import annotations
import argparse,json,os,urllib.error,urllib.parse,urllib.request

def token():
 data=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST'),timeout=30) as r:return json.load(r)['access_token']
def call(path,access,method='GET'):
 url=f"https://www.googleapis.com/blogger/v3/blogs/{os.environ['BLOGGER_BLOG_ID']}{path}"
 req=urllib.request.Request(url,method=method,headers={'Authorization':'Bearer '+access})
 try:
  with urllib.request.urlopen(req,timeout=60) as r:
   raw=r.read();return json.loads(raw) if raw else {}
 except urllib.error.HTTPError as exc:
  if exc.code==404:return None
  raise
def by_url(url,access):
 path=urllib.parse.urlparse(url).path
 query=urllib.parse.urlencode({'path':path,'fields':'id,title,url,status'})
 return call('/posts/bypath?'+query,access)
def main():
 p=argparse.ArgumentParser();p.add_argument('--duplicate-url',required=True);p.add_argument('--replacement-url',required=True);p.add_argument('--expected-title-phrase',required=True);a=p.parse_args()
 if a.duplicate_url.rstrip('/')==a.replacement_url.rstrip('/'):raise RuntimeError('duplicate and replacement URLs are identical')
 access=token();replacement=by_url(a.replacement_url,access)
 if not replacement or replacement.get('status')!='LIVE':raise RuntimeError('replacement is not confirmed LIVE; refusing cleanup')
 duplicate=by_url(a.duplicate_url,access)
 if not duplicate:
  print(json.dumps({'status':'PASS','action':'already_absent','duplicate':a.duplicate_url}));return
 if duplicate.get('status')!='LIVE':
  print(json.dumps({'status':'PASS','action':'already_not_live','duplicate':a.duplicate_url}));return
 if a.expected_title_phrase.casefold() not in str(duplicate.get('title','')).casefold():raise RuntimeError('duplicate title safety phrase did not match; refusing cleanup')
 call('/posts/'+urllib.parse.quote(str(duplicate['id'])),access,method='DELETE')
 print(json.dumps({'status':'PASS','action':'deleted_wrong_duplicate','duplicate':a.duplicate_url,'replacement':a.replacement_url}))
if __name__=='__main__':main()
