#!/usr/bin/env python3
"""Generation-free batch refresh of editorial photos on selected live Master V2 posts."""
from __future__ import annotations
import gzip,json,re
from datetime import datetime,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).parent
REPORT=ROOT/'MASTER_PHOTO_REFRESH_REPORT.json'
BACKUPS=ROOT/'master_photo_refresh_backups'
TARGETS=['9090794225984393149','5283900934510767783','1224431701070336470','8594486389302937562','5564629106804601974']
AUTHOR='Kushal K. Daga';MARKER='<!-- DY_MASTER_V2 -->'

def save(status,**data):
 REPORT.write_text(json.dumps({'status':status,'at':datetime.now(timezone.utc).isoformat(),**data},indent=2)+'\n')

def main():
 from brand_identity import ensure_brand_identity
 from continuous_motion import ensure as ensure_continuous_motion
 from master_article_v2 import render,validate
 from publication_preflight import assert_publishable
 from rewrite_existing_masters import auth,base,headers,is_master
 from seo_meta import ensure_seo_meta
 from social_identity import ensure_social_identity
 token=auth(); prepared=[];BACKUPS.mkdir(exist_ok=True)
 # Back up and fully preflight every item before the first irreversible update.
 for post_id in TARGETS:
  r=requests.get(base()+'/posts/'+post_id,headers=headers(token),timeout=60);r.raise_for_status();post=r.json()
  if not is_master(post):raise RuntimeError(f'{post_id} is not an eligible Master Post')
  backup=BACKUPS/f'post_{post_id}.json.gz'
  with gzip.open(backup,'wt',encoding='utf-8') as f:json.dump(post,f,ensure_ascii=False)
  package=json.loads((ROOT/f'master_packages/rewrites/post_{post_id}.json').read_text());metrics=validate(package)
  labels=post.get('labels') or [];category=next((x for x in labels if x not in (AUTHOR,'News')),'Daily Article')
  topic={'#':'photo-refresh-'+post_id,'Punchy Title':post.get('title',''),'Video Idea':post.get('title',''),'Category':category}
  published=post.get('published') or datetime.now(timezone.utc).isoformat();now=datetime.now(timezone.utc)
  title,slug,meta,new_labels,body=render(package,topic,published[:10],published[11:16],canonical_url=post.get('url'),modified_date=now.date().isoformat(),modified_time=now.strftime('%H:%M'))
  first=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I)
  body=ensure_seo_meta(body,title,meta,first.group(1) if first else '')
  body=ensure_social_identity(ensure_brand_identity(body));body=ensure_continuous_motion(body)
  assert_publishable(title,body,labels)
  photo_urls=[x['url'] for x in package['photos']]
  if not all(u in body for u in photo_urls):raise RuntimeError(f'{post_id} rendered body is missing a replacement photo')
  prepared.append((post,package,title,body,photo_urls,metrics,str(backup.relative_to(ROOT))))
 save('BACKUP_READY',targets=TARGETS,backups=[x[6] for x in prepared])
 results=[]
 for post,package,title,body,photo_urls,metrics,backup in prepared:
  post_id=post['id'];payload={'kind':'blogger#post','id':post_id,'title':title,'content':body,'labels':post.get('labels') or []}
  r=requests.put(base()+'/posts/'+post_id,headers=headers(token),json=payload,timeout=120);r.raise_for_status()
  c=requests.get(base()+'/posts/'+post_id,headers=headers(token),timeout=60);c.raise_for_status();live=c.json();content=live.get('content') or ''
  if MARKER not in content or live.get('title')!=title or live.get('url')!=post.get('url') or not all(u in content for u in photo_urls):
   raise RuntimeError(f'authenticated reread failed for {post_id}')
  results.append({'post_id':post_id,'url':live.get('url'),'title':title,'photos':photo_urls,'metrics':metrics,'backup':backup,'verified_at':datetime.now(timezone.utc).isoformat()})
 save('PASS',count=len(results),results=results)
 print(json.dumps({'status':'PASS','count':len(results)}))

if __name__=='__main__':
 try:main()
 except Exception as exc:
  message=str(exc)[:1600].replace('%','%25').replace('\r','%0D').replace('\n','%0A')
  save('FAIL',error_type=type(exc).__name__,error=str(exc)[:1600])
  print(f'::error title=Master photo refresh failure::{message}',flush=True)
  raise
