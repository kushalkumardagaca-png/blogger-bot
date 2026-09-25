#!/usr/bin/env python3
"""Add compact contextual Daily Yield cards to every Post and repair broken hero assets."""
from pathlib import Path
import html, json, os, re, urllib.parse, urllib.request
from contextual_links import STYLE, card

BLOG_ID=os.environ['BLOGGER_BLOG_ID'];BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
APPLY=os.environ.get('APPLY','false').lower()=='true'
BROKEN='https://images.unsplash.com/photo-1611974748038-1e8768f0db4a?auto=format&fit=crop&w=1600&h=900&q=85'
REPLACEMENT='https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&h=900&q=85'

def token():
 data=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST'),timeout=30) as r:return json.load(r)['access_token']

def call(path,tok,method='GET',body=None,params=None):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)

def collect(tok):
 out=[];page=None
 while True:
  params={'fetchBodies':'true','maxResults':'50','orderBy':'published'}
  if page:params['pageToken']=page
  data=call('/posts',tok,params=params);out+=data.get('items',[]);page=data.get('nextPageToken')
  if not page:return out

def plain(s):return html.unescape(re.sub(r'<[^>]+>',' ',s or ''))

def add_news_cards(content):
 def enhance(match):
  block=match.group(0)
  if 'dy-context' in block or 'fbk-src' not in block:return block
  hm=re.search(r'<h3[^>]*>(.*?)</h3>',block,re.I|re.S)
  if not hm:return block
  title=plain(hm.group(1)).strip()
  if title.startswith('EUR/') or 'ECB Daily Rates' in title:return block
  pm=re.search(r'<p[^>]*>(.*?)</p>',block,re.I|re.S)
  context=title+' '+(plain(pm.group(1)) if pm else '')
  links=list(re.finditer(r'<a[^>]*class=["\'][^"\']*fbk-src[^"\']*["\'][^>]*>.*?</a>',block,re.I|re.S))
  if not links:return block
  end=links[-1].end()
  return block[:end]+'\n      '+card(context)+block[end:]
 return re.sub(r'<div[^>]+class=["\'][^"\']*\bfbk-item\b[^"\']*["\'][^>]*>.*?</div>',enhance,content,flags=re.I|re.S)

def add_article_card(content,title):
 if 'class="dy-context"' in content:return content
 m=re.search(r'</figure\s*>',content,re.I)
 insert=card(title+' '+plain(content[:7000]))
 if m:return content[:m.end()]+'\n'+insert+content[m.end():]
 # Old text-only article fallback: place after the first substantive paragraph.
 m=re.search(r'</p\s*>',content,re.I)
 return content[:m.end()]+'\n'+insert+content[m.end():] if m else insert+content

def main():
 tok=token();posts=collect(tok);changes=[]
 Path('contextual_links_backup.json').write_text(json.dumps({'posts':posts},ensure_ascii=False))
 for post in posts:
  old=post.get('content','');new=old.replace(BROKEN,REPLACEMENT);is_news='News' in post.get('labels',[])
  new=add_news_cards(new) if is_news else add_article_card(new,post.get('title',''))
  if 'class="dy-context"' in new and 'id="dyContextStyle"' not in new:new=STYLE+'\n'+new
  if new==old:continue
  detail={'url':post.get('url'),'news':is_news,'cards':new.count('class="dy-context"'),'hero_repaired':BROKEN in old}
  changes.append(detail)
  if APPLY:
   body={'kind':'blogger#post','id':post['id'],'title':post['title'],'content':new,'labels':post.get('labels',[])}
   call('/posts/'+post['id'],tok,'PUT',body=body)
 report={'apply':APPLY,'posts_scanned':len(posts),'posts_changed':len(changes),'changes':changes}
 Path('CONTEXTUAL_LINKS_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
 print(json.dumps({'apply':APPLY,'scanned':len(posts),'changed':len(changes),'cards':sum(x['cards'] for x in changes),'heroes_repaired':sum(x['hero_repaired'] for x in changes)},indent=2))
if __name__=='__main__':main()
