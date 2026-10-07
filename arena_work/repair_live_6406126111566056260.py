#!/usr/bin/env python3
import gzip,hashlib,json,os,re
from datetime import datetime,timezone
from pathlib import Path
import requests
from brand_identity import ensure_brand_identity
from continuous_motion import ensure as ensure_continuous_motion
from master_article_v2 import render,validate
from publication_preflight import assert_publishable
from seo_meta import ensure_seo_meta
from social_identity import ensure_social_identity
ROOT=Path(__file__).resolve().parents[1];POST_ID='6406126111566056260';URL='https://dailyyield.blogspot.com/2026/09/ask-for-raise-that-beats-budgeting.html';REPORT=ROOT/'arena_work'/'repair_report_6406126111566056260.json';BACKUP=ROOT/'arena_work'/'repair_backup_6406126111566056260.json.gz'
def req(n):
 v=os.environ.get(n,'').strip()
 if not v:raise RuntimeError(n+' is required')
 return v
def main():
 tok=requests.post('https://oauth2.googleapis.com/token',data={'client_id':req('BLOGGER_CLIENT_ID'),'client_secret':req('BLOGGER_CLIENT_SECRET'),'refresh_token':req('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'},timeout=30);tok.raise_for_status();token=tok.json()['access_token'];base=f"https://www.googleapis.com/blogger/v3/blogs/{req('BLOGGER_BLOG_ID')}/posts/{POST_ID}";h={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
 r=requests.get(base,headers=h,timeout=60);r.raise_for_status();post=r.json()
 if post.get('url')!=URL:raise RuntimeError('canonical URL mismatch')
 with gzip.open(BACKUP,'wt',encoding='utf-8') as f:json.dump(post,f,ensure_ascii=False)
 p=json.loads((ROOT/f'master_packages/rewrites/post_{POST_ID}.json').read_text());validate(p)
 labels=post.get('labels') or [];category=next((x for x in labels if x not in ('Kushal K. Daga','News')),'Career Salary and Raises');published=post.get('published') or datetime.now(timezone.utc).isoformat();now=datetime.now(timezone.utc)
 title,_,meta,_,body=render(p,{'Category':category},published[:10],published[11:16],canonical_url=URL,modified_date=now.date().isoformat(),modified_time=now.strftime('%H:%M'))
 first=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I);body=ensure_seo_meta(body,title,meta,first.group(1) if first else '');body=ensure_social_identity(ensure_brand_identity(body));body=ensure_continuous_motion(body);assert_publishable(title,body,labels)
 if 'dy2-data-table' not in body or 'Illustrative index</th>' not in body:raise RuntimeError('responsive percentile table missing')
 if not all(x in body for x in ('5439148','7654487','4344860')):raise RuntimeError('replacement photo attribution missing')
 u=requests.put(base,headers=h,json={'kind':'blogger#post','id':POST_ID,'title':title,'content':body,'labels':labels},timeout=120);u.raise_for_status()
 c=requests.get(base,headers=h,timeout=60);c.raise_for_status();live=c.json();content=live.get('content') or ''
 if live.get('url')!=URL or live.get('title')!=title or 'dy2-data-table' not in content or not all(x in content for x in ('5439148','7654487','4344860')):raise RuntimeError('authenticated reread did not match repair')
 REPORT.write_text(json.dumps({'status':'PASS','post_id':POST_ID,'title':title,'url':URL,'verified_at':now.isoformat(),'content_sha256':hashlib.sha256(content.encode()).hexdigest(),'repair':['responsive percentile table','three topic-specific salary-negotiation photos']},indent=2)+'\n');print(URL)
if __name__=='__main__':
 try:main()
 except Exception as e:
  REPORT.write_text(json.dumps({'status':'FAIL','post_id':POST_ID,'error_type':type(e).__name__,'error':str(e)[:800]},indent=2)+'\n');raise
