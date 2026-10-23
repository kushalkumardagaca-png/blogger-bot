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

BASE=f"https://www.googleapis.com/blogger/v3/blogs/{os.environ['BLOGGER_BLOG_ID']}"
# Two modes, deliberately. `full` is the whole-site remediation this file was written for: it removes
# exact twins, upgrades stale disclosures and reverts unresolved legacy posts to drafts, and it stays
# closed while the owner's freeze stands. `rights` is the narrow repair the owner released on
# 23 October 2026: it writes only the licence credit inside a photo figure, and it can never delete a
# post, revert a post to draft or rewrite a sentence - because a blank caption, not deleted content, is
# what held every desk that morning. The policy audit still runs either way, so a PASS reported from the
# narrow mode is a measured fact and not a narrowed definition.
SCOPE=(os.environ.get('CORPUS_REPAIR_SCOPE','full') or 'full').strip().casefold()
ACTION='corpus_figure_rights_repair'
TWIN_ACTION='duplicate_twin_retirement'
# A double publication is a fresh, dated, same-title pair. Older same-title pairs are the
# site's own history (a country edition refreshed the next day, a renamed legacy post) and
# bulk editorial deletion is the owner's call alone, so the window is the whole difference
# between fixing an accident and quietly emptying the blog.
RECENT_TWIN_HOURS=float(os.environ.get('CORPUS_TWIN_WINDOW_HOURS','48'))
TWIN_LIMIT=int(os.environ.get('CORPUS_TWIN_LIMIT','5'))
TWIN_BACKUP_DIR=Path('duplicate_twin_backups')
_CONTROL=__import__('site_change_control')
APPLY=os.environ.get('APPLY_CORPUS_REMEDIATION','').casefold()=='true' and (not _CONTROL.is_frozen() or ((SCOPE=='rights' and _CONTROL.allowed(ACTION)) or (SCOPE=='duplicates' and _CONTROL.allowed(TWIN_ACTION))))
# 'duplicates' is the only twin-side release: it retires one copy to a draft. `full` is NOT unlocked
# by it - whole-site remediation stays held until the owner lifts the freeze, and a release for one
# narrow write must not be read as a release for every write the file knows how to do.
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
def published_at(post):
 try:return dt.datetime.fromisoformat((post.get('published') or post.get('updated') or '').replace('Z','+00:00'))
 except Exception:return None
def collision_suffixed(url):
 # Blogger marks a permalink it had to make room for: `name_1234567890.html`.
 return bool(re.search(r'_\d{6,}\.html?$',(url or '').rstrip('/')))
def twin_groups(rows,h):
 """Every pair of live posts carrying the same edition twice, by URL and by title.

 `by_url` is the original check and its semantics are unchanged, because the green
 operating gate reads it: it must not start holding the day for a new reason.
 `by_title` is what a double publication actually looks like - same date in the title,
 same prose, two addresses - and it is reported and repaired, never deleted en masse.
 """
 groups=[]
 for kind,keyfn in (('url',lambda p:(p.get('url') or '').rstrip('/')),('title',lambda p:normalized_title(p.get('title','') or ''))):
  bucket=defaultdict(list)
  for post in rows:
   value=keyfn(post)
   if value:bucket[value].append(post)
  for value,items in bucket.items():
   if len(items)<2:continue
   if kind=='title' and len(re.sub(r'[^a-z0-9]','',str(value)))<24:continue
   matched={}
   for i,a in enumerate(items):
    for b in items[i+1:]:
     # Same title *and* the same prose. A matching title alone is how a country
     # desk names itself every day, and grading that as a duplicate would put
     # yesterday's edition in the way of today's.
     if normalized_title(a.get('title','') or '')==normalized_title(b.get('title','') or '') and language_similarity(a.get('content',''),b.get('content',''))>=.985:
      matched[a['id']]=a;matched[b['id']]=b
   if len(matched)<2:continue
   times=[t for t in (published_at(p) for p in matched.values()) if t]
   age=round((dt.datetime.now(dt.timezone.utc)-max(times)).total_seconds()/3600,1) if times else None
   ordered=sorted(matched.values(),key=lambda q:(str(q.get('published') or ''),str(q['id'])))
   keep=next((q for q in ordered if not collision_suffixed(q.get('url'))),ordered[0])
   if kind=='url':
    cid=canonical_id(value,h)
    if cid:keep=next((q for q in ordered if str(q['id'])==cid),keep)
   groups.append({'kind':kind,'key':value,'keep_id':keep['id'],'keep_url':keep.get('url',''),
    'remove_ids':sorted(x for x in matched if x!=keep['id']),'similarity_floor':.985,
    'newest_age_hours':age,'recent':age is not None and age<=RECENT_TWIN_HOURS})
 return groups
def exact_duplicate_groups(rows,h):
 return [g for g in twin_groups(rows,h) if g['kind']=='url']
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
  if selected:return '<article>'+''.join(str(x) for x in selected)+'</article>'
 article=soup.select_one('article.dy2')
 if article:
  return str(article)
 return str(soup)
def commons_page(candidate):
 """The Wikimedia file page an address refers to, when it refers to one."""
 from urllib.parse import unquote as _unquote
 value=_unquote(str(candidate or ''))
 match=re.search(r'/wiki/(?:File|Image):([^?#]+)',value,re.I)
 if match:return 'https://commons.wikimedia.org/wiki/File:'+match.group(1)
 match=re.search(r'/commons/[0-9a-f]/[0-9a-f]{2}/([^/?#]+)',value,re.I) or re.search(r'/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/',value,re.I)
 if match:return 'https://commons.wikimedia.org/wiki/File:'+_unquote(match.group(1))
 return ''


def figure_credit_markup(src,links):
 """The words a figure's credit has to carry, taken from the site's own rights records.

 Nothing is invented. The photo registry written when the picture was chosen is read first, because it
 holds the creator, the licence and both source addresses verified at selection time; a picture that
 predates that registry is credited by naming the source record its own figure already links to.
 """
 from photo_credit import caption_is_visible, figure_html, rights_for
 markup=figure_html(rights_for({'url':src}))
 if markup and caption_is_visible(markup):return markup
 for candidate in [x for x in links if x]+[src]:
  page=commons_page(candidate)
  label='Editorial image · Wikimedia Commons source and licence record'
  if not page:
   host=(urlparse(candidate).hostname or '').lower()
   if not host.endswith('unsplash.com'):continue
   page=candidate;label='Editorial photograph · Unsplash source record'
  return f'<a href="{html.escape(page,quote=True)}" rel="noopener license" target="_blank">{label}</a>'
 return ''


def ensure_figure_rights(content):
 """Give every photo figure a credit line a reader can actually read.

 On 22 October 2026 three articles went live whose second and third photographs kept their source link
 but lost their words, because an anti-repetition repair deleted the licence credit it mistook for
 duplicated prose. The whole-site image-rights audit read those empty captions as missing attribution
 and reported a gap, and the green operating gate refused every publication the next morning on the
 strength of that single field. So a caption that exists but says nothing is treated here exactly as it
 reads: as no caption at all.
 """
 soup=BeautifulSoup(content,'html.parser');changed=False;repaired=0
 for figure in soup.select('figure'):
  image=figure.select_one('img[src]')
  if not image:continue
  caption=figure.select_one('figcaption')
  text='' if caption is None else caption.get_text(' ',strip=True)
  if caption is not None and len(text)>=12:continue
  src=html.unescape(image.get('src','') or '')
  links=[html.unescape(a.get('href','') or '') for a in figure.select('a[href]')]
  markup=figure_credit_markup(src,links)
  if not markup:continue
  if caption is None:
   caption=soup.new_tag('figcaption');figure.append(caption)
  caption.clear();caption.append(BeautifulSoup(markup,'html.parser'))
  changed=True;repaired+=1
 return (str(soup),repaired) if changed else (content,0)

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
 h={'Authorization':'Bearer '+token(),'Content-Type':'application/json'};rows=posts(h);groups=twin_groups(rows,h)
 duplicates=[g for g in groups if g['kind']=='url'];title_twins=[g for g in groups if g['kind']=='title']
 recent_twins=[g for g in title_twins if g['recent']]
 deleted=[];updated=[];quarantined=[];unsafe=[];rights=[];news_sentences_removed=0;remaining=[];captions_restored=0;twins_retired=[];twins_pending=[]
 if APPLY and SCOPE=='full':
  # Whole-site deletion stays exactly as closed as the freeze left it: the duplicates
  # scope retires a copy to a draft, it does not erase a post.
  for group in duplicates:
   for ident in group['remove_ids']:call('DELETE','/posts/'+ident,h);deleted.append(ident)
 if APPLY and SCOPE in ('duplicates','full') and _CONTROL.allowed(TWIN_ACTION):
  for group in recent_twins[:TWIN_LIMIT]:
   for ident in group['remove_ids']:
    try:
     saved=call('GET','/posts/'+ident,h,params={'fetchBody':'true'}).json()
     TWIN_BACKUP_DIR.mkdir(parents=True,exist_ok=True)
     backup=TWIN_BACKUP_DIR/f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d}-{ident}.json"
     backup.write_text(json.dumps(saved,indent=2)+'\n')
     if normalized_title(saved.get('title','') or '')!=normalized_title(group['key'] or ''):
      raise RuntimeError('post changed under us; nothing was reverted')
     call('POST','/posts/'+ident+'/revert',h)
     twins_retired.append({'post_id':ident,'url':saved.get('url',''),'kept_url':group['keep_url'],'backup':str(backup)})
    except Exception as exc:
     # A twin that cannot be retired safely is reported, never forced. Losing the
     # repair is a visible duplicate; a wrong revert is a lost article.
     twins_pending.append({'post_id':ident,'error':str(exc)[:180]})
  for group in recent_twins[TWIN_LIMIT:]:
   twins_pending.append({'title':group['key'],'pending':'over the per-run cap of '+str(TWIN_LIMIT)})
 removed=set(deleted)|{x['post_id'] for x in twins_retired}
 for p in rows:
  if p['id'] in removed:continue
  # Audit the real stored copy, not a cleaned hypothetical copy.
  content=p.get('content','')
  if APPLY:
   if SCOPE!='rights':
    content=clean_legacy_promises(content)
    if 'News' in set(p.get('labels') or []):content,count=dedupe_news_context(content);news_sentences_removed+=count
   if len(updated)>=60:
    # The released scope is capped at sixty posts per run; a backlog waits for the next run rather than
    # spending the whole hour on one pass, and the audit below still measures every post in this one.
    rights.append(rights_entry(p,content))
    continue
   content,repaired=ensure_figure_rights(content);captions_restored+=repaired
   if automated(p) and SCOPE!='rights':content=upgrade_disclosure(content)
  audit_content=editorial_only(p,content);issues=[x for x in audit_text(p.get('title',''),audit_content,'historical',require_disclosure=False) if x!='insufficient sentence-level originality']
  bad_links=[]
  for href in re.findall(r'<a\b[^>]*href=["\']([^"\']+)',content,re.I):
   if re.match(r'\s*(?:javascript|vbscript|data):',html.unescape(href),re.I):bad_links.append(href)
  issues+=['unsafe active link scheme'] if bad_links else []
  if APPLY and issues and SCOPE!='rights':
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
 unresolved_duplicates=[] if (APPLY and SCOPE=='full') else duplicates;status='PASS' if not unresolved_duplicates and not remaining and not unsafe and not rights_gaps else ('REMEDIATED' if APPLY and not remaining and not unsafe and not rights_gaps else 'WARNING')
 report={'status':status,'apply':APPLY,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'posts_checked':len(rows),'automated_posts':sum(automated(x) for x in rows),'disclosures_current_before':sum(DISCLOSURE_MARKER in x.get('content','') for x in rows if automated(x)),'duplicate_groups_found':duplicates,'unresolved_duplicate_groups':unresolved_duplicates,'deleted_duplicate_post_ids':deleted,'posts_updated':len(updated),'historical_news_sentences_deduplicated':news_sentences_removed,'quarantined_to_draft':quarantined,'remaining_live_policy_flags':remaining,'unsafe_active_links':unsafe,'image_rights_gap_posts':len(rights_gaps),'figure_captions_restored':captions_restored,'repair_scope':SCOPE,
'title_twin_groups_open':len(title_twins),'recent_title_twins':len(recent_twins),'twins_retired':twins_retired,'twins_pending':twins_pending,'open_title_twins':[{'title':g['key'],'urls':[x.get('url','') for x in rows if normalized_title(x.get('title','') or '')==g['key']],'age_hours':g['newest_age_hours']} for g in title_twins if not g['recent']][:25],'site_writes':len(updated),'zero_public_pageviews':True};REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('status','posts_checked','automated_posts','deleted_duplicate_post_ids','posts_updated','figure_captions_restored','repair_scope','site_writes','historical_news_sentences_deduplicated','quarantined_to_draft','remaining_live_policy_flags','image_rights_gap_posts')}))
if __name__=='__main__':main()
