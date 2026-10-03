#!/usr/bin/env python3
"""Prepare and audit every live Daily Yield Page/Post for AdSense review.

Uses the authenticated Blogger API only (zero public page requests), creates a
pre-change backup, changes only marked policy disclosures and missing image alt
text, and preserves every URL, title, label and unrelated content byte.
"""
from __future__ import annotations
import gzip, html, json, os, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from seo_hygiene import image_alt_failures, repair_image_alts

BLOG_ID=os.environ.get('BLOGGER_BLOG_ID','8911514070006792465')
BACKUP=Path('ADSENSE_READINESS_BACKUP.json.gz')
REPORT_JSON=Path('ADSENSE_READINESS_REPORT.json')
REPORT_MD=Path('ADSENSE_READINESS_REPORT.md')
START='<!-- DY_ADSENSE_READINESS_START -->'; END='<!-- DY_ADSENSE_READINESS_END -->'

POLICY_BLOCKS={
 'privacy-policy.html': '''<section aria-labelledby="dy-ads-privacy" class="dy-adsense-disclosure"><h2 id="dy-ads-privacy">Advertising, Google AdSense and your choices</h2><p>Daily Yield has applied to participate in Google AdSense and may display Google-served advertising after approval. Google and its advertising partners may use cookies, local storage, device information and similar technologies to deliver, limit, measure and protect advertising. Depending on your location and choices, ads may be personalised, non-personalised or limited.</p><p>Advertising consent is requested where required. You can revisit available choices through the <strong>Privacy choices</strong> control in the Daily Yield footer. You can also review <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">how Google uses information from sites and apps</a>, <a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">Google advertising technologies</a> and <a href="https://adssettings.google.com/" rel="noopener" target="_blank">Google Ads Settings</a>.</p><p>Daily Yield does not ask readers to click advertisements. An advertisement does not constitute editorial endorsement, financial advice or a recommendation by Daily Yield or Kushal K. Daga.</p></section>''',
 'terms-and-conditions.html': '''<section aria-labelledby="dy-ads-terms" class="dy-adsense-disclosure"><h2 id="dy-ads-terms">Advertising terms</h2><p>Daily Yield may display advertisements supplied by Google AdSense or other clearly identified providers after approval. Advertisers are responsible for their offers, products, destination pages and representations. Advertising does not alter Daily Yield's educational purpose and does not imply endorsement.</p><p>Readers must not use automated, incentivised, deceptive or repeated interactions with advertisements. Daily Yield does not offer rewards for viewing or clicking ads and does not ask readers to support the publication by clicking them.</p></section>''',
 'disclaimer.html': '''<section aria-labelledby="dy-ads-disclaimer" class="dy-adsense-disclosure"><h2 id="dy-ads-disclaimer">Advertising and editorial independence</h2><p>Advertising is operationally separate from Daily Yield's editorial content. The appearance of an advertisement does not make the advertiser, product or service part of a Daily Yield recommendation, and it is never personal financial, investment, tax, legal or credit advice. Readers should independently assess any advertised claim before acting.</p></section>''',
 'about-us_02080501126.html': '''<section aria-labelledby="dy-ads-about" class="dy-adsense-disclosure"><h2 id="dy-ads-about">How advertising supports Daily Yield</h2><p>Daily Yield may use clearly distinguishable advertising to help fund publishing and technical operations. Advertising does not purchase favourable coverage, change article conclusions or replace source-based editorial checks. Kushal K. Daga remains the accountable named author and Daily Yield remains responsible for its own published material.</p></section>''',
 'contact-us_01883938366.html': '''<section aria-labelledby="dy-ads-contact" class="dy-adsense-disclosure"><h2 id="dy-ads-contact">Advertising and privacy enquiries</h2><p>For questions about Daily Yield advertising placement, privacy choices or an advertisement appearing near our content, contact <a href="mailto:dailyyield.official@gmail.com">dailyyield.official@gmail.com</a>. Do not send passwords, one-time codes, bank details or identity documents.</p></section>'''
}
STYLE='''<style>.dy-adsense-disclosure{max-width:1040px;margin:24px auto;padding:22px;border:1px solid #dce7e1;border-radius:16px;background:#fff;color:#17231d;line-height:1.7}.dy-adsense-disclosure h2{margin:0 0 10px;color:#073b2b;font-size:clamp(22px,3vw,31px)}.dy-adsense-disclosure p{margin:9px 0}.dy-adsense-disclosure a{color:#08744f;text-decoration:underline;text-underline-offset:2px}</style>'''

def required(n):
 v=os.environ.get(n,'').strip()
 if not v: raise RuntimeError('missing required secret: '+n)
 return v

def request(url,method='GET',headers=None,body=None):
 if 'dailyyield.blogspot.com' in url.lower(): raise RuntimeError('ZERO-VIEW POLICY BLOCKED public Daily Yield request')
 data=json.dumps(body).encode() if body is not None else None
 h={'User-Agent':'DailyYield-AdSenseReadiness/1.0',**(headers or {})}
 if body is not None:h['Content-Type']='application/json'
 with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=h,method=method),timeout=75) as r:
  raw=r.read();return json.loads(raw) if raw else {}

def oauth():
 form=urllib.parse.urlencode({'client_id':required('BLOGGER_CLIENT_ID'),'client_secret':required('BLOGGER_CLIENT_SECRET'),'refresh_token':required('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'}).encode()
 with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=form,method='POST'),timeout=30) as r:return json.load(r)['access_token']

def inventory(token):
 out=[];h={'Authorization':'Bearer '+token}
 for resource in ('pages','posts'):
  cursor=''
  while True:
   fields='id,title,url,content,published,updated,status'+(',labels' if resource=='posts' else '')
   q={'status':'live','fetchBodies':'true','maxResults':'50','fields':f'items({fields}),nextPageToken'}
   if cursor:q['pageToken']=cursor
   d=request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{resource}?{urllib.parse.urlencode(q)}",headers=h)
   for x in d.get('items',[]):x['resource']=resource;out.append(x)
   cursor=d.get('nextPageToken','')
   if not cursor:break
 return out

def policy_key(url):
 path=urllib.parse.urlsplit(url).path
 return next((k for k in POLICY_BLOCKS if path.endswith('/'+k)),None)

def ensure_block(content,key):
 block=START+STYLE+POLICY_BLOCKS[key]+END
 pattern=re.compile(re.escape(START)+'.*?'+re.escape(END),re.S)
 return pattern.sub(block,content,count=1) if pattern.search(content) else content.rstrip()+"\n"+block+"\n"

def patch(token,item,content):
 body={'title':item['title'],'content':content}
 if item['resource']=='posts':body['labels']=item.get('labels',[])
 return request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{item['resource']}/{item['id']}",method='PATCH',headers={'Authorization':'Bearer '+token},body=body)

def main():
 token=oauth();before=inventory(token);urls={f"{x['resource']}:{x['id']}":x['url'] for x in before}
 with gzip.open(BACKUP,'wt',encoding='utf-8') as f:json.dump({'createdAt':datetime.now(timezone.utc).isoformat(),'items':before},f,ensure_ascii=False)
 changed=[]
 for item in before:
  content=item.get('content','');new,alts_repaired=repair_image_alts(content,item.get('title','Daily Yield'))
  key=policy_key(item.get('url',''))
  if key:new=ensure_block(new,key)
  if new!=content:
   patch(token,item,new);changed.append({'kind':item['resource'][:-1],'id':item['id'],'title':item['title'],'url':item['url'],'policyDisclosure':bool(key),'imageAltsRepaired':alts_repaired})
 after=inventory(token);fail=[];page_keys=set()
 for item in after:
  ident=f"{item['resource']}:{item['id']}";content=item.get('content','');key=policy_key(item.get('url',''))
  if item.get('url')!=urls.get(ident):fail.append({'id':ident,'issue':'URL changed'})
  if not item.get('title','').strip():fail.append({'id':ident,'issue':'empty title'})
  readable=len(html.unescape(re.sub('<[^>]+>',' ',content))).strip()
  controlled_move=item.get('url','').endswith('/p/share-market_0718113516.html')
  if len(readable)<200 and not controlled_move:fail.append({'id':ident,'issue':'insufficient readable content'})
  if image_alt_failures(content):fail.append({'id':ident,'issue':'missing image alt','count':len(image_alt_failures(content))})
  if key:
   page_keys.add(key)
   if START not in content or END not in content:fail.append({'id':ident,'issue':'AdSense disclosure missing'})
 missing=sorted(set(POLICY_BLOCKS)-page_keys)
 for key in missing:fail.append({'id':'page:'+key,'issue':'required policy page missing'})
 report={'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'PASS' if not fail else 'FAIL','mode':'AUTHENTICATED_BLOGGER_API_ZERO_PUBLIC_VIEWS','syntheticViews':0,'summary':{'items':len(after),'posts':sum(x['resource']=='posts' for x in after),'pages':sum(x['resource']=='pages' for x in after),'changed':len(changed),'policyPagesReady':len(page_keys),'failures':len(fail)},'changed':changed,'failures':fail,'notes':['Approval and revenue remain Google decisions.','No ad code is installed before approval.','Unrelated content, URLs, titles and labels are preserved.']}
 REPORT_JSON.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 s=report['summary'];lines=['# Daily Yield AdSense Readiness','',f"- **Status:** {report['status']}",'- **Public Daily Yield requests:** 0','- **Synthetic views:** 0',f"- **Inventory:** {s['items']} items · {s['posts']} Posts · {s['pages']} Pages",f"- **Policy Pages ready:** {s['policyPagesReady']}/5",f"- **Items changed:** {s['changed']}",f"- **Failures:** {s['failures']}",'','## Changes']+[f"- {x['kind'].title()}: {x['title']} — disclosure={x['policyDisclosure']}, repaired alts={x['imageAltsRepaired']}" for x in changed]
 if fail:lines+=['','## Failures']+[f"- {x}" for x in fail]
 REPORT_MD.write_text('\n'.join(lines)+'\n')
 print(json.dumps({'status':report['status'],**s,'syntheticViews':0}))
 for row in fail[:20]:print('::error title=AdSense readiness audit::'+json.dumps(row,ensure_ascii=True))
 return 1 if fail else 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as exc:
  diagnostic={'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'ERROR','mode':'AUTHENTICATED_BLOGGER_API_ZERO_PUBLIC_VIEWS','syntheticViews':0,'errorType':exc.__class__.__name__,'error':str(exc)[:500]}
  REPORT_JSON.write_text(json.dumps(diagnostic,indent=2)+'\n')
  REPORT_MD.write_text('# Daily Yield AdSense Readiness\n\n- **Status:** ERROR\n- **Public Daily Yield requests:** 0\n- **Error:** '+exc.__class__.__name__+'\n')
  print('::error title=AdSense readiness execution::'+exc.__class__.__name__+': '+str(exc)[:500])
  raise
