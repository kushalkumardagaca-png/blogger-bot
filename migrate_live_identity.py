#!/usr/bin/env python3
"""Rename live Blogger pages/posts and shrink legacy embedded raster images.

Safe default is audit-only. Set APPLY_IDENTITY_MIGRATION=1 only immediately after
uploading Daily_Yield_Theme.xml and changing the Blogger title to DAILY YIELD.
Technical email addresses, social handles, and profile URLs are intentionally not
rewritten because changing their visible targets would break working links.
"""
from io import BytesIO
from pathlib import Path
import base64, json, os, re, sys
import requests
from PIL import Image

BLOG_ID=os.environ['BLOGGER_BLOG_ID']
APPLY=os.getenv('APPLY_IDENTITY_MIGRATION') == '1'
BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
IMG_RE=re.compile(r'data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)')
REPL=[
 ('FINANCE BY CA KUSHAL','DAILY YIELD'),
 ('Finance by CA Kushal','Daily Yield'),
 ('CA Kushal K. Daga','Kushal K. Daga'),
 ('CA Kushal Daga','Kushal K. Daga'),
 ('Kushal Kumar Daga','Kushal K. Daga'),
 ('CA Kushal','Kushal K. Daga'),
 ('CHARTERED ACCOUNTANT','CERTIFIED ACCOUNTANT'),
 ('Chartered Accountant','Certified Accountant'),
 ('chartered accountant','Certified Accountant'),
 ('https://financebycakushal.blogspot.com','https://dailyyield.blogspot.com'),
 ('http://financebycakushal.blogspot.com','https://dailyyield.blogspot.com'),
]

def headers():
 r=requests.post('https://oauth2.googleapis.com/token',data={
  'client_id':os.environ['BLOGGER_CLIENT_ID'],
  'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],
  'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],
  'grant_type':'refresh_token'},timeout=30); r.raise_for_status()
 return {'Authorization':'Bearer '+r.json()['access_token']}

def text_rewrite(s):
 for a,b in REPL: s=s.replace(a,b)
 return s

def slim_images(s, stat):
 def cv(m):
  raw=base64.b64decode(m.group(2))
  if len(raw)<20_000:return m.group(0)
  im=Image.open(BytesIO(raw)); out=BytesIO()
  alpha=im.mode in ('RGBA','LA') or (im.mode=='P' and 'transparency' in im.info)
  if not alpha and im.mode!='RGB': im=im.convert('RGB')
  im.save(out,'WEBP',quality=80,method=6,lossless=alpha)
  b=out.getvalue()
  if len(b)>=len(raw)*.90:return m.group(0)
  stat['images']+=1;stat['bytes']+=len(raw)-len(b)
  return 'data:image/webp;base64,'+base64.b64encode(b).decode()
 return IMG_RE.sub(cv,s)

def all_items(H, kind):
 items=[]; token=None
 while True:
  params={'maxResults':'50','fetchBodies':'true'}
  if kind=='posts':params['status']='live'
  if token:params['pageToken']=token
  r=requests.get(f'{BASE}/{kind}',headers=H,params=params,timeout=60);r.raise_for_status()
  j=r.json();items += j.get('items',[]);token=j.get('nextPageToken')
  if not token:return items

def main():
 H=headers(); backup=[]; planned=[]
 for kind in ('pages','posts'):
  for item in all_items(H,kind):
   title=item.get('title','');content=item.get('content',''); stat={'images':0,'bytes':0}
   nt=text_rewrite(title);nc=slim_images(text_rewrite(content),stat)
   old_labels=item.get('labels',[]); new_labels=[text_rewrite(x) for x in old_labels]
   if nt==title and nc==content and new_labels==old_labels:continue
   backup.append({'kind':kind,'id':item['id'],'title':title,'content':content,
                  'labels':old_labels,'published':item.get('published')})
   planned.append((kind,item,nt,nc,new_labels,stat))
 Path('identity_migration_backup.json').write_text(json.dumps(backup,ensure_ascii=False))
 print(f"Mode: {'APPLY' if APPLY else 'AUDIT ONLY'}; items requiring update: {len(planned)}")
 for kind,item,nt,nc,new_labels,st in planned:
  print(f"{kind[:-1]:4} {item['id']} | {item.get('title','')[:58]} | images {st['images']}, saved ~{st['bytes']//1024} KB")
  if not APPLY:continue
  body={'kind':'blogger#'+kind[:-1],'id':item['id'],'title':nt,'content':nc}
  if kind=='posts':
   body['labels']=new_labels
   if item.get('published'):body['published']=item['published']
  r=requests.put(f"{BASE}/{kind}/{item['id']}",headers=H,json=body,timeout=90);r.raise_for_status()
  chk=requests.get(f"{BASE}/{kind}/{item['id']}",headers=H,params={'fetchBody':'true'},timeout=30);chk.raise_for_status()
  got=chk.json()
  # Blogger may alphabetize labels on write; identity, not order, is the invariant.
  labels_ok = kind != 'posts' or set(got.get('labels',[])) == set(new_labels)
  if got.get('title')!=nt or got.get('content')!=nc or not labels_ok:
   raise RuntimeError('verification failed: '+item['id'])
 if not APPLY:
  print('No live content changed. Set APPLY_IDENTITY_MIGRATION=1 only at the coordinated theme flip.')
 else:print(f'Verified {len(planned)} live updates.')

if __name__=='__main__':main()
