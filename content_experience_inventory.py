#!/usr/bin/env python3
"""Authenticated zero-view inventory for feed, label, image and Page-shelf repairs."""
from __future__ import annotations
import hashlib, html, json, os, re
from pathlib import Path
import requests

BLOG_ID=os.environ['BLOGGER_BLOG_ID']
BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
OUT=Path('CONTENT_EXPERIENCE_INVENTORY.json')

def auth():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}

def list_all(kind,h):
 out=[];token=None
 while True:
  params={'fetchBodies':'true','maxResults':'50','status':'live'}
  if token:params['pageToken']=token
  r=requests.get(f'{BASE}/{kind}',headers=h,params=params,timeout=120);r.raise_for_status();data=r.json();out.extend(data.get('items',[]));token=data.get('nextPageToken')
  if not token:return out

def clean_src(src):
 src=html.unescape(src or '').strip()
 return re.sub(r'([?&])(w|h|q|fit|crop|auto)=[^&]+','',src).rstrip('?&')

def main():
 h=auth();posts=list_all('posts',h);pages=list_all('pages',h)
 image_owners={};post_rows=[]
 for p in posts:
  content=p.get('content','');imgs=[clean_src(x) for x in re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',content,re.I)];imgs=[x for x in imgs if x]
  hero=imgs[0] if imgs else ''
  if hero:image_owners.setdefault(hero,[]).append(p.get('id'))
  post_rows.append({'id':p.get('id'),'title':p.get('title'),'url':p.get('url'),'published':p.get('published'),'updated':p.get('updated'),'labels':p.get('labels',[]),'hero':hero,'image_count':len(imgs),'content_sha256':hashlib.sha256(content.encode()).hexdigest()})
 page_rows=[]
 for p in pages:
  c=p.get('content','');low=c.lower();needle='checking the shelves';at=low.find(needle)
  excerpt=c[max(0,at-1800):at+3200] if at>=0 else ''
  classes=sorted(set(re.findall(r'class=["\']([^"\']+)',excerpt,re.I)))
  ids=sorted(set(re.findall(r'id=["\']([^"\']+)',excerpt,re.I)))
  scripts=re.findall(r'<script\b[^>]*>(.*?)</script>',c,re.I|re.S)
  relevant_scripts=[s for s in scripts if 'ar-feedstatus' in s or '/feeds/posts' in s or 'ar-viewport' in s]
  page_rows.append({'id':p.get('id'),'title':p.get('title'),'url':p.get('url'),'updated':p.get('updated'),'content_length':len(c),'has_shelf_wait':at>=0,'shelf_excerpt':excerpt,'nearby_classes':classes,'nearby_ids':ids,'script_count':len(scripts),'relevant_scripts':relevant_scripts})
 duplicates=[{'hero':src,'post_ids':ids,'count':len(ids)} for src,ids in image_owners.items() if len(ids)>1]
 labels={}
 for p in post_rows:
  for label in p['labels']:labels[label]=labels.get(label,0)+1
 result={'zero_view':True,'post_count':len(post_rows),'page_count':len(page_rows),'posts':post_rows,'pages':page_rows,'duplicate_hero_groups':sorted(duplicates,key=lambda x:-x['count']),'label_counts':dict(sorted(labels.items(),key=lambda x:(-x[1],x[0].lower())))}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'posts':len(post_rows),'pages':len(page_rows),'duplicate_groups':len(duplicates),'shelf_pages':sum(x['has_shelf_wait'] for x in page_rows)}))
if __name__=='__main__':main()
