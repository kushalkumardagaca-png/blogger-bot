#!/usr/bin/env python3
"""Merge one prepared Master slot and photo registry into concurrent main state."""
import json,sys
from pathlib import Path

def merge_plan(current,incoming,status):
 if current.get('date')!=incoming.get('date'):return incoming
 out=dict(current);kind=status.get('kind');slot=int(status.get('slot',-1));topic=str(status.get('topic_id',''))
 if kind not in ('trending','evergreen') or slot not in range(5):raise RuntimeError('invalid prepared slot status')
 rows=list(out.get(kind,[]));incoming_rows=incoming.get(kind,[])
 chosen=next((x for x in incoming_rows if str(x.get('id'))==topic),None)
 if chosen is None:raise RuntimeError('prepared topic is absent from incoming daily plan')
 if slot>=len(rows):raise RuntimeError('prepared slot is absent from current daily plan')
 rows[slot]=chosen;out[kind]=rows;out['publication_enabled']=bool(current.get('publication_enabled') or incoming.get('publication_enabled'));return out

def merge_registry(current,incoming):
 out={**current}
 seen={};order=[]
 for row in list(current.get('items',[]))+list(incoming.get('items',[])):
  key=str(row.get('sha256') or row.get('source_id') or row.get('url'))
  if not key:continue
  if key not in seen:order.append(key);seen[key]=dict(row)
  else:
   merged={**seen[key],**row}
   for field in ('historic_usages','usages'):
    vals=[];ids=set()
    for value in list(seen[key].get(field,[]))+list(row.get(field,[])):
     token=json.dumps(value,sort_keys=True,ensure_ascii=False)
     if token not in ids:ids.add(token);vals.append(value)
    if vals:merged[field]=vals
   seen[key]=merged
 out.update({k:v for k,v in incoming.items() if k!='items' and not isinstance(v,(int,float))})
 for key in ('authenticated_items','historic_unique_urls','unavailable_count'):out[key]=max(int(current.get(key,0)),int(incoming.get(key,0)))
 out['items']=[seen[k] for k in order];return out

def main():
 if len(sys.argv)!=7:raise SystemExit('usage: merge_master_preparation.py CURRENT_PLAN INCOMING_PLAN STATUS CURRENT_REGISTRY INCOMING_REGISTRY OUTPUT_PREFIX')
 cp,ip,st,cr,ir=[json.loads(Path(x).read_text()) for x in sys.argv[1:6]];prefix=Path(sys.argv[6])
 Path(str(prefix)+'.plan.json').write_text(json.dumps(merge_plan(cp,ip,st),indent=2,ensure_ascii=False)+'\n')
 Path(str(prefix)+'.registry.json').write_text(json.dumps(merge_registry(cr,ir),indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
