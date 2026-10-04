#!/usr/bin/env python3
"""Remove retired LinkedIn/X/Reddit contact links and Reddit app disclosures.

Authenticated Blogger API only: this maintenance creates zero public pageviews.
"""
from __future__ import annotations
import gzip, html, json, os, re, time
from pathlib import Path
import requests
from social_identity import ensure_social_identity

BLOG_ID=os.environ['BLOGGER_BLOG_ID'];BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
BACKUP=Path('INACTIVE_SOCIAL_REMOVAL_BACKUP.json.gz');REPORT=Path('INACTIVE_SOCIAL_REMOVAL_REPORT.json')
INACTIVE=re.compile(r'https?://(?:www\.)?(?:linkedin\.com/|(?:x|twitter)\.com/|reddit\.com/)',re.I)


def headers():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}


def inventory(kind,h):
 out=[];token=None
 while True:
  params={'status':'live','fetchBodies':'true','maxResults':'500','fields':'nextPageToken,items(id,title,url,content,status,labels)'}
  if token:params['pageToken']=token
  r=requests.get(f'{BASE}/{kind}',headers=h,params=params,timeout=60);r.raise_for_status();data=r.json();out.extend(data.get('items',[]));token=data.get('nextPageToken')
  if not token:return out


def clean_terms(content):
 content=re.sub(r'<section\b[^>]*id=["\']dyt-reddit["\'][^>]*>.*?</section\s*>','',content,flags=re.I|re.S)
 content=re.sub(r'<a\b[^>]*href=["\']#dyt-reddit["\'][^>]*>.*?</a\s*>','',content,flags=re.I|re.S)
 replacements={
  'The practical boundaries for using Daily Yield’s website, educational material and official Reddit application—written to be read, not hidden.':'The practical boundaries for using Daily Yield’s website and educational material—written to be read, not hidden.',
  '<span>Official app: r/DailyYield only</span>':'',
  'These terms apply when you use Daily Yield’s website, public educational material or official Reddit Devvit app in r/DailyYield. By using those services, you agree to these terms and applicable platform rules.':'These terms apply when you use Daily Yield’s website and public educational material. By using the service, you agree to these terms and applicable law.',
  ' Reddit participation remains subject to Reddit’s User Agreement, Content Policy and community rules.':'',
  'Blogger, Reddit, follow.it':'Blogger, follow.it',
 }
 for old,new in replacements.items():content=content.replace(old,new)
 return content


def clean(content,path):
 content=re.sub(r'<!-- DY_REDDIT_APP_PRIVACY_START -->.*?<!-- DY_REDDIT_APP_PRIVACY_END -->','',content or '',flags=re.S)
 content=re.sub(r'<section\b[^>]*id=["\']dy-reddit-app-privacy["\'][^>]*>.*?</section\s*>','',content,flags=re.I|re.S)
 if path=='/p/terms-and-conditions.html':content=clean_terms(content)
 return ensure_social_identity(content).strip()


def update_item(kind,item_id,body,h):
 url=f'{BASE}/{kind}/{item_id}'
 last=None
 for attempt in range(5):
  r=requests.patch(url,headers={**h,'Content-Type':'application/json'},json=body,timeout=60)
  if r.ok:return r
  last=r
  if r.status_code not in (409,429,500,502,503,504):return r
  time.sleep(2 ** attempt)
 return last


def main():
 h=headers();items=[]
 for kind in ('posts','pages'):
  for x in inventory(kind,h):x['_kind']=kind;items.append(x)
 with gzip.open(BACKUP,'wt',encoding='utf-8') as f:json.dump(items,f,ensure_ascii=False)
 changed=[];fail=[]
 for x in items:
  path=re.sub(r'^https://dailyyield\.blogspot\.com','',x.get('url','')).split('?',1)[0]
  revised=clean(x.get('content',''),path)
  if INACTIVE.search(revised):fail.append({'id':x['id'],'title':x.get('title'),'reason':'inactive URL remained'});continue
  if revised==x.get('content',''):continue
  body={'kind':f'blogger#{x["_kind"][:-1]}','id':x['id'],'title':x.get('title',''),'content':revised}
  if x['_kind']=='posts':body['labels']=x.get('labels',[])
  r=update_item(x['_kind'],x['id'],body,h)
  if not r.ok:fail.append({'id':x['id'],'title':x.get('title'),'reason':f'HTTP {r.status_code}: {r.text[:160]}'});continue
  changed.append({'id':x['id'],'kind':x['_kind'],'title':x.get('title'),'url':x.get('url')})
  time.sleep(.25)
 # Re-inventory through the authenticated API and fail closed if any URL survived.
 remaining=[]
 for kind in ('posts','pages'):
  for x in inventory(kind,h):
   if INACTIVE.search(x.get('content','')):remaining.append({'id':x['id'],'kind':kind,'title':x.get('title')})
 report={'status':'PASS' if not fail and not remaining else 'FAIL','inventory':len(items),'updated':len(changed),'failures':fail,'remainingInactiveUrls':remaining,'publicPageRequests':0,'removedChannels':['LinkedIn','X/Twitter','Reddit']}
 REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
 if report['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
