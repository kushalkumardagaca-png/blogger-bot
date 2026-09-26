#!/usr/bin/env python3
"""Rendered production audit of every public Daily Yield URL at three responsive widths."""
import asyncio,json,re,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
BLOG='https://dailyyield.blogspot.com';OUT=Path('rendered_audit');OUT.mkdir(exist_ok=True)
def get_json(url):
 req=urllib.request.Request(url,headers={'User-Agent':'DailyYield-audit/2.0'})
 with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
def inventory():
 urls=[(BLOG+'/', 'home')]
 for kind in ('pages','posts'):
  start=1;seen=0
  while True:
   feed=get_json(f'{BLOG}/feeds/{kind}/default?alt=json&max-results=50&start-index={start}').get('feed',{});batch=feed.get('entry',[])
   for e in batch:
    u=next((x['href'] for x in e.get('link',[]) if x.get('rel')=='alternate'),'')
    if u:urls.append((u,kind[:-1]))
   seen+=len(batch);total=int(feed.get('openSearch$totalResults',{}).get('$t',seen))
   if not batch or seen>=total:break
   start+=len(batch)
 return list(dict.fromkeys(urls))
VIEWPORTS=[('mobile',360,800),('tablet',768,1024),('desktop',1440,1000)]
IGNORE_FAIL=('google-analytics.com','googletagmanager.com','doubleclick.net','googleads','favicon.ico','csp.withgoogle.com','api.frankfurter.app','api.coingecko.com','widget-sheriff.tradingview-widget.com')
EVAL='''() => {
 const q=s=>Array.from(document.querySelectorAll(s)),vw=document.documentElement.clientWidth;
 const cards=q('.ar-card,.kn-card,.dy-related-card,.kvsd-mqcard').filter(x=>x.getClientRects().length);
 const imgs=q('img').filter(x=>{const r=x.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth&&(!x.complete||x.naturalWidth===0)}).map(x=>x.currentSrc||x.src);
 const ids={},dups=[];q('[id]').forEach(x=>{ids[x.id]=(ids[x.id]||0)+1});Object.keys(ids).forEach(x=>{if(ids[x]>1)dups.push([x,ids[x]])});
 const overflow=[];q('body *').forEach(x=>{const r=x.getBoundingClientRect(),cs=getComputedStyle(x);if(r.width>vw+8&&cs.position!=='fixed'&&!x.closest('.kn-track,.ar-group,.dy-related-track,.kvsd-mq,.dyw-category-track,.marquee-track')&&cs.overflowX!=='auto'&&cs.overflowX!=='scroll'&&overflow.length<15)overflow.push([x.tagName,x.id,x.className,String(Math.round(r.width))])});
 const badCards=cards.map(x=>[x.className,Math.round(x.getBoundingClientRect().width),Math.round(x.getBoundingClientRect().height)]).filter(x=>x[1]<180||x[1]>340||x[2]>900);
 function qs(el,s){return Array.from(el.querySelectorAll(s))}const shelves=q('.dy-related').map(s=>Array.from(new Set(qs(s,'.dy-related-card').map(a=>a.href))).length);
 const badHrefs=q('a[href]').map(a=>a.getAttribute('href')).filter(h=>!h||h==='#'||/^javascript:/i.test(h));
 const desc=(document.querySelector('meta[name="description"]')||{}).content||'',canonical=(document.querySelector('link[rel="canonical"]')||{}).href||'',ogTitle=(document.querySelector('meta[property="og:title"]')||{}).content||'',ogDesc=(document.querySelector('meta[property="og:description"]')||{}).content||'',ogImage=(document.querySelector('meta[property="og:image"]')||{}).content||'';
 const schemaErrors=[];q('script[type="application/ld+json"]').forEach((s,i)=>{try{JSON.parse(s.textContent)}catch(e){schemaErrors.push(i+': '+e.message)}});
 const allLinks=q('a[href]').map(a=>a.href),internal=allLinks.filter(h=>h.startsWith('https://dailyyield.blogspot.com/')),external=allLinks.filter(h=>/^https?:/i.test(h)&&!h.startsWith('https://dailyyield.blogspot.com/'));
 return {vw,bodyScroll:document.documentElement.scrollWidth,badCards,imgs,dups,overflow,shelves,badHrefs:badHrefs.slice(0,20),title:document.title,byline:document.body.innerText.includes('Kushal K. Daga'),desc,canonical,ogTitle,ogDesc,ogImage,schemaErrors,h1:q('h1').filter(x=>x.getClientRects().length).length,contextCards:q('.dy-context').length,sourceLinks:q('.fbk-src').length,internalLinks:new Set(internal).size,externalLinks:new Set(external).size};
}'''
def evaluate_issues(data,url,kind,failed,console):
 issues=[]
 if data['bodyScroll']>data['vw']+8:issues.append(f"body horizontal overflow {data['bodyScroll']} > {data['vw']}")
 if data['badCards']:issues.append('bad card dimensions '+json.dumps(data['badCards'][:8]))
 if data['imgs']:issues.append('broken visible images '+json.dumps(data['imgs'][:8]))
 if data['dups']:issues.append('duplicate ids '+json.dumps(data['dups'][:10]))
 if any(x!=4 for x in data['shelves']):issues.append('related shelf does not contain 4 unique links '+str(data['shelves']))
 if kind=='post' and not data['byline']:issues.append('visible Kushal K. Daga branding missing')
 if data['badHrefs']:issues.append('empty/script hrefs '+json.dumps(data['badHrefs']))
 if not data['title'].strip():issues.append('SEO title missing')
 if 'share-market_0718113516' not in url and not (50<=len(data['desc'])<=180):issues.append(f"meta description length {len(data['desc'])}, expected 50–180")
 if 'share-market_0718113516' not in url and data['canonical'].rstrip('/')!=url.rstrip('/'):issues.append('canonical mismatch '+data['canonical'])
 if not data['ogTitle'] or not data['ogDesc']:issues.append('Open Graph title/description missing')
 if kind=='post' and not data['ogImage']:issues.append('Open Graph image missing')
 if kind!='home' and data['h1']<1:issues.append('visible H1 missing')
 if data['schemaErrors']:issues.append('invalid rendered JSON-LD '+json.dumps(data['schemaErrors']))
 if kind=='post' and data['contextCards']<1:issues.append('contextual internal-link card missing')
 if kind=='post' and data['internalLinks']<5:issues.append(f"only {data['internalLinks']} unique internal links")
 if kind=='post' and ('Finance News' in data['title'] or 'Finance Wire' in data['title']) and data['sourceLinks']<1:issues.append('news external source links missing')
 relevant=[x for x in failed if not any(y in x for y in IGNORE_FAIL)]
 if relevant:issues.append('failed resources '+json.dumps(relevant[:10]))
 severe=[x for x in console if x.startswith('pageerror:') and 'solveSimpleChallenge is not defined' not in x or any(y in x.lower() for y in ['uncaught','referenceerror','typeerror']) and 'solvesimplechallenge' not in x.lower()]
 if severe:issues.append('console '+json.dumps(severe[:8]))
 return issues
async def audit_url(browser,sem,url,kind):
 rows=[]
 async with sem:
  page=await browser.new_page(viewport={'width':1440,'height':1000});console=[];failed=[]
  page.on('pageerror',lambda e:console.append('pageerror: '+str(e)))
  page.on('console',lambda m:console.append(m.type+': '+m.text) if m.type=='error' else None)
  page.on('requestfailed',lambda r:failed.append(r.url+' :: '+str(r.failure)))
  try:
   resp=None
   for attempt in range(4):
    resp=await page.goto(url,wait_until='domcontentloaded',timeout=45000)
    if resp and resp.status not in (429,500,502,503,504):break
    await page.wait_for_timeout(2500*(attempt+1))
   status=resp.status if resp else 0
   if status>=400 or not resp:
    return [{'url':url,'kind':kind,'viewport':n,'issues':[f'HTTP {status or "no response"}']} for n,_,_ in VIEWPORTS]
   try:await page.wait_for_load_state('networkidle',timeout=12000)
   except:pass
   await page.wait_for_timeout(2200)
   for name,w,h in VIEWPORTS:
    await page.set_viewport_size({'width':w,'height':h});await page.wait_for_timeout(450)
    data=await page.evaluate(EVAL);issues=evaluate_issues(data,url,kind,failed,console)
    if issues:
     slug=re.sub(r'[^a-z0-9]+','-',url.lower()).strip('-')[-90:];await page.screenshot(path=str(OUT/f'{slug}-{name}.png'),full_page=False)
    rows.append({'url':url,'kind':kind,'viewport':name,'issues':issues,'data':data})
   return rows
  except Exception as e:return [{'url':url,'kind':kind,'viewport':n,'issues':['AUDIT ERROR '+repr(e)]} for n,_,_ in VIEWPORTS]
  finally:await page.close()
async def main():
 urls=inventory();print('inventory',len(urls),flush=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox']);sem=asyncio.Semaphore(2)
  tasks=[audit_url(browser,sem,u,k) for u,k in urls];rows=[]
  for fut in asyncio.as_completed(tasks):
   batch=await fut;rows+=batch;print(batch[0]['url'],sum(bool(x['issues']) for x in batch),flush=True)
  await browser.close()
 report={'urls':len(urls),'rendered_checks':len(rows),'failures':sum(bool(x['issues']) for x in rows),'results':sorted(rows,key=lambda x:(x['url'],x['viewport']))}
 Path('RENDERED_SITE_AUDIT.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
if __name__=='__main__':asyncio.run(main())
