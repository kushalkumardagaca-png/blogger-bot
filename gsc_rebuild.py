#!/usr/bin/env python3
"""Rebuild Daily Yield's official Search Console baseline and inspect every current URL.

Official API boundaries:
- Automates property/sitemap inventory, sitemap submit/delete, Search Analytics,
  and inspection of Google's indexed version.
- Does NOT automate Test Live URL or Request Indexing; Google exposes no API for them.
"""
from pathlib import Path
import datetime as dt, html, json, os, re, time, urllib.error, urllib.parse, urllib.request

BLOG='https://dailyyield.blogspot.com'; SITE=BLOG+'/'
CURRENT_SITEMAPS=[BLOG+'/sitemap.xml',BLOG+'/sitemap-pages.xml']
RESET=os.environ.get('RESET_OLD_SITEMAPS','true').lower()=='true'
TODAY=dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).date()

def fetch_json(url,headers=None,method='GET',body=None):
 data=json.dumps(body).encode() if body is not None else None
 req=urllib.request.Request(url,data=data,method=method,headers=headers or {'User-Agent':'DailyYield-GSC/1.0'})
 with urllib.request.urlopen(req,timeout=60) as r:
  raw=r.read();return json.loads(raw) if raw else {}
def token():
 form=urllib.parse.urlencode({'client_id':os.environ.get('GSC_CLIENT_ID') or os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ.get('GSC_CLIENT_SECRET') or os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['GSC_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 req=urllib.request.Request('https://oauth2.googleapis.com/token',data=form,method='POST')
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)['access_token']
def gsc(access,method,path,body=None):
 url=path if path.startswith('http') else 'https://www.googleapis.com/webmasters/v3/'+path
 return fetch_json(url,{'Authorization':'Bearer '+access,'Content-Type':'application/json','User-Agent':'DailyYield-GSC/1.0'},method,body)
def feed(kind):
 data=fetch_json(f'{BLOG}/feeds/{kind}/default?alt=json&max-results=100')
 out=[]
 for e in data.get('feed',{}).get('entry',[]):
  url=next((x.get('href','') for x in e.get('link',[]) if x.get('rel')=='alternate'),'')
  out.append({'kind':kind[:-1],'title':e.get('title',{}).get('$t',''),'url':url,'published':e.get('published',{}).get('$t',''),'updated':e.get('updated',{}).get('$t','')})
 return out
def indexable_inventory():
 items=[{'kind':'home','title':'Daily Yield','url':SITE,'published':'','updated':''}]+feed('pages')+feed('posts')
 # This legacy URL is intentionally a redirect notice and must not be submitted as an index target.
 for x in items:x['indexable']=not x['url'].endswith('/p/share-market_0718113516.html')
 return items
def inspect(access,url):
 result=gsc(access,'POST','https://searchconsole.googleapis.com/v1/urlInspection/index:inspect',{'inspectionUrl':url,'siteUrl':SITE,'languageCode':'en-US'})
 status=(result.get('inspectionResult',{}).get('indexStatusResult') or {})
 return {'verdict':status.get('verdict','UNKNOWN'),'coverageState':status.get('coverageState',''),'robotsTxtState':status.get('robotsTxtState',''),'indexingState':status.get('indexingState',''),'pageFetchState':status.get('pageFetchState',''),'lastCrawlTime':status.get('lastCrawlTime',''),'googleCanonical':status.get('googleCanonical',''),'userCanonical':status.get('userCanonical',''),'crawledAs':status.get('crawledAs',''),'referringUrls':status.get('referringUrls',[])[:5],'sitemap':status.get('sitemap',[])[:5],'inspectionLink':result.get('inspectionResult',{}).get('inspectionResultLink','')}
def main():
 if not os.environ.get('GSC_REFRESH_TOKEN'):raise SystemExit('GSC_REFRESH_TOKEN is missing. Complete the one-time owner OAuth authorization first.')
 access=token();sites=gsc(access,'GET','sites');entries=sites.get('siteEntry',[])
 exact=next((x for x in entries if x.get('siteUrl')==SITE),None)
 if not exact:
  visible=', '.join(x.get('siteUrl','') for x in entries) or 'none'
  raise SystemExit(f'Exact verified URL-prefix property {SITE} is not visible to this Google account. Visible: {visible}')
 inventory=indexable_inventory();active=[x for x in inventory if x['indexable']]
 enc=urllib.parse.quote(SITE,safe='');before=gsc(access,'GET',f'sites/{enc}/sitemaps').get('sitemap',[]);deleted=[]
 if RESET:
  for sm in before:
   path=sm.get('path','')
   if path and path not in CURRENT_SITEMAPS:
    gsc(access,'DELETE',f'sites/{enc}/sitemaps/{urllib.parse.quote(path,safe="")}');deleted.append(path)
 for path in CURRENT_SITEMAPS:gsc(access,'PUT',f'sites/{enc}/sitemaps/{urllib.parse.quote(path,safe="")}')
 after=gsc(access,'GET',f'sites/{enc}/sitemaps').get('sitemap',[])
 inspections=[]
 for i,item in enumerate(active):
  try:status=inspect(access,item['url']);error=''
  except Exception as exc:status={};error=str(exc)[:240]
  inspections.append({**item,**status,'error':error});time.sleep(.13)
 manual=[]
 for row in inspections:
  canonical_ok=not row.get('googleCanonical') or row.get('googleCanonical').rstrip('/')==row['url'].rstrip('/')
  if row.get('verdict')!='PASS' or not canonical_ok:
   manual.append({'url':row['url'],'title':row['title'],'indexedVerdict':row.get('verdict','UNKNOWN'),'coverageState':row.get('coverageState',''),'pageFetchState':row.get('pageFetchState',''),'googleCanonical':row.get('googleCanonical',''),'manualSteps':['Open URL Inspection in Search Console','Click Test Live URL','If the live result says the URL can be indexed, click Request Indexing']})
 baseline={'started':TODAY.isoformat(),'note':'Fresh Daily Yield monitoring baseline. Historical Search Console data remains Google-owned and cannot be erased through the API.','property':SITE,'permission':exact.get('permissionLevel'),'sitemaps':CURRENT_SITEMAPS,'url_count':len(active)}
 Path('GSC_BASELINE.json').write_text(json.dumps(baseline,indent=2))
 report={'runDate':TODAY.isoformat(),'property':SITE,'permission':exact.get('permissionLevel'),'visibleProperties':entries,'resetOldSitemaps':RESET,'deletedSitemaps':deleted,'submittedSitemaps':after,'inventory':inventory,'inspections':inspections,'summary':{'inventory':len(inventory),'indexable':len(active),'redirectExcluded':len(inventory)-len(active),'pass':sum(x.get('verdict')=='PASS' for x in inspections),'notPass':sum(x.get('verdict')!='PASS' for x in inspections),'inspectionErrors':sum(bool(x.get('error')) for x in inspections),'manualLiveTestQueue':len(manual)},'manualQueue':manual}
 Path('GSC_REBUILD_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
 lines=['# Daily Yield — Search Console Rebuild','',f"Baseline: **{TODAY.isoformat()}**  ",f"Property: `{SITE}`  ",f"Permission: **{exact.get('permissionLevel','unknown')}**",'',f"- Current inventory: **{len(inventory)} URLs**",f"- Indexable targets: **{len(active)}**",f"- Intentional redirect excluded: **{len(inventory)-len(active)}**",f"- Google indexed-version verdict PASS: **{report['summary']['pass']}**",f"- Inspection errors: **{report['summary']['inspectionErrors']}**",f"- Manual Live Test queue: **{len(manual)}**",'', '## Current sitemap submissions']
 for sm in after:lines.append(f"- `{sm.get('path')}` — errors {sm.get('errors',0)}, warnings {sm.get('warnings',0)}, pending {sm.get('isPending',False)}")
 lines+=['','## Manual Live Test / Request Indexing queue','', '> Google provides no API for these two actions. Complete them in the Search Console interface.','']
 if manual:
  for i,x in enumerate(manual,1):lines.append(f"{i}. [{x['title']}]({x['url']}) — {x['indexedVerdict']}; {x['coverageState'] or 'no coverage state'}")
 else:lines.append('No URLs currently require manual follow-up based on the indexed-version inspection.')
 Path('GSC_REBUILD_REPORT.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(report['summary'],indent=2))
if __name__=='__main__':main()
