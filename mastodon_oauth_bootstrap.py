#!/usr/bin/env python3
"""One-time Mastodon OAuth exchanger. Never logs credentials or tokens."""
import json, os, urllib.parse, urllib.request
from cryptography.fernet import Fernet
INSTANCE=os.environ.get('MASTODON_INSTANCE','https://mastodon.social').rstrip('/')
REDIRECT='urn:ietf:wg:oauth:2.0:oob'
SCOPE='read:accounts write:media write:statuses'
def request(url,method='GET',data=None,token=None):
 headers={'Accept':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 if data is not None:headers['Content-Type']='application/x-www-form-urlencoded'
 req=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode() if data is not None else None,method=method,headers=headers)
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
code=os.environ['MASTODON_AUTH_CODE'].strip()
try:
 token=request(INSTANCE+'/oauth/token','POST',{'client_id':os.environ['MASTODON_CLIENT_ID'],'client_secret':os.environ['MASTODON_CLIENT_SECRET'],'redirect_uri':REDIRECT,'grant_type':'authorization_code','code':code,'scope':SCOPE})
 access=token['access_token']
 account=request(INSTANCE+'/api/v1/accounts/verify_credentials',token=access)
 if account.get('username','').lower()!='dailyyield':raise RuntimeError('Authorized account was not @dailyyield; refusing to store token')
 bundle={'instance':INSTANCE,'access_token':access,'token_type':token.get('token_type','Bearer'),'scope':token.get('scope',SCOPE),'account_id':account['id'],'username':account['username'],'acct':account.get('acct',account['username'])}
 encrypted=Fernet(os.environ['MASTODON_TOKEN_KEY'].encode()).encrypt(json.dumps(bundle,separators=(',',':')).encode())
 with open('mastodon_token.enc','wb') as f:f.write(encrypted+b'\n')
 with open('MASTODON_BOOTSTRAP_STATUS.json','w') as f:json.dump({'status':'PASS','instance':INSTANCE,'username':account['username'],'acct':account.get('acct'),'account_id':account['id'],'scopes':SCOPE.split()},f,indent=2)
 print('Mastodon authorization verified and encrypted for @dailyyield. No token was logged.')
except Exception as exc:
 print('Mastodon authorization failed safely. No credential details were logged.')
 raise SystemExit(1)
