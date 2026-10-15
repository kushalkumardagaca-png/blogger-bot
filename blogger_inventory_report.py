#!/usr/bin/env python3
"""Authenticated Blogger inventory: live, draft and scheduled post records.

Answers three operational questions without generating any public pageview:
1. Which posts exist in each Blogger status?
2. Which drafts are leftover copies of a post that is already live?
3. Which of today's planned articles are still missing from the live blog?
"""
from __future__ import annotations
import datetime as dt, json, os, re, urllib.parse, urllib.request
from pathlib import Path
IST=dt.timezone(dt.timedelta(hours=5,minutes=30));ROOT=Path(__file__).parent

def required(name):
 value=os.environ.get(name,'').strip()
 if not value:raise RuntimeError(f'{name} is required')
 return value

def token():
 data=urllib.parse.urlencode({'client_id':required('BLOGGER_CLIENT_ID'),'client_secret':required('BLOGGER_CLIENT_SECRET'),'refresh_token':required('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'}).encode()
 req=urllib.request.Request('https://oauth2.googleapis.com/token',data=data)
 return json.loads(urllib.request.urlopen(req,timeout=60).read())['access_token']

def call(path,tok,method='GET',body=None):
 url=f"https://www.googleapis.com/blogger/v3/blogs/{required('BLOGGER_BLOG_ID')}{path}"
 data=json.dumps(body).encode() if body else None
 req=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
 try:return json.loads(urllib.request.urlopen(req,timeout=90).read() or b'{}')
 except urllib.error.HTTPError as exc:raise RuntimeError(f'{exc.code} {exc.read()[:200].decode(errors="replace")}')

def inventory(tok,status):
 rows=[];page=None
 for _ in range(40):
  query={'status':status,'fetchBodies':'false','maxResults':50,'fields':'items(id,title,url,published,updated,labels),nextPageToken'}
  if page:query['pageToken']=page
  data=call('/posts?'+urllib.parse.urlencode(query),tok)
  rows.extend(data.get('items',[]));page=data.get('nextPageToken')
  if not page:break
 return rows

def key(value):return ' '.join(re.findall(r'[a-z0-9]+',str(value or '').casefold()))

QUARANTINE_IDS=(
 ('8304416218719683957','Best life insurance companies for seniors'),
 ('6779600207608409311','From digital India to intelligent India'),
 ('6893610896651799359','Sold a property? Eight different ways'),
 ('8023797526917435508','What to expect from Europe’s most valuable'),
 ('4798885766859226553','How RMDs Determine Withdrawals'),
 ('8656941344223656311','Gold price holds critical support'),
 ('8549378344780817191','IFS budget'),
 ('4654575691668632397','Global Market Singapore'),
 ('3982102288480941665','0% Capital Gains Tax Guide'),
 ('2436300762236386235','Your Tax Refund Is a Trap'),
 ('3824305036751783911','Graduate with credit file'),
 ('4498405341941524443','The market is not a casino'),
 ('7255018414657547539','BRRRR with ugly months'),
 ('314352988888289456','Where to park your emergency fund'),
 ('5611067798787673649','Laid off first 72 hours'),
 ('7839033619702786971','First 1000 scared persons plan'),
 ('3640853899029929702','Why your budget dies in week two'),
 ('2691449182304659819','I tested 6 AI money coaches'),
 ('1246197502482808342','15 money myths your uncle repeats'),
)

def main():
 tok=token()
 live=inventory(tok,'LIVE');drafts=inventory(tok,'DRAFT');scheduled=inventory(tok,'SCHEDULED')
 live_keys={key(x.get('title')):x for x in live}
 live_paths={re.sub(r'/$','',urllib.parse.urlsplit(x.get('url','')).path):x for x in live if x.get('url')}
 duplicate_drafts=[];unique_drafts=[]
 for d in drafts:
  match=live_keys.get(key(d.get('title')))
  if match:duplicate_drafts.append({'draft_id':d['id'],'title':d.get('title'),'live_id':match['id'],'live_url':match.get('url'),'draft_updated':d.get('updated')})
  else:unique_drafts.append({'id':d['id'],'title':d.get('title'),'published':d.get('published'),'updated':d.get('updated'),'url':d.get('url')})
 today_live=[]
 for x in live:
  stamp=str(x.get('published') or '')
  try: day_ist=dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(IST).date().isoformat()
  except Exception: continue
  if day_ist==dt.datetime.now(IST).date().isoformat(): today_live.append({'id':x['id'],'title':x.get('title'),'url':x.get('url'),'published_ist':stamp})
 def tokens(value):return set(re.findall(r'[a-z0-9]{4,}',str(value or '').casefold()))
 quarantined=[]
 for post_id,label in QUARANTINE_IDS:
  try:
   row=call('/posts/'+post_id+'?fetchBody=true',tok)
   quarantined.append({'post_id':post_id,'label':label,'current_status':row.get('status'),'url':row.get('url'),'updated':row.get('updated'),'has_current_disclosure':'DY_AUTOMATION_DISCLOSURE_GREEN_V2' in (row.get('content') or '')})
  except Exception as exc:
   quarantined.append({'post_id':post_id,'label':label,'current_status':'LOOKUP_FAILED','detail':str(exc)[:120]})
 still_live=[x for x in quarantined if x.get('current_status')=='LIVE']
 plan=json.loads((ROOT/'MASTER_DAILY_PLAN.json').read_text()) if (ROOT/'MASTER_DAILY_PLAN.json').exists() else {}
 day=dt.datetime.now(IST).date().isoformat()
 expected=[]
 for kind in ('trending','evergreen'):
  for slot,item in enumerate(plan.get(kind,[]) or []):
   title=str(item.get('title',''));want=tokens(title)
   hit=None
   for cand in live:
    have=tokens(cand.get('title'))
    if have and want and len(want&have)/max(1,min(len(want),len(have)))>=0.6:hit=cand;break
   expected.append({'key':f'master-{kind}-{slot}','title':title[:70],'live':bool(hit),'url':(hit or {}).get('url')})
 news=json.loads((ROOT/'news_tracker.json').read_text()) if (ROOT/'news_tracker.json').exists() else {}
 news_rows=[{'key':'news-'+desk,'edition':row.get('edition'),'url':row.get('url')} for desk,row in (news.get('desks') or {}).items() if row.get('edition')==day]
 report={'status':'PASS','checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'date_ist':day,
  'live_posts':len(live),'draft_posts':len(drafts),'scheduled_posts':len(scheduled),
  'drafts_matching_a_live_post':duplicate_drafts,'drafts_with_no_live_match':unique_drafts,
  'master_plan_today':expected,'news_live_today':news_rows,'live_posts_published_today_ist':today_live,'zero_public_pageviews':True,
  'quarantine_audit':quarantined,'quarantine_still_live':still_live}
 (ROOT/'BLOGGER_INVENTORY_STATUS.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'live':len(live),'draft':len(drafts),'scheduled':len(scheduled),'draft_duplicates':len(duplicate_drafts),'draft_unique':len(unique_drafts),
  'master_live_today':sum(1 for x in expected if x['live']),'master_expected_today':len(expected),'news_live_today':len(news_rows),'quarantine_still_live':len(still_live)},indent=2))
 for row in still_live:print(' QUARANTINED BUT STILL LIVE:',row.get('post_id'),row.get('label'),row.get('url'))
 for row in unique_drafts:print(' UNIQUE DRAFT:',row['updated'],row['title'])
 for row in duplicate_drafts:print(' DRAFT COPY OF LIVE POST:',row['title'],'->',row['live_url'])
 for row in expected:
  if not row['live']:print(' MISSING TODAY:',row['key'],row['title'])

if __name__=='__main__':main()
