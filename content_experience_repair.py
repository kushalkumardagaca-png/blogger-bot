#!/usr/bin/env python3
"""Repair Daily Yield labels, duplicate hero photography and Page feed rendering.

Uses authenticated Blogger API inventory only; it never opens a public Daily Yield URL
and therefore creates no synthetic pageviews.
"""
from __future__ import annotations
import html, json, os, re, time
from pathlib import Path
import requests

BLOG_ID=os.environ['BLOGGER_BLOG_ID'];BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
REPORT=Path('CONTENT_EXPERIENCE_REPAIR_STATUS.json')
COMMONS='https://commons.wikimedia.org/w/api.php'
START='<!-- DY_CONTENT_EXPERIENCE_REPAIR_START -->';END='<!-- DY_CONTENT_EXPERIENCE_REPAIR_END -->'
NEWS_LABELS=['US','China','Germany','India','Japan','UK','France','Italy','Russia','Canada','Brazil','Spain','Mexico','Australia','South Korea','Market and Trading','Economy and Macro Policy','Corporate Finance and Industry','Personal Finance','Global News']

def auth():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}

def list_all(kind,h):
 out=[];token=None
 while True:
  params={'fetchBodies':'true','maxResults':'50','status':'live'}
  if token:params['pageToken']=token
  r=requests.get(f'{BASE}/{kind}',headers=h,params=params,timeout=120);r.raise_for_status();data=r.json();out.extend(data.get('items',[]));token=data.get('nextPageToken')
  if not token:return out

def put(kind,item,h,content=None,labels=None):
 body={'kind':f'blogger#{kind[:-1]}','id':item['id'],'title':item['title'],'content':item.get('content','') if content is None else content}
 if kind=='posts':body['labels']=item.get('labels',[]) if labels is None else labels
 r=requests.put(f"{BASE}/{kind}/{item['id']}",headers=h,json=body,timeout=120);r.raise_for_status();return r.json()

def norm(v):return re.sub(r'\s+',' ',re.sub(r'[,：:&]+',' ',str(v).lower().replace('&',' and '))).strip()
def srcs(c):return re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',c or '',re.I)
def clean_src(s):return re.sub(r'([?&])(w|h|q|fit|crop|auto)=[^&]+','',html.unescape(s or '')).rstrip('?&')
def strip_tags(v):return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(v or ''))).strip()

def categories_from_article_page(pages):
 page=next(p for p in pages if p.get('title','').strip().upper()=='DAILY ARTICLE')
 m=re.search(r'<script[^>]+id=["\']ar-config["\'][^>]*>(.*?)</script>',page['content'],re.I|re.S)
 if not m:raise RuntimeError('Daily Article ar-config missing')
 cfg=json.loads(html.unescape(m.group(1)))
 return page,cfg,[c['label'] for c in cfg['categories']]

def category_for(post,categories):
 labels=post.get('labels',[]);by={norm(c):c for c in categories}
 aliases={'starters students and first jobs':'Starters Students and First Jobs'}
 for label in labels:
  n=norm(label)
  if n in by:return by[n]
  if n in aliases and aliases[n] in categories:return aliases[n]
 # The existing Strategy label is also evidence after removing its suffix.
 for label in labels:
  n=norm(re.sub(r'\s+strategy\s*$','',label,flags=re.I))
  if n in by:return by[n]
 raise RuntimeError('No valid Daily Article category for post '+post.get('title',''))

def normalized_labels(post,categories):
 old=post.get('labels',[])
 if any(norm(x)=='news' for x in old):
  desk=next((x for x in old if x in NEWS_LABELS),None)
  if not desk:
   title=post.get('title','').lower();desk=next((x for x in NEWS_LABELS if x.lower() in title),None)
  if not desk:raise RuntimeError('News desk label missing for '+post.get('title',''))
  return ['News',desk]
 cat=category_for(post,categories);return list(dict.fromkeys([cat,'2026 Money Moves','Kushal K. Daga']))

def commons_photo(query,used):
 params={'action':'query','format':'json','generator':'search','gsrnamespace':'6','gsrlimit':'20','gsrsearch':query+' photograph filetype:bitmap','prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':'1200','origin':'*'}
 r=requests.get(COMMONS,params=params,headers={'User-Agent':'DailyYieldEditorialRepair/1.0 (dailyyield.official@gmail.com)'},timeout=45);r.raise_for_status()
 pages=(r.json().get('query') or {}).get('pages',{})
 for page in pages.values():
  info=(page.get('imageinfo') or [{}])[0];meta=info.get('extmetadata') or {};url=info.get('thumburl') or info.get('url') or '';base=clean_src(info.get('descriptionurl') or info.get('url') or '')
  if not url or base in used or re.search(r'\.(?:svg|gif|webm|ogv)(?:\?|$)',url,re.I):continue
  license_name=strip_tags((meta.get('LicenseShortName') or {}).get('value')) or 'Wikimedia Commons licence';artist=strip_tags((meta.get('Artist') or {}).get('value')) or 'Wikimedia Commons contributor'
  used.add(base);return {'url':url,'base':base,'credit':f'Photo: {artist[:100]} · {license_name} · Wikimedia Commons'}
 return None

def replace_hero(content,pic):
 m=re.search(r'<img\b[^>]*\bsrc=(["\'])([^"\']+)\1[^>]*>',content,re.I)
 if not m:return content
 tag=m.group(0);newtag=re.sub(r'\bsrc=(["\'])[^"\']+\1',lambda x:'src='+x.group(1)+html.escape(pic['url'],quote=True)+x.group(1),tag,count=1,flags=re.I)
 newtag=re.sub(r'\bloading=(["\'])lazy\1','loading="eager"',newtag,count=1,flags=re.I)
 out=content[:m.start()]+newtag+content[m.end():]
 fm=re.search(r'<figcaption\b[^>]*>.*?</figcaption>',out,re.I|re.S)
 credit=html.escape(pic['credit'])
 if fm:out=out[:fm.start()]+re.sub(r'>.*?</figcaption>',f'>{credit}</figcaption>',fm.group(0),flags=re.S)+out[fm.end():]
 return out

def entry(post):
 c=post.get('content','');im=(srcs(c) or [''])[0]
 text=strip_tags(c)[:1200]
 return {'id':{'$t':post['id']},'title':{'$t':post['title']},'published':{'$t':post.get('published','')},'category':[{'term':x} for x in post.get('labels',[])],'link':[{'rel':'alternate','href':post.get('url','')}],'content':{'$t':('<img src="'+html.escape(im,quote=True)+'">' if im else '')+'<p>'+html.escape(text)+'</p>'}}

def marked(content,block):
 if START in content:return re.sub(re.escape(START)+r'.*?'+re.escape(END),lambda _m:block,content,count=1,flags=re.S)
 return content+'\n'+block

def repair_article_page(page,posts,cfg):
 cfg['preview']=False;cfg['snapshotEntries']=[entry(p) for p in sorted(posts,key=lambda x:x.get('published',''),reverse=True) if 'News' not in p.get('labels',[])]
 c=page['content'];pat=r'(<script[^>]+id=["\']ar-config["\'][^>]*>).*?(</script>)';c,n=re.subn(pat,lambda m:m.group(1)+json.dumps(cfg,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+m.group(2),c,count=1,flags=re.I|re.S)
 if n!=1:raise RuntimeError('Unable to update article snapshot')
 c=c.replace("var thisRun=++runId;records=[];failed=false;loading=true;finished=false;retry.hidden=true;render();status.textContent='Reading the published article feed\\u2026';", "var thisRun=++runId;records=[];failed=false;loading=true;finished=false;retry.hidden=true;status.textContent='Refreshing the published article index\\u2026';")
 old="if(preview){records=(cfg.snapshotEntries||[]).map(parseEntry).filter(Boolean);finished=true;render();status.textContent=records.length?'Published-post snapshot \\u00b7 article cards link directly to the full posts':'No published non-news articles were available in the public feed at the last check';}\nelse load();"
 new="records=(cfg.snapshotEntries||[]).map(parseEntry).filter(Boolean);finished=true;render();status.textContent=records.length?'Archive ready \\u00b7 newest articles first \\u00b7 News excluded':'No non-news articles published yet';\nif(!preview)setTimeout(load,80);"
 if old not in c and new not in c:raise RuntimeError('Daily Article startup source not found')
 c=c.replace(old,new)
 css=START+'''<style>
#articleHub .ar-section{content-visibility:auto;contain-intrinsic-size:1px 430px}#articleHub .ar-track{gap:10px}#articleHub .ar-card{width:clamp(210px,24vw,280px)}#articleHub .ar-image{aspect-ratio:16/9}@media(max-width:620px){#articleHub .ar-card{width:210px}#articleHub .ar-section{padding-block:22px}.ar-heading h2{font-size:24px!important}}
</style>'''+END
 return marked(c,css)

def news_item(post):
 labels=post.get('labels',[]);desk=next((x for x in labels if x!='News'),'Global News');flags={'US':'🇺🇸','China':'🇨🇳','Germany':'🇩🇪','India':'🇮🇳','Japan':'🇯🇵','UK':'🇬🇧','France':'🇫🇷','Italy':'🇮🇹','Russia':'🇷🇺','Canada':'🇨🇦','Brazil':'🇧🇷','Spain':'🇪🇸','Mexico':'🇲🇽','Australia':'🇦🇺','South Korea':'🇰🇷'}
 return {'title':post['title'],'labels':labels,'flag':flags.get(desk,'🌐'),'published':post.get('published',''),'link':post.get('url',''),'img':(srcs(post.get('content','')) or [''])[0]}

def repair_news_page(page,posts):
 c=page['content'];items=[news_item(p) for p in sorted(posts,key=lambda x:x.get('published',''),reverse=True) if 'News' in p.get('labels',[])]
 snap='<script>window.ENH_NEWS_SNAPSHOT='+json.dumps(items,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';</script>'
 c=re.sub(r'<script>window\.ENH_NEWS_SNAPSHOT=.*?</script>','',c,flags=re.S)+snap
 # Repair an earlier alt-text migration that accidentally modified a JavaScript regex literal.
 c=re.sub(r'/<img\[\^ alt=["\'][^"\']+["\']>\]\+src=',r'/<img[^>]+src=',c)
 c=c.replace("renderAll(w.ENH_PREVIEW?demoItems():[],!!w.ENH_PREVIEW);", "renderAll(w.ENH_PREVIEW?demoItems():(w.ENH_NEWS_SNAPSHOT||[]),!!w.ENH_PREVIEW);")
 c=c.replace("status('demo',w.ENH_PREVIEW?'Offline sample layout \\u00b7 examples, not published news':'Loading published news\\u2026');", "status(w.ENH_PREVIEW?'demo':'live',w.ENH_PREVIEW?'Offline sample layout \\u00b7 examples, not published news':'Published news ready \\u00b7 newest first');")
 css=START+'''<style>
#enhancedSite .kn-rowwrap{overflow:visible!important}#enhancedSite .kn-track{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important;transform:none!important;animation:none!important;max-width:none!important}#enhancedSite .kn-card{min-width:0!important;width:auto!important}#enhancedSite .kn-cimg{aspect-ratio:16/9;max-height:150px}#enhancedSite .kn-cimg img{width:100%;height:100%;object-fit:cover}@media(max-width:700px){#enhancedSite .kn-track{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important}#enhancedSite .kn-card{padding:9px!important}#enhancedSite .kn-ctitle{font-size:15px!important}.kn-cfoot{font-size:8px!important}}
</style>'''+END
 return marked(c,css)

def main():
 h=auth();posts=list_all('posts',h);pages=list_all('pages',h);article_page,cfg,categories=categories_from_article_page(pages)
 labels_fixed=0;images_fixed=0;used=set();hero_owner={}
 # Newest instance keeps an existing duplicated photo; older repeats receive a distinct Commons photo.
 for p in sorted(posts,key=lambda x:x.get('published',''),reverse=True):
  old=p.get('labels',[]);new=normalized_labels(p,categories)
  hero=clean_src((srcs(p.get('content','')) or [''])[0]);duplicate=bool(hero and hero in hero_owner);content=p.get('content','')
  if hero:used.add(hero)
  if duplicate:
   desk=next((x for x in new if x not in ('News','2026 Money Moves','Kushal K. Daga')),new[0]);pic=commons_photo(p.get('title','')+' '+desk,used)
   if pic:content=replace_hero(content,pic);images_fixed+=1
  if hero:hero_owner.setdefault(hero,p['id'])
  if new!=old or content!=p.get('content',''):
   put('posts',p,h,content,new);p['labels']=new;p['content']=content;labels_fixed+=int(new!=old);time.sleep(.08)
 by_title={p['title'].strip().upper():p for p in pages}
 ap=by_title['DAILY ARTICLE'];np=by_title['DAILY NEWS']
 ac=repair_article_page(ap,posts,cfg);nc=repair_news_page(np,posts)
 pages_fixed=0
 if ac!=ap['content']:put('pages',ap,h,ac);pages_fixed+=1
 if nc!=np['content']:put('pages',np,h,nc);pages_fixed+=1
 # Authenticated verification; no public URL requests.
 verified=list_all('posts',h);heroes=[clean_src((srcs(p.get('content','')) or [''])[0]) for p in verified];heroes=[x for x in heroes if x];dupes=len(heroes)-len(set(heroes))
 report={'status':'PASS' if dupes==0 else 'PARTIAL','zero_view':True,'posts_checked':len(posts),'labels_normalized':labels_fixed,'duplicate_heroes_replaced':images_fixed,'remaining_duplicate_heroes':dupes,'pages_repaired':pages_fixed,'article_snapshot_entries':sum('News' not in p.get('labels',[]) for p in posts),'news_snapshot_entries':sum('News' in p.get('labels',[]) for p in posts)}
 REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
 if dupes:raise RuntimeError(f'{dupes} duplicate hero assignments remain')
if __name__=='__main__':main()
