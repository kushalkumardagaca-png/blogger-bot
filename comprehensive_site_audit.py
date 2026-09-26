#!/usr/bin/env python3
"""Every-URL SEO/GEO/content/link/image audit for the post-publication watchdog."""
import concurrent.futures,datetime as dt,html,json,re,time,urllib.error,urllib.request
from pathlib import Path
from urllib.parse import urlparse
BLOG='https://dailyyield.blogspot.com';UA={'User-Agent':'Mozilla/5.0 (compatible; DailyYieldWatchdog/2.0)'}
IST=dt.timezone(dt.timedelta(hours=5,minutes=30))

def fetch(url,timeout=25):
 last=None
 for n in range(3):
  try:
   req=urllib.request.Request(url,headers=UA)
   with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,r.headers.get('Content-Type',''),r.read(),r.geturl()
  except urllib.error.HTTPError as e:
   last=(e.code,e.headers.get('Content-Type',''),b'',url)
   if e.code not in (429,500,502,503,504):return last
  except Exception as e:last=('ERR','',str(e).encode(),url)
  time.sleep(1.2*(n+1))
 return last

def feed(kind):
 st,_,raw,_=fetch(f'{BLOG}/feeds/{kind}/default?alt=json&max-results=100')
 if st!=200:raise RuntimeError(f'{kind} feed HTTP {st}')
 return json.loads(raw).get('feed',{}).get('entry',[])

def alt(e):return next((x.get('href','') for x in e.get('link',[]) if x.get('rel')=='alternate'),'')
def clean(s):return re.sub(r'<[^>]+>',' ',html.unescape(s or ''))
def ids(s):
 found=re.findall(r'\bid=["\']([^"\']+)',s,re.I);return sorted({x for x in found if found.count(x)>1})
def hrefs(s):return [html.unescape(x) for x in re.findall(r'<a\b[^>]*\bhref=["\']([^"\']+)',s,re.I)]
def imgs(s):return [html.unescape(x) for x in re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',s,re.I)]
def schemas(s):return re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',s,re.I|re.S)

def inventory():
 out=[{'kind':'home','title':'DAILY YIELD','url':BLOG+'/','content':''}]
 for kind in ('pages','posts'):
  for e in feed(kind):
   out.append({'kind':kind[:-1],'title':e.get('title',{}).get('$t',''),'url':alt(e),
    'content':e.get('content',{}).get('$t',''),'labels':[x.get('term','') for x in e.get('category',[])],
    'published':e.get('published',{}).get('$t','')})
 return list({x['url']:x for x in out if x['url']}.values())

def audit_item(x):
 issues=[];warn=[];c=x['content'];kind=x['kind'];url=x['url'];labels=x.get('labels',[])
 st,ct,raw,final=fetch(url);page=raw.decode(errors='ignore') if st==200 else ''
 if st!=200:issues.append(f'page HTTP {st}')
 if final and final.rstrip('/')!=url.rstrip('/') and 'share-market_0718113516' not in url:warn.append('redirected to '+final)
 if kind!='home':
  if len(clean(c).split())<40:issues.append('content is unexpectedly short')
  if ids(c):issues.append('duplicate ids: '+', '.join(ids(c)[:8]))
  if 'challenge-platform' in c:issues.append('copied challenge script')
  if kind=='post' and not imgs(c):issues.append('image missing')
  if '/p/share-market_0718113516.html' in c and 'GLOBAL SNAPSHOT — MOVED' not in x['title']:issues.append('obsolete market URL')
  sch=schemas(c)
  if kind=='post' and not sch:issues.append('JSON-LD schema missing')
  for n,s in enumerate(sch,1):
   try:json.loads(html.unescape(s).strip())
   except Exception as e:issues.append(f'JSON-LD {n} invalid: {str(e)[:80]}')
  if 'id="dyPageFamily"' not in c and 'GLOBAL SNAPSHOT — MOVED' not in x['title']:issues.append('comprehensive Daily Yield family directory missing')
 if kind=='post':
  if 'Kushal K. Daga' not in c:issues.append('author/byline missing')
  if 'class="dy-context"' not in c:issues.append('context-sensitive internal link missing')
  if 'class="dy-related"' not in c:issues.append('article suggestions shelf missing')
  related=set(re.findall(r'class=["\'][^"\']*dy-related-card[^"\']*["\'][^>]*href=["\']([^"\']+)',c,re.I))
  if len(related)!=4:issues.append(f'article suggestions count {len(related)}, expected 4')
  if 'DY_CONTINUOUS_MOTION_START' not in c:issues.append('gesture/motion controller missing')
  if not any(t in c for t in ('BlogPosting','Article','NewsArticle')):issues.append('BlogPosting/Article/NewsArticle schema type missing')
  if 'News' in labels:
   if set(labels)!={'News',next((z for z in labels if z!='News'),'')}:issues.append('news labels malformed')
   if ' · Coverage ' not in x['title']:issues.append('news title coverage window missing')
   if 'class="fbk-src' not in c:issues.append('external source links missing')
  if not any(u.startswith(BLOG) for u in hrefs(c)):issues.append('internal links missing')
 # Rendered head metadata may be script-injected; confirm source package has the canonical ingredients.
 if page:
  if '<title>' not in page.lower():issues.append('HTML title missing')
  canonical=re.search(r'<link\b(?=[^>]*\brel=["\']canonical["\'])(?=[^>]*\bhref=["\']([^"\']+))[^>]*>',page,re.I)
  if not canonical:issues.append('canonical link missing')
  elif canonical.group(1).rstrip('/')!=url.rstrip('/') and 'share-market_0718113516' not in url:issues.append('canonical mismatch')
  if kind=='post' and not any(k in c for k in ('SEARCH DESCRIPTION:','DY_SEO_META_START','metaDesc')):issues.append('SEO meta-description package missing')
 return {'kind':kind,'title':x['title'],'url':url,'issues':issues,'warnings':warn,'images':imgs(c),'links':hrefs(c)}

def check_asset(url):
 st,ct,_,_=fetch(url,18);return url,st,ct

def main():
 items=inventory();rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
  rows=list(ex.map(audit_item,items))
 image_urls=sorted({u for r in rows for u in r['images'] if u.startswith(('http://','https://'))})
 internal=sorted({u.split('#')[0] for r in rows for u in r['links'] if u.startswith(BLOG) and '/search' not in u})
 external=sorted({u.split('#')[0] for r in rows for u in r['links'] if u.startswith(('http://','https://')) and not u.startswith(BLOG)})
 asset_results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:asset_results=list(ex.map(check_asset,image_urls+internal+external))
 broken_images=[{'url':u,'status':s,'content_type':ct} for u,s,ct in asset_results[:len(image_urls)] if s not in (200,206) or not ct.lower().startswith('image/')]
 offset=len(image_urls);broken_internal=[{'url':u,'status':s} for u,s,ct in asset_results[offset:offset+len(internal)] if s not in (200,206)]
 ext_rows=asset_results[offset+len(internal):]
 broken_external=[{'url':u,'status':s} for u,s,ct in ext_rows if s in (404,410)]
 external_restricted=[{'url':u,'status':s} for u,s,ct in ext_rows if s in (401,403,429,'ERR')]
 hard=sum(bool(r['issues']) for r in rows)+len(broken_images)+len(broken_internal)+len(broken_external)
 report={'checked_at_ist':dt.datetime.now(IST).isoformat(timespec='seconds'),'urls':len(rows),'posts':sum(r['kind']=='post' for r in rows),'pages':sum(r['kind']=='page' for r in rows),'hard_failures':hard,'url_failures':sum(bool(r['issues']) for r in rows),'images_checked':len(image_urls),'broken_images':broken_images,'internal_links_checked':len(internal),'broken_internal_links':broken_internal,'external_links_checked':len(external),'broken_external_links':broken_external,'external_restricted_not_broken':external_restricted,'results':rows}
 Path('COMPREHENSIVE_SITE_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
 lines=['# Comprehensive Post-Publication Site Audit','',f"**Checked:** {report['checked_at_ist']}",f"**Inventory:** {report['urls']} URLs · {report['posts']} Posts · {report['pages']} Pages",f"**Result:** {'PASS' if not hard else 'FAIL'} · {hard} hard failure(s)",'',f"Images: {len(image_urls)} checked · {len(broken_images)} broken  ",f"Internal links: {len(internal)} checked · {len(broken_internal)} broken  ",f"External links: {len(external)} checked · {len(broken_external)} confirmed 404/410  ",f"Restricted/rate-limited external checks (not classified broken): {len(external_restricted)}",'']
 for r in rows:
  lines.append(f"- {'✅' if not r['issues'] else '❌'} **{r['kind']} · {r['title']}**"+((' — '+'; '.join(r['issues'])) if r['issues'] else ''))
 Path('COMPREHENSIVE_SITE_AUDIT.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ('results','external_restricted_not_broken')},ensure_ascii=False)[:4000])
 return 0 if not hard else 1
if __name__=='__main__':raise SystemExit(main())
