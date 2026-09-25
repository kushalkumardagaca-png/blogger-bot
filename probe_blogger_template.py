#!/usr/bin/env python3
"""Read-only probe for Blogger's administrator template feed."""
import json,os,urllib.parse,urllib.request,urllib.error

def token():
 data=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST'),timeout=30) as r:return json.load(r)['access_token']
tok=token();bid=os.environ['BLOGGER_BLOG_ID'];results=[]
for url in [f'https://www.blogger.com/feeds/{bid}/template',f'https://www.blogger.com/feeds/{bid}/template/full',f'https://www.blogger.com/feeds/{bid}/archive']:
 req=urllib.request.Request(url,headers={'Authorization':'Bearer '+tok,'GData-Version':'2.0','User-Agent':'DailyYield-maintenance'})
 try:
  with urllib.request.urlopen(req,timeout=120) as r:
   data=r.read();name='probe_'+url.rsplit('/',1)[-1]+'.xml';open(name,'wb').write(data);results.append({'url':url,'status':r.status,'bytes':len(data),'type':r.headers.get('Content-Type'),'file':name})
 except urllib.error.HTTPError as e:results.append({'url':url,'status':e.code,'bytes':len(e.read()),'type':e.headers.get('Content-Type')})
print(json.dumps(results,indent=2))
open('template_probe.json','w').write(json.dumps(results,indent=2))
