#!/usr/bin/env python3
"""Race-safe semantic merge for concurrent News desk tracker updates."""
import json,sys
from pathlib import Path

def rank(row):return (str(row.get('edition','')),str(row.get('window_end','')),str(row.get('published_at','')),str(row.get('url','')))
def merge(current,incoming):
 out={**current,**incoming};desks={}
 for name in set(current.get('desks',{}))|set(incoming.get('desks',{})):
  a=current.get('desks',{}).get(name,{});b=incoming.get('desks',{}).get(name,{})
  desks[name]=dict(max((a,b),key=rank))
 out['desks']=desks;return out

def main():
 if len(sys.argv)!=4:raise SystemExit('usage: merge_news_state.py CURRENT INCOMING OUTPUT')
 a=json.loads(Path(sys.argv[1]).read_text());b=json.loads(Path(sys.argv[2]).read_text());Path(sys.argv[3]).write_text(json.dumps(merge(a,b),indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
