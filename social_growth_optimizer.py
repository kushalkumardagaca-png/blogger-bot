#!/usr/bin/env python3
"""Evidence-led organic social creative optimizer.

Uses only official-API observations already captured in SOCIAL_PERFORMANCE.json.
It never requests Daily Yield pages, buys engagement or automates replies. Sparse
samples retain exploration instead of overfitting to one lucky interaction.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).parent; SOURCE=ROOT/'SOCIAL_PERFORMANCE.json'; OUT=ROOT/'SOCIAL_OPTIMIZER_STATE.json'
PLATFORMS=('facebook','bluesky','mastodon')

def interactions(metrics):
 ignore={'post_impressions','post_impressions_unique'}
 return sum(float(v) for k,v in metrics.items() if k not in ignore and isinstance(v,(int,float)))
def posterior(rows):
 n=len(rows);engaged=sum(1 for x in rows if x>0);total=sum(rows)
 # Conservative beta prior: two pseudo-successes in ten posts.
 rate=(engaged+2)/(n+10)
 return {'observations':n,'engagedPosts':engaged,'interactions':round(total,2),'smoothedEngagedPostRate':round(rate,4),'interactionsPerPost':round(total/max(1,n),4)}
def group(rows,key):
 buckets=defaultdict(list)
 for row in rows:buckets[str(key(row))].append(row['_interactions'])
 return {k:posterior(v) for k,v in sorted(buckets.items())}
def best(stats,minimum=2):
 eligible=[(v['smoothedEngagedPostRate'],v['interactionsPerPost'],k,v) for k,v in stats.items() if v['observations']>=minimum]
 if not eligible:return None
 _,_,key,value=max(eligible);return key,value
def build(data):
 raw=[]
 for item in data.get('items',[]):
  creative=item.get('creative') or {};platform=item.get('platform')
  if platform not in PLATFORMS or not creative:continue
  row={**item,'_interactions':interactions(item.get('metrics',{}))};raw.append(row)
 report={'generatedAt':datetime.now(timezone.utc).isoformat(),'status':'ACTIVE','method':'Official API interactions with conservative smoothing; 20% exploration retained.','syntheticViews':0,'publicDailyYieldRequests':0,'platforms':{},'recommendations':{}}
 for platform in PLATFORMS:
  rows=[x for x in raw if x['platform']==platform];topics=sorted({x['creative'].get('topic','general') for x in rows})
  p={'summary':posterior([x['_interactions'] for x in rows]),'byTopic':{}}
  rec={}
  for topic in topics:
   subset=[x for x in rows if x['creative'].get('topic','general')==topic]
   styles=group(subset,lambda x:x['creative'].get('style_index'))
   layouts=group(subset,lambda x:x['creative'].get('layout'))
   hooks=group(subset,lambda x:x['creative'].get('hook',''))
   hours=group(subset,lambda x:str(x.get('published_at',''))[11:13])
   p['byTopic'][topic]={'summary':posterior([x['_interactions'] for x in subset]),'styles':styles,'layouts':layouts,'hooks':hooks,'hoursUTC':hours}
   bs,bl,bh=best(styles),best(layouts),best(hooks)
   # Require a meaningful topic sample and evidence for every selected cell.
   engaged_posts=sum(1 for x in subset if x['_interactions']>0)
   if len(subset)>=12 and engaged_posts>=2 and bs and bl and bh:
    rec[topic]={'style_index':int(bs[0]),'layout':int(bl[0]),'hook':bh[0],'evidencePosts':len(subset),'engagedPosts':engaged_posts,'explorationRate':0.20}
  report['platforms'][platform]=p
  if rec:report['recommendations'][platform]=rec
 if not raw:report['status']='WAITING_FOR_OFFICIAL_OBSERVATIONS'
 return report

def main():
 try:data=json.loads(SOURCE.read_text())
 except (OSError,json.JSONDecodeError):data={}
 report=build(data);OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'status':report['status'],'observations':sum(x['summary']['observations'] for x in report['platforms'].values()),'recommendations':sum(len(x) for x in report['recommendations'].values()),'syntheticViews':0}));return 0
if __name__=='__main__':raise SystemExit(main())
