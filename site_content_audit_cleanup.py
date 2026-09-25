#!/usr/bin/env python3
"""Audit/fix every News post and remove obsolete explore-card blocks sitewide."""
from pathlib import Path
import datetime as dt, hashlib, html, json, os, re, urllib.parse, urllib.request
from page_family import remove_legacy_explore_blocks
from retrofit_live_news import retrofit
from news_pipeline import BLOG, CATEGORY_DESKS, CATEGORY_FILTERS, DESKS, HINT_RE, IST

BLOG_ID=os.environ['BLOGGER_BLOG_ID'];BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}';APPLY=os.environ.get('APPLY','false').lower()=='true'

def token():
 data=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST'),timeout=30) as r:return json.load(r)['access_token']

def call(path,tok,method='GET',body=None,params=None):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)

def collect(kind,tok):
 out=[];page=None
 while True:
  p={'fetchBodies':'true','maxResults':'50'}
  if kind=='posts':p['orderBy']='published'
  if page:p['pageToken']=page
  data=call('/'+kind,tok,params=p);out+=data.get('items',[]);page=data.get('nextPageToken')
  if not page:return out

def plain(s):return html.unescape(re.sub(r'<[^>]+>','',s)).strip()
def norm(s):return re.sub(r'\W+',' ',plain(s).lower()).strip()

def desk_for(post):
 for key,val in DESKS.items():
  if val[1] in post.get('labels',[]):return key
 return None

def current_blocks(content):
 boundary=len(content)
 m=re.search(r'<h2 class="fbk-h2"><b>(?:BG|04|05)</b>',content,re.I)
 if m:boundary=m.start()
 area=content[:boundary];result=[]
 for match in re.finditer(r'<div class="fbk-item">.*?</div>',area,re.S|re.I):
  hm=re.search(r'<h3>(.*?)</h3>',match.group(0),re.S|re.I)
  if hm:result.append({'raw':match.group(0),'title':plain(hm.group(1))})
 return result

def owner_score(desk,title):
 score=0;hint=HINT_RE.get(desk)
 if hint and hint.search(title):score+=100
 if desk in CATEGORY_DESKS and any(k in title.lower() for k in CATEGORY_FILTERS[desk]):score+=80
 if desk=='global':score+=5
 # Stable tie-break distributes shared regional stories instead of assigning all to one desk.
 score+=(int(hashlib.sha256((desk+'|'+title).encode()).hexdigest()[:6],16)%1000)/10000
 return score

def update_item(kind,tok,item,content,labels=None,title=None):
 body={'kind':'blogger#'+('page' if kind=='pages' else 'post'),'id':item['id'],'title':title or item['title'],'content':content}
 if kind=='posts':body['labels']=labels if labels is not None else item.get('labels',[])
 if APPLY:return call('/'+kind+'/'+item['id'],tok,'PUT',body=body)
 return body

def audit_news(post,content,title,labels,desk):
 issues=[];blocks=current_blocks(content);heads=[norm(b['title']) for b in blocks];background=len(re.findall(r'class="fbk-item fbk-background"',content))
 expected_labels={'News',DESKS[desk][1]}
 if set(labels)!=expected_labels or len(labels)!=2:issues.append('labels')
 if not title.startswith(desk_title:=DESKS[desk][1].replace('Global News','Global Finance Wire')): # informational; robust check below
  if desk_for({'labels':labels})!=desk:issues.append('desk-title')
 if ' · Coverage ' not in title:issues.append('coverage-title')
 if 'By Kushal K. Daga' not in content:issues.append('byline')
 if '"@type": "NewsArticle"' not in content and '"@type":"NewsArticle"' not in content:issues.append('schema')
 if post.get('url','') not in content:issues.append('canonical')
 if not re.search(r'<figure class="fbk-hero">\s*<img ',content,re.I):issues.append('hero')
 if len(heads)!=len(set(heads)):issues.append('duplicate-within-post')
 if background>3:issues.append('background-over-3')
 if not blocks:issues.append('no-current-items')
 source_count=len(re.findall(r'class="fbk-src"',content))
 if source_count<len(blocks)+background:issues.append('missing-source-links')
 if re.search(r'By CA Kushal|Finance by CA Kushal|financebycakushal',content,re.I):issues.append('old-brand')
 return {'desk':desk,'url':post.get('url'),'title':title,'current_items':len(blocks),'background_items':background,'source_links':source_count,'issues':issues}

def main():
 tok=token();pages=collect('pages',tok);posts=collect('posts',tok)
 backup={'pages':pages,'posts':posts};Path('site_content_backup.json').write_text(json.dumps(backup,ensure_ascii=False))
 changes=[]
 # Remove obsolete small explore blocks across every static Page and every Post.
 for kind,items in [('pages',pages),('posts',posts)]:
  for item in items:
   old=item.get('content','');new=remove_legacy_explore_blocks(old)
   if new!=old:
    update_item(kind,tok,item,new);item['content']=new
    changes.append({'kind':kind[:-1],'url':item.get('url'),'change':'removed obsolete explore block','bytes_removed':len(old)-len(new)})

 news=[p for p in posts if 'News' in p.get('labels',[]) and desk_for(p)]
 # Cross-post duplicate allocation.
 occurrences={}
 for idx,p in enumerate(news):
  for block in current_blocks(p.get('content','')):
   occurrences.setdefault(norm(block['title']),[]).append((idx,block))
 removed={i:[] for i in range(len(news))};remaining={i:len(current_blocks(p.get('content',''))) for i,p in enumerate(news)}
 for key,occ in occurrences.items():
  if not key or len(occ)<2:continue
  owner=max(occ,key=lambda x:owner_score(desk_for(news[x[0]]),x[1]['title']))[0]
  for idx,block in occ:
   if idx==owner or remaining[idx]<=1:continue
   news[idx]['content']=news[idx]['content'].replace(block['raw'],'',1);remaining[idx]-=1;removed[idx].append(block['title'])

 reports=[]
 for idx,p in enumerate(news):
  # Enforce exactly two labels, then retrofit title/H1/schema/coverage/volume wording.
  desk=desk_for(p);labels=['News',DESKS[desk][1]]
  work=dict(p);work['content']=p.get('content','');work['labels']=labels
  title,content,meta=retrofit(work)
  before_issues=audit_news(p,p.get('content',''),p['title'],p.get('labels',[]),desk)['issues']
  after=audit_news(p,content,title,labels,desk)
  after['issues_before']=before_issues;after['duplicates_removed']=len(removed[idx]);after['duplicate_titles_removed']=removed[idx]
  reports.append(after)
  changed=(content!=p.get('content','') or title!=p['title'] or labels!=p.get('labels',[]))
  if changed:
   update_item('posts',tok,p,content,labels,title)
   changes.append({'kind':'news post','url':p.get('url'),'change':'audited and repaired','duplicates_removed':len(removed[idx])})

 fail=[r for r in reports if r['issues']]
 family_remaining=[]
 for item in pages+posts:
  cleaned=remove_legacy_explore_blocks(item.get('content',''))
  if cleaned!=item.get('content',''):family_remaining.append(item.get('url'))
 result={'apply':APPLY,'pages_scanned':len(pages),'posts_scanned':len(posts),'news_scanned':len(news),'changes':changes,'news':reports,'failures_after_fix':fail,'obsolete_blocks_remaining_in_memory':family_remaining}
 Path('SITE_CONTENT_AUDIT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
 lines=['# Daily Yield Site Content Audit','',f"Mode: {'APPLY' if APPLY else 'DRY RUN'}",'',f"Pages scanned: {len(pages)}  ",f"Posts scanned: {len(posts)}  ",f"News articles audited: {len(news)}  ",f"Planned/applied changes: {len(changes)}",'']
 for r in reports:lines.append(f"- {'✅' if not r['issues'] else '❌'} **{r['desk']}** — {r['current_items']} current, {r['background_items']} background, {r['source_links']} source links, {r['duplicates_removed']} cross-post duplicates removed"+(f"; unresolved: {', '.join(r['issues'])}" if r['issues'] else ''))
 Path('SITE_CONTENT_AUDIT.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({'apply':APPLY,'news':len(news),'changes':len(changes),'failures':len(fail)},indent=2))
 if fail:raise SystemExit(1)
if __name__=='__main__':main()
