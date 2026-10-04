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
  # Preserve the authenticated, non-script opening structure for visual diagnosis
  # without requesting or rendering the public Page (zero synthetic views).
  article_opening='';authenticated_design_source=''
  page_title=p.get('title','').strip().upper()
  if page_title in ('DAILY NEWS','DAILY ARTICLE','ABOUT US','CONTACT US','PRIVACY POLICY','DISCLAIMER','FINANCIAL DISCLAIMER'):
   # Public Page content, obtained through authenticated Blogger API only. This
   # enables exact local rendering and cross-Page design analysis with zero
   # public URL requests and therefore zero synthetic views.
   authenticated_design_source=c
  if page_title=='DAILY ARTICLE':
   root_at=c.find('id="articleHub"');first_section=c.find('class="ar-section"',root_at)
   if root_at>=0:
    article_opening=c[root_at:min(len(c),first_section if first_section>root_at else root_at+30000)]
    article_opening=re.sub(r'<script\b[^>]*>.*?</script>','[SCRIPT OMITTED]',article_opening,flags=re.I|re.S)
  page_rows.append({'id':p.get('id'),'title':p.get('title'),'url':p.get('url'),'updated':p.get('updated'),'content_length':len(c),'has_shelf_wait':at>=0,'shelf_excerpt':excerpt,'article_opening':article_opening,'authenticated_design_source':authenticated_design_source,'article_from_scratch':('DY_ARTICLE_FROM_SCRATCH_V1' in c and 'id="dyArticle"' in c and 'id="articleHub"' not in c),'article_legacy_absent':('DAILY ARTICLE EXPERIENCE' not in c and 'DY_CONTENT_EXPERIENCE_REPAIR_START' not in c and 'Checking the shelves' not in c),'article_static_card_count':c.count('class="dya-card"'),'article_desk_count':c.count('class="dya-desk"'),'article_authored_hero_present':('class="dya-hero"' in c and 'class="dya-note"' in c),'article_sticky_note_count':c.count('class="dya-sheet"'),'article_titles_left_aligned':('#dyArticle .dya-desk h2{' in c and 'text-align:left' in c),'article_clean_css_selectors':('#dyArticle .dya-hero{' in c and '#dyArticle .dya-card{' in c and '#dyArticle.dya-card' not in c),'article_no_broken_selectors':('#dyArticle.dya-hero' not in c and '#dyArticle.dya-card' not in c and '#dyArticle.dya-desk' not in c),'article_browser_engine':('function wire(row)' in c and 'row.scrollLeft+=72*dt' in c and 'row.scrollLeft=drag.left-dx' in c),'article_no_runtime_feed':('/feeds/posts' not in c),'article_render_ready':('DY_ARTICLE_FROM_SCRATCH_V1' in c and c.count('class="dya-desk"')==25 and c.count('class="dya-card"')>0 and '#dyArticle .dya-card{' in c and 'function wire(row)' in c),'policy_hero_scale':('DY_POLICY_HERO_SCALE_START' in c),'policy_hero_selector_repaired':('#enhancedSite.kvP-in.kvP-h1' not in c and '#enhancedSite.kc-htop h1' not in c),'nearby_classes':classes,'nearby_ids':ids,'script_count':len(scripts),'relevant_scripts':relevant_scripts})
 duplicates=[{'hero':src,'post_ids':ids,'count':len(ids)} for src,ids in image_owners.items() if len(ids)>1]
 labels={}
 for p in post_rows:
  for label in p['labels']:labels[label]=labels.get(label,0)+1
 result={'zero_view':True,'post_count':len(post_rows),'page_count':len(page_rows),'posts':post_rows,'pages':page_rows,'duplicate_hero_groups':sorted(duplicates,key=lambda x:-x['count']),'label_counts':dict(sorted(labels.items(),key=lambda x:(-x[1],x[0].lower())))}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'posts':len(post_rows),'pages':len(page_rows),'duplicate_groups':len(duplicates),'shelf_pages':sum(x['has_shelf_wait'] for x in page_rows)}))
if __name__=='__main__':main()
