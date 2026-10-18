#!/usr/bin/env python3
"""Truthful Daily Yield growth control tower.

Combines first-party engaged-reader analytics (when GA4 reporting access is
configured) with Search Console, publishing and official social evidence. It
never requests a Daily Yield public URL and never substitutes views, clicks or
impressions for distinct engaged readers.
"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).parent
OUT=ROOT/'GROWTH_CONTROL_TOWER.json'; MD=ROOT/'GROWTH_CONTROL_TOWER.md'
TARGET=10_000_000; DEADLINE=date(2027,9,30)

def load(name,default):
 try:return json.loads((ROOT/name).read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return default

def oauth_token():
 prefix='GA4' if all(os.getenv('GA4_'+suffix) for suffix in ('CLIENT_ID','CLIENT_SECRET','REFRESH_TOKEN')) else 'GSC'
 cid=os.getenv(prefix+'_CLIENT_ID','');secret=os.getenv(prefix+'_CLIENT_SECRET','');refresh=os.getenv(prefix+'_REFRESH_TOKEN','')
 if not all((cid,secret,refresh)):raise RuntimeError('OAuth reporting credentials are not configured')
 data=urllib.parse.urlencode({'client_id':cid,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'}).encode()
 req=urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST')
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)['access_token']

def ga4_report(token,property_id,start,end,dimensions,metrics,event=None,limit=10000):
 body={'dateRanges':[{'startDate':start,'endDate':end}],
       'dimensions':[{'name':x} for x in dimensions], 'metrics':[{'name':x} for x in metrics], 'limit':str(limit)}
 if event:body['dimensionFilter']={'filter':{'fieldName':'eventName','stringFilter':{'matchType':'EXACT','value':event}}}
 req=urllib.request.Request(f'https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)

def rows(report):
 out=[]
 for row in report.get('rows',[]):
  out.append([x.get('value','') for x in row.get('dimensionValues',[])]+[x.get('value','0') for x in row.get('metricValues',[])])
 return out

def engaged_analytics(today):
 pid=os.getenv('GA4_PROPERTY_ID','').strip()
 if not pid:
  existing=load('EXISTING_ANALYTICS_CONNECTION.json',{})
  if existing.get('verifiedExisting') is True and urllib.parse.urlparse(str(existing.get('defaultUri',''))).hostname=='dailyyield.blogspot.com':
   pid=str(existing.get('propertyId','')).strip()
 base={'status':'NOT_CONFIGURED','metricDefinition':'Distinct consented users triggering article_read after at least 30 active seconds and 50% article depth.','dau':None,'average7Day':None,'average28Day':None,'newUsers28Day':None,'returningUsers28Day':None,'daily':[]}
 if not pid:return base
 try:
  token=oauth_token(); end=(today-timedelta(days=1)).isoformat(); start=(today-timedelta(days=28)).isoformat()
  daily=rows(ga4_report(token,pid,start,end,['date'],['activeUsers'],'article_read'))
  series=[{'date':datetime.strptime(r[0],'%Y%m%d').date().isoformat(),'engagedReaders':int(float(r[1]))} for r in daily]
  # API omits dates with no recorded events; don't inflate averages by dividing
  # only by active dates. This is still consented observed activity, not all users.
  observed={x['date']:x['engagedReaders'] for x in series}
  begin=today-timedelta(days=28)
  series=[{'date':(begin+timedelta(days=i)).isoformat(),'engagedReaders':observed.get((begin+timedelta(days=i)).isoformat(),0)} for i in range(28)]
  vals=[x['engagedReaders'] for x in series]
  base.update(status='ACTIVE',daily=series,dau=(vals[-1] if vals else 0),average7Day=round(sum(vals[-7:])/max(1,len(vals[-7:])),1),average28Day=round(sum(vals)/max(1,len(vals)),1))
  # New/returning users are reported only among article_read events.
  nr=rows(ga4_report(token,pid,start,end,['newVsReturning'],['activeUsers'],'article_read'))
  for r in nr:
   if r[0]=='new':base['newUsers28Day']=int(float(r[1]))
   elif r[0]=='returning':base['returningUsers28Day']=int(float(r[1]))
 except Exception as exc:
  base.update(status='UNAVAILABLE',error=type(exc).__name__+': '+str(exc)[:240])
 return base

def build(today=None):
 today=today or datetime.now(timezone.utc).date(); analytics=engaged_analytics(today)
 search=load('AUDIENCE_GROWTH_BASELINE.json',{}).get('searchAcquisition',{})
 social=load('SOCIAL_PERFORMANCE.json',{}); master=load('MASTER_AUTOMATION_TRACKER.json',{}); news=load('news_tracker.json',{})
 items=social.get('items',[]); interactions=sum(sum(float(v) for v in x.get('metrics',{}).values() if isinstance(v,(int,float))) for x in items)
 days=max(0,(DEADLINE-today).days); current=analytics.get('dau'); required=None
 if isinstance(current,(int,float)) and current>0 and days>0:required=round((TARGET/current)**(1/days)-1,6)
 # Do not fabricate a 300-reader baseline or a forecast from missing data.
 checkpoints=[]
 if isinstance(current,(int,float)) and current>0 and days>0:
  for offset in (30,60,90,180,270,days):
   if 0<offset<=days:checkpoints.append({'daysFromNow':offset,'date':(today+timedelta(days=offset)).isoformat(),'arithmeticTargetReaders':round(current*((1+required)**offset))})
 return {'generatedAt':datetime.now(timezone.utc).isoformat(),'deadline':DEADLINE.isoformat(),'targetDistinctDailyEngagedReaders':TARGET,'daysRemaining':days,
  'stretchTrajectory':{'verifiedBaseline':current,'requiredDailyGrowth':required,'checkpoints':checkpoints,'warning':'Arithmetic to an ambition, not a forecast. No trajectory is generated without a verified positive baseline.'},
  'primaryMetric':analytics,
  'pace':{'currentVerifiedDAU':current,'targetGap':TARGET-current if isinstance(current,(int,float)) else None,'requiredDailyCompoundGrowth':required,'onTarget':bool(current and current>=TARGET)},
  'acquisition':{'search7Day':search.get('last7Days'),'search28Day':search.get('last28Days'),'socialOfficialObservations':len(items),'socialObservedInteractions':round(interactions)},
  'production':{'masterPublishedTotal':len(master.get('published',[])),'newsDesksTracked':len(news.get('desks',{}))},
  'integrity':{'syntheticViews':0,'publicDailyYieldRequests':0,'impressionsAreReaders':False,'searchClicksAreReaders':False},
  'status':'ACTIVE' if analytics.get('status')=='ACTIVE' else 'MEASUREMENT_INSTRUMENTED_REPORTING_'+analytics.get('status','UNKNOWN')}

def markdown(r):
 p=r['primaryMetric']; pace=r['pace']; current='Not yet reportable' if pace['currentVerifiedDAU'] is None else f"{pace['currentVerifiedDAU']:,}"
 return f"""# Daily Yield Growth Control Tower

- **Status:** {r['status']}
- **Verified distinct daily engaged readers:** {current}
- **Target:** {r['targetDistinctDailyEngagedReaders']:,} by {r['deadline']}
- **Days remaining:** {r['daysRemaining']}
- **Synthetic views:** 0

## Primary metric

{p['metricDefinition']}

Search clicks, impressions, social reach and Blogger pageviews are deliberately not counted as readers.

## Acquisition evidence

- Search, last 7 days: `{json.dumps(r['acquisition']['search7Day'])}`
- Search, last 28 days: `{json.dumps(r['acquisition']['search28Day'])}`
- Official social observations: {r['acquisition']['socialOfficialObservations']}
- Observed social interactions: {r['acquisition']['socialObservedInteractions']}
"""

def main():
 r=build();OUT.write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n');MD.write_text(markdown(r));print(json.dumps({'status':r['status'],'dau':r['pace']['currentVerifiedDAU'],'syntheticViews':0}));return 0
if __name__=='__main__':raise SystemExit(main())
