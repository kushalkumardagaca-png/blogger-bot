#!/usr/bin/env python3
"""Create Global Snapshot at a new Blogger URL and retire the former Market Explorer page."""
from pathlib import Path
import json, os, requests

BLOG_ID=os.environ['BLOGGER_BLOG_ID']
BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
OLD_PATH='/p/share-market_0718113516.html'
EXPECTED_NEW='https://dailyyield.blogspot.com/p/global-snapshot.html'

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

def snapshot_content(content,new_url):
 replacements=[
  ('MARKET EXPLORER','GLOBAL SNAPSHOT'),('Market Explorer','Global Snapshot'),
  ('SHARE & MARKET','GLOBAL SNAPSHOT'),('Share & Market','Global Snapshot'),
  ('Share &amp; Market','Global Snapshot'),
  ('https://dailyyield.blogspot.com'+OLD_PATH,new_url),(OLD_PATH,new_url.replace('https://dailyyield.blogspot.com','')),
 ]
 for old,new in replacements:content=content.replace(old,new)
 marker='data-global-snapshot-nav="1"'
 if marker not in content:
  content+='''\n<script data-global-snapshot-nav="1">(function(){var u=%s;document.querySelectorAll('a[href*="share-market_0718113516"]').forEach(function(a){a.href=u;var s=a.querySelector('span');if(s)s.textContent='Global Snapshot';else if(a.textContent.trim())a.textContent='Global Snapshot';a.setAttribute('aria-label','Global Snapshot');a.setAttribute('title','Global Snapshot')})})();</script>''' % json.dumps(new_url)
 return content

def transition_content(new_url):
 return '''<div id="dyGlobalSnapshotTransition" style="max-width:760px;margin:40px auto;padding:clamp(28px,6vw,64px);border:1px solid #eadcc8;border-radius:20px;background:#fffdf8;color:#241610;text-align:center;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"><div style="font-size:10px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:#9c4522">Daily Yield</div><h1 style="margin:14px 0 10px;font:700 clamp(34px,7vw,58px)/1.05 Georgia,serif">Global Snapshot has moved.</h1><p style="max-width:560px;margin:0 auto 22px;color:#6e5d4b;line-height:1.7">The compact cross-asset summary now has its own address. Markets Today remains the complete global research command centre.</p><p style="display:flex;flex-wrap:wrap;justify-content:center;gap:10px"><a href="NEW_URL" style="padding:12px 17px;border-radius:9px;background:#241610;color:#fff;text-decoration:none;font-weight:800">Open Global Snapshot</a><a href="https://dailyyield.blogspot.com/p/markets-today.html" style="padding:12px 17px;border:1px solid #eadcc8;border-radius:9px;color:#241610;text-decoration:none;font-weight:800">Open Markets Today</a></p><small style="color:#6e5d4b">Redirecting to Global Snapshot…</small></div><script data-global-snapshot-transition="1">(function(){var u='NEW_URL';document.querySelectorAll('a[href*="share-market_0718113516"]').forEach(function(a){a.href=u;var s=a.querySelector('span');if(s)s.textContent='Global Snapshot'});setTimeout(function(){location.replace(u)},2200)})();</script>'''.replace('NEW_URL',new_url)

def main():
 H=headers();allp=pages(H);actions=[]
 snapshot=next((p for p in allp if p.get('title','').strip().upper()=='GLOBAL SNAPSHOT'),None)
 legacy=next((p for p in allp if p.get('url','').endswith(OLD_PATH) or p.get('title','').strip().upper() in ('MARKET EXPLORER','SHARE & MARKET','GLOBAL SNAPSHOT — MOVED')),None)
 if snapshot:
  source=snapshot.get('content','');actions.append('found existing GLOBAL SNAPSHOT')
 else:
  if not legacy:raise RuntimeError('former Market Explorer source page not found')
  source=legacy.get('content','')
  body={'kind':'blogger#page','title':'GLOBAL SNAPSHOT','content':snapshot_content(source,EXPECTED_NEW)}
  r=requests.post(BASE+'/pages',headers=H,params={'isDraft':'false'},json=body,timeout=90);r.raise_for_status();snapshot=r.json();actions.append('created GLOBAL SNAPSHOT from former summary page')
 new_url=snapshot.get('url') or EXPECTED_NEW
 if new_url != EXPECTED_NEW:
  raise RuntimeError(f'Blogger created unexpected Global Snapshot URL: {new_url}; expected {EXPECTED_NEW}')
 snapshot=put(H,snapshot['id'],'GLOBAL SNAPSHOT',snapshot_content(source,new_url));actions.append('aligned Global Snapshot identity and links')
 if not legacy or legacy['id']==snapshot['id']:
  refreshed=pages(H);legacy=next((p for p in refreshed if p.get('url','').endswith(OLD_PATH) and p['id']!=snapshot['id']),None)
 if not legacy:raise RuntimeError('legacy page URL not found for transition')
 legacy=put(H,legacy['id'],'GLOBAL SNAPSHOT — MOVED',transition_content(new_url));actions.append('converted former Market Explorer URL to transition page')
 check_new=requests.get(f"{BASE}/pages/{snapshot['id']}",headers=H,params={'fetchBody':'true'},timeout=30);check_new.raise_for_status();got=check_new.json()
 check_old=requests.get(f"{BASE}/pages/{legacy['id']}",headers=H,params={'fetchBody':'true'},timeout=30);check_old.raise_for_status();old=check_old.json()
 assert got.get('title')=='GLOBAL SNAPSHOT' and got.get('url')==new_url and 'data-global-snapshot-nav' in got.get('content','')
 assert old.get('title')=='GLOBAL SNAPSHOT — MOVED' and 'dyGlobalSnapshotTransition' in old.get('content','') and new_url in old.get('content','')
 report={'actions':actions,'global_snapshot':{'id':snapshot['id'],'url':new_url},'legacy_transition':{'id':legacy['id'],'url':legacy.get('url')},'verified':True}
 Path('global_snapshot_deploy_result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
