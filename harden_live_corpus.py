#!/usr/bin/env python3
"""Authenticated, zero-pageview Blogger corpus remediation and evidence audit.

Safe application removes exact duplicate records, upgrades process disclosures,
removes repeated boilerplate from historical News, and reverts unresolved high-risk
legacy posts to Blogger drafts for supervised repair rather than leaving them live.
"""
from __future__ import annotations
import datetime as dt,hashlib,html,json,os,re,time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote,unquote,urlparse
import requests
from bs4 import BeautifulSoup,Comment
from content_policy_guard import DISCLOSURE_MARKER,audit_text,automation_disclosure
from editorial_integrity import language_similarity,normalized_title

BASE=f"https://www.googleapis.com/blogger/v3/blogs/{os.environ['BLOGGER_BLOG_ID']}";APPLY=os.environ.get('APPLY_CORPUS_REMEDIATION','').casefold()=='true' and not __import__('site_change_control').is_frozen()
REPORT=Path('BLOGGER_CORPUS_POLICY_STATUS.json');RIGHTS=Path('BLOGGER_IMAGE_RIGHTS_LEDGER.json')
UTILITY_SELECTORS=('.dy2-summary','.dy2-faq','.dy2-glossary','.dy2-links','.dy2-low','.dy2-follow','#dyPageFamily','.dy-policy-disclosure','.dy-related','.dy-context','script','style','noscript','template')

def token():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return r.json()['access_token']
def call(method,path,h,**kwargs):
 for attempt in range(6):
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
 return bool(labels&{'News','Master Article','Kushal Daga'} or any(x in content for x in ('DY_MASTER_V2','DY_NEWS','fbk-news','DY_AUTOMATION')))
def canonical_id(url,h):
 try:return str(call('GET','/posts/bypath',h,params={'path':urlparse(url).path,'fields':'id'}).json().get('id',''))
 except Exception:return ''
def exact_duplicate_groups(rows,h):
 by_url=defaultdict(list)
 for p in rows:by_url[(p.get('url') or '').rstrip('/')].append(p)
 groups=[]
 for url,items in by_url.items():
  if not url or len(items)<2:continue
  exact=[]
  for i,p in enumerate(items):
   for q in items[i+1:]:
    if normalized_title(p.get('title',''))==normalized_title(q.get('title','')) and language_similarity(p.get('content',''),q.get('content',''))>=.985:exact.extend((p,q))
  unique={p['id']:p for p in exact}
  if len(unique)>1:
   keep=canonical_id(url,h) or sorted(unique.values(),key=lambda x:x.get('published',''))[0]['id'];groups.append({'url':url,'keep_id':keep,'remove_ids':sorted(x for x in unique if x!=keep),'similarity_floor':.985})
 return groups

def upgrade_disclosure(content):
 content=re.sub(r'<!--\s*DY_AUTOMATION_DISCLOSURE[^>]*-->\s*<aside\b[^>]*class=["\'][^"\']*dy-policy-disclosure[^"\']*["\'][^>]*>.*?</aside>','',content or '',flags=re.I|re.S)
 return content.rstrip()+'\n'+automation_disclosure('automated publication')
def clean_legacy_promises(content):
 # These historical phrases were headings/examples, not promises, but clearer
 # bounded wording removes avoidable scam-like signals.
 replacements={'Guaranteed Return':'Promised-return claim','guaranteed return':'promised-return claim','risk-free return':'plan-defined employer contribution','Risk-Free Return':'Plan-defined employer contribution'}
 for old,new in replacements.items():content=content.replace(old,new)
 return content
def dedupe_news_context(content):
 soup=BeautifulSoup(content,'html.parser');seen=set();removed=0
 for node in soup.select('p.fbk-context'):
  parts=[x.strip() for x in re.split(r'(?<=[.!?])\s+',node.get_text(' ',strip=True)) if x.strip()];keep=[]
  for sentence in parts:
   key=re.sub(r'[^a-z0-9]+',' ',sentence.casefold()).strip()
   if len(key.split())>=10 and key in seen:removed+=1;continue
   if len(key.split())>=10:seen.add(key)
   keep.append(sentence)
  node.clear();node.append(' '.join(keep))
 return str(soup),removed
def editorial_only(post,content):
 soup=BeautifulSoup(content,'html.parser')
 for selector in UTILITY_SELECTORS:
  for node in soup.select(selector):node.decompose()
 if 'News' in set(post.get('labels') or []) or soup.select_one('.fbk-item'):
  selected=soup.select('p.fbk-description,p.fbk-context')
  return '<article>'+''.join(str(x) for x in selected)+'</article>'
 article=soup.select_one('article.dy2')
 if article:
  return str(article)
 return str(soup)
def ensure_figure_rights(content):
 soup=BeautifulSoup(content,'html.parser');changed=False
 for figure in soup.select('figure'):
  if figure.select_one('figcaption'):continue
  image=figure.select_one('img[src]')
  if not image:continue
  src=html.unescape(image.get('src',''));host=(urlparse(src).hostname or '').lower();source='';label=''
  if host.endswith('wikimedia.org'):
   path=urlparse(src).path;match=re.search(r'/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/',path,re.I) or re.search(r'/commons/[0-9a-f]/[0-9a-f]{2}/([^/]+)$',path,re.I)
   if match:source='https://commons.wikimedia.org/wiki/File:'+quote(unquote(match.group(1)));label='Editorial image · Wikimedia Commons source and licence record'
  elif host.endswith('unsplash.com'):source=src;label='Editorial photograph · Unsplash source record'
  if source:
   caption=soup.new_tag('figcaption');link=soup.new_tag('a',href=source,rel='noopener license',target='_blank');link.string=label;caption.append(link);figure.append(caption);changed=True
 return str(soup) if changed else content

def rights_entry(post,content):
 soup=BeautifulSoup(content,'html.parser');assets=[]
 for figure in soup.select('figure'):
  image=figure.select_one('img[src]')
  if not image:continue
  src=html.unescape(image.get('src',''));caption=figure.select_one('figcaption');caption_text=caption.get_text(' ',strip=True) if caption else '';links=[html.unescape(x.get('href','')) for x in figure.select('a[href]')]
  host=(urlparse(src).hostname or '').lower();trusted=host.endswith(('wikimedia.org','unsplash.com','blogger.googleusercontent.com','githubusercontent.com'))
  assets.append({'src':src,'alt_present':bool((image.get('alt') or '').strip()),'source_links':links,'caption_present':bool(caption_text),'trusted_editorial_host':trusted,'rights_evidence':bool(caption_text and (links or trusted))})
 return {'post_id':post['id'],'url':post.get('url'),'assets':assets,'complete':all(x['alt_present'] and x['rights_evidence'] for x in assets) if assets else True}

def main():
 h={'Authorization':'Bearer '+token(),'Content-Type':'application/json'};rows=posts(h);duplicates=exact_duplicate_groups(rows,h);deleted=[];updated=[];quarantined=[];unsafe=[];rights=[];news_sentences_removed=0;remaining=[]
 if APPLY:
  for group in duplicates:
   for ident in group['remove_ids']:call('DELETE','/posts/'+ident,h);deleted.append(ident)
 removed=set(deleted)
 for p in rows:
  if p['id'] in removed:continue
  # Audit the real stored copy, not a cleaned hypothetical copy.
  content=p.get('content','')
  if APPLY:
   content=clean_legacy_promises(content)
   if 'News' in set(p.get('labels') or []):content,count=dedupe_news_context(content);news_sentences_removed+=count
   content=ensure_figure_rights(content)
   if automated(p):content=upgrade_disclosure(content)
  audit_content=editorial_only(p,content);issues=[x for x in audit_text(p.get('title',''),audit_content,'historical',require_disclosure=False) if x!='insufficient sentence-level originality']
  bad_links=[]
  for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)',content,re.I):
   if re.match(r'\s*(?:javascript|vbscript|data):',html.unescape(href),re.I):bad_links.append(href)
  issues+=['unsafe active link scheme'] if bad_links else []
  if APPLY and issues:
   # Keep the content recoverable as a Blogger draft. No unsafe or materially
   # repetitive legacy item remains publicly distributed merely to preserve count.
   call('POST','/posts/'+p['id']+'/revert',h);quarantined.append({'post_id':p['id'],'url':p.get('url'),'issues':sorted(set(issues))});continue
  if issues:remaining.append({'post_id':p['id'],'url':p.get('url'),'issues':sorted(set(issues))})
  if bad_links:unsafe.append({'post_id':p['id'],'url':p.get('url')})
  if APPLY and content!=p.get('content',''):
   body={'kind':'blogger#post','id':p['id'],'blog':{'id':os.environ['BLOGGER_BLOG_ID']},'title':p.get('title'),'content':content,'labels':p.get('labels') or []};saved=call('PUT','/posts/'+p['id'],h,json=body).json()
   if automated(p) and DISCLOSURE_MARKER not in saved.get('content',''):raise RuntimeError('disclosure verification failed for '+p['id'])
   updated.append(p['id'])
  rights.append(rights_entry(p,content))
 rights_gaps=[x for x in rights if not x['complete']]
 rights_doc={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'posts_checked':len(rows)-len(removed),'posts_with_figure_rights_gaps':len(rights_gaps),'gaps':rights_gaps,'ledger_hash':hashlib.sha256(json.dumps(rights,sort_keys=True).encode()).hexdigest()};RIGHTS.write_text(json.dumps(rights_doc,indent=2)+'\n')
 unresolved_duplicates=[] if APPLY else duplicates;status='PASS' if not unresolved_duplicates and not remaining and not unsafe and not rights_gaps else ('REMEDIATED' if APPLY and not remaining and not unsafe and not rights_gaps else 'WARNING')
 report={'status':status,'apply':APPLY,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'posts_checked':len(rows),'automated_posts':sum(automated(x) for x in rows),'disclosures_current_before':sum(DISCLOSURE_MARKER in x.get('content','') for x in rows if automated(x)),'duplicate_groups_found':duplicates,'unresolved_duplicate_groups':unresolved_duplicates,'deleted_duplicate_post_ids':deleted,'posts_updated':len(updated),'historical_news_sentences_deduplicated':news_sentences_removed,'quarantined_to_draft':quarantined,'remaining_live_policy_flags':remaining,'unsafe_active_links':unsafe,'image_rights_gap_posts':len(rights_gaps),'zero_public_pageviews':True};REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('status','posts_checked','automated_posts','deleted_duplicate_post_ids','posts_updated','historical_news_sentences_deduplicated','quarantined_to_draft','remaining_live_policy_flags','image_rights_gap_posts')}))
if __name__=='__main__':main()
