#!/usr/bin/env python3
"""Install consented engaged-reader measurement in every live Blogger Post.

Uses the authenticated Blogger API only; it never opens a public Daily Yield URL.
The idempotent inline guard measures active reading, not page loading, and sends
one GA4 article_read event after 30 visible seconds plus 50% content depth.
"""
from __future__ import annotations

from site_change_control import stop_if_frozen as _dy_stop_if_frozen
if __name__ == "__main__":
    _dy_stop_if_frozen('reader_measurement_retrofit')

import json, os, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BLOG_ID=os.environ.get('BLOGGER_BLOG_ID',''); BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
MARK='DY_ENGAGED_READER_V2'
SNIPPET=r'''<!-- DY_ENGAGED_READER_V2 --><aside aria-label="Keep reading Daily Yield" data-dy-reader-actions="1" style="margin:34px 0 8px;padding:20px;border:1px solid #eadcc8;border-radius:16px;background:#fffaf0;color:#241610;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif"><strong style="display:block;font:700 22px/1.2 Georgia,serif">Make Daily Yield easier to find again.</strong><span style="display:block;margin:7px 0 15px;color:#6e5d4b;font-size:13px;line-height:1.55">Follow for the next useful money story, or share this article with someone making the same decision.</span><span style="display:flex;flex-wrap:wrap;gap:8px"><a data-dy-follow-intent="1" href="https://www.blogger.com/followers/follow/8911514070006792465" rel="noopener" target="_blank" style="padding:10px 14px;border-radius:10px;background:#241610;color:#fff;text-decoration:none;font-weight:800">Follow Daily Yield</a><button data-dy-share-intent="1" type="button" style="padding:10px 14px;border:1px solid #c99770;border-radius:10px;background:#fff;color:#241610;font-weight:800;cursor:pointer">Share this article</button></span></aside><script data-dy-engaged-reader="2">(function(){if(window.__dyEngagedReaderV2)return;window.__dyEngagedReaderV2=1;var D=document,H=D.documentElement,S=D.currentScript,A=S&&S.parentElement;if(!A)return;var active=0,depth=0,sent=false,last=Date.now();function consent(){try{return localStorage.getItem('dy-consent')==='all'}catch(e){return false}}function event(name,p){if(consent()&&typeof window.gtag==='function')window.gtag('event',name,p||{})}function tick(){var now=Date.now();if(D.visibilityState==='visible'&&D.hasFocus())active+=Math.min(2,(now-last)/1000);last=now;var r=A.getBoundingClientRect(),h=Math.max(1,A.scrollHeight),seen=Math.min(h,Math.max(0,innerHeight-r.top));depth=Math.max(depth,Math.round(seen/h*100));H.setAttribute('data-dy-read-seconds',String(Math.floor(active)));H.setAttribute('data-dy-read-depth',String(depth));if(!sent&&active>=30&&depth>=50&&consent()&&typeof window.gtag==='function'){sent=true;event('article_read',{article_path:location.pathname,engaged_seconds:Math.floor(active),scroll_percent:depth,engagement_threshold:'30s_50pct'});H.setAttribute('data-dy-article-read','sent')}}setInterval(tick,1000);addEventListener('scroll',tick,{passive:true});D.addEventListener('visibilitychange',function(){last=Date.now();tick()});var f=A.querySelector('[data-dy-follow-intent]'),b=A.querySelector('[data-dy-share-intent]');if(f)f.addEventListener('click',function(){event('follow_intent',{article_path:location.pathname})});if(b)b.addEventListener('click',function(){event('share_intent',{article_path:location.pathname});if(navigator.share)navigator.share({title:D.title,url:location.href}).catch(function(){});else navigator.clipboard&&navigator.clipboard.writeText(location.href).then(function(){b.textContent='Link copied'}).catch(function(){})});tick()}());</script><!-- /DY_ENGAGED_READER_V2 -->'''

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
  content=re.sub(r'<!-- DY_ENGAGED_READER_V1 -->.*?<!-- /DY_ENGAGED_READER_V1 -->','',content,flags=re.S)
  body={'kind':'blogger#post','id':post['id'],'title':post.get('title',''),'content':content+'\n'+SNIPPET,'labels':post.get('labels',[])}
  call('/posts/'+post['id'],tok,'PUT',body=body);changed.append({'id':post['id'],'url':post.get('url','')})
 report={'generatedAt':datetime.now(timezone.utc).isoformat(),'status':'PASS','livePostsScanned':len(posts),'instrumentedNow':len(changed),'alreadyInstrumented':already,'instrumentedTotal':already+len(changed),'metric':'article_read: 30 active seconds + 50% depth + analytics consent','retention':'Blogger follow and native share actions live on every Post','syntheticViews':0,'publicDailyYieldRequests':0}
 Path('READER_MEASUREMENT_STATUS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));return 0
if __name__=='__main__':raise SystemExit(main())
