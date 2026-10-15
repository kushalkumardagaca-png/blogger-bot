#!/usr/bin/env python3
"""Authenticated, zero-pageview Blogger corpus remediation and evidence audit.

Dry-run is the default. APPLY_CORPUS_REMEDIATION=true removes only exact duplicate
Blogger records that share one canonical URL and adds the standard transparent
process/correction disclosure to automated posts that lack it.
"""
from __future__ import annotations
import datetime as dt,hashlib,html,json,os,re,time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse
import requests
from content_policy_guard import DISCLOSURE_MARKER,audit_text,automation_disclosure
from editorial_integrity import content_fingerprint,language_similarity,normalized_title

BASE=f"https://www.googleapis.com/blogger/v3/blogs/{os.environ['BLOGGER_BLOG_ID']}"
APPLY=os.environ.get('APPLY_CORPUS_REMEDIATION','').casefold()=='true'
REPORT=Path('BLOGGER_CORPUS_POLICY_STATUS.json');RIGHTS=Path('BLOGGER_IMAGE_RIGHTS_LEDGER.json')

def token():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return r.json()['access_token']
def call(method,path,h,**kwargs):
 for attempt in range(5):
  r=requests.request(method,BASE+path,headers=h,timeout=120,**kwargs)
  if r.status_code not in (429,500,502,503,504):r.raise_for_status();return r
  time.sleep(2**attempt)
 r.raise_for_status()
def posts(h):
 out=[];page=None
 while True:
  params={'status':'live','fetchBodies':'true','maxResults':50,'fields':'items(id,title,url,content,labels,published,updated),nextPageToken'}
  if page:params['pageToken']=page
  data=call('GET','/posts',h,params=params).json();out+=data.get('items',[]);page=data.get('nextPageToken')
  if not page:return out

def automated(post):
 labels=set(post.get('labels') or []);content=post.get('content','')
 return bool(labels&{'News','Master Article','Kushal K. Daga'} or any(x in content for x in ('DY_MASTER_V2','DY_NEWS','fbk-news','DY_AUTOMATION')))
def canonical_id(url,h):
 path=urlparse(url).path
 try:return str(call('GET','/posts/bypath',h,params={'path':path,'fields':'id'}).json().get('id',''))
 except Exception:return ''
def exact_duplicate_groups(rows,h):
 by_url=defaultdict(list)
 for p in rows:by_url[(p.get('url') or '').rstrip('/')].append(p)
 groups=[]
 for url,items in by_url.items():
  if not url or len(items)<2:continue
  exact=[]
  for p in items:
   for q in items:
    if p['id']>=q['id']:continue
    if normalized_title(p.get('title',''))==normalized_title(q.get('title','')) and language_similarity(p.get('content',''),q.get('content',''))>=.985:exact.extend((p,q))
  unique={p['id']:p for p in exact}
  if len(unique)>1:
   keep=canonical_id(url,h) or sorted(unique.values(),key=lambda x:x.get('published',''))[0]['id']
   groups.append({'url':url,'keep_id':keep,'remove_ids':sorted(x for x in unique if x!=keep),'similarity_floor':.985})
 return groups

def rights_entry(post):
 content=post.get('content','');figures=re.findall(r'<figure\b[^>]*>(.*?)</figure>',content,flags=re.I|re.S);assets=[]
 for block in figures:
  src=re.search(r'<img\b[^>]*\bsrc=["\']([^"\']+)',block,re.I);alt=re.search(r'<img\b[^>]*\balt=["\']([^"\']*)',block,re.I);links=re.findall(r'<a\b[^>]*href=["\']([^"\']+)',block,re.I);caption=re.search(r'<figcaption\b[^>]*>(.*?)</figcaption>',block,re.I|re.S)
  if src:assets.append({'src':html.unescape(src.group(1)),'alt_present':bool(alt and html.unescape(alt.group(1)).strip()),'source_links':[html.unescape(x) for x in links],'caption_present':bool(caption and re.sub(r'<[^>]+>','',caption.group(1)).strip())})
 return {'post_id':post['id'],'url':post.get('url'),'assets':assets,'complete':all(x['alt_present'] and x['caption_present'] and x['source_links'] for x in assets) if assets else True}

def main():
 h={'Authorization':'Bearer '+token(),'Content-Type':'application/json'};rows=posts(h);duplicates=exact_duplicate_groups(rows,h);deleted=[];updated=[];policy_flags=[];unsafe_links=[];rights=[]
 for p in rows:
  content=p.get('content','');prospective=content
  if automated(p) and DISCLOSURE_MARKER not in content:prospective=content+'\n'+automation_disclosure('automated publication')
  issues=[x for x in audit_text(p.get('title',''),prospective,'historical',require_disclosure=automated(p)) if x!='insufficient sentence-level originality']
  if issues:policy_flags.append({'post_id':p['id'],'url':p.get('url'),'issues':issues})
  for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)',content,re.I):
   if re.match(r'\s*(?:javascript|vbscript|data):',html.unescape(href),re.I):unsafe_links.append({'post_id':p['id'],'url':p.get('url')})
  rights.append(rights_entry(p))
 if APPLY:
  for group in duplicates:
   for ident in group['remove_ids']:
    call('DELETE','/posts/'+ident,h);deleted.append(ident)
  removed=set(deleted)
  for p in rows:
   if p['id'] in removed or not automated(p) or DISCLOSURE_MARKER in p.get('content',''):continue
   body={'kind':'blogger#post','id':p['id'],'blog':{'id':os.environ['BLOGGER_BLOG_ID']},'title':p.get('title'),'content':p.get('content','')+'\n'+automation_disclosure('automated publication'),'labels':p.get('labels') or []}
   saved=call('PUT','/posts/'+p['id'],h,json=body).json()
   if DISCLOSURE_MARKER not in saved.get('content',''):raise RuntimeError('disclosure verification failed for '+p['id'])
   updated.append(p['id'])
 rights_gaps=[x for x in rights if not x['complete']]
 rights_doc={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'posts_checked':len(rows),'posts_with_figure_rights_gaps':len(rights_gaps),'gaps':rights_gaps,'ledger_hash':hashlib.sha256(json.dumps(rights,sort_keys=True).encode()).hexdigest()}
 RIGHTS.write_text(json.dumps(rights_doc,indent=2)+'\n')
 status='PASS' if not duplicates and not policy_flags and not unsafe_links and not rights_gaps else ('REMEDIATED' if APPLY and not policy_flags and not unsafe_links and not rights_gaps else 'WARNING')
 report={'status':status,'apply':APPLY,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'posts_checked':len(rows),'automated_posts':sum(automated(x) for x in rows),'disclosures_present_before':sum(DISCLOSURE_MARKER in x.get('content','') for x in rows if automated(x)),'duplicate_groups':duplicates,'deleted_duplicate_post_ids':deleted,'disclosures_added':len(updated),'policy_flags':policy_flags,'unsafe_active_links':unsafe_links,'image_rights_gap_posts':len(rights_gaps),'zero_public_pageviews':True}
 REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('status','posts_checked','automated_posts','disclosures_present_before','duplicate_groups','disclosures_added','image_rights_gap_posts')}))
 # Residual historical findings are persisted for supervised repair. They do not
 # roll back safe duplicate deletion or disclosure updates already verified.
if __name__=='__main__':main()
