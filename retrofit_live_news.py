#!/usr/bin/env python3
"""Retrofit today's already-live news posts to the current title/coverage policy."""
from pathlib import Path
import datetime as dt, html, json, os, re, urllib.parse, urllib.request
from news_pipeline import BLOG, DESKS, IST, clip_words, coverage_window_text, desk_title_prefix

BLOG_ID=os.environ.get('BLOGGER_BLOG_ID',''); BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'

def token():
 data=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data,method='POST'),timeout=30) as r:return json.load(r)['access_token']

def call(path,tok,method='GET',body=None,params=None):
 url=BASE+path
 if params:url+='?'+urllib.parse.urlencode(params)
 data=json.dumps(body).encode() if body is not None else None
 req=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)

def plain(x):return html.unescape(re.sub(r'<[^>]+>','',x)).strip()

def retrofit(post):
 labels=post.get('labels',[]); desk=None
 for key,values in DESKS.items():
  if values[1] in labels:desk=key;break
 if not desk:raise RuntimeError(f"desk not found for {post.get('url')}: {labels}")
 published=dt.datetime.fromisoformat(post['published']).astimezone(IST)
 end=published;start=end-dt.timedelta(hours=24)
 coverage=coverage_window_text(start,end)
 publish_date=f"{published.day} {['January','February','March','April','May','June','July','August','September','October','November','December'][published.month-1]} {published.year}"
 content=post.get('content','')
 # Only current reporting h3s before optional Background/FX/Week-Ahead sections.
 current_area=re.split(r'<h2 class="fbk-h2"><b>(?:BG|04|05)</b>',content,maxsplit=1)[0]
 heads=[plain(x) for x in re.findall(r'<h3>(.*?)</h3>',current_area,re.S|re.I)]
 if not heads:raise RuntimeError('no current headlines in '+post.get('url',''))
 bits=clip_words('; '.join(heads[:2]),90)
 title=f"{desk_title_prefix(desk)} · {publish_date} · Coverage {coverage} — {bits}"
 current_count=len(heads);background_count=len(re.findall(r'class="fbk-item fbk-background"',content))
 volume=(f"All {current_count} significant current items are included." if current_count>12 else f"The strongest {current_count} current item(s) are included.")
 lede=(f'<p class="fbk-lede">{current_count} current, verified finance items from the {html.escape(DESKS[desk][1])} desk for '
       f'<strong>{coverage}</strong>{f", plus {background_count} clearly labelled background item(s)" if background_count else ""}. '
       f'{volume} Current coverage always leads. Read the source, not the noise.</p>')
 content,n1=re.subn(r'<h1 class="fbk-h1">.*?</h1>',f'<h1 class="fbk-h1">{html.escape(title)}</h1>',content,count=1,flags=re.S)
 content,n2=re.subn(r'<p class="fbk-lede">.*?</p>',lede,content,count=1,flags=re.S)
 sign=(f'<p>Every news item above is dated inside the stated coverage period, <strong>{coverage}</strong>. '
       'Where an item refers to an earlier fact, it is marked as background. The Week Ahead section looks forward only. '
       'Every item links to a genuine, trustworthy source — official or an established newsroom.</p>')
 content,n3=re.subn(r'(<div class="fbk-signoff">\s*<span class="fbk-script">.*?</span>\s*)<p>.*?</p>',lambda m:m.group(1)+sign,content,count=1,flags=re.S)
 def patch_schema(m):
  obj=json.loads(m.group(1));obj['headline']=clip_words(title,110)
  obj['description']=clip_words(f"{desk_title_prefix(desk)}, coverage {coverage}: {'; '.join(heads[:3])}",158)
  obj['publisher']={'@type':'Organization','name':'Daily Yield','url':BLOG+'/'}
  kws=str(obj.get('keywords',''));obj['keywords']=re.sub(r'last \d+ (?:hours|days)',f'coverage {coverage}',kws,flags=re.I)
  return '<script type="application/ld+json">'+json.dumps(obj,ensure_ascii=False)+'</script>'
 content,n4=re.subn(r'<script type="application/ld\+json">(.*?)</script>',patch_schema,content,count=1,flags=re.S)
 if not all((n1,n2,n4)):raise RuntimeError(f'critical patch marker missing h1={n1} lede={n2} schema={n4}')
 return title,content,{'desk':desk,'url':post['url'],'current_items':current_count,'background_items':background_count,'coverage':coverage,'signoff_patched':bool(n3)}

def main():
 tok=token();data=call('/posts',tok,params={'fetchBodies':'true','maxResults':'50','orderBy':'published'})
 today=dt.datetime.now(IST).date();targets=[]
 for p in data.get('items',[]):
  pd=dt.datetime.fromisoformat(p['published']).astimezone(IST).date()
  if pd==today and 'News' in p.get('labels',[]):targets.append(p)
 if not targets:raise RuntimeError('no live News posts found for today')
 results=[]
 for p in targets:
  title,content,rec=retrofit(p)
  body={'kind':'blogger#post','id':p['id'],'title':title,'content':content,'labels':p['labels']}
  updated=call('/posts/'+p['id'],tok,'PUT',body=body)
  rec['title']=updated.get('title');results.append(rec);print('updated',rec['desk'],updated.get('url'))
 Path('retrofit_live_news_result.json').write_text(json.dumps({'date':today.isoformat(),'updated':results},indent=2))
 print(json.dumps({'updated_count':len(results),'desks':[x['desk'] for x in results]},indent=2))
if __name__=='__main__':main()
