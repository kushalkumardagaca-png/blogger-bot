#!/usr/bin/env python3
"""Race-safe semantic merge for concurrent Master publication records."""
import json,sys
from pathlib import Path

def merge(current,incoming,list_key):
 out={**current,**incoming};combined={};order=[]
 for row in list(current.get(list_key,[]))+list(incoming.get(list_key,[])):
  identity=str(row.get('topic_id') or row.get('url') or row.get('title'))
  # A revalidated evergreen topic may legitimately recur on another edition.
  # Publication identity is therefore date + topic, while topic-history lists
  # retain their existing global topic identity.
  key=(str(row.get('date') or ''),identity) if list_key=='published' else identity
  if not identity:continue
  if key not in combined:order.append(key);combined[key]=dict(row)
  else:combined[key].update(row)
 rows=[combined[k] for k in order];rows.sort(key=lambda x:(str(x.get('date','')),str(x.get('published_at','')),str(x.get('topic_id',''))))
 out[list_key]=rows;return out

def main():
 if len(sys.argv)!=5:raise SystemExit('usage: merge_master_state.py CURRENT INCOMING OUTPUT LIST_KEY')
 current=json.loads(Path(sys.argv[1]).read_text());incoming=json.loads(Path(sys.argv[2]).read_text())
 Path(sys.argv[3]).write_text(json.dumps(merge(current,incoming,sys.argv[4]),indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
