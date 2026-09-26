#!/usr/bin/env python3
"""Sitewide continuous gesture motion plus topic-related article shelves."""
from pathlib import Path
import json,os,re,urllib.parse,urllib.request
from continuous_motion import ensure as ensure_motion
from related_articles import ensure as ensure_related
from page_family import ensure_family
from seo_meta import ensure_seo_meta
from brand_identity import ensure_brand_identity
PAGE_DESCRIPTIONS={
 'GLOBAL SNAPSHOT':'Daily Yield Global Snapshot: a concise cross-asset view of global indices, currencies, commodities, crypto and market conditions.',
 'MARKETS TODAY':'Daily Yield Markets Today: search and analyse global stocks, indices, currencies, commodities and digital assets with transparent data fallbacks.',
 'DAILY ARTICLE':'Original financial explainers, practical money guides and evidence-led analysis by Kushal K. Daga at Daily Yield.',
 'DAILY NEWS':'Current finance, economy, markets and policy reporting from Daily Yield with dated links to official and reputable sources.',
 'CALCULATOR':'Daily Yield financial calculators for loans, investing, tax, savings, retirement and practical money planning.',
 'MONEY ATLAS':'Explore country-by-country currencies, financial context, markets and practical money information with Daily Yield Money Atlas.',
 'FOR CORPORATE':'Daily Yield resources and financial analysis for corporate decision-makers, professionals and business teams.',
 'ABOUT US':'About Daily Yield and Kushal K. Daga: transparent financial education, global finance news, market tools and practical money guidance.',
 'CONTACT US':'Contact Daily Yield regarding financial education, editorial feedback, corrections and corporate enquiries.',
 'DISCLAIMER':'Daily Yield financial-information disclaimer covering educational content, market data, external sources and investment risk.',
 'PRIVACY POLICY':'Daily Yield privacy policy explaining data handling, cookies, external services and visitor choices.',
}
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

def repair_external_runtime(content):
 """Remove copied anti-bot scripts and repair the Money Atlas FX fallback chain."""
 old=content
 content=re.sub(r'<script\b[^>]*src=["\'][^"\']*cdn-cgi/challenge-platform/scripts/jsd/main\.js[^"\']*["\'][^>]*>\s*</script\s*>','',content,flags=re.I)
 content=re.sub(r'<script\b[^>]*>[^<]*cdn-cgi/challenge-platform/scripts/jsd/main\.js[^<]*</script\s*>','',content,flags=re.I|re.S)
 broken="fetch('https://api.frankfurter.app/latest?from=USD').then(function(r){return r.json();}).then(function(j){fx=j;paintFx();}).catch(function(){fx=null;});"
 fixed="fetch('https://api.frankfurter.app/latest?from=USD').then(function(r){if(!r.ok)throw new Error('Frankfurter '+r.status);return r.json();}).catch(function(){return fetch('https://open.er-api.com/v6/latest/USD').then(function(r){if(!r.ok)throw new Error('ER API '+r.status);return r.json();}).then(function(j){return {rates:j.rates,date:j.time_last_update_utc?j.time_last_update_utc.slice(5,16):'latest'};});}).then(function(j){fx=j;paintFx();}).catch(function(){fx=null;});"
 content=content.replace(broken,fixed)
 link_repairs={
  'https://corporate.vanguard.com/content/corporatesite/us/en/corp/articles/fuel-for-the-fire-retirement.html':'https://investor.vanguard.com/investor-resources-education/retirement',
  'https://www.bankofengland.co.uk/financial-stability-report':'https://www.bankofengland.co.uk/financial-stability',
  'https://www.finra.org/investors/personal-finance/paying-off-debt':'https://www.finra.org/investors/personal-finance/manage-your-debt',
  'https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-403b-tax-sheltered-annuity-plans':'https://www.irs.gov/publications/p571',
 }
 for stale,current in link_repairs.items():content=content.replace(stale,current)
 return content,content!=old

def remove_duplicate_article_package(content):
 """Remove an accidentally repeated schema/style/article package, preserving the first."""
 articles=list(re.finditer(r'<article\b',content,re.I))
 if len(articles)<2:return content,False
 second=articles[1].start();schemas=list(re.finditer(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>',content[:second],re.I))
 start=schemas[-1].start() if len(schemas)>=2 else second
 endm=re.search(r'</article\s*>',content[second:],re.I)
 if not endm:return content,False
 return content[:start]+content[second+endm.end():],True

def repair_article_schema(content,url):
 """Repair canonical identity in every regular BlogPosting JSON-LD graph."""
 changed=False
 def repl(match):
  nonlocal changed
  try:data=json.loads(match.group(2))
  except Exception:return match.group(0)
  found=False
  def walk(node):
   nonlocal found
   if isinstance(node,dict):
    typ=node.get('@type');types=typ if isinstance(typ,list) else [typ]
    if 'BlogPosting' in types:
     found=True;node['@id']=url+'#article';node['url']=url
     me=node.get('mainEntityOfPage')
     node['mainEntityOfPage']={'@type':'WebPage','@id':url} if not isinstance(me,dict) else {**me,'@id':url}
    for value in node.values():walk(value)
   elif isinstance(node,list):
    for value in node:walk(value)
  walk(data)
  if not found:return match.group(0)
  rendered=json.dumps(data,ensure_ascii=False,indent=2);new=match.group(1)+rendered+match.group(3);changed=changed or new!=match.group(0);return new
 pattern=r'(<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script\s*>)'
 return re.sub(pattern,repl,content,flags=re.I|re.S),changed

def main():
 tok=token();pages=collect('pages',tok);posts=collect('posts',tok);Path('motion_related_backup.json').write_text(json.dumps({'pages':pages,'posts':posts},ensure_ascii=False));changes=[]
 for p in pages:
  old=p.get('content','');new,runtime_fixed=repair_external_runtime(old);new=new.replace('if(!s.visible||s.hover||s.focus||s.touchUntil>Date.now())return;','if(!s.visible)return;')
  if 'MOVED' not in p.get('title','').upper():
   desc=PAGE_DESCRIPTIONS.get(p.get('title','').upper(),f"{p.get('title','')} from Daily Yield by Kushal K. Daga: finance information, tools and transparent analysis.")
   im=re.search(r'<img[^>]+src=["\']([^"\']+)',new,re.I);new=ensure_seo_meta(new,'Daily Yield: '+p.get('title','').title(),desc,im.group(1) if im else '')
  new=ensure_brand_identity(new);new=ensure_motion(new)
  if new!=old:update('pages',tok,p,new);changes.append({'kind':'page','url':p.get('url'),'related':0,'article_motion_loop_repaired':new.count('if(!s.visible)return;')>old.count('if(!s.visible)return;'),'runtime_fixed':runtime_fixed,'seo_meta':True,'brand_identity':True})
 for p in posts:
  old=p.get('content','');new,runtime_fixed=repair_external_runtime(old);new,deduped=remove_duplicate_article_package(new);new,schema_fixed=repair_article_schema(new,p.get('url',''));new=ensure_related(new,p,posts)
  if 'News' in p.get('labels',[]) or not any(k in new for k in ('DY_SEO_META_START','metaDesc')):
   desc='';sm=re.search(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',new,re.I|re.S)
   if sm:
    try:desc=json.loads(sm.group(1)).get('description','')
    except Exception:pass
   if not desc:desc=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',new)).strip()[:158]
   im=re.search(r'<img[^>]+src=["\']([^"\']+)',new,re.I)
   new=ensure_seo_meta(new,p.get('title',''),desc,im.group(1) if im else '')
  new=ensure_family(new);new=ensure_motion(new)
  if new!=old:update('posts',tok,p,new);changes.append({'kind':'post','url':p.get('url'),'related':new.count('class="dy-related-card"')//2,'duplicate_package_removed':deduped,'schema_fixed':schema_fixed,'runtime_fixed':runtime_fixed,'family':True,'seo_meta':('News' not in p.get('labels',[]) or 'DY_SEO_META_START' in new)})
 result={'apply':APPLY,'pages_scanned':len(pages),'posts_scanned':len(posts),'changes':changes,'related_shelves':sum(x['kind']=='post' and x['related']>=3 for x in changes)};Path('MOTION_RELATED_AUDIT.json').write_text(json.dumps(result,indent=2));print(json.dumps({'apply':APPLY,'pages':len(pages),'posts':len(posts),'changes':len(changes),'shelves':result['related_shelves']},indent=2))
if __name__=='__main__':main()
