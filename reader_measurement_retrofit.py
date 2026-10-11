#!/usr/bin/env python3
"""Install consented engaged-reader measurement in every live Blogger Post.

Uses the authenticated Blogger API only; it never opens a public Daily Yield URL.
The idempotent inline guard measures active reading, not page loading, and sends
one GA4 article_read event after 30 visible seconds plus 50% content depth.
"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BLOG_ID=os.environ.get('BLOGGER_BLOG_ID',''); BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
MARK='DY_ENGAGED_READER_V1'
SNIPPET=r'''<!-- DY_ENGAGED_READER_V1 --><script data-dy-engaged-reader="1">(function(){if(window.__dyEngagedReaderV1)return;window.__dyEngagedReaderV1=1;var D=document,H=D.documentElement,A=D.currentScript&&D.currentScript.parentElement;if(!A)return;var active=0,depth=0,sent=false,last=Date.now();function consent(){try{return localStorage.getItem('dy-consent')==='all'}catch(e){return false}}function tick(){var now=Date.now();if(D.visibilityState==='visible'&&D.hasFocus())active+=Math.min(2,(now-last)/1000);last=now;var r=A.getBoundingClientRect(),h=Math.max(1,A.scrollHeight),seen=Math.min(h,Math.max(0,innerHeight-r.top));depth=Math.max(depth,Math.round(seen/h*100));H.setAttribute('data-dy-read-seconds',String(Math.floor(active)));H.setAttribute('data-dy-read-depth',String(depth));if(!sent&&active>=30&&depth>=50&&consent()&&typeof window.gtag==='function'){sent=true;window.gtag('event','article_read',{article_path:location.pathname,engaged_seconds:Math.floor(active),scroll_percent:depth,engagement_threshold:'30s_50pct'});H.setAttribute('data-dy-article-read','sent')}}setInterval(tick,1000);addEventListener('scroll',tick,{passive:true});D.addEventListener('visibilitychange',function(){last=Date.now();tick()});tick()}());</script><!-- /DY_ENGAGED_READER_V1 -->'''

def token():
 data=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 req=urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST')
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)['access_token']
def call(path,tok,method='GET',body=None,params=None):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json','User-Agent':'DailyYield-ReaderMeasurement/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
def collect(tok):
 out=[];page=None
 while True:
  p={'fetchBodies':'true','maxResults':'50','status':'live'}
  if page:p['pageToken']=page
  d=call('/posts',tok,params=p);out+=d.get('items',[]);page=d.get('nextPageToken')
  if not page:return out
def main():
 if not BLOG_ID:raise RuntimeError('missing required secret: BLOGGER_BLOG_ID')
 tok=token();posts=collect(tok);changed=[];already=0
 for post in posts:
  content=post.get('content','')
  if MARK in content:already+=1;continue
  body={'kind':'blogger#post','id':post['id'],'title':post.get('title',''),'content':content+'\n'+SNIPPET,'labels':post.get('labels',[])}
  call('/posts/'+post['id'],tok,'PUT',body=body);changed.append({'id':post['id'],'url':post.get('url','')})
 report={'generatedAt':datetime.now(timezone.utc).isoformat(),'status':'PASS','livePostsScanned':len(posts),'instrumentedNow':len(changed),'alreadyInstrumented':already,'instrumentedTotal':already+len(changed),'metric':'article_read: 30 active seconds + 50% depth + analytics consent','syntheticViews':0,'publicDailyYieldRequests':0}
 Path('READER_MEASUREMENT_STATUS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));return 0
if __name__=='__main__':raise SystemExit(main())
