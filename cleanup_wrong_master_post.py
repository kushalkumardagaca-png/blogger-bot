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
from site_change_control import stop_if_frozen as _dy_stop_if_frozen
# The owner's rule of 22 October, placed at the program's entry point so that no combination of flags
# can reach the DELETE: a workflow, however it fails, must not take a published article down. A held
# run prints HELD_BY_OWNER_FREEZE and exits 0, because a held action is not a failure. Importing the
# module is left open so the tests and a dry read of the two addresses keep working.
if __name__ == '__main__':
 _dy_stop_if_frozen('cleanup_wrong_master_post')

def main():
 p=argparse.ArgumentParser();p.add_argument('--duplicate-url',required=True);p.add_argument('--replacement-url',required=True);p.add_argument('--expected-title-phrase',required=True);a=p.parse_args()
 if a.duplicate_url.rstrip('/')==a.replacement_url.rstrip('/'):raise RuntimeError('duplicate and replacement URLs are identical')
 access=token();replacement=by_url(a.replacement_url,access)
 # Blogger's getByPath response may omit `status` even for a publicly live post.
 # Authenticated existence plus an exact canonical URL proves the replacement;
 # reject only an explicit non-LIVE status.
 replacement_status=str((replacement or {}).get('status') or '').upper()
 replacement_url=str((replacement or {}).get('url') or '').rstrip('/')
 if not replacement or replacement_url!=a.replacement_url.rstrip('/') or (replacement_status and replacement_status!='LIVE'):
  raise RuntimeError('replacement is not confirmed LIVE; refusing cleanup')
 duplicate=by_url(a.duplicate_url,access)
 if not duplicate:
  print(json.dumps({'status':'PASS','action':'already_absent','duplicate':a.duplicate_url}));return
 duplicate_status=str(duplicate.get('status') or '').upper()
 if duplicate_status and duplicate_status!='LIVE':
  print(json.dumps({'status':'PASS','action':'already_not_live','duplicate':a.duplicate_url}));return
 if a.expected_title_phrase.casefold() not in str(duplicate.get('title','')).casefold():raise RuntimeError('duplicate title safety phrase did not match; refusing cleanup')
 call('/posts/'+urllib.parse.quote(str(duplicate['id'])),access,method='DELETE')
 print(json.dumps({'status':'PASS','action':'deleted_wrong_duplicate','duplicate':a.duplicate_url,'replacement':a.replacement_url}))
if __name__=='__main__':main()
