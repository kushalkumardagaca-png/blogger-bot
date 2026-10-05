#!/usr/bin/env python3
"""Back up and replace one legacy master Post with a validated Master V2 package.

Two phases make an irreversible Blogger update impossible until the original full
API representation has been committed separately. The script never touches News
or Pages and never creates a replacement Post; it updates the original Post ID.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,re
from datetime import datetime,timezone
from pathlib import Path
import requests
from brand_identity import ensure_brand_identity
from continuous_motion import ensure as ensure_continuous_motion
from master_article_v2 import render,validate
from prepare_master_article import build_package
from publication_preflight import assert_publishable
from seo_meta import ensure_seo_meta
from social_identity import ensure_social_identity

ROOT=Path(__file__).parent
STATE=ROOT/'MASTER_REWRITE_STATE.json';REPORT=ROOT/'MASTER_REWRITE_REPORT.json'
BACKUPS=ROOT/'master_rewrite_backups';PACKAGES=ROOT/'master_packages'/'rewrites'
AUTHOR='Kushal K. Daga';MARKER='<!-- DY_MASTER_V2 -->'

def required(name):
 value=os.environ.get(name,'').strip()
 if not value:raise RuntimeError(name+' is required')
 return value

def auth():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':required('BLOGGER_CLIENT_ID'),'client_secret':required('BLOGGER_CLIENT_SECRET'),'refresh_token':required('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return r.json()['access_token']

def base():return f"https://www.googleapis.com/blogger/v3/blogs/{required('BLOGGER_BLOG_ID')}"
def headers(token):return {'Authorization':'Bearer '+token,'Content-Type':'application/json'}
def digest(text):return hashlib.sha256((text or '').encode()).hexdigest()

def load_state():
 if STATE.exists():return json.loads(STATE.read_text())
 return {'version':1,'completed':{},'pending':None}
def save_state(state):STATE.write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
def save_report(status,**data):REPORT.write_text(json.dumps({'status':status,'at':datetime.now(timezone.utc).isoformat(),**data},indent=2)+'\n')

def inventory(token):
 out=[];page=None
 while True:
  params={'status':'live','fetchBodies':'true','maxResults':50,'fields':'items(id,title,url,content,labels,published,updated),nextPageToken'}
  if page:params['pageToken']=page
  r=requests.get(base()+'/posts',headers=headers(token),params=params,timeout=90);r.raise_for_status();data=r.json();out.extend(data.get('items',[]));page=data.get('nextPageToken')
  if not page:return out

def is_master(post):
 labels=post.get('labels') or []
 return AUTHOR in labels and 'News' not in labels

def backup_next():
 token=auth();state=load_state()
 if state.get('pending'):
  pending=state['pending'];path=ROOT/pending['backup']
  if not path.exists():raise RuntimeError('pending rewrite backup is missing')
  save_report('BACKUP_READY',pending=pending,master_count=state.get('inventory_master_count'),remaining=state.get('inventory_master_count',0)-len(state.get('completed',{})))
  print(pending['id']);return
 posts=inventory(token);masters=sorted((p for p in posts if is_master(p)),key=lambda x:(x.get('published',''),x['id']))
 for post in masters:
  if MARKER in (post.get('content') or ''):
   state['completed'].setdefault(post['id'],{'url':post.get('url'),'title':post.get('title'),'status':'already-v2'})
 for post in masters:
  if post['id'] in state['completed']:continue
  BACKUPS.mkdir(exist_ok=True);path=BACKUPS/f"post_{post['id']}.json.gz"
  with gzip.open(path,'wt',encoding='utf-8') as f:json.dump(post,f,ensure_ascii=False)
  state['pending']={'id':post['id'],'title':post.get('title'),'url':post.get('url'),'published':post.get('published'),'labels':post.get('labels') or [],'content_sha256':digest(post.get('content')),'backup':str(path.relative_to(ROOT))}
  state['inventory_master_count']=len(masters);state['inventory_completed_count']=len(state['completed']);save_state(state)
  save_report('BACKUP_READY',pending=state['pending'],master_count=len(masters),remaining=len(masters)-len(state['completed']))
  print(post['id']);return
 state['pending']=None;save_state(state);save_report('COMPLETE',master_count=len(masters),completed=len(state['completed']),remaining=0);print('COMPLETE')

def rewrite_pending(apply=False):
 token=auth();state=load_state();pending=state.get('pending')
 if not pending:raise RuntimeError('no durably backed-up master rewrite is pending')
 post_id=pending['id'];r=requests.get(base()+'/posts/'+post_id,headers=headers(token),timeout=60);r.raise_for_status();post=r.json()
 if not is_master(post):raise RuntimeError('pending Blogger item no longer qualifies as a master Post')
 if digest(post.get('content'))!=pending['content_sha256']:raise RuntimeError('live Post changed after backup; refusing stale overwrite')
 labels=post.get('labels') or [];category=next((x for x in labels if x not in (AUTHOR,'News')),'Daily Article')
 topic={'#':'rewrite-'+post_id,'Punchy Title':post.get('title',''),'Video Idea':post.get('title',''),'Category':category}
 package_path=PACKAGES/f'post_{post_id}.json';package=build_package(topic,package_path);validate(package)
 if not apply:
  save_report('PACKAGE_READY',post_id=post_id,package=str(package_path.relative_to(ROOT)),title=package['title']);print(package_path);return
 published=post.get('published') or datetime.now(timezone.utc).isoformat();pub_date=published[:10];pub_time=published[11:16]
 now=datetime.now(timezone.utc);title,slug,meta,new_labels,body=render(package,topic,pub_date,pub_time,canonical_url=post.get('url'),modified_date=now.date().isoformat(),modified_time=now.strftime('%H:%M'))
 first=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I)
 body=ensure_seo_meta(body,title,meta,first.group(1) if first else '')
 body=ensure_social_identity(ensure_brand_identity(body));body=ensure_continuous_motion(body)
 assert_publishable(title,body,labels)
 payload={'kind':'blogger#post','id':post_id,'title':title,'content':body,'labels':labels}
 updated=requests.put(base()+'/posts/'+post_id,headers=headers(token),json=payload,timeout=120);updated.raise_for_status();result=updated.json()
 check=requests.get(base()+'/posts/'+post_id,headers=headers(token),timeout=60);check.raise_for_status();live=check.json()
 if MARKER not in (live.get('content') or '') or live.get('title')!=title or live.get('url')!=post.get('url'):raise RuntimeError('authenticated Blogger reread did not match the intended in-place rewrite')
 state['completed'][post_id]={'url':live.get('url'),'old_title':pending['title'],'title':title,'content_sha256':digest(live.get('content')),'status':'rewritten-v2','verified_at':datetime.now(timezone.utc).isoformat()};state['pending']=None;save_state(state)
 save_report('PASS',post_id=post_id,url=live.get('url'),old_title=pending['title'],title=title,completed=len(state['completed']),master_count=state.get('inventory_master_count'))
 print(live.get('url'))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('backup-next','prepare-pending','apply-pending'));args=parser.parse_args()
 try:
  backup_next() if args.phase=='backup-next' else rewrite_pending(apply=args.phase=='apply-pending')
 except Exception as exc:
  save_report('FAIL',phase=args.phase,error_type=type(exc).__name__,error=str(exc)[:1200]);raise
if __name__=='__main__':main()
