#!/usr/bin/env python3
"""Build a zero-view visual fingerprint baseline from every live Post and Page."""
import hashlib,html,json,os,re
from concurrent.futures import ThreadPoolExecutor,as_completed
from io import BytesIO
from pathlib import Path
import imagehash,requests
from PIL import Image
from photo_selector import REGISTRY,load_registry,save_registry,UA
ROOT=Path(__file__).parent
def need(n):
 v=os.environ.get(n,'').strip()
 if not v:raise RuntimeError(n+' is required')
 return v
def token():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':need('BLOGGER_CLIENT_ID'),'client_secret':need('BLOGGER_CLIENT_SECRET'),'refresh_token':need('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return r.json()['access_token']
def inventory(t,kind):
 base=f"https://www.googleapis.com/blogger/v3/blogs/{need('BLOGGER_BLOG_ID')}/{kind}";items=[];page=None
 while True:
  params={'status':'live','fetchBodies':'true','maxResults':50,'fields':'items(id,title,url,content),nextPageToken'}
  if page:params['pageToken']=page
  r=requests.get(base,headers={'Authorization':'Bearer '+t},params=params,timeout=60);r.raise_for_status();d=r.json();items+=d.get('items',[]);page=d.get('nextPageToken')
  if not page:return items
def fingerprint(row):
 url,usages=row
 try:
  r=requests.get(url,headers={'User-Agent':UA},timeout=35);r.raise_for_status();raw=r.content[:12_000_000];im=Image.open(BytesIO(raw)).convert('RGB')
  return {'url':url,'original_url':url,'source_id':'historic-url:'+hashlib.sha256(url.encode()).hexdigest()[:24],'sha256':hashlib.sha256(raw).hexdigest(),'phash':str(imagehash.phash(im)),'historic_usages':usages,'baseline':'authenticated-blogger'}
 except Exception:return {'url':url,'original_url':url,'source_id':'historic-url:'+hashlib.sha256(url.encode()).hexdigest()[:24],'sha256':None,'phash':None,'historic_usages':usages,'baseline':'unavailable-historic-url'}
def main():
 r=load_registry()
 if r.get('baseline_complete'):print('photo baseline already complete');return
 t=token();all_items=[('posts',x) for x in inventory(t,'posts')]+[('pages',x) for x in inventory(t,'pages')];urls={}
 for kind,x in all_items:
  for u in re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',x.get('content',''),re.I):
   u=html.unescape(u)
   if u.startswith(('http://','https://')):urls.setdefault(u,[]).append({'kind':kind,'id':x['id'],'title':x.get('title'),'page_url':x.get('url')})
 existing={x.get('original_url') or x.get('url') for x in r['items']};rows=[(u,v) for u,v in urls.items() if u not in existing]
 with ThreadPoolExecutor(max_workers=12) as pool:
  futures=[pool.submit(fingerprint,row) for row in rows]
  for f in as_completed(futures):r['items'].append(f.result())
 r['baseline_complete']=True;r['authenticated_items']=len(all_items);r['historic_unique_urls']=len(urls);r['unavailable_count']=sum(1 for x in r['items'] if x.get('baseline')=='unavailable-historic-url');save_registry(r)
 print(json.dumps({'items':len(all_items),'images':len(urls),'unavailable':r['unavailable_count']}))
if __name__=='__main__':main()
