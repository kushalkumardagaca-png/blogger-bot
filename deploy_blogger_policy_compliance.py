#!/usr/bin/env python3
"""Idempotently publish Daily Yield's Blogger-policy disclosures and safeguards."""
from __future__ import annotations

from site_change_control import stop_if_frozen as _dy_stop_if_frozen
if __name__ == "__main__":
    _dy_stop_if_frozen('deploy_blogger_policy_compliance')

import datetime,json,os,re
from pathlib import Path
from urllib.parse import urlparse
import requests
START='<!-- DY_BLOGGER_POLICY_2026_12_START -->';END='<!-- DY_BLOGGER_POLICY_2026_12_END -->'
BLOG='https://dailyyield.blogspot.com';BASE=f"https://www.googleapis.com/blogger/v3/blogs/{os.environ['BLOGGER_BLOG_ID']}"
PATHS={'/p/about-us_02080501126.html':'about','/p/disclaimer.html':'disclaimer','/p/privacy-policy.html':'privacy','/p/contact-us_01883938366.html':'contact','/p/terms-and-conditions.html':'terms'}
COMMON='''<p><strong>Effective editorial standard:</strong> 15 October 2026. Last policy review: 14 October 2026.</p><p>Daily Yield does not publish guaranteed-return claims, fabricated reviews, invented personal experience, undisclosed paid recommendations, get-rich-quick schemes, phishing, dangerous instructions, private financial identifiers, or promotional material for prohibited or regulated goods. Educational reporting about a risk is clearly contextualised and does not facilitate it.</p>'''
BLOCKS={
'about':'''<h2>How Daily Yield is produced</h2><p>Daily Yield uses automated tools to assist topic discovery, source collection, drafting, validation, formatting, scheduling and distribution. “By Kushal Daga” identifies the publisher responsible for the publication; it does not state that every automated draft was personally reviewed. Articles must pass evidence, originality, licensing, privacy, deceptive-claim and publication checks before release.</p><p>Automation is not used to invent experience, qualifications, quotations or financial results. Material claims should remain attributable to the linked record. When the evidence is insufficient, the item must be rebuilt, replaced or held rather than forced live.</p>''',
'disclaimer':'''<h2>Editorial and financial-use limits</h2><p>Daily Yield provides general education and source-led reporting, not personalised financial, tax, legal, credit, medical or investment advice. Nothing is a promise of profit, approval, suitability or future performance. Dates, jurisdictions, eligibility and source revisions matter; verify current primary records and use an appropriately qualified adviser where needed.</p><p>A product discussion is not a personal testimonial unless it explicitly says so and can be substantiated. Sponsorship, affiliate compensation or another material commercial relationship must be disclosed prominently on the relevant page; absence of such a disclosure means the article is not presented as paid endorsement.</p>''',
'privacy':'''<h2>Advertising, cookies and third-party vendors</h2><p>Daily Yield has applied to participate in Google AdSense and, if approved, may display advertising. Third-party vendors, including Google, may use cookies to serve ads based on a reader’s prior visits to this site or other sites. Readers can opt out of personalised advertising at <a href="https://www.aboutads.info/choices/" rel="nofollow noopener" target="_blank">aboutads.info/choices</a> or through Google’s own advertising settings.</p><h2>Do not send sensitive information</h2><p>Do not submit passwords, payment-card numbers, bank-account details, national identification numbers, signatures, private health records or confidential financial documents through comments, email or contact routes. Daily Yield articles and screenshots must not expose such information without lawful authorisation.</p><p>Blogger and enabled service providers may process technical data under their own notices. Daily Yield’s optional analytics controls do not override Google or browser-level controls. The current Privacy choices control and this Privacy Policy explain the publication’s own use of optional measurement.</p>''',
'contact':'''<h2>Corrections and policy reports</h2><p>For a factual correction, copyright concern, privacy concern, commercial-disclosure issue or accessibility problem, email <a href="mailto:dailyyield.official@gmail.com">dailyyield.official@gmail.com</a> with the exact page URL and supporting detail. Do not include passwords or private financial identifiers.</p><p>Readers can also use Blogger’s <a href="https://www.blogger.com/go/report-abuse" rel="nofollow noopener" target="_blank">Report Abuse mechanism</a> for content they believe violates Blogger policy or applicable law.</p>''',
'terms':'''<h2>Content integrity and acceptable use</h2><p>Do not use Daily Yield comments, contact routes or links to promote scams, impersonation, harassment, hate, malware, phishing, dangerous activity, regulated-goods sales or disclosure of another person’s confidential information. Automated scraping or solicitation that disrupts the service is not permitted.</p><p>Daily Yield may correct, annotate, unpublish or remove material that fails its evidence, originality, rights, privacy or platform-policy standards. A publication quota never overrides these safeguards.</p>'''}
def token():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return r.json()['access_token']
def pages(h):
 out=[];page=None
 while True:
  params={'fetchBodies':'true','maxResults':50}
  if page:params['pageToken']=page
  r=requests.get(BASE+'/pages',headers=h,params=params,timeout=60);r.raise_for_status();d=r.json();out+=d.get('items',[]);page=d.get('nextPageToken')
  if not page:return out
def main():
 h={'Authorization':'Bearer '+token(),'Content-Type':'application/json'};results=[]
 by_path={urlparse(x.get('url','')).path:x for x in pages(h)}
 for path,kind in PATHS.items():
  page=by_path.get(path)
  if not page:raise RuntimeError('required policy page missing: '+path)
  old=page.get('content') or '';clean=re.sub(re.escape(START)+r'.*?'+re.escape(END),'',old,flags=re.S).rstrip()
  clean=re.sub(r'<p class="dy-vendor-note">.*?</p>','',clean,flags=re.S).rstrip()
  # Remove legacy claims that are broader than the evidence or could imply an
  # unverified qualification/personal review.
  clean=re.sub(r"A Certified Accountant(?:'|’|&#39;)s perspective","A source-led publisher's perspective",clean,flags=re.I)
  clean=re.sub(r"informed by his work as a Certified Accountant\s*:?","built around sourced financial education:",clean,flags=re.I)
  clean=clean.replace('Nothing to sell you; nothing stored about you.','No personalised recommendation is sold here; data handling is explained in the Privacy Policy.')
  block=START+'<section class="dy-policy-2026" aria-label="Blogger content policy compliance"><hr>'+COMMON+BLOCKS[kind]+'</section>'+END
  content=clean+'\n'+block
  body={'id':page['id'],'blog':{'id':os.environ['BLOGGER_BLOG_ID']},'title':page['title'],'content':content}
  r=requests.put(BASE+'/pages/'+page['id'],headers=h,json=body,timeout=90);r.raise_for_status();saved=r.json()
  if START not in saved.get('content',''):raise RuntimeError('policy block verification failed: '+path)
  results.append({'path':path,'title':saved.get('title'),'status':'UPDATED','url':saved.get('url')})
 Path('BLOGGER_POLICY_DEPLOYMENT_STATUS.json').write_text(json.dumps({'status':'PASS','policy_version':'BLOGGER_CONTENT_POLICY_2026_12_GREEN_V2','deployed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pages':results},indent=2)+'\n')
 print(json.dumps(results))
if __name__=='__main__':main()
