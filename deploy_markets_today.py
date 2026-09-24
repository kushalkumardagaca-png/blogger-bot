#!/usr/bin/env python3
"""Create or update Markets Today without mutating Global Snapshot."""
from pathlib import Path
import json, os, requests

BLOG_ID=os.environ['BLOGGER_BLOG_ID']
BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
HTML=Path(__file__).with_name('markets_today_page.html').read_text(encoding='utf-8')

def headers():
 r=requests.post('https://oauth2.googleapis.com/token',data={
  'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],
  'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30)
 r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}

def pages(H):
 out=[];token=None
 while True:
  p={'fetchBodies':'true','maxResults':'50'}
  if token:p['pageToken']=token
  r=requests.get(BASE+'/pages',headers=H,params=p,timeout=60);r.raise_for_status();j=r.json();out+=j.get('items',[]);token=j.get('nextPageToken')
  if not token:return out

def put(H,pid,title,content):
 body={'kind':'blogger#page','id':pid,'title':title,'content':content}
 r=requests.put(f'{BASE}/pages/{pid}',headers=H,json=body,timeout=90);r.raise_for_status();return r.json()

def main():
 H=headers();allp=pages(H);actions=[]
 current=next((p for p in allp if p.get('title','').strip().upper()=='MARKETS TODAY'),None)
 if current:
  result=put(H,current['id'],'MARKETS TODAY',HTML);actions.append('updated MARKETS TODAY')
 else:
  body={'kind':'blogger#page','title':'MARKETS TODAY','content':HTML}
  r=requests.post(BASE+'/pages',headers=H,params={'isDraft':'false'},json=body,timeout=90);r.raise_for_status();result=r.json();actions.append('created MARKETS TODAY')
 url=result.get('url','')
 if url and url!='https://dailyyield.blogspot.com/p/markets-today.html':
  fixed=HTML.replace('https://dailyyield.blogspot.com/p/markets-today.html',url)
  result=put(H,result['id'],'MARKETS TODAY',fixed);actions.append('aligned structured canonical to '+url)
 check=requests.get(f"{BASE}/pages/{result['id']}",headers=H,params={'fetchBody':'true'},timeout=30);check.raise_for_status();got=check.json()
 assert got.get('title')=='MARKETS TODAY' and ('id="dyMarkets"' in got.get('content','') or 'id="dyMarketWall"' in got.get('content',''))
 report={'actions':actions,'markets_today':{'id':result['id'],'url':result.get('url')},'verified':True}
 Path('markets_today_deploy_result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
