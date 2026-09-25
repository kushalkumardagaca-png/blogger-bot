#!/usr/bin/env python3
"""Sitewide continuous gesture motion plus topic-related article shelves."""
from pathlib import Path
import json,os,urllib.parse,urllib.request
from continuous_motion import ensure as ensure_motion
from related_articles import ensure as ensure_related
BLOG_ID=os.environ['BLOGGER_BLOG_ID'];BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}';APPLY=os.environ.get('APPLY','false').lower()=='true'
def token():
 data=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST'),timeout=30) as r:return json.load(r)['access_token']
def call(path,tok,method='GET',body=None,params=None):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '');req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
def collect(kind,tok):
 out=[];page=None
 while True:
  p={'fetchBodies':'true','maxResults':'50'}
  if kind=='posts':p['orderBy']='published'
  if page:p['pageToken']=page
  d=call('/'+kind,tok,params=p);out+=d.get('items',[]);page=d.get('nextPageToken')
  if not page:return out
def update(kind,tok,item,content):
 body={'kind':'blogger#'+('page' if kind=='pages' else 'post'),'id':item['id'],'title':item['title'],'content':content}
 if kind=='posts':body['labels']=item.get('labels',[])
 if APPLY:call('/'+kind+'/'+item['id'],tok,'PUT',body=body)
def main():
 tok=token();pages=collect('pages',tok);posts=collect('posts',tok);Path('motion_related_backup.json').write_text(json.dumps({'pages':pages,'posts':posts},ensure_ascii=False));changes=[]
 for p in pages:
  old=p.get('content','');new=old.replace('if(!s.visible||s.hover||s.focus||s.touchUntil>Date.now())return;','if(!s.visible)return;');new=ensure_motion(new)
  if new!=old:update('pages',tok,p,new);changes.append({'kind':'page','url':p.get('url'),'related':0,'article_motion_loop_repaired':new.count('if(!s.visible)return;')>old.count('if(!s.visible)return;')})
 for p in posts:
  old=p.get('content','');new=ensure_related(old,p,posts);new=ensure_motion(new)
  if new!=old:update('posts',tok,p,new);changes.append({'kind':'post','url':p.get('url'),'related':new.count('class="dy-related-card"')//2})
 result={'apply':APPLY,'pages_scanned':len(pages),'posts_scanned':len(posts),'changes':changes,'related_shelves':sum(x['kind']=='post' and x['related']>=3 for x in changes)};Path('MOTION_RELATED_AUDIT.json').write_text(json.dumps(result,indent=2));print(json.dumps({'apply':APPLY,'pages':len(pages),'posts':len(posts),'changes':len(changes),'shelves':result['related_shelves']},indent=2))
if __name__=='__main__':main()
