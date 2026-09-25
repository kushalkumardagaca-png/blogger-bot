#!/usr/bin/env python3
"""Rendered production audit of every public Daily Yield Page and Post."""
import asyncio,json,re,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
BLOG='https://dailyyield.blogspot.com';OUT=Path('rendered_audit');OUT.mkdir(exist_ok=True)
def get_json(url):
 req=urllib.request.Request(url,headers={'User-Agent':'DailyYield-audit/1.0'})
 with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
def inventory():
 urls=[(BLOG+'/', 'home')]
 for kind in ('pages','posts'):
  data=get_json(f'{BLOG}/feeds/{kind}/default?alt=json&max-results=100')
  for e in data.get('feed',{}).get('entry',[]):
   u=next((x['href'] for x in e.get('link',[]) if x.get('rel')=='alternate'),'')
   if u:urls.append((u,kind[:-1]))
 return list(dict.fromkeys(urls))
VIEWPORTS=[('mobile',360,800),('tablet',768,1024),('desktop',1440,1000)]
IGNORE_FAIL=('google-analytics.com','googletagmanager.com','doubleclick.net','googleads','favicon.ico','csp.withgoogle.com')
async def audit_one(browser,sem,url,kind,vp):
 name,w,h=vp;issues=[];console=[];failed=[]
 async with sem:
  page=await browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1,is_mobile=(name=='mobile'),has_touch=(name=='mobile'))
  page.on('pageerror',lambda e:console.append('pageerror: '+str(e)))
  page.on('console',lambda m:console.append(m.type+': '+m.text) if m.type=='error' else None)
  page.on('requestfailed',lambda r:failed.append(r.url+' :: '+str(r.failure)))
  try:
   resp=await page.goto(url,wait_until='domcontentloaded',timeout=45000)
   if not resp or resp.status>=400:issues.append(f'HTTP {resp.status if resp else "no response"}')
   try:await page.wait_for_load_state('networkidle',timeout=12000)
   except:pass
   await page.wait_for_timeout(2800)
   data=await page.evaluate('''() => {
    const q=s=>Array.from(document.querySelectorAll(s)), vw=document.documentElement.clientWidth;
    const cards=q('.ar-card,.kn-card,.dy-related-card,.kvsd-mqcard').filter(x=>x.getClientRects().length);
    const imgs=q('img').filter(x=>{const r=x.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth&&(!x.complete||x.naturalWidth===0)}).map(x=>x.currentSrc||x.src);
    const ids={},dups=[];q('[id]').forEach(x=>{ids[x.id]=(ids[x.id]||0)+1});Object.keys(ids).forEach(x=>{if(ids[x]>1)dups.push([x,ids[x]])});
    const overflow=[];q('body *').forEach(x=>{const r=x.getBoundingClientRect(),cs=getComputedStyle(x);if(r.width>vw+8 && cs.position!=='fixed' && !x.closest('.kn-track,.ar-group,.dy-related-track,.kvsd-mq,.dyw-category-track,.marquee-track') && cs.overflowX!=='auto' && cs.overflowX!=='scroll' && overflow.length<15)overflow.push([x.tagName,x.id,x.className,String(Math.round(r.width))])});
    const badCards=cards.map(x=>[x.className,Math.round(x.getBoundingClientRect().width),Math.round(x.getBoundingClientRect().height)]).filter(x=>x[1]<180||x[1]>340||x[2]>900);
    const related=q('.dy-related').map(s=>new Set(q.call?[]:[]));
    const shelves=q('.dy-related').map(s=>Array.from(new Set(qs(s,'.dy-related-card').map(a=>a.href))).length);
    function qs(el,s){return Array.from(el.querySelectorAll(s))}
    const badHrefs=q('a[href]').map(a=>a.getAttribute('href')).filter(h=>!h||h==='#'||/^javascript:/i.test(h));
    return {vw,bodyScroll:document.documentElement.scrollWidth,badCards,imgs,dups,overflow,shelves,badHrefs:badHrefs.slice(0,20),title:document.title,byline:document.body.innerText.includes('Kushal K. Daga')};
   }''')
   if data['bodyScroll']>data['vw']+8:issues.append(f"body horizontal overflow {data['bodyScroll']} > {data['vw']}")
   if data['badCards']:issues.append('bad card dimensions '+json.dumps(data['badCards'][:8]))
   if data['imgs']:issues.append('broken visible images '+json.dumps(data['imgs'][:8]))
   if data['dups']:issues.append('duplicate ids '+json.dumps(data['dups'][:10]))
   if any(x!=4 for x in data['shelves']):issues.append('related shelf does not contain 4 unique links '+str(data['shelves']))
   if kind=='post' and not data['byline']:issues.append('visible Kushal K. Daga branding missing')
   if data['badHrefs']:issues.append('empty/script hrefs '+json.dumps(data['badHrefs']))
   relevant=[x for x in failed if not any(y in x for y in IGNORE_FAIL)]
   if relevant:issues.append('failed resources '+json.dumps(relevant[:10]))
   severe_console=[x for x in console if not any(y in x.lower() for y in ['favicon','adsbygoogle','cors','third-party cookie','requeststorageaccess','frame-ancestors','framing'])]
   if severe_console:issues.append('console '+json.dumps(severe_console[:8]))
   if issues:
    slug=re.sub(r'[^a-z0-9]+','-',url.lower()).strip('-')[-90:]
    await page.screenshot(path=str(OUT/f'{slug}-{name}.png'),full_page=False)
   return {'url':url,'kind':kind,'viewport':name,'issues':issues,'data':data}
  except Exception as e:return {'url':url,'kind':kind,'viewport':name,'issues':['AUDIT ERROR '+repr(e)]}
  finally:await page.close()
async def main():
 urls=inventory();print('inventory',len(urls),flush=True)
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox']);sem=asyncio.Semaphore(6)
  tasks=[audit_one(browser,sem,u,k,v) for u,k in urls for v in VIEWPORTS]
  rows=[]
  for fut in asyncio.as_completed(tasks):
   r=await fut;rows.append(r);print(r['viewport'],r['url'],len(r['issues']),flush=True)
  await browser.close()
 report={'urls':len(urls),'rendered_checks':len(rows),'failures':sum(bool(x['issues']) for x in rows),'results':sorted(rows,key=lambda x:(x['url'],x['viewport']))}
 Path('RENDERED_SITE_AUDIT.json').write_text(json.dumps(report,indent=2));
 print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
if __name__=='__main__':asyncio.run(main())
