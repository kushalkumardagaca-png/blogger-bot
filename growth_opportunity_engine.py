#!/usr/bin/env python3
"""Turn genuine Search Console evidence into a controlled growth queue."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).parent; OUT=ROOT/'GROWTH_OPPORTUNITIES.json'

def load():
 try:return json.loads((ROOT/'AUDIENCE_GROWTH_BASELINE.json').read_text())
 except (OSError,json.JSONDecodeError):return {}
def expected_ctr(position):
 if position<=1:return .28
 if position<=3:return .14
 if position<=5:return .08
 if position<=10:return .035
 if position<=20:return .012
 return .005
def build(data):
 acq=data.get('searchAcquisition',{}); candidates=[]
 for row in acq.get('queryPage28Days',[]):
  q=row.get('query','').strip(); page=row.get('page','').strip(); imp=int(row.get('impressions',0) or 0); clicks=int(row.get('clicks',0) or 0); pos=row.get('averagePosition')
  if not q or not page or not imp or pos is None:continue
  gap=max(0,expected_ctr(float(pos))-float(row.get('ctr',0) or 0)); score=round(imp*gap*(1.6 if 4<=float(pos)<=20 else 1),2)
  action='REFRESH_AND_EXPAND' if 4<=float(pos)<=20 else 'TITLE_SNIPPET_TEST'
  candidates.append({'query':q,'page':page,'impressions':imp,'clicks':clicks,'ctr':row.get('ctr',0),'averagePosition':pos,'opportunityScore':score,'action':action,'guardrail':'Preserve URL; add sourced original value; do not change solely for keywords.'})
 candidates.sort(key=lambda x:(x['opportunityScore'],x['impressions']),reverse=True)
 return {'generatedAt':datetime.now(timezone.utc).isoformat(),'status':'READY' if candidates else 'WAITING_FOR_SEARCH_DEMAND','source':'Authenticated Search Console only','syntheticViews':0,'queue':candidates[:50],'releasePolicy':{'automaticPublishing':False,'requiresEditorialSafetyGate':True,'rollbackRequired':True,'maximumRefreshesPerRun':5}}
def main():
 r=build(load());OUT.write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'status':r['status'],'opportunities':len(r['queue']),'syntheticViews':0}));return 0
if __name__=='__main__':raise SystemExit(main())
