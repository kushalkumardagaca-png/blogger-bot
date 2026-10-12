#!/usr/bin/env python3
"""Generic, idempotent publication and two-network social recovery.

Permanent recovery generation 15: exact failure capture, bounded serial recovery and wrong-post cleanup are active.
"""
from __future__ import annotations
import argparse, datetime as dt, json, subprocess
from pathlib import Path
ROOT=Path(__file__).parent; IST=dt.timezone(dt.timedelta(hours=5,minutes=30),name='IST')
LEDGER=ROOT/'RECOVERY_LEDGER.json'; STATUS=ROOT/'PUBLICATION_RECOVERY_STATUS.json'
NEWS_TIMES={'asia-pacific':'04:15','china':'05:15','india':'07:15','russia':'10:15','markets':'12:15','europe':'12:45','economy':'13:15','americas':'17:15','companies':'17:45','global':'18:15','banking':'18:45'}
MASTER_TIMES={'trending':['07:45','13:45','16:15','19:15','20:15'],'evergreen':['08:15','14:15','16:45','19:45','20:45']}
WRONG_MASTER_REPAIRS=[{'key':'master-trending-0','duplicateUrl':'https://dailyyield.blogspot.com/2026/10/budget-airlines-lose-their-cost-edge.html','titlePhrase':'Budget Airlines'}]
GRACE=dt.timedelta(minutes=20); SOCIAL_GRACE=dt.timedelta(minutes=10); RETRY=dt.timedelta(hours=3); MAX_RETRIES=3

def load(path,default):
 try:return json.loads(path.read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return default
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def parse(v):
 try:
  x=dt.datetime.fromisoformat(str(v).replace('Z','+00:00'));return x if x.tzinfo else x.replace(tzinfo=IST)
 except Exception:return None
def due(day,value):
 h,m=map(int,value.split(':'));return dt.datetime.combine(day,dt.time(h,m),IST)
def may_retry(ledger,key,now):
 row=ledger.get(key,{})
 if int(row.get('attempts',0))>=MAX_RETRIES:return False
 last=parse(row.get('lastAttempt',''));return not last or now-last>=RETRY
def mark(ledger,key,now):
 row=ledger.setdefault(key,{});row['attempts']=int(row.get('attempts',0))+1;row['lastAttempt']=now.isoformat()
def call(args,apply):
 if apply:subprocess.run(args,check=True)

def published_inventory(day):
 news=load(ROOT/'news_tracker.json',{}).get('desks',{});master=load(ROOT/'MASTER_AUTOMATION_TRACKER.json',{}).get('published',[]);plan=load(ROOT/'MASTER_DAILY_PLAN.json',{})
 out=[]
 for desk in NEWS_TIMES:
  row=news.get(desk,{})
  if row.get('edition')==day.isoformat() and str(row.get('url','')).startswith('https://dailyyield.blogspot.com/'):
   out.append({'key':'news-'+desk,'url':row['url'],'published_at':row.get('window_end',''),'kind':'news','slot':desk})
 for kind in ('trending','evergreen'):
  rows=plan.get(kind,[]) if plan.get('date')==day.isoformat() else []
  by_id={str(x.get('topic_id')):x for x in master if x.get('date')==day.isoformat() and x.get('kind')==kind}
  for slot,item in enumerate(rows[:5]):
   row=by_id.get(str(item.get('id')))
   if row and str(row.get('url','')).startswith('https://dailyyield.blogspot.com/'):
    out.append({'key':f'master-{kind}-{slot}','url':row['url'],'published_at':row.get('published_at',''),'kind':kind,'slot':slot})
 return out

def tracker_urls(platform):
 return {str(x.get('url','')).split('#')[0].rstrip('/') for x in load(ROOT/f'{platform}_tracker.json',{}).get('published',[]) if x.get('url')}
def reconcile(now,apply=False):
 from social_rotation import platform_pair_for
 day=now.astimezone(IST).date();ledger=load(LEDGER,{});inventory=published_inventory(day);by_key={x['key']:x for x in inventory};actions=[];blocked=[]
 for desk,t in NEWS_TIMES.items():
  key='news-'+desk
  if now<due(day,t)+GRACE or key in by_key:continue
  lk=f'source:{day}:{key}'
  if may_retry(ledger,lk,now):
   call(['gh','workflow','run','daily_news_wires.yml','--ref','main','-f',f'desks={desk}'],apply);mark(ledger,lk,now);actions.append({'type':'source_recovery','key':key,'applied':apply})
  else:blocked.append(lk)
 master_deferred=[];master_dispatched=False
 master_slots=sorted((due(day,t),kind,slot) for kind,times in MASTER_TIMES.items() for slot,t in enumerate(times))
 for slot_due,kind,slot in master_slots:
  key=f'master-{kind}-{slot}'
  if now<slot_due+GRACE or key in by_key:continue
  lk=f'source:{day}:{key}'
  if not may_retry(ledger,lk,now):blocked.append(lk);continue
  # Model and image providers throttle bursts. Dispatch only the oldest eligible
  # missing Master slot per recovery pass; later half-hourly passes advance the
  # queue while the three-hour ledger spacing prevents duplicate work.
  if master_dispatched:master_deferred.append(lk);continue
  call(['gh','workflow','run',f'master_{kind}_writer.yml','--ref','main','-f',f'slot={slot}','-f','publish=true'],apply);mark(ledger,lk,now);actions.append({'type':'source_recovery','key':key,'applied':apply});master_dispatched=True
 for repair in WRONG_MASTER_REPAIRS:
  replacement=by_key.get(repair['key']);lk=f"cleanup:{day}:{repair['key']}"
  if not replacement or lk in ledger:continue
  cmd=['gh','workflow','run','cleanup_wrong_master_post.yml','--ref','main','-f',f"duplicate_url={repair['duplicateUrl']}",'-f',f"replacement_url={replacement['url']}",'-f',f"expected_title_phrase={repair['titlePhrase']}"]
  call(cmd,apply);mark(ledger,lk,now);actions.append({'type':'wrong_publication_cleanup','key':repair['key'],'duplicateUrl':repair['duplicateUrl'],'replacementUrl':replacement['url'],'applied':apply})
 platform_urls={p:tracker_urls(p) for p in ('facebook','bluesky','tumblr','mastodon')}
 for item in inventory:
  published=parse(item.get('published_at'))
  if published and now-published.astimezone(IST)<SOCIAL_GRACE:continue
  for route_index,platform in enumerate(platform_pair_for(item['key'])):
   if item['url'].split('#')[0].rstrip('/') in platform_urls[platform]:continue
   lk=f'social:{day}:{item["key"]}:{route_index}'
   if may_retry(ledger,lk,now):
    cmd=['gh','workflow','run','coordinated_social_publish.yml','--ref','main','-f',f'item_key={item["key"]}','-f',f'target_url={item["url"]}','-f','content_mode=post','-f',f'published_at={item.get("published_at","")}','-f',f'route_index={route_index}']
    call(cmd,apply);mark(ledger,lk,now);actions.append({'type':'social_replay','key':item['key'],'platform':platform,'routeIndex':route_index,'applied':apply})
   else:blocked.append(lk)
 if apply:save(LEDGER,ledger)
 report={'generatedAt':now.isoformat(),'dateIST':day.isoformat(),'status':'PASS','apply':apply,'confirmedPublications':len(inventory),'actions':actions,'retryBlocked':blocked,'masterRecoveryDeferred':master_deferred,'syntheticViews':0,'publicDailyYieldRequests':0}
 save(STATUS,report);return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();r=reconcile(dt.datetime.now(IST),a.apply);print(json.dumps({'status':r['status'],'confirmed':r['confirmedPublications'],'actions':len(r['actions']),'apply':r['apply'],'syntheticViews':0}));return 0
if __name__=='__main__':raise SystemExit(main())
