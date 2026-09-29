#!/usr/bin/env python3
"""Repair explicitly verified malformed external links through Blogger API only."""
import json, os, urllib.parse, urllib.request
BLOG_ID=os.environ['BLOGGER_BLOG_ID']
OLD='https://www.sebi.gov.in/https://www.sebi.gov.in/sebi_data/attachdocs/sep-2026/ORDER_1790584774.pdf'
NEW='https://www.sebi.gov.in/sebi_data/attachdocs/sep-2026/ORDER_1790584774.pdf'
PATH='/2026/09/india-2026-09-29.html'

def call(url,token,method='GET',body=None):
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
form=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=form,method='POST'),timeout=30) as r:token=json.load(r)['access_token']
base=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
post=call(base+'/posts/bypath?'+urllib.parse.urlencode({'path':PATH}),token)
content=post.get('content','')
if OLD not in content:
 print('Known malformed SEBI URL is not present; no update required.')
 raise SystemExit(0)
updated=content.replace(OLD,NEW)
body={'kind':'blogger#post','id':post['id'],'title':post['title'],'content':updated,'labels':post.get('labels',[])}
result=call(base+'/posts/'+post['id'],token,'PUT',body)
if OLD in result.get('content','') or NEW not in result.get('content',''):raise RuntimeError('Blogger did not persist the exact link repair')
print(f"Repaired one malformed SEBI source link in Blogger post {post['id']}.")
