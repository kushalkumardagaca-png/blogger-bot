"""Refresh already-published Master V2 posts after renderer-only design upgrades.

Uses authenticated Blogger API reads and exact reread verification; it never opens a
public post URL and therefore creates no synthetic pageview.
"""
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from master_article_v2 import render,validate

ROOT=Path(__file__).parent
BLOG_ID=os.environ.get('BLOGGER_BLOG_ID','')
TARGETS=(
 {'post_id':'76036352328662163','package':'master_packages/rewrites/post_76036352328662163.json'},
 {'url':'https://dailyyield.blogspot.com/2026/10/your-tax-refund-is-trap.html','package':'master_packages/topic_4.json'},
)

def token():
 required=('BLOGGER_CLIENT_ID','BLOGGER_CLIENT_SECRET','BLOGGER_REFRESH_TOKEN','BLOGGER_BLOG_ID')
 missing=[key for key in required if not os.environ.get(key)]
 if missing:raise RuntimeError('missing Blogger credentials: '+', '.join(missing))
 creds=Credentials(None,refresh_token=os.environ['BLOGGER_REFRESH_TOKEN'],token_uri='https://oauth2.googleapis.com/token',client_id=os.environ['BLOGGER_CLIENT_ID'],client_secret=os.environ['BLOGGER_CLIENT_SECRET'],scopes=['https://www.googleapis.com/auth/blogger'])
 creds.refresh(Request());return creds.token

def api():return f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
def headers(access):return {'Authorization':'Bearer '+access,'Content-Type':'application/json'}
def digest(text):return hashlib.sha256((text or '').encode()).hexdigest()

def inventory(access):
 items=[];page=None
 while True:
  params={'fetchBodies':'false','maxResults':500,'status':'live'}
  if page:params['pageToken']=page
  r=requests.get(api()+'/posts',headers=headers(access),params=params,timeout=60);r.raise_for_status();data=r.json();items.extend(data.get('items',[]));page=data.get('nextPageToken')
  if not page:return items

def main():
 access=token();posts=inventory(access);by_url={p.get('url'):p.get('id') for p in posts};results=[]
 for target in TARGETS:
  post_id=target.get('post_id') or by_url.get(target.get('url'))
  if not post_id:raise RuntimeError('target post could not be found through authenticated inventory')
  r=requests.get(api()+'/posts/'+post_id,headers=headers(access),timeout=60);r.raise_for_status();live=r.json()
  package=json.loads((ROOT/target['package']).read_text());validate(package)
  published=datetime.fromisoformat(live['published'].replace('Z','+00:00')).astimezone(timezone.utc)
  now=datetime.now(timezone.utc);labels=live.get('labels') or [];category=next((x for x in labels if x!='Kushal K. Daga'),'Daily Article')
  topic={'#':'refresh','Category':category,'Punchy Title':package['title']}
  title,slug,meta,new_labels,body=render(package,topic,published.strftime('%Y-%m-%d'),published.strftime('%H:%M'),canonical_url=live.get('url'),modified_date=now.strftime('%Y-%m-%d'),modified_time=now.strftime('%H:%M'))
  payload={'kind':'blogger#post','id':post_id,'title':title,'content':body,'labels':labels}
  put=requests.put(api()+'/posts/'+post_id,headers=headers(access),json=payload,timeout=120);put.raise_for_status()
  check=requests.get(api()+'/posts/'+post_id,headers=headers(access),timeout=60);check.raise_for_status();confirmed=check.json()
  expected={'id':post_id,'url':live.get('url'),'published':live.get('published'),'labels':labels,'title':title,'content_sha256':digest(body)}
  actual={'id':confirmed.get('id'),'url':confirmed.get('url'),'published':confirmed.get('published'),'labels':confirmed.get('labels') or [],'title':confirmed.get('title'),'content_sha256':digest(confirmed.get('content'))}
  if actual!=expected:raise RuntimeError('authenticated Blogger reread did not exactly match refreshed post '+post_id)
  results.append({'post_id':post_id,'url':actual['url'],'title':title,'status':'design-refreshed','content_sha256':actual['content_sha256']})
 (ROOT/'MASTER_V2_DESIGN_REFRESH_REPORT.json').write_text(json.dumps({'status':'PASS','at':datetime.now(timezone.utc).isoformat(),'results':results},indent=2)+'\n')
 print(json.dumps(results,indent=2))

if __name__=='__main__':main()
