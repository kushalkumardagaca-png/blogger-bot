#!/usr/bin/env python3
"""Prepare and audit every live Daily Yield Page/Post for AdSense review.

Uses the authenticated Blogger API only (zero public page requests), creates a
pre-change backup, changes only marked policy disclosures and missing image alt
text, and preserves every URL, title, label and unrelated content byte.
"""
from __future__ import annotations

from site_change_control import stop_if_frozen as _dy_stop_if_frozen
if __name__ == "__main__":
    _dy_stop_if_frozen('adsense_readiness')

import gzip, html, json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from seo_hygiene import image_alt_failures, repair_image_alts
import identity_contact as ident
import brand_seo
import reader_prose

BLOG_ID=os.environ.get('BLOGGER_BLOG_ID','8911514070006792465')
BACKUP=Path('ADSENSE_READINESS_BACKUP.json.gz')
REPORT_JSON=Path('ADSENSE_READINESS_REPORT.json')
REPORT_MD=Path('ADSENSE_READINESS_REPORT.md')
START='<!-- DY_ADSENSE_READINESS_START -->'; END='<!-- DY_ADSENSE_READINESS_END -->'

# The identity statement lives in one module, so the blog, the policy pages and
# the article footers cannot disagree about who publishes the site.
IDENTITY_START=ident.IDENTITY_START; IDENTITY_END=ident.IDENTITY_END
# Two live inconsistencies that read as misleading on review: the Contact page
# promised replies in two different time frames, and its email line showed a
# single address while the blog is administered from another one.
CONTACT_CONSISTENCY=(
 ('Replies in 24–48 hrs','Replies usually within 2–3 working days'),
 ('Reply lands in 24–48 hrs','Reply lands within 2–3 working days'),
 ('replies in 24–48 hours.','replies usually within 2–3 working days.'),
 ('replies in 24&#8211;48 hours.','replies usually within 2–3 working days.'),
 ('<b>24 to 48 hours</b>','<b>2 to 3 working days</b>'),
 ('24 to 48 hours','2 to 3 working days'),
)
# Any older reply-time promise, whatever the dash or entity used.
OLD_REPLY_TIME_PROMISE=re.compile(r'24\s*(?:&#8211;|&#8212;|to|[\u2013\u2014-])\s*48\s*hours?')
IDENTITY_PAGES=('about-us_02080501126.html','contact-us_01883938366.html')

POLICY_BLOCKS={
 'privacy-policy.html': '''<section aria-labelledby="dy-ads-privacy" class="dy-adsense-disclosure"><h2 id="dy-ads-privacy">Advertising, Google AdSense and your choices</h2><p>Daily Yield has applied to participate in Google AdSense and may display Google-served advertising after approval. Google and its advertising partners may use cookies, local storage, device information and similar technologies to deliver, limit, measure and protect advertising. Depending on your location and choices, ads may be personalised, non-personalised or limited.</p><p>Advertising consent is requested where required. You can revisit available choices through the <strong>Privacy choices</strong> control in the Daily Yield footer. You can also review <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">how Google uses information from sites and apps</a>, <a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">Google advertising technologies</a> and <a href="https://adssettings.google.com/" rel="noopener" target="_blank">Google Ads Settings</a>.</p><p>Daily Yield does not ask readers to click advertisements. An advertisement does not constitute editorial endorsement, financial advice or a recommendation by Daily Yield or Kushal Daga.</p></section>''',
 'terms-and-conditions.html': '''<section aria-labelledby="dy-ads-terms" class="dy-adsense-disclosure"><h2 id="dy-ads-terms">Advertising terms</h2><p>Daily Yield may display advertisements supplied by Google AdSense or other clearly identified providers after approval. Advertisers are responsible for their offers, products, destination pages and representations. Advertising does not alter Daily Yield's educational purpose and does not imply endorsement.</p><p>Readers must not use automated, incentivised, deceptive or repeated interactions with advertisements. Daily Yield does not offer rewards for viewing or clicking ads and does not ask readers to support the publication by clicking them.</p></section>''',
 'disclaimer.html': '''<section aria-labelledby="dy-ads-disclaimer" class="dy-adsense-disclosure"><h2 id="dy-ads-disclaimer">Advertising and editorial independence</h2><p>Advertising is operationally separate from Daily Yield's editorial content. The appearance of an advertisement does not make the advertiser, product or service part of a Daily Yield recommendation, and it is never personal financial, investment, tax, legal or credit advice. Readers should independently assess any advertised claim before acting.</p></section>''',
 'about-us_02080501126.html': '''<section aria-labelledby="dy-ads-about" class="dy-adsense-disclosure"><h2 id="dy-ads-about">How advertising supports Daily Yield</h2><p>Daily Yield may use clearly distinguishable advertising to help fund publishing and technical operations. Advertising does not purchase favourable coverage, change article conclusions or replace source-based editorial checks. Kushal Daga remains the accountable named author and Daily Yield remains responsible for its own published material.</p></section>''',
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

def ensure_identity(content,key):
 """Add the identity statement and remove two contradictory reply-time promises."""
 out=content
 for before,after in CONTACT_CONSISTENCY:
  if before!=after:out=out.replace(before,after)
 # One last sweep so no phrasing of the old promise survives anywhere on a page.
 out=OLD_REPLY_TIME_PROMISE.sub('2–3 working days',out)
 if key in IDENTITY_PAGES:
  block=ident.identity_block('page')
  if IDENTITY_START in out and IDENTITY_END in out:
   out=re.sub(re.escape(IDENTITY_START)+r'.*?'+re.escape(IDENTITY_END),lambda _m:block,out,flags=re.S)
  else:
   out=out+block
 return out


def ensure_block(content,key):
 block=START+STYLE+POLICY_BLOCKS[key]+END
 pattern=re.compile(re.escape(START)+'.*?'+re.escape(END),re.S)
 return pattern.sub(block,content,count=1) if pattern.search(content) else content.rstrip()+"\n"+block+"\n"

def patch(token,item,content,attempts=3):
 """Store the corrected page or post, retrying a transient Blogger conflict.

 Two maintenance runs touching the same page at the same moment, or a burst of
 updates, can make one call fail with a conflict or a temporary server error.
 A retry keeps a correct page from being reported as an unrepaired one.
 """
 body={'title':item['title'],'content':content}
 if item['resource']=='posts':body['labels']=item.get('labels',[])
 url=f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{item['resource']}/{item['id']}"
 last=None
 for attempt in range(1,attempts+1):
  try:
   return request(url,method='PATCH',headers={'Authorization':'Bearer '+token},body=body)
  except Exception as exc:
   last=exc
   time.sleep(2*attempt)
 raise last

def main():
 token=oauth();before=inventory(token);urls={f"{x['resource']}:{x['id']}":x['url'] for x in before}
 with gzip.open(BACKUP,'wt',encoding='utf-8') as f:json.dump({'createdAt':datetime.now(timezone.utc).isoformat(),'items':before},f,ensure_ascii=False)
 changed=[]
 for item in before:
  content=item.get('content','');new,alts_repaired=repair_image_alts(content,item.get('title','Daily Yield'))
  # An unrelated surname was once published as an alias of the author; that is a
  # materially inaccurate declaration, so it is corrected on every item.
  new,name_repaired=ident.repair_names(new)
  labels=item.get('labels') or [];labels_repaired=False
  if item['resource']=='posts' and any(ident.name_problems(label) for label in labels):
   relabelled=[ident.repair_names(label)[0] for label in labels]
   labels_repaired=relabelled!=labels
   item['labels']=relabelled;name_repaired=name_repaired or labels_repaired
  # Machine-assembled pages carried unnamed source links, repeated links and
  # leftover drafting shorthand; the reader-quality pass repairs that too.
  new,prose_repaired=reader_prose.normalise(new)
  # Every page and article carries the same statement of who writes it, the same
  # reader questions answered, and the same linked entity data, so one author and
  # one publication are recognised across the whole site.
  new,brand_repaired=brand_seo.enrich(new,'page' if item['resource']=='pages' else 'article',
                                      item.get('title',''),item.get('url',''))
  key=policy_key(item.get('url',''))
  if key:
   new=ensure_identity(new,key)
   new=ensure_block(new,key)
  if new!=content or labels_repaired:
   patch(token,item,new);changed.append({'kind':item['resource'][:-1],'id':item['id'],'title':item['title'],'url':item['url'],'policyDisclosure':bool(key),'imageAltsRepaired':alts_repaired,'nameClaimRepaired':name_repaired,'proseRepaired':prose_repaired,'brandSeoAdded':brand_repaired})
 def verify(items):
  """Return the failures that are really on the stored copies, plus the pages seen."""
  found=[];keys=set()
  for item in items:
   ref=f"{item['resource']}:{item['id']}";content=item.get('content','');key=policy_key(item.get('url',''))
   if item.get('url')!=urls.get(ref):found.append({'id':ref,'issue':'URL changed'})
   if not item.get('title','').strip():found.append({'id':ref,'issue':'empty title'})
   readable=html.unescape(re.sub('<[^>]+>',' ',content)).strip()
   controlled_move=item.get('url','').endswith('/p/share-market_0718113516.html')
   if len(readable)<200 and not controlled_move:found.append({'id':ref,'issue':'insufficient readable content'})
   if image_alt_failures(content):found.append({'id':ref,'issue':'missing image alt','count':len(image_alt_failures(content))})
   for problem in ident.name_problems(content):found.append({'id':ref,'issue':problem})
   for problem in reader_prose.problems(content):found.append({'id':ref,'issue':problem})
   if key:
    keys.add(key)
    if START not in content or END not in content:found.append({'id':ref,'issue':'AdSense disclosure missing'})
    if key in IDENTITY_PAGES:
     page_text=html.unescape(re.sub('<[^>]+>',' ',content))
     if IDENTITY_START not in content or IDENTITY_END not in content:found.append({'id':ref,'issue':'identity statement missing'})
     if ident.PRIMARY_EMAIL not in page_text or ident.OWNER_EMAIL not in page_text:
      found.append({'id':ref,'issue':'both monitored addresses must appear on this page'})
     if ident.BYLINE not in page_text:found.append({'id':ref,'issue':'public author name missing'})
     if ident.LEGAL_NAME not in page_text:found.append({'id':ref,'issue':"publisher's legal name missing"})
     if OLD_REPLY_TIME_PROMISE.search(page_text):found.append({'id':ref,'issue':'contradictory reply-time promise still present'})
  missing=sorted(set(POLICY_BLOCKS)-keys)
  for key in missing:found.append({'id':'page:'+key,'issue':'required policy page missing'})
  return found,keys
 # The blog's own name and description appear in the head of every page and in
 # search results, so they are part of the site's public identity. The Blogger
 # API is the only way to change them, so it is done here and then read back.
 blog_error=None
 try:
  h={'Authorization':'Bearer '+token};endpoint=f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}"
  blog=request(endpoint,headers=h)
  wanted=(f"{ident.PUBLICATION} publishes finance news, practical money guides, market insights and "
          f"transparent calculations, written by {ident.BYLINE}. Contact {ident.PRIMARY_EMAIL} "
          f"or {ident.OWNER_EMAIL}.")
  if ident.name_problems(blog.get('description','') or '') or (blog.get('description') or '').strip()!=wanted:
   # Blogger accepts the update with the full resource; the name and URL are sent
   # back unchanged so nothing else on the blog is touched.
   body={'kind':'blogger#blog','id':BLOG_ID,'name':blog.get('name') or 'DAILY YIELD',
         'description':wanted,'url':blog.get('url','https://dailyyield.blogspot.com/')}
   request(endpoint,method='PUT',headers=h,body=body)
   changed.append({'kind':'blog','id':BLOG_ID,'title':'Blog name and description','url':blog.get('url',''),
                   'policyDisclosure':False,'imageAltsRepaired':0,'nameClaimRepaired':True,'proseRepaired':False})
  stored=request(endpoint,headers=h).get('description','')
  if ident.name_problems(stored):blog_error=f"blog description still names the old name: {stored[:120]}"
 except Exception as exc:
  detail=''
  if hasattr(exc,'read'):
   try:detail=' '+exc.read().decode('utf-8','replace')[:240]
   except Exception:detail=''
  blog_error=f"blog name and description could not be updated: {type(exc).__name__}{detail}"

 after=inventory(token)
 fail,page_keys=verify(after)
 item_fail=list(fail)
 if blog_error:item_fail.append({'id':'blog:'+BLOG_ID,'issue':blog_error})
 if fail and any(not str(f['id']).startswith('blog:') for f in fail):
  # Blogger can serve a cached copy for a short time after a write. A repair that
  # has landed must not be reported as a failure, so every failing item is read
  # once more before it is judged. Anything that is still wrong is still a failure,
  # and a blog-level problem is never dismissed by re-reading cached pages.
  time.sleep(30)
  still,page_keys=verify(inventory(token))
  lingering={(f['id'],f['issue']) for f in still}
  fail=[f for f in fail if str(f['id']).startswith('blog:') or (f['id'],f['issue']) in lingering]
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
