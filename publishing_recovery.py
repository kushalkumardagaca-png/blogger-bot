#!/usr/bin/env python3
"""Generic, idempotent publication and two-network social recovery.

Permanent recovery generation 38: deterministic completion now guarantees four-to-six bounded paragraphs, successful preparation requeues after persistence conflicts, and the 06:15 current-date recovery is rearmed; repository-model fallback is wired into the live job, pre-gate core/summary/visual completion is deterministic, parallel recovery is non-blocking and no article retry ceiling is active.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).parent; IST=dt.timezone(dt.timedelta(hours=5,minutes=30),name='IST')
LEDGER=ROOT/'RECOVERY_LEDGER.json'; STATUS=ROOT/'PUBLICATION_RECOVERY_STATUS.json'
NEWS_TIMES={'asia-pacific':'04:15','china':'05:15','india':'07:15','russia':'10:15','markets':'12:15','europe':'12:45','economy':'13:15','americas':'17:15','companies':'17:45','global':'18:15','banking':'18:45'}
MASTER_TIMES={'trending':['06:15','09:15','14:15','16:15','20:45'],'evergreen':['08:15','11:15','15:15','19:45','22:15']}
WRONG_MASTER_REPAIRS=[{'key':'master-trending-0','duplicateUrl':'https://dailyyield.blogspot.com/2026/10/budget-airlines-lose-their-cost-edge.html','titlePhrase':'Budget Airlines'}]
GRACE=dt.timedelta(minutes=20); SOCIAL_GRACE=dt.timedelta(minutes=10); RETRY=dt.timedelta(hours=3); ARTICLE_RETRY=dt.timedelta(minutes=30); MAX_RETRIES=3
PREWARM=dt.timedelta(hours=3,minutes=15)

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
def implementation_revision():
 """Fingerprint reliability code, excluding generated-state commits."""
 digest=hashlib.sha256()
 for name in ('master_v3_generator.py','master_v3_pipeline.py','publishing_recovery.py','.github/workflows/master_trending_writer.yml','.github/workflows/master_evergreen_writer.yml'):
  path=ROOT/name
  if path.exists():digest.update(name.encode());digest.update(path.read_bytes())
 return digest.hexdigest()[:16]

def may_retry(ledger,key,now,revision=None):
 row=ledger.get(key,{});revision=revision or implementation_revision()
 # A repaired implementation gets one immediate fresh retry even when the old
 # version exhausted or recently used its bounded attempts. Generated tracker
 # commits do not alter this content fingerprint.
 if row.get('revision')!=revision:return True
 # Source and preparation recovery have no terminal attempt ceiling during the
 # IST publication day. Each attempt remains time-spaced and individually
 # bounded, but an article is never abandoned because an arbitrary counter was
 # reached. Social replay retains a three-attempt cap to avoid duplicate posts.
 if not key.startswith(('source:','prewarm:')) and int(row.get('attempts',0))>=MAX_RETRIES:return False
 last=parse(row.get('lastAttempt',''));spacing=ARTICLE_RETRY if key.startswith(('source:','prewarm:')) else RETRY
 return not last or now-last>=spacing
def mark(ledger,key,now,revision=None):
 revision=revision or implementation_revision();row=ledger.setdefault(key,{})
 if row.get('revision')!=revision:row.clear();row['revision']=revision
 row['attempts']=int(row.get('attempts',0))+1;row['lastAttempt']=now.isoformat()
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
 master_deferred=[]
 # From 14 October onward, recovery is current-date only. Never dispatch the
 # explicitly abandoned 12/13 October backlog during the next morning.
 master_day=day
 master_by_key={x['key']:x for x in published_inventory(master_day)}
 daily_plan=load(ROOT/'MASTER_DAILY_PLAN.json',{});plan_rows={kind:daily_plan.get(kind,[]) if daily_plan.get('date')==master_day.isoformat() else [] for kind in ('trending','evergreen')}
 master_slots=[] if master_day<dt.date(2026,10,14) else sorted((due(master_day,t),kind,slot) for kind,times in MASTER_TIMES.items() for slot,t in enumerate(times) if slot<len(plan_rows[kind]))
 # If GitHub's scheduler misses a preparation cron during a deployment, prepare
 # the validated package before release rather than waiting until the article is
 # already overdue. A later publish recovery reuses this committed package.
 for slot_due,kind,slot in master_slots:
  key=f'master-{kind}-{slot}'
  if key in master_by_key or not slot_due-PREWARM<=now<slot_due+GRACE:continue
  lk=f'prewarm:{master_day}:{key}'
  if not may_retry(ledger,lk,now):continue
  call(['gh','workflow','run',f'master_{kind}_writer.yml','--ref','main','-f',f'slot={slot}','-f','publish=false','-f','retry_attempt=0'],apply);mark(ledger,lk,now);actions.append({'type':'preparation_recovery','key':key,'applied':apply})
 for slot_due,kind,slot in master_slots:
  key=f'master-{kind}-{slot}'
  if now<slot_due+GRACE or key in master_by_key:continue
  lk=f'source:{master_day}:{key}'
  if not may_retry(ledger,lk,now):blocked.append(lk);continue
  # Every Master workflow owns a separate local model runner, so missing slots
  # can recover concurrently without a shared API quota. Photo-registry merge
  # guards reject any cross-article image collision before publication.
  call(['gh','workflow','run',f'master_{kind}_writer.yml','--ref','main','-f',f'slot={slot}','-f','publish=true','-f','retry_attempt=0'],apply);mark(ledger,lk,now);actions.append({'type':'source_recovery','key':key,'applied':apply})
 for repair in WRONG_MASTER_REPAIRS:
  replacement=master_by_key.get(repair['key']);lk=f"cleanup:{master_day}:{repair['key']}"
  if not replacement or lk in ledger:continue
  cmd=['gh','workflow','run','cleanup_wrong_master_post.yml','--ref','main','-f',f"duplicate_url={repair['duplicateUrl']}",'-f',f"replacement_url={replacement['url']}",'-f',f"expected_title_phrase={repair['titlePhrase']}"]
  call(cmd,apply);mark(ledger,lk,now);actions.append({'type':'wrong_publication_cleanup','key':repair['key'],'duplicateUrl':repair['duplicateUrl'],'replacementUrl':replacement['url'],'applied':apply})
 platform_urls={p:tracker_urls(p) for p in ('facebook','bluesky','tumblr','mastodon')}
 for item in inventory:
  published=parse(item.get('published_at'))
  if published and now-published.astimezone(IST)<SOCIAL_GRACE:continue
  route_day=parse(item.get('published_at')).astimezone(IST).date() if parse(item.get('published_at')) else day
  for route_index,platform in enumerate(platform_pair_for(item['key'],route_day)):
   if item['url'].split('#')[0].rstrip('/') in platform_urls[platform]:continue
   lk=f'social:{day}:{item["key"]}:{route_index}'
   if may_retry(ledger,lk,now):
    cmd=['gh','workflow','run','coordinated_social_publish.yml','--ref','main','-f',f'item_key={item["key"]}','-f',f'target_url={item["url"]}','-f','content_mode=post','-f',f'published_at={item.get("published_at","")}','-f',f'route_index={route_index}']
    call(cmd,apply);mark(ledger,lk,now);actions.append({'type':'social_replay','key':item['key'],'platform':platform,'routeIndex':route_index,'applied':apply})
   else:blocked.append(lk)
 if apply:save(LEDGER,ledger)
 overdue=[]
 for desk,t in NEWS_TIMES.items():
  key='news-'+desk
  if now>=due(day,t)+GRACE and key not in by_key:overdue.append(key)
 for slot_due,kind,slot in master_slots:
  key=f'master-{kind}-{slot}'
  if now>=slot_due+GRACE and key not in master_by_key:overdue.append(key)
 report={'generatedAt':now.isoformat(),'dateIST':day.isoformat(),'status':'PASS' if not overdue else 'DEGRADED','apply':apply,'confirmedPublications':len(inventory),'overdueMissing':overdue,'actions':actions,'retryBlocked':blocked,'masterRecoveryDeferred':master_deferred,'syntheticViews':0,'publicDailyYieldRequests':0}
 save(STATUS,report);return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();r=reconcile(dt.datetime.now(IST),a.apply);print(json.dumps({'status':r['status'],'confirmed':r['confirmedPublications'],'actions':len(r['actions']),'apply':r['apply'],'syntheticViews':0}));return 0
if __name__=='__main__':raise SystemExit(main())
