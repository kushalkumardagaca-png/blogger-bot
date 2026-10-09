#!/usr/bin/env python3
"""Repair Daily Yield labels, duplicate hero photography and Page feed rendering.

Uses authenticated Blogger API inventory only; it never opens, prefetches or renders a
public Daily Yield URL and therefore creates no synthetic pageviews.
"""
from __future__ import annotations
import html, json, os, re, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from page_family import ensure_family

BLOG_ID=os.environ['BLOGGER_BLOG_ID'];BASE=f'https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}'
REPORT=Path('CONTENT_EXPERIENCE_REPAIR_STATUS.json')
LABEL_INDEX=Path('LABEL_FEED_INDEX.json')
COMMONS='https://commons.wikimedia.org/w/api.php'
START='<!-- DY_CONTENT_EXPERIENCE_REPAIR_START -->';END='<!-- DY_CONTENT_EXPERIENCE_REPAIR_END -->'
NEWS_GEOGRAPHIES=['Global Finance News','Americas Finance News','China Finance News','Asia-Pacific Finance News','India Finance News','Russia Finance News','Europe Finance News']
NEWS_TOPICS=['Markets, Crypto & Commodities','Economy, Trade & Jobs','Banking, Fintech & Personal Money','Companies, IPOs & Deals']
NEWS_LABELS=NEWS_GEOGRAPHIES+NEWS_TOPICS
COUNTRY_LABELS=['Country · United States','Country · Canada','Country · Mexico','Country · Brazil','Country · China','Country · Japan','Country · South Korea','Country · Australia','Country · India','Country · Russia','Country · United Kingdom','Country · Germany','Country · France','Country · Italy','Country · Spain']
LEGACY_COUNTRY_MAP={
 'US':'Country · United States','Canada':'Country · Canada','Mexico':'Country · Mexico','Brazil':'Country · Brazil',
 'China':'Country · China','Japan':'Country · Japan','South Korea':'Country · South Korea','Australia':'Country · Australia',
 'India':'Country · India','Russia':'Country · Russia','UK':'Country · United Kingdom','Germany':'Country · Germany',
 'France':'Country · France','Italy':'Country · Italy','Spain':'Country · Spain',
}
LEGACY_NEWS_MAP={
 'Global News':'Global Finance News','US':'Americas Finance News','Canada':'Americas Finance News',
 'Mexico':'Americas Finance News','Brazil':'Americas Finance News','China':'China Finance News',
 'Japan':'Asia-Pacific Finance News','South Korea':'Asia-Pacific Finance News','Australia':'Asia-Pacific Finance News',
 'India':'India Finance News','Russia':'Russia Finance News','UK':'Europe Finance News',
 'Germany':'Europe Finance News','France':'Europe Finance News','Italy':'Europe Finance News','Spain':'Europe Finance News',
 'Market and Trading':'Markets, Crypto & Commodities','Economy and Macro Policy':'Economy, Trade & Jobs',
 'Corporate Finance and Industry':'Companies, IPOs & Deals','Personal Finance':'Banking, Fintech & Personal Money',
}
_PROVENANCE=None

def auth():
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}

def api(method,url,**kwargs):
 last=None
 for attempt in range(5):
  try:
   r=requests.request(method,url,timeout=120,**kwargs)
   if r.status_code in (429,500,502,503,504):raise requests.HTTPError(f'transient Blogger API {r.status_code}',response=r)
   r.raise_for_status();return r
  except requests.RequestException as exc:
   last=exc
   if attempt<4:time.sleep(2**attempt)
 raise last

def list_all(kind,h):
 out=[];token=None
 while True:
  params={'fetchBodies':'true','maxResults':'50','status':'live'}
  if token:params['pageToken']=token
  data=api('GET',f'{BASE}/{kind}',headers=h,params=params).json();out.extend(data.get('items',[]));token=data.get('nextPageToken')
  if not token:return out

def put(kind,item,h,content=None,labels=None):
 body={'kind':f'blogger#{kind[:-1]}','id':item['id'],'title':item['title'],'content':item.get('content','') if content is None else content}
 if kind=='posts':body['labels']=item.get('labels',[]) if labels is None else labels
 return api('PUT',f"{BASE}/{kind}/{item['id']}",headers=h,json=body).json()

def norm(v):return re.sub(r'\s+',' ',re.sub(r'[,：:&]+',' ',str(v).lower().replace('&',' and '))).strip()
def srcs(c):return re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',c or '',re.I)
def clean_src(s):return re.sub(r'([?&])(w|h|q|fit|crop|auto)=[^&]+','',html.unescape(s or '')).rstrip('?&')
def strip_tags(v):return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html.unescape(v or ''))).strip()
def image_key(url):
 from urllib.parse import unquote,urlparse
 path=unquote(urlparse(url or '').path);parts=[x for x in path.split('/') if x]
 if 'thumb' in parts and len(parts)>=2:return parts[-2].lower()
 if parts:
  last=parts[-1]
  if last.lower().startswith('file:'):last=last[5:]
  return last.lower()
 return clean_src(url).lower()

def categories_from_article_page(pages):
 page=next(p for p in pages if p.get('title','').strip().upper()=='DAILY ARTICLE')
 m=re.search(r'<script[^>]+id=["\']ar-config["\'][^>]*>(.*?)</script>',page['content'],re.I|re.S)
 if not m:raise RuntimeError('Daily Article ar-config missing')
 cfg=json.loads(html.unescape(m.group(1)))
 return page,cfg,[c['label'] for c in cfg['categories']]

def category_for(post,categories):
 # The authenticated pre-repair inventory preserves the original desk labels and
 # is the recovery source after the former shared "2026 Money Moves" tag caused
 # every Master Article to be grouped into one shelf.
 global _PROVENANCE
 if _PROVENANCE is None:
  try:
   inv=json.loads(Path('CONTENT_EXPERIENCE_INVENTORY.json').read_text())
   _PROVENANCE={x.get('id'):x.get('labels',[]) for x in inv.get('posts',[])}
  except Exception:_PROVENANCE={}
 labels=_PROVENANCE.get(post.get('id')) or post.get('labels',[]);by={norm(c):c for c in categories}
 aliases={'starters students and first jobs':'Starters Students and First Jobs'}
 # Prefer a specific desk; the shared collection name is considered only when
 # no other canonical category exists (the real Desk 25 articles).
 ordered=[x for x in labels if norm(x)!='2026 money moves']+[x for x in labels if norm(x)=='2026 money moves']
 for label in ordered:
  n=norm(label)
  if n in by:return by[n]
  if n in aliases and aliases[n] in categories:return aliases[n]
 for label in ordered:
  n=norm(re.sub(r'\s+strategy\s*$','',label,flags=re.I))
  if n in by:return by[n]
 raise RuntimeError('No valid Daily Article category for post '+post.get('title',''))

def normalized_labels(post,categories):
 old=post.get('labels',[])
 if any(norm(x)=='news' for x in old):
  canonical=[x for x in old if x in NEWS_LABELS]
  countries=[x for x in old if x in COUNTRY_LABELS]
  if canonical:
   kind='Category Edition' if 'Category Edition' in old else 'Geographic Edition'
   allowed=['News',kind]+canonical+countries
   return list(dict.fromkeys(allowed))
  legacy=next((x for x in old if x in LEGACY_NEWS_MAP),None)
  if not legacy:
   title=post.get('title','').lower();legacy=next((x for x in LEGACY_NEWS_MAP if x.lower() in title),None)
  if not legacy:raise RuntimeError('News desk label missing for '+post.get('title',''))
  mapped=LEGACY_NEWS_MAP[legacy]
  kind='Category Edition' if mapped in NEWS_TOPICS else 'Geographic Edition'
  country=[LEGACY_COUNTRY_MAP[legacy]] if legacy in LEGACY_COUNTRY_MAP else []
  return ['News',kind,mapped,*country,'Legacy News']
 cat=category_for(post,categories);return [cat,'Kushal K. Daga']

def commons_photo(title,desk,used):
 country={'Global Finance News':'world financial district','Americas Finance News':'Americas financial district','China Finance News':'China financial district','Asia-Pacific Finance News':'Asia Pacific financial district','India Finance News':'India financial district','Russia Finance News':'Russia financial district','Europe Finance News':'Europe financial district','Markets, Crypto & Commodities':'stock market crypto commodities','Economy, Trade & Jobs':'economy trade employment','Banking, Fintech & Personal Money':'banking payments household finance','Companies, IPOs & Deals':'corporate business capital markets'}
 cleaned=re.sub(r'\b(?:finance|news|20\d\d|september|october|november|december|january|february|march|april|may|june|july|august)\b|[—–-]|\d+',' ',title,flags=re.I)
 words=' '.join(re.findall(r"[A-Za-z£$']+",cleaned)[:5])
 queries=[(country.get(desk,desk)+' city business').strip(),(words+' '+country.get(desk,desk)).strip(),country.get(desk,desk)+' economy',(words+' people working').strip(),'finance people office','city business district']
 for query in queries:
  params={'action':'query','format':'json','generator':'search','gsrnamespace':'6','gsrlimit':'50','gsrsearch':query,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':'1200','origin':'*'}
  try:
   r=requests.get(COMMONS,params=params,headers={'User-Agent':'DailyYieldEditorialRepair/1.0 (dailyyield.official@gmail.com)'},timeout=45);r.raise_for_status()
  except requests.RequestException:
   continue
  pages=(r.json().get('query') or {}).get('pages',{})
  for page in pages.values():
   info=(page.get('imageinfo') or [{}])[0];meta=info.get('extmetadata') or {};url=info.get('thumburl') or info.get('url') or '';source_ref=(page.get('title','')+' '+(info.get('descriptionurl') or info.get('url') or ''));base=image_key(info.get('descriptionurl') or info.get('url') or '')
   # Commons can render a PDF or DjVu cover as a JPEG thumbnail. Those are
   # documents, not editorial photographs, and previously caused repeat heroes.
   if not url or base in used or re.search(r'\.(?:svg|gif|webm|ogv)(?:\?|$)',url,re.I) or re.search(r'\.(?:pdf|djvu|tif|tiff)(?:\b|/|$)',source_ref,re.I):continue
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

def repair_remaining_duplicate_heroes(h,rounds=3):
 """Retry only genuine duplicate heroes and return any unresolved groups.

 Each pass re-reads Blogger so URL normalization performed by Blogger is taken
 into account. The newest post keeps the image; older members receive distinct
 Commons photographs. A bounded pass count prevents an endless repair loop.
 """
 unresolved=[]
 for _ in range(rounds):
  current=list_all('posts',h);groups={};used=set()
  for post in current:
   key=image_key(clean_src((srcs(post.get('content','')) or [''])[0]))
   if key:used.add(key);groups.setdefault(key,[]).append(post)
  duplicate_groups={key:sorted(items,key=lambda x:x.get('published',''),reverse=True) for key,items in groups.items() if len(items)>1}
  if not duplicate_groups:return [],0
  changed=0;unresolved=[]
  for key,items in duplicate_groups.items():
   for post in items[1:]:
    labels=post.get('labels',[]);desk=next((x for x in labels if x not in ('News','2026 Money Moves','Kushal K. Daga')),labels[0] if labels else 'Personal Finance')
    pic=commons_photo(post.get('title',''),desk,used)
    if not pic:
     unresolved.append({'image_key':key,'post_id':post.get('id'),'title':post.get('title','')});continue
    content=replace_hero(post.get('content',''),pic)
    if content==post.get('content',''):
     unresolved.append({'image_key':key,'post_id':post.get('id'),'title':post.get('title','')});continue
    put('posts',post,h,content,post.get('labels',[]));changed+=1;time.sleep(.08)
  if not changed:break
 final=list_all('posts',h);groups={}
 for post in final:
  key=image_key(clean_src((srcs(post.get('content','')) or [''])[0]))
  if key:groups.setdefault(key,[]).append(post)
 unresolved=[{'image_key':key,'posts':[{'post_id':x.get('id'),'title':x.get('title','')} for x in items]} for key,items in groups.items() if len(items)>1]
 return unresolved,sum(len(x['posts'])-1 for x in unresolved)

def entry(post):
 c=post.get('content','');im=(srcs(c) or [''])[0]
 text=strip_tags(c)[:1200];alt=html.escape(post.get('title','Daily Yield article photograph'),quote=True)
 return {'id':{'$t':post['id']},'title':{'$t':post['title']},'published':{'$t':post.get('published','')},'category':[{'term':x} for x in post.get('labels',[])],'link':[{'rel':'alternate','href':post.get('url','')}],'content':{'$t':('<img alt="'+alt+'" src="'+html.escape(im,quote=True)+'">' if im else '')+'<p>'+html.escape(text)+'</p>'}}

def page_hygiene(content,title):
 # Add alt text only to literal Page markup, never by rewriting JavaScript.
 parts=re.split(r'(<script\b.*?</script>)',content or '',flags=re.I|re.S);safe_alt=html.escape(title.title()+' — Daily Yield',quote=True)
 for i in range(0,len(parts),2):parts[i]=re.sub(r'<img\b(?![^>]*\balt\s*=)',lambda m:'<img alt="'+safe_alt+'"',parts[i],flags=re.I)
 out=''.join(parts)
 if 'DY_SEO_META_START' not in out and 'metaDesc' not in out:
  desc=html.escape(title.title()+' — Official Daily Yield information, context and reader guidance.',quote=True)
  out+='''<!-- DY_SEO_META_START --><script>(function(d){var metaDesc="'''+desc+'''",m=d.querySelector('meta[name="description"]');if(!m){m=d.createElement('meta');m.name='description';d.head.appendChild(m);}if(!m.content)m.content=metaDesc;})(document);</script><!-- DY_SEO_META_END -->'''
 return out

def marked(content,block):
 if START in content:return re.sub(re.escape(START)+r'.*?'+re.escape(END),lambda _m:block,content,count=1,flags=re.S)
 return content+'\n'+block

# Immutable marker for the clean static Article application deployed from authenticated data.
ARTICLE_SCRATCH_MARK='DY_ARTICLE_FROM_SCRATCH_V5_OVERSIZED_LATEST_CARDS'

def article_card(post,cat):
 title=html.escape(post.get('title','Untitled article'));url=html.escape(post.get('url','#'),quote=True);image=(srcs(post.get('content','')) or [cat.get('art','')])[0]
 try:date=time.strftime('%d %b %Y',time.strptime(post.get('published','')[:10],'%Y-%m-%d'))
 except Exception:date='From the journal'
 pic=('<img src="'+html.escape(image,quote=True)+'" alt="'+html.escape(post.get('title','Daily Yield article'),quote=True)+' — Daily Yield article photograph" loading="lazy" decoding="async">') if image else '<span class="dya-fallback">DY</span>'
 published=html.escape(post.get('published',''),quote=True)
 return '<a class="dya-card" data-published="'+published+'" href="'+url+'"><span class="dya-image">'+pic+'</span><span class="dya-cardbody"><small>'+html.escape(date)+' · '+html.escape(cat.get('name','Article'))+'</small><strong>'+title+'</strong><b>Read article <i>↗</i></b></span></a>'

def build_article_page(posts,cfg):
 eligible=sorted((p for p in posts if 'News' not in p.get('labels',[])),key=lambda x:x.get('published',''),reverse=True)
 cats=cfg.get('categories',[]);sections=[];index=[]
 cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
 def recent(post):
  try:return datetime.fromisoformat(post.get('published','').replace('Z','+00:00')).astimezone(timezone.utc)>=cutoff
  except (TypeError,ValueError):return False
 def card_category(post):
  return next((cat for cat in cats if any(norm(x)==norm(cat.get('label','')) for x in post.get('labels',[]))),{'name':'Latest article','art':''})
 newest=[p for p in eligible if recent(p)]
 recent_cards=''.join(article_card(p,card_category(p)) for p in newest)
 recent_body=('''<div class="dya-row" tabindex="0" role="region" aria-label="Articles published in the last 24 hours"><div class="dya-strip"><div class="dya-set">'''+recent_cards+'''</div></div></div>''') if newest else '<p class="dya-empty">No new articles were published in the last 24 hours. The shelf updates automatically when a new article arrives.</p>'
 recent_section='''<section class="dya-desk dya-new" id="dya-new"><header class="dya-deskhead"><div><small>THE LATEST · A ROLLING 24-HOUR WINDOW</small><h2>NEW ON THE PAGE</h2></div></header><p class="dya-desc">Every Daily Yield article published during the previous 24 hours, newest first.</p><div class="dya-tools"><span>'''+str(len(newest))+''' new article'''+('' if len(newest)==1 else 's')+'''</span></div>'''+recent_body+'''</section>'''
 for cat in cats:
  number=str(cat.get('number',''));found=[p for p in eligible if any(norm(x)==norm(cat.get('label','')) for x in p.get('labels',[]))]
  cards=''.join(article_card(p,cat) for p in found)
  index.append('<a href="#dya-'+number+'"><b>'+number.zfill(2)+'</b><span>'+html.escape(cat.get('name',''))+'</span></a>')
  sections.append('''<section class="dya-desk" id="dya-'''+number+'''"><header class="dya-deskhead"><div><small>DESK '''+number.zfill(2)+''' · '''+html.escape(cat.get('eyebrow','Explore the question'))+'''</small><h2>'''+html.escape(cat.get('name',''))+'''</h2></div><a href="/search/label/'''+html.escape(cat.get('label',''),quote=True).replace(' ','%20')+'''?max-results=20">More articles ↗</a></header><p class="dya-desc">'''+html.escape(cat.get('description',''))+'''</p><div class="dya-tools"><span>'''+str(len(found))+''' article'''+('' if len(found)==1 else 's')+'''</span><button type="button" data-dir="-1" aria-label="Move '''+html.escape(cat.get('name',''))+''' articles left">←</button><button type="button" data-dir="1" aria-label="Move '''+html.escape(cat.get('name',''))+''' articles right">→</button></div><div class="dya-row" tabindex="0" role="region" aria-label="'''+html.escape(cat.get('name',''))+''' article carousel"><div class="dya-strip"><div class="dya-set">'''+cards+'''</div></div></div></section>''')
 config=json.dumps({'categories':cats},ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
 return '''<!-- '''+ARTICLE_SCRATCH_MARK+''' --><style>
#dyArticle{--ink:#241610;--muted:#6e5d4b;--accent:#bc5b33;--deep:#9c4522;--line:#e3d3b3;--paper:#fffdf8;--cream:#f8f0e3;box-sizing:border-box;max-width:1180px;margin:0 auto;padding:clamp(16px,4vw,46px);color:var(--ink);background:linear-gradient(180deg,#fffdf8,#f8f0e3);font:400 15px/1.7 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;overflow:hidden}#dyArticle *{box-sizing:border-box}#dyArticle a{text-decoration:none}
#dyArticle .dya-hero{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(290px,.92fr);gap:clamp(18px,4vw,42px);align-items:center;padding:clamp(24px,4vw,42px) clamp(16px,3vw,32px);border:1px solid #e3ccb0;border-radius:8px 24px 8px 24px;background:linear-gradient(180deg,rgba(246,227,211,.8),rgba(248,240,227,0))}#dyArticle .dya-copy{min-width:0;text-align:left}#dyArticle .dya-kicker{display:inline-block;padding:7px 12px;border:1px dashed var(--accent);border-radius:4px;color:var(--accent);background:#fbf1e5;font-size:10px;font-weight:800;letter-spacing:.18em;text-transform:uppercase}#dyArticle h1{margin:18px 0 12px;font:800 clamp(36px,6vw,68px)/1.02 Georgia,serif;letter-spacing:-.045em}#dyArticle h1 em{color:var(--accent)}#dyArticle .dya-lede{max-width:680px;margin:0;color:#4a4036;font-size:15px}#dyArticle .dya-chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:18px}#dyArticle .dya-chips span{padding:5px 9px;border:1px solid var(--line);border-radius:999px;background:#fbf6ec;color:var(--muted);font-size:9px;font-weight:800;text-transform:uppercase}
#dyArticle .dya-note{position:relative;width:100%;max-width:370px;justify-self:end;padding:15px;border:1px solid #eadcc8;border-radius:19px;background:var(--paper);box-shadow:0 20px 38px -26px rgba(36,22,16,.4);transform:rotate(.5deg)}#dyArticle .dya-note:before{content:"";position:absolute;z-index:2;left:50%;top:-10px;width:78px;height:20px;background:rgba(188,91,51,.22);border-inline:2px dashed rgba(255,253,248,.75);transform:translateX(-50%) rotate(-3deg)}#dyArticle .dya-deck{overflow:hidden;border-radius:12px}#dyArticle .dya-notetrack{display:flex;transition:transform .6s cubic-bezier(.22,.61,.36,1)}#dyArticle .dya-sheet{flex:0 0 100%;min-width:0;min-height:250px;padding:16px 13px 12px;border:1px solid #eadcc8;border-radius:12px;background:var(--cream)}#dyArticle .dya-sheet h2{margin:0 0 9px;color:var(--deep);font:500 22px/1.15 Caveat,"Segoe Script",cursive}#dyArticle .dya-nrow{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px dashed rgba(156,69,34,.18);font-size:11px}#dyArticle .dya-nrow b{max-width:46%;color:var(--deep);font-size:10px;text-align:right}#dyArticle .dya-progress{height:3px;margin:12px 2px 5px;overflow:hidden;border-radius:99px;background:#eadcc8}#dyArticle .dya-progress i{display:block;width:0;height:100%;background:var(--accent)}
#dyArticle .dya-nav{margin:22px 0 8px;padding:16px;border-block:1px solid var(--line)}#dyArticle .dya-nav strong{display:block;margin-bottom:10px;font:700 18px Georgia,serif}#dyArticle .dya-index{display:flex;gap:7px;overflow-x:auto;padding-bottom:7px;scrollbar-width:thin}#dyArticle .dya-index a{display:flex;flex:0 0 auto;gap:6px;padding:8px 10px;border:1px solid var(--line);border-radius:999px;color:var(--deep);background:#fbf6ec;font-size:10px;font-weight:700}#dyArticle .dya-index b{color:var(--accent)}
#dyArticle .dya-desk{padding:34px 0 40px;border-bottom:1px solid var(--line);text-align:left}#dyArticle .dya-deskhead{display:flex;align-items:end;justify-content:space-between;gap:16px}#dyArticle .dya-deskhead>div{text-align:left}#dyArticle .dya-deskhead small{display:block;margin-bottom:8px;color:var(--accent);font-size:10px;font-weight:800;letter-spacing:.2em;text-transform:uppercase}#dyArticle .dya-desk h2{position:relative;display:inline-block;margin:0;color:var(--ink);font:800 clamp(26px,4vw,38px)/1.06 Georgia,serif;letter-spacing:-.025em;text-align:left}#dyArticle .dya-desk h2:after{content:"";position:absolute;left:0;bottom:-8px;width:54px;height:3px;border-radius:3px;background:var(--accent)}#dyArticle .dya-deskhead>a{flex:0 0 auto;padding:9px 14px;border:1px solid var(--line);border-radius:999px;color:var(--accent);background:#fbf6ec;font-size:11px;font-weight:800}#dyArticle .dya-desc{max-width:760px;margin:20px 0 14px;color:var(--muted);text-align:left}#dyArticle .dya-tools{display:flex;align-items:center;gap:7px;margin-bottom:8px}#dyArticle .dya-tools span{margin-right:auto;color:#8c7a66;font-size:9px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}#dyArticle .dya-tools button{display:grid;width:34px;height:34px;place-items:center;border:1px solid var(--line);border-radius:50%;background:#fbf6ec;color:var(--deep);cursor:pointer}
#dyArticle .dya-row{width:100%;overflow-x:auto;overflow-y:hidden;border-radius:14px;cursor:grab;touch-action:pan-y;overscroll-behavior-inline:contain;scrollbar-width:none}#dyArticle .dya-row::-webkit-scrollbar{display:none}#dyArticle .dya-row.dya-dragging{cursor:grabbing;user-select:none}#dyArticle .dya-strip{display:flex;width:max-content;max-width:none}#dyArticle .dya-set{display:flex;flex:0 0 auto;gap:18px;padding:6px 18px 8px 2px}#dyArticle .dya-card{display:flex;flex:0 0 clamp(340px,38vw,410px);width:clamp(340px,38vw,410px);min-width:340px;min-height:410px;overflow:hidden;flex-direction:column;border:1px solid #eadcc8;border-radius:16px;background:var(--paper);color:var(--ink);box-shadow:0 8px 22px -14px rgba(36,22,16,.35);transition:transform .25s,box-shadow .25s,border-color .25s}#dyArticle .dya-card:hover{transform:translateY(-3px);border-color:var(--accent);box-shadow:0 18px 36px -18px rgba(188,91,51,.35)}#dyArticle .dya-image{display:block;width:100%;aspect-ratio:16/9;overflow:hidden;background:#ead8bc}#dyArticle .dya-image img{display:block!important;width:100%!important;height:100%!important;max-width:none!important;margin:0!important;padding:0!important;border:0!important;object-fit:cover!important;object-position:center center!important;transform:none!important}#dyArticle .dya-fallback{display:grid;width:100%;height:100%;place-items:center;color:var(--accent);font:700 40px Georgia,serif}#dyArticle .dya-cardbody{display:flex;flex:1;flex-direction:column;padding:18px}#dyArticle .dya-cardbody small{color:#8c7a66;font-size:10px;font-weight:800;text-transform:uppercase}#dyArticle .dya-cardbody strong{display:-webkit-box;margin:10px 0 18px;overflow:hidden;color:var(--ink);font:700 22px/1.25 Georgia,serif;-webkit-line-clamp:3;-webkit-box-orient:vertical}#dyArticle .dya-cardbody b{display:flex;justify-content:space-between;margin-top:auto;padding-top:11px;border-top:1px solid #eee0ce;color:var(--accent);font-size:11px}#dyArticle .dya-cardbody i{font-size:18px}
#dyArticle .dya-new{margin-top:10px;padding:38px 18px 44px;border:1px solid #e3d3b3;border-radius:22px;background:linear-gradient(180deg,rgba(246,227,211,.55),transparent 78%)}#dyArticle .dya-new .dya-deskhead small{color:var(--deep)}#dyArticle .dya-new .dya-set{gap:22px;padding:8px 22px 10px 2px}#dyArticle .dya-new .dya-card{flex-basis:clamp(440px,56vw,620px);width:clamp(440px,56vw,620px);min-width:440px;min-height:500px;border-radius:20px}#dyArticle .dya-new .dya-cardbody{padding:22px}#dyArticle .dya-new .dya-cardbody strong{font-size:clamp(24px,3vw,30px);line-height:1.2}#dyArticle .dya-new .dya-cardbody small{font-size:11px}#dyArticle .dya-empty{margin:8px 0 0;padding:22px;border:1px dashed var(--line);border-radius:14px;background:#fbf6ec;color:var(--muted)}#dyArticle .dya-disclaimer{margin:22px 0 0;color:#806b55;font-size:11px}
@media(max-width:760px){#dyArticle{padding:14px 10px}#dyArticle .dya-hero{grid-template-columns:1fr;gap:22px;padding:24px 14px}#dyArticle .dya-note{max-width:100%;justify-self:stretch;transform:none}#dyArticle h1{font-size:clamp(36px,12vw,54px)}#dyArticle .dya-deskhead{align-items:start}#dyArticle .dya-deskhead>a{padding:8px 10px;font-size:9px}#dyArticle .dya-card{flex-basis:86vw;width:86vw;min-width:300px;min-height:390px}#dyArticle .dya-image{aspect-ratio:16/10}#dyArticle .dya-cardbody{padding:16px}#dyArticle .dya-cardbody strong{font-size:20px}#dyArticle .dya-new{padding:28px 10px 34px}#dyArticle .dya-new .dya-card{flex-basis:92vw;width:92vw;min-width:320px;min-height:450px}#dyArticle .dya-new .dya-cardbody strong{font-size:24px}}
@media(prefers-reduced-motion:reduce){#dyArticle *{animation:none!important;transition:none!important}}
</style><main id="dyArticle"><header class="dya-hero"><div class="dya-copy"><span class="dya-kicker">The article collection · Take your time</span><h1>Good money questions.<br>Better <em>answers.</em></h1><p class="dya-lede">Beyond the daily headlines: original explainers and practical guides for decisions that stay with you. Find your question, follow the working and read at your own pace.</p><div class="dya-chips"><span>25 topic desks</span><span>'''+str(len(eligible))+''' published articles</span><span>News excluded</span></div></div><aside class="dya-note" aria-label="Daily Article reading notes"><div class="dya-deck"><div class="dya-notetrack"><article class="dya-sheet"><h2>a little reading order ✳</h2><div class="dya-nrow"><span>Find your question</span><b>pick a desk</b></div><div class="dya-nrow"><span>Follow the working</span><b>not the hype</b></div><div class="dya-nrow"><span>Check your context</span><b>country + date</b></div><div class="dya-nrow"><span>Leave with one action</span><b>keep it simple</b></div></article><article class="dya-sheet"><h2>the article promise ✳</h2><div class="dya-nrow"><span>Longer-lived ideas</span><b>not the news wire</b></div><div class="dya-nrow"><span>Show the trade-offs</span><b>no false certainty</b></div><div class="dya-nrow"><span>Ask a better question</span><b>always useful</b></div><div class="dya-nrow"><span>Education, not advice</span><b>context matters</b></div></article><article class="dya-sheet"><h2>make it your own ✳</h2><div class="dya-nrow"><span>Take one topic</span><b>no rush</b></div><div class="dya-nrow"><span>Drag any article row</span><b>either direction</b></div><div class="dya-nrow"><span>Follow a category</span><b>go deeper</b></div><div class="dya-nrow"><span>Return when life changes</span><b>keep learning</b></div></article></div></div><div class="dya-progress"><i></i></div></aside></header><nav class="dya-nav" aria-label="Article topic desks"><strong>Find your desk</strong><div class="dya-index">'''+''.join(index)+'''</div></nav>'''+recent_section+''.join(sections)+'''<p class="dya-disclaimer">Financial education, not personalised advice. Check the article date, country and current rules before acting.</p></main><script id="ar-config" type="application/json">'''+config+'''</script><script>
(function(w,d){'use strict';var root=d.getElementById('dyArticle');if(!root)return;var reduce=w.matchMedia&&w.matchMedia('(prefers-reduced-motion: reduce)').matches;
function wire(row){var strip=row.querySelector('.dya-strip'),first=strip&&strip.querySelector('.dya-set');if(!strip||!first)return;var guard=0;while(strip.scrollWidth<row.clientWidth*2.2&&guard++<10){var copy=first.cloneNode(true);copy.setAttribute('aria-hidden','true');copy.querySelectorAll('a').forEach(function(a){a.tabIndex=-1});strip.appendChild(copy)}var cycle=first.getBoundingClientRect().width,last=0,drag=null,moved=false,hover=false,pausedUntil=0,visible=true;function delay(ms){pausedUntil=Date.now()+ms}if('IntersectionObserver' in w)new IntersectionObserver(function(es){visible=es[0].isIntersecting},{rootMargin:'100px'}).observe(row);row.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.button!==0)return;drag={x:e.clientX,left:row.scrollLeft,id:e.pointerId};moved=false;pausedUntil=0;row.classList.add('dya-dragging');try{row.setPointerCapture(e.pointerId)}catch(_){}});row.addEventListener('pointermove',function(e){if(!drag)return;var dx=e.clientX-drag.x;if(Math.abs(dx)>6)moved=true;row.scrollLeft=drag.left-dx;e.preventDefault()});function end(){if(!drag)return;var id=drag.id;drag=null;row.classList.remove('dya-dragging');try{if(row.hasPointerCapture(id))row.releasePointerCapture(id)}catch(_){}delay(180)}row.addEventListener('pointerup',end);row.addEventListener('pointercancel',end);row.addEventListener('lostpointercapture',end);row.addEventListener('wheel',function(){delay(900)},{passive:true});row.addEventListener('pointerenter',function(e){if(e.pointerType==='mouse')hover=true});row.addEventListener('pointerleave',function(e){if(e.pointerType==='mouse'){hover=false;delay(250)}});row.addEventListener('click',function(e){if(moved){e.preventDefault();e.stopPropagation();moved=false}},true);function frame(ts){if(!last)last=ts;var dt=Math.min(.05,(ts-last)/1000);last=ts;if(visible&&!drag&&!hover&&Date.now()>pausedUntil&&!d.hidden&&!reduce&&cycle>0){row.scrollLeft+=72*dt;if(row.scrollLeft>=cycle)row.scrollLeft-=cycle}w.requestAnimationFrame(frame)}w.requestAnimationFrame(frame)}
var newShelf=root.querySelector('#dya-new'),newRow=newShelf&&newShelf.querySelector('.dya-row');if(newRow){var now=Date.now();newRow.querySelectorAll('.dya-card').forEach(function(card){var stamp=Date.parse(card.dataset.published||''),age=now-stamp;if(!Number.isFinite(stamp)||age<0||age>86400000)card.remove()});var fresh=newRow.querySelectorAll('.dya-card').length,count=newShelf.querySelector('.dya-tools span');if(count)count.textContent=fresh+' new article'+(fresh===1?'':'s');if(!fresh){var empty=d.createElement('p');empty.className='dya-empty';empty.textContent='No new articles were published in the last 24 hours. The shelf updates automatically when a new article arrives.';newRow.replaceWith(empty)}}root.querySelectorAll('.dya-row').forEach(function(row){wire(row)});root.querySelectorAll('[data-dir]').forEach(function(b){b.addEventListener('click',function(){b.closest('.dya-desk').querySelector('.dya-row').scrollBy({left:Number(b.dataset.dir)*300,behavior:reduce?'auto':'smooth'})})});var track=root.querySelector('.dya-notetrack'),bar=root.querySelector('.dya-progress i'),n=0;function note(){if(!track)return;track.style.transform='translateX(-'+(n*100)+'%)';if(bar){bar.style.transition='none';bar.style.width='0';void bar.offsetWidth;bar.style.transition=reduce?'none':'width 4s linear';bar.style.width='100%'}}note();if(!reduce)setInterval(function(){n=(n+1)%3;note()},4000);
})(window,document);
</script>'''

def repair_article_page(page,posts,cfg):
 # Full replacement by design: no legacy Article HTML, CSS or JavaScript is
 # retained. Published content and the canonical 25 category definitions are
 # the only inputs.
 content=build_article_page(posts,cfg)
 content=ensure_family(content,'/p/article.html')
 return page_hygiene(content,'DAILY ARTICLE')

def news_item(post):
 labels=post.get('labels',[]);desk=next((x for x in labels if x in NEWS_LABELS),'Global Finance News')
 flags={'Americas Finance News':'🌎','China Finance News':'🇨🇳','Asia-Pacific Finance News':'🌏','India Finance News':'🇮🇳','Russia Finance News':'🇷🇺','Europe Finance News':'🇪🇺','Global Finance News':'🌐','Markets, Crypto & Commodities':'📈','Economy, Trade & Jobs':'📊','Banking, Fintech & Personal Money':'🏦','Companies, IPOs & Deals':'🏢'}
 return {'title':post['title'],'labels':labels,'flag':flags.get(desk,'🌐'),'published':post.get('published',''),'link':post.get('url',''),'img':(srcs(post.get('content','')) or [''])[0]}

def news_static_fallback(items):
 payload=json.dumps(items,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
 regions=[('Global Finance News','🌐','Global'),('Americas Finance News','🌎','Americas'),('China Finance News','🇨🇳','China'),('Asia-Pacific Finance News','🌏','Asia-Pacific'),('India Finance News','🇮🇳','India'),('Russia Finance News','🇷🇺','Russia'),('Europe Finance News','🇪🇺','Europe')]
 topics=[('Markets, Crypto & Commodities','📈','Markets, Crypto & Commodities'),('Economy, Trade & Jobs','📊','Economy, Trade & Jobs'),('Banking, Fintech & Personal Money','🏦','Banking, Fintech & Personal Money'),('Companies, IPOs & Deals','🏢','Companies, IPOs & Deals')]
 countries=[('Country · United States','🇺🇸','United States'),('Country · Canada','🇨🇦','Canada'),('Country · Mexico','🇲🇽','Mexico'),('Country · Brazil','🇧🇷','Brazil'),('Country · China','🇨🇳','China'),('Country · Japan','🇯🇵','Japan'),('Country · South Korea','🇰🇷','South Korea'),('Country · Australia','🇦🇺','Australia'),('Country · India','🇮🇳','India'),('Country · Russia','🇷🇺','Russia'),('Country · United Kingdom','🇬🇧','United Kingdom'),('Country · Germany','🇩🇪','Germany'),('Country · France','🇫🇷','France'),('Country · Italy','🇮🇹','Italy'),('Country · Spain','🇪🇸','Spain')]
 desks=json.dumps({'regions':regions,'topics':topics},ensure_ascii=False,separators=(',',':'))
 return '''<!-- DY_AUTHENTICATED_NEWS_FALLBACK_START --><style>/* DY_AUTHENTICATED_NEWS_FALLBACK_V6_OVERSIZED_LATEST_CARDS */
.dy-auth-news{padding:10px 0 30px}.dy-auth-news-kicker{color:#a34d2c;font:700 9px/1.4 sans-serif;letter-spacing:.22em;text-transform:uppercase}.dy-auth-news-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 24px}.dy-auth-news-top h2{font-size:clamp(28px,5vw,44px)}.dy-auth-news-all,.dy-auth-news-more{border:1px solid #dfcdb9;border-radius:999px;padding:9px 14px;color:#9d4a2b;font:700 10px/1 sans-serif;white-space:nowrap}.dy-auth-desk{padding:20px 0 30px;border-top:1px solid #eadcca}.dy-auth-desk-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}.dy-auth-desk h3{font-size:24px}.dy-auth-row{display:flex;gap:16px;overflow-x:auto;overscroll-behavior-inline:contain;scrollbar-width:none;cursor:grab;touch-action:pan-y}.dy-auth-row::-webkit-scrollbar{display:none}.dy-auth-row.dy-dragging{cursor:grabbing;user-select:none}.dy-auth-card{display:flex;flex:0 0 clamp(330px,37vw,400px);width:clamp(330px,37vw,400px);min-width:330px;min-height:360px;overflow:hidden;flex-direction:column;border:1px solid #eadcca;border-radius:14px;background:#fffdf8}.dy-auth-img{width:100%;aspect-ratio:16/9;background:#f5e5cd;display:grid;place-items:center;color:#b36a41;font:700 28px Georgia,serif;overflow:hidden}.dy-auth-img img{display:block!important;width:100%!important;height:100%!important;max-width:none!important;margin:0!important;padding:0!important;border:0!important;object-fit:cover!important;object-position:center center!important;transform:none!important}.dy-auth-body{display:flex;flex:1;flex-direction:column;padding:16px}.dy-auth-body b{display:-webkit-box;overflow:hidden;font:600 20px/1.28 Georgia,serif;-webkit-line-clamp:4;-webkit-box-orient:vertical}.dy-auth-body small{display:block;margin-top:auto;padding-top:12px;color:#857261;font:700 10px/1.3 sans-serif}.dy-auth-recent{margin-bottom:28px;padding:28px!important;border:1px solid #eadcca;border-radius:22px;background:linear-gradient(180deg,rgba(246,227,211,.68),#fffdf8)}.dy-auth-recent .dy-auth-news-top{margin-bottom:18px}.dy-auth-recent .dy-auth-row{gap:22px}.dy-auth-recent .dy-auth-card{flex-basis:clamp(440px,56vw,620px);width:clamp(440px,56vw,620px);min-width:440px;min-height:500px;border-radius:20px}.dy-auth-recent .dy-auth-body{padding:22px}.dy-auth-recent .dy-auth-body b{font-size:clamp(24px,3vw,30px);line-height:1.2}.dy-auth-recent .dy-auth-body small{font-size:11px}.dy-auth-recent-empty{margin:0;padding:20px;border:1px dashed #dfcdb9;border-radius:12px;color:#6e5d4b;background:#fbf6ec;font:500 14px/1.6 sans-serif}@media(max-width:700px){.dy-auth-row{gap:12px}.dy-auth-card{flex-basis:86vw;width:86vw;min-width:300px;min-height:340px}.dy-auth-desk h3{font-size:21px}.dy-auth-body{padding:14px}.dy-auth-body b{font-size:18px}.dy-auth-recent{padding:20px 10px 26px!important}.dy-auth-recent .dy-auth-card{flex-basis:92vw;width:92vw;min-width:320px;min-height:450px}.dy-auth-recent .dy-auth-body b{font-size:24px}}
</style><script>(function(w,d){var items='''+payload+''',desks='''+desks+''';function findTitle(name){var hs=d.querySelectorAll('h1,h2,h3,h4');for(var i=0;i<hs.length;i++){if((hs[i].textContent||'').trim()===name)return hs[i];}return null;}function link(label){return '/search/label/'+encodeURIComponent(label)+'?max-results=50';}function makeCard(it){var a=d.createElement('a');a.className='dy-auth-card';a.href=it.link;a.dataset.labels=(it.labels||[]).join('|');var pic=d.createElement('div');pic.className='dy-auth-img';if(it.img){var im=d.createElement('img');im.src=it.img;im.alt=it.title||'Daily Yield news photograph';im.loading='lazy';pic.appendChild(im);}else pic.textContent=(it.title||'N').charAt(0);var body=d.createElement('div');body.className='dy-auth-body';var b=d.createElement('b');b.textContent=it.title;var sm=d.createElement('small');sm.textContent=(it.published||'').slice(0,10);body.appendChild(b);body.appendChild(sm);a.appendChild(pic);a.appendChild(body);return a;}function globalTitle(){var hs=d.querySelectorAll('h1,h2,h3,h4');for(var i=0;i<hs.length;i++){var t=(hs[i].textContent||'').trim().toLowerCase();if(t.indexOf('global')>=0&&(t.indexOf('news')>=0||t.indexOf('dispatch')>=0||t.indexOf('wire')>=0))return hs[i];}return null;}function recentShelf(anchor){var prior=d.querySelector('.dy-auth-recent');if(prior)prior.remove();if(!anchor)return;var anchorSection=anchor.closest('section')||anchor.parentElement;if(!anchorSection||!anchorSection.parentNode)return;var now=Date.now(),fresh=items.filter(function(it){var stamp=Date.parse(it.published||'');var age=now-stamp;return Number.isFinite(stamp)&&age>=0&&age<=86400000;}).sort(function(a,b){return Date.parse(b.published)-Date.parse(a.published)});var sec=d.createElement('section');sec.className='dy-auth-news dy-auth-recent';sec.id='dy-auth-new';var k=d.createElement('p');k.className='dy-auth-news-kicker';k.textContent=fresh.length+' POST'+(fresh.length===1?'':'S')+' · PUBLISHED IN THE LAST 24 HOURS';var top=d.createElement('div');top.className='dy-auth-news-top';var h=d.createElement('h2');h.textContent='NEW ON THE PAGE';top.appendChild(h);sec.appendChild(k);sec.appendChild(top);if(fresh.length){var row=d.createElement('div');row.className='dy-auth-row';row.setAttribute('aria-label','News published in the last 24 hours');fresh.forEach(function(it){row.appendChild(makeCard(it));});sec.appendChild(row);wire(row);}else{var empty=d.createElement('p');empty.className='dy-auth-recent-empty';empty.textContent='No new News posts were published in the last 24 hours. This shelf updates automatically when the next dispatch arrives.';sec.appendChild(empty);}anchorSection.parentNode.insertBefore(sec,anchorSection);}function wire(row){var originals=[].slice.call(row.children);if(!originals.length)return;originals.forEach(function(n){var c=n.cloneNode(true);c.setAttribute('aria-hidden','true');c.tabIndex=-1;row.appendChild(c);});var half=0,pausedUntil=0,last=0,drag=null,moved=false,hover=false;function measure(){half=row.scrollWidth/2;}requestAnimationFrame(measure);function delay(ms){pausedUntil=Date.now()+ms;}row.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.button!==0)return;drag={x:e.clientX,left:row.scrollLeft,id:e.pointerId};moved=false;pausedUntil=0;row.classList.add('dy-dragging');try{row.setPointerCapture(e.pointerId);}catch(_e){}});row.addEventListener('pointermove',function(e){if(!drag)return;var dx=e.clientX-drag.x;if(Math.abs(dx)>6)moved=true;row.scrollLeft=drag.left-dx;e.preventDefault();});function end(e){if(!drag)return;var id=drag.id;drag=null;row.classList.remove('dy-dragging');try{if(row.hasPointerCapture(id))row.releasePointerCapture(id);}catch(_e){}delay(180);}row.addEventListener('pointerup',end);row.addEventListener('pointercancel',end);row.addEventListener('lostpointercapture',end);w.addEventListener('blur',end);row.addEventListener('wheel',function(){delay(900);},{passive:true});row.addEventListener('pointerenter',function(e){if(e.pointerType==='mouse')hover=true;});row.addEventListener('pointerleave',function(e){if(e.pointerType==='mouse'){hover=false;delay(250);}});row.addEventListener('click',function(e){if(moved){e.preventDefault();e.stopPropagation();moved=false;}},true);function tick(ts){if(!last)last=ts;var dt=Math.min(.05,(ts-last)/1000);last=ts;if(!drag&&!hover&&Date.now()>pausedUntil&&!d.hidden&&half>0){row.scrollLeft+=72*dt;if(row.scrollLeft>=half)row.scrollLeft-=half;}requestAnimationFrame(tick);}requestAnimationFrame(tick);}function buildShelf(spec,kicker,forced){var label=spec[0],flag=spec[1],shown=spec[2],sec;if(forced){sec=forced.closest('section')||forced.parentElement;if(!sec)return null;sec.innerHTML='';}else{sec=d.createElement('section');}sec.className=(sec.className||'')+' dy-auth-news dy-auth-desk-shelf';var k=d.createElement('p');k.className='dy-auth-news-kicker';k.textContent=kicker;var top=d.createElement('div');top.className='dy-auth-news-top';var hd=d.createElement('h2');hd.textContent=flag+' '+shown;var all=d.createElement('a');all.className='dy-auth-news-all';all.href=link(label);all.textContent='Read more →';top.appendChild(hd);top.appendChild(all);sec.appendChild(k);sec.appendChild(top);var found=items.filter(function(it){return (it.labels||[]).indexOf(label)>=0;}).sort(function(a,b){return Date.parse(b.published)-Date.parse(a.published)}).slice(0,8);if(found.length){var row=d.createElement('div');row.className='dy-auth-row';row.setAttribute('aria-label',shown+' latest articles');found.forEach(function(it){row.appendChild(makeCard(it));});sec.appendChild(row);wire(row);}return sec;}function buildShelfGroup(anchor,list,kicker){if(!anchor)return;var old=anchor.closest('section')||anchor.parentElement;if(!old||!old.parentNode)return;var parent=old.parentNode;list.forEach(function(spec){parent.insertBefore(buildShelf(spec,kicker),old);});old.remove();}function buildOrderedShelves(regionAnchor,subjectAnchor){var anchor=regionAnchor||subjectAnchor;if(!anchor)return;var old=anchor.closest('section')||anchor.parentElement;if(!old||!old.parentNode)return;var subject=subjectAnchor&&(subjectAnchor.closest('section')||subjectAnchor.parentElement);if(subject&&subject!==old)subject.remove();var parent=old.parentNode;desks.topics.forEach(function(spec){parent.insertBefore(buildShelf(spec,'SUBJECT EDITION'),old);});desks.regions.slice(1).forEach(function(spec){parent.insertBefore(buildShelf(spec,'GEOGRAPHIC EDITION'),old);});old.remove();}function boot(){var g=globalTitle(),a=findTitle('Country dispatches')||findTitle('News by region'),b=findTitle('Specialty desks')||findTitle('News by subject');recentShelf(g||a||b);if(g)buildShelf(['Global Finance News','🌐','Global Finance News'],'GLOBAL EDITION',g);buildOrderedShelves(a,b);}if(d.readyState==='loading')d.addEventListener('DOMContentLoaded',boot,{once:true});else setTimeout(boot,0);})(window,document);</script><!-- DY_AUTHENTICATED_NEWS_FALLBACK_END -->'''

def repair_news_page(page,posts):
 c=page['content'];items=[news_item(p) for p in sorted(posts,key=lambda x:x.get('published',''),reverse=True) if 'News' in p.get('labels',[])]
 snap='<script>window.ENH_NEWS_SNAPSHOT='+json.dumps(items,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';</script>'
 c=re.sub(r'<script>window\.ENH_NEWS_SNAPSHOT=.*?</script>','',c,flags=re.S)
 engine=c.find("var w=window,d=document,root=d.getElementById('enhancedSite');")
 script_start=c.rfind('<script',0,engine)
 if engine<0 or script_start<0:raise RuntimeError('Daily News rendering engine not found')
 c=c[:script_start]+snap+c[script_start:]
 # Repair an earlier alt-text migration that accidentally modified a JavaScript regex literal.
 c=re.sub(r'/<img\[\^ alt=["\'][^"\']+["\']>\]\+src=',r'/<img[^>]+src=',c)
 c=re.sub(r"function labelURL\(l\)\{.*?\n\}", "function labelURL(l){return '/search/label/'+encodeURIComponent(l)+'?max-results=50';}", c, count=1, flags=re.S)
 c=c.replace("fillTrack(rows.g,byLabel(items,GLOBAL).slice(0,10),GLOBAL,sample);", "var globalItems=byLabel(items,GLOBAL);if(!globalItems.length)globalItems=items.slice().sort(function(a,b){return a.published<b.published?1:-1;}).slice(0,12);fillTrack(rows.g,globalItems,GLOBAL,sample);")
 c=c.replace("renderAll(w.ENH_PREVIEW?demoItems():[],!!w.ENH_PREVIEW);", "renderAll(w.ENH_PREVIEW?demoItems():(w.ENH_NEWS_SNAPSHOT||[]),!!w.ENH_PREVIEW);")
 c=c.replace("status('demo',w.ENH_PREVIEW?'Offline sample layout \\u00b7 examples, not published news':'Loading published news\\u2026');", "status(w.ENH_PREVIEW?'demo':'live',w.ENH_PREVIEW?'Offline sample layout \\u00b7 examples, not published news':'Published news ready \\u00b7 newest first');")
 c=c.replace("var loop=items.length>=4;\n var pool=loop?items.concat(items):items;", "var loop=false;\n var pool=items;")
 c=c.replace("try{pull();setInterval(function(){if(!d.hidden)pull();},300000);}catch(e){}", "/* Authenticated snapshot is complete; public feed must not replace it with a partial batch. */")
 c=c.replace("if(d.readyState==='loading'){d.addEventListener('DOMContentLoaded',main);}else{main();}", "if(d.readyState==='loading'){d.addEventListener('DOMContentLoaded',main);}else{setTimeout(main,0);}")
 # Independent authenticated renderer: if the legacy carousel engine fails, this
 # replaces each News section with real cards built from the same complete API
 # snapshot. It does not depend on public feeds or script execution order.
 c=re.sub(r'<!-- DY_AUTHENTICATED_NEWS_FALLBACK_START -->.*?<!-- DY_AUTHENTICATED_NEWS_FALLBACK_END -->','',c,flags=re.S)
 c+=news_static_fallback(items)
 css=START+'''<style>
#enhancedSite .kn-rowwrap{overflow:visible!important}#enhancedSite .kn-track{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:16px!important;transform:none!important;animation:none!important;max-width:none!important}#enhancedSite .kn-card{min-width:0!important;width:auto!important;min-height:360px!important}#enhancedSite .kn-cimg{aspect-ratio:16/9;max-height:none!important;overflow:hidden!important}#enhancedSite .kn-cimg img{display:block!important;width:100%!important;height:100%!important;max-width:none!important;margin:0!important;padding:0!important;object-fit:cover!important;object-position:center center!important;transform:none!important}@media(max-width:700px){#enhancedSite .kn-track{grid-template-columns:1fr!important;gap:12px!important}#enhancedSite .kn-card{padding:12px!important;min-height:340px!important}#enhancedSite .kn-ctitle{font-size:18px!important}.kn-cfoot{font-size:9px!important}}
</style>'''+END
 return marked(c,css)

def main():
 h=auth();posts=list_all('posts',h);pages=list_all('pages',h);article_page,cfg,categories=categories_from_article_page(pages)
 labels_fixed=0;images_fixed=0;used=set();hero_owner={}
 # Newest instance keeps an existing duplicated photo; older repeats receive a distinct Commons photo.
 for p in sorted(posts,key=lambda x:x.get('published',''),reverse=True):
  old=p.get('labels',[]);new=normalized_labels(p,categories)
  hero=clean_src((srcs(p.get('content','')) or [''])[0]);hero_key=image_key(hero);duplicate=bool(hero_key and hero_key in hero_owner);content=p.get('content','')
  if hero_key:used.add(hero_key)
  if duplicate:
   desk=next((x for x in new if x not in ('News','2026 Money Moves','Kushal K. Daga')),new[0]);pic=commons_photo(p.get('title',''),desk,used)
   if pic:content=replace_hero(content,pic);images_fixed+=1;hero_key=pic['base']
  if hero_key:hero_owner.setdefault(hero_key,p['id'])
  labels_changed={norm(x) for x in new}!={norm(x) for x in old}
  if labels_changed or content!=p.get('content',''):
   put('posts',p,h,content,new);p['labels']=new;p['content']=content;labels_fixed+=int(labels_changed);time.sleep(.08)
 pages_hygiene=0
 for page in pages:
  clean=page_hygiene(page.get('content',''),page.get('title','Daily Yield page'))
  if clean!=page.get('content',''):
   put('pages',page,h,clean);page['content']=clean;pages_hygiene+=1;time.sleep(.08)
 by_title={p['title'].strip().upper():p for p in pages}
 ap=by_title['DAILY ARTICLE'];np=by_title['DAILY NEWS']
 latest_article=next((p for p in sorted(posts,key=lambda x:x.get('published',''),reverse=True) if 'News' not in p.get('labels',[])),None)
 latest_news=next((p for p in sorted(posts,key=lambda x:x.get('published',''),reverse=True) if 'News' in p.get('labels',[])),None)
 article_current=bool(latest_article and latest_article.get('url','') in ap['content'] and ARTICLE_SCRATCH_MARK in ap['content'] and 'id="dyArticle"' in ap['content'] and 'id="articleHub"' not in ap['content'] and 'DAILY ARTICLE EXPERIENCE' not in ap['content'] and "row.scrollLeft+=72*dt" in ap['content'] and 'class="dya-hero"' in ap['content'] and 'class="dya-note"' in ap['content'] and ap['content'].count('class="dya-desk"')==len(categories) and all(('id="dya-'+str(c.get('number'))+'"') in ap['content'] for c in cfg.get('categories',[])))
 news_snapshot_at=np['content'].find('window.ENH_NEWS_SNAPSHOT=');news_engine_at=np['content'].find("var w=window,d=document,root=d.getElementById('enhancedSite');")
 news_current=bool(latest_news and latest_news.get('url','') in np['content'] and news_snapshot_at>=0 and news_engine_at>=0 and news_snapshot_at<news_engine_at and "w.ENH_NEWS_SNAPSHOT||[]" in np['content'] and "'/search/label/'+encodeURIComponent(l)" in np['content'] and 'var globalItems=byLabel(items,GLOBAL)' in np['content'] and 'public feed must not replace it with a partial batch' in np['content'] and 'var loop=false;' in np['content'] and "else{setTimeout(main,0);}" in np['content'] and 'DY_AUTHENTICATED_NEWS_FALLBACK_V6_OVERSIZED_LATEST_CARDS' in np['content'] and "function buildShelf(spec,kicker,forced)" in np['content'] and 'function buildOrderedShelves(regionAnchor,subjectAnchor)' in np['content'] and 'buildOrderedShelves(a,b)' in np['content'] and 'row.scrollLeft+=72*dt' in np['content'] and 'lostpointercapture' in np['content'] and START in np['content'])
 ac=ap['content'] if article_current else repair_article_page(ap,posts,cfg)
 nc=np['content'] if news_current else repair_news_page(np,posts)
 pages_fixed=pages_hygiene
 if ac!=ap['content']:put('pages',ap,h,ac);pages_fixed+=1
 if nc!=np['content']:put('pages',np,h,nc);pages_fixed+=1
 # Re-read and retry residual collisions. Blogger can normalize remote image URLs
 # after a PUT, so uniqueness must be assessed from authenticated stored content.
 unresolved_duplicates,dupes=repair_remaining_duplicate_heroes(h)
 # Authenticated verification; no public URL requests.
 verified=list_all('posts',h)
 # A compact exact-image index lets the Theme render Homepage and label cards
 # from summary feeds instead of downloading hundreds of kilobytes of Post bodies.
 def indexed_images(post):
  urls=srcs(post.get('content',''))
  primary=urls[0] if urls else ''
  # Keep the exact opening photograph. If its external host rate-limits a card,
  # recover with another existing editorial photo from that same Post.
  fallback=next((u for u in urls[1:] if u!=primary and not re.search(r'https?://(?:thumb|upload)\.wikimedia\.org/',u,re.I)),'')
  return primary,fallback
 pairs={p['id']:indexed_images(p) for p in verified}
 images={pid:pair[0] for pid,pair in pairs.items()};fallbacks={pid:pair[1] for pid,pair in pairs.items()}
 LABEL_INDEX.write_text(json.dumps({'version':4,'generated_at':datetime.now(timezone.utc).isoformat(),'images':images,'fallbacks':fallbacks},ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
 # Fail closed if even one canonical Article or Global News shelf would be empty.
 category_counts={cat:sum(any(norm(x)==norm(cat) for x in p.get('labels',[])) for p in posts if 'News' not in p.get('labels',[])) for cat in categories}
 news_counts={desk:sum(desk in p.get('labels',[]) for p in posts if 'News' in p.get('labels',[])) for desk in NEWS_LABELS}
 critical_ok=all(category_counts.values()) and news_counts.get('Global Finance News',0)>0
 status='PASS' if critical_ok and dupes==0 else ('WARNING' if critical_ok else 'FAIL')
 report={'status':status,'zero_view':True,'posts_checked':len(posts),'labels_normalized':labels_fixed,'duplicate_heroes_replaced':images_fixed,'remaining_duplicate_heroes':dupes,'unresolved_duplicate_groups':unresolved_duplicates,'pages_repaired':pages_fixed,'article_snapshot_entries':sum('News' not in p.get('labels',[]) for p in posts),'news_snapshot_entries':sum('News' in p.get('labels',[]) for p in posts),'label_image_index_entries':sum(bool(x) for x in images.values()),'article_category_counts':category_counts,'news_desk_counts':news_counts}
 REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
 # A residual image-source limitation is recorded as a warning, not reported as
 # a failed workflow. Missing canonical shelves remains a genuine hard failure.
 if status=='FAIL':raise RuntimeError('Content inventory has an empty article category or missing Global News desk')
if __name__=='__main__':
 try:main()
 except Exception as exc:
  prior={}
  try:prior=json.loads(REPORT.read_text())
  except Exception:pass
  prior.update({'status':'FAIL','zero_view':True,'error_type':type(exc).__name__,'error':str(exc)[:500]})
  REPORT.write_text(json.dumps(prior,indent=2),encoding='utf-8')
  raise
