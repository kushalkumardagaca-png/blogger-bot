#!/usr/bin/env python3
"""Repair Daily Yield labels, duplicate hero photography and Page feed rendering.

Uses authenticated Blogger API inventory only; it never opens, prefetches or renders a
public Daily Yield URL and therefore creates no synthetic pageviews.
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
  desk=next((x for x in old if x in NEWS_LABELS),None)
  if not desk:
   title=post.get('title','').lower();desk=next((x for x in NEWS_LABELS if x.lower() in title),None)
  if not desk:raise RuntimeError('News desk label missing for '+post.get('title',''))
  return ['News',desk]
 cat=category_for(post,categories);return [cat,'Kushal K. Daga']

def commons_photo(title,desk,used):
 country={'UK':'United Kingdom','US':'United States','Global News':'world financial district','Market and Trading':'stock market trading','Economy and Macro Policy':'economy central bank','Corporate Finance and Industry':'business industry','Personal Finance':'personal finance money'}
 cleaned=re.sub(r'\b(?:finance|news|20\d\d|september|october|november|december|january|february|march|april|may|june|july|august)\b|[—–-]|\d+',' ',title,flags=re.I)
 words=' '.join(re.findall(r"[A-Za-z£$']+",cleaned)[:5])
 queries=[(country.get(desk,desk)+' city business').strip(),(words+' '+country.get(desk,desk)).strip(),country.get(desk,desk)+' economy']
 for query in queries:
  params={'action':'query','format':'json','generator':'search','gsrnamespace':'6','gsrlimit':'50','gsrsearch':query,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':'1200','origin':'*'}
  try:
   r=requests.get(COMMONS,params=params,headers={'User-Agent':'DailyYieldEditorialRepair/1.0 (dailyyield.official@gmail.com)'},timeout=45);r.raise_for_status()
  except requests.RequestException:
   continue
  pages=(r.json().get('query') or {}).get('pages',{})
  for page in pages.values():
   info=(page.get('imageinfo') or [{}])[0];meta=info.get('extmetadata') or {};url=info.get('thumburl') or info.get('url') or '';base=image_key(info.get('descriptionurl') or info.get('url') or '')
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

def article_design_v7():
 return START+"""<style>
/* DAILY ARTICLE EXPERIENCE V7 — left-aligned desks, uninterrupted gesture-aware rows */
#articleHub{--ar-ink:#241610;--ar-accent:#bc5b33;--ar-deep:#9c4522;--ar-line:#e3d3b3;--ar-paper:#fffdf8;--ar-cream:#f8f0e3;color:var(--ar-ink);animation:arIn .9s cubic-bezier(.22,.7,.3,1) both}@keyframes arIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
#articleHub .ar-hero{display:grid!important;grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr)!important;gap:clamp(14px,3vw,40px)!important;align-items:center;margin:0 0 18px!important;padding:clamp(22px,3vw,38px) clamp(14px,2vw,28px)!important;overflow:visible!important;border:1px solid #e3ccb0!important;border-radius:8px 24px 8px 24px!important;background:linear-gradient(180deg,rgba(246,227,211,.8),rgba(248,240,227,0))!important;box-shadow:none!important;isolation:isolate}
#articleHub .ar-copy{min-width:0;width:100%;padding:0;text-align:left}#articleHub .ar-kicker{display:inline-block;padding:7px 13px!important;border:1px dashed var(--ar-accent)!important;border-radius:4px;background:#fbf1e5;color:var(--ar-accent)!important;font-size:10px!important;letter-spacing:.18em!important;animation:arStamp .8s cubic-bezier(.34,1.56,.64,1) both .15s}@keyframes arStamp{from{opacity:0;transform:rotate(-4deg) scale(.9)}to{opacity:1;transform:none}}
#articleHub .ar-h1{margin:18px 0 12px!important;color:var(--ar-ink)!important;font-size:clamp(30px,4.6vw,54px)!important;line-height:1.12!important;letter-spacing:-.025em!important;animation:arRise .9s cubic-bezier(.22,.7,.3,1) both .2s}@keyframes arRise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}#articleHub .ar-word{display:inline-block;color:var(--ar-accent)!important;border-bottom:3px solid rgba(188,91,51,.35);transition:opacity .45s ease,transform .45s ease}#articleHub .ar-word.ar-out{opacity:0;transform:translateY(10px)}#articleHub .ar-lede{max-width:none!important;margin:12px 0 0!important;color:#4a4036!important;font-size:14px!important;line-height:1.75!important}#articleHub .ar-hero-tags{justify-content:flex-start!important;gap:6px!important;margin-top:18px!important}#articleHub .ar-hero-tags span{padding:4px 9px!important;border:1px solid var(--ar-line)!important;border-radius:999px!important;background:#fbf6ec!important;color:#6e5d4b!important;font-size:9px!important;text-transform:uppercase}
#articleHub .ar-note{width:100%;max-width:370px;min-width:0;justify-self:end;position:relative;padding:15px 15px 12px!important;border:1px solid #eadcc8!important;border-radius:19px!important;background:var(--ar-paper)!important;box-shadow:0 20px 38px -26px rgba(36,22,16,.4)!important;transform:rotate(.5deg);transition:transform .5s cubic-bezier(.19,1,.22,1)}#articleHub .ar-note:hover{transform:translateY(-4px) rotate(-.35deg)}#articleHub .ar-note:before{content:"";position:absolute;z-index:2;left:50%;top:-10px;width:78px;height:20px;background:rgba(188,91,51,.22);border-left:2px dashed rgba(255,253,248,.75);border-right:2px dashed rgba(255,253,248,.75);transform:translateX(-50%) rotate(-3deg)}
#articleHub .ar-note-sheet{min-height:250px;padding:16px 13px 12px!important;overflow:hidden;border:1px solid #eadcc8!important;border-radius:12px!important;background:var(--ar-cream)!important;animation:arNoteIn .55s cubic-bezier(.22,.61,.36,1) both}@keyframes arNoteIn{from{opacity:0;transform:translateX(12px)}to{opacity:1;transform:none}}#articleHub .ar-hand{margin:0 0 9px!important;color:var(--ar-deep)!important;font-size:21px!important;line-height:1.15!important}#articleHub .ar-note-row{gap:9px!important;padding:8px 0!important;border-bottom:1px dashed rgba(156,69,34,.16)!important;color:var(--ar-ink)!important;font-size:11.5px!important;line-height:1.45!important}#articleHub .ar-note-row b{max-width:46%;color:var(--ar-deep)!important;font-size:10px!important;text-align:right}#articleHub .ar-note-controls{display:flex!important;gap:5px;margin:12px 2px 4px!important}#articleHub .ar-note-controls button{display:block!important;flex:1;height:3px!important;padding:0!important;border:0!important;border-radius:99px;background:#eadcc8!important}#articleHub .ar-note-controls button[aria-pressed=true]{background:var(--ar-accent)!important}#articleHub .ar-note-end{margin:8px 2px 0!important;color:#7a6854!important;font-size:10.5px!important;line-height:1.5!important}
#articleHub .ar-toolbar,#articleHub .ar-directory{border-color:#ddc8ac!important;background:#fbf6ec!important}#articleHub .ar-section{position:relative;margin-top:clamp(28px,4vw,42px)!important;padding:28px 0 36px!important;border-top:1px solid #eadcc8!important;content-visibility:auto;contain-intrinsic-size:1px 470px;text-align:left!important}#articleHub .ar-heading{align-items:flex-end!important;text-align:left!important}#articleHub .ar-heading-copy{display:block!important;width:auto!important;margin:0!important;text-align:left!important}#articleHub .ar-eyebrow{color:var(--ar-accent)!important;font-size:10.5px!important;letter-spacing:.24em!important}#articleHub .ar-heading h2{position:relative;display:inline-block;margin:0!important;color:var(--ar-ink)!important;font-size:clamp(24px,3.6vw,36px)!important;line-height:1.05!important;letter-spacing:-.015em!important;text-align:left!important}#articleHub .ar-heading h2:after{content:"";position:absolute;left:0;bottom:-7px;width:54px;height:3px;border-radius:3px;background:var(--ar-accent);transform-origin:left;animation:arUnder 1.2s cubic-bezier(.22,.7,.3,1) both .3s}@keyframes arUnder{from{transform:scaleX(0)}to{transform:scaleX(1)}}#articleHub .ar-description{max-width:780px;margin:14px 0 0!important;color:#6e5d4b!important;font-size:14px!important;line-height:1.65!important;text-align:left!important}
#articleHub .ar-more{border:1px solid var(--ar-line)!important;border-radius:999px!important;background:#fbf6ec!important;color:var(--ar-accent)!important;transition:transform .25s,background .25s!important}#articleHub .ar-more:hover{background:var(--ar-accent)!important;color:var(--ar-paper)!important;transform:translateY(-1px)}#articleHub .ar-rowtools{display:flex!important;align-items:center;justify-content:flex-end;gap:7px;margin:6px 0 10px}#articleHub .ar-rowtools[hidden]{display:none!important}#articleHub .ar-rowcount{margin-right:auto;color:#8c7a66;font-size:9px!important;letter-spacing:.12em;text-transform:uppercase}#articleHub .ar-rowtools button{display:grid;width:34px;height:34px;place-items:center;border:1px solid var(--ar-line);border-radius:50%;background:#fbf6ec;color:var(--ar-deep);cursor:pointer}
#articleHub .ar-viewport{display:block;max-width:100%;overflow-x:auto!important;overflow-y:hidden!important;overscroll-behavior-inline:contain;scroll-snap-type:x proximity;scrollbar-width:none;cursor:grab;touch-action:pan-y;border-radius:14px;mask-image:linear-gradient(90deg,transparent,#000 18px,#000 calc(100% - 18px),transparent)}#articleHub .ar-viewport::-webkit-scrollbar{display:none}#articleHub .ar-viewport:active{cursor:grabbing}#articleHub .ar-track{display:flex!important;flex-wrap:nowrap!important;gap:0!important;width:max-content!important;max-width:none!important;transform:none!important}#articleHub .ar-group{display:flex!important;flex:0 0 auto!important;gap:14px!important;width:auto!important;max-width:none!important;padding:4px 14px 4px 2px!important}#articleHub .ar-duplicate,#articleHub .ar-duplicate[hidden]{display:flex!important}
#articleHub .ar-card{--mx:50%;--my:50%;flex:0 0 clamp(250px,28vw,300px)!important;width:clamp(250px,28vw,300px)!important;min-width:250px!important;overflow:hidden;border:1px solid #eadcc8!important;border-radius:14px!important;background:var(--ar-paper)!important;scroll-snap-align:start;box-shadow:0 6px 18px -14px rgba(36,22,16,.35);transition:transform .25s,box-shadow .25s,border-color .25s;animation:arCardIn .7s cubic-bezier(.22,.7,.3,1) both}@keyframes arCardIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}#articleHub .ar-card:hover{transform:translateY(-3px) rotate(-.3deg);border-color:var(--ar-accent)!important;box-shadow:0 18px 36px -18px rgba(188,91,51,.35)}#articleHub .ar-card:before{content:"";position:absolute;inset:0;z-index:2;pointer-events:none;background:radial-gradient(220px circle at var(--mx) var(--my),rgba(188,91,51,.10),transparent 60%);opacity:0;transition:opacity .3s}#articleHub .ar-card:hover:before{opacity:1}#articleHub .ar-card:after{content:"";position:absolute;z-index:2;top:0;left:-75%;width:50%;height:100%;pointer-events:none;background:linear-gradient(105deg,transparent 40%,rgba(255,255,255,.45) 50%,transparent 60%);transform:skewX(-15deg);animation:arShine 5.5s ease-in-out infinite}@keyframes arShine{0%,70%{left:-75%}85%,100%{left:130%}}#articleHub .ar-image{aspect-ratio:16/9;overflow:hidden;background:#ecd7b9}#articleHub .ar-image img{width:100%;height:100%;object-fit:cover}#articleHub .ar-card-body{padding:15px!important}#articleHub .ar-card h3{font-size:16.5px!important;line-height:1.25!important}#articleHub .ar-card:hover h3{color:var(--ar-accent)!important}
@media(max-width:760px){#articleHub .ar-hero{grid-template-columns:1fr!important;gap:18px!important;border-radius:6px 18px 6px 18px!important;padding:22px 14px!important}#articleHub .ar-note{max-width:100%;justify-self:stretch;transform:none}#articleHub .ar-h1{font-size:clamp(28px,8vw,40px)!important}#articleHub .ar-card{flex-basis:78vw!important;width:78vw!important;min-width:250px!important}#articleHub .ar-section{padding-block:25px}#articleHub .ar-heading{align-items:flex-start!important}#articleHub .ar-more{white-space:nowrap}}
@media(prefers-reduced-motion:reduce){#articleHub *,#articleHub *:before,#articleHub *:after{animation:none!important;transition:none!important}}
</style><script>(function(w,d){var root=d.getElementById('articleHub');if(!root||root.dataset.arNewsGrammar)return;root.dataset.arNewsGrammar='7';var word=d.getElementById('ar-word'),words=['answers.','context.','choices.','questions.'],wi=0,reduce=w.matchMedia&&w.matchMedia('(prefers-reduced-motion: reduce)').matches;if(word&&!reduce)setInterval(function(){word.classList.add('ar-out');setTimeout(function(){wi=(wi+1)%words.length;word.textContent=words[wi];word.classList.remove('ar-out')},450)},3200);root.addEventListener('pointermove',function(e){var c=e.target.closest&&e.target.closest('.ar-card');if(!c)return;var r=c.getBoundingClientRect();c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')});})(window,document);</script>"""+END

def repair_article_page(page,posts,cfg):
 eligible=sorted((p for p in posts if 'News' not in p.get('labels',[])),key=lambda x:x.get('published',''),reverse=True)
 cfg['preview']=False;cfg['snapshotEntries']=[entry(p) for p in eligible]
 c=page['content'];pat=r'(<script[^>]+id=["\']ar-config["\'][^>]*>).*?(</script>)';c,n=re.subn(pat,lambda m:m.group(1)+json.dumps(cfg,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+m.group(2),c,count=1,flags=re.I|re.S)
 if n!=1:raise RuntimeError('Unable to update article snapshot')
 c=c.replace("function inCategory(post,cat){return post.labels.indexOf(cat.label)!==-1;}", "function inCategory(post,cat){return post.labels.some(function(label){return norm(label)===norm(cat.label);});}")
 c=c.replace("function labelURL(cat){var query=cat?'label:\"'+cat.label+'\" -label:News':'-label:News';return cfg.blog+'/search?q='+encodeURIComponent(query)+'&max-results=20';}", "function labelURL(cat){return cat?cfg.blog+'/search/label/'+encodeURIComponent(cat.label)+'?max-results=20':cfg.blog+'/search?max-results=20';}")
 c=c.replace("var thisRun=++runId;records=[];failed=false;loading=true;finished=false;retry.hidden=true;render();status.textContent='Reading the published article feed\\u2026';", "var thisRun=++runId;records=[];failed=false;loading=true;finished=false;retry.hidden=true;status.textContent='Refreshing the published article index\\u2026';")
 old="if(preview){records=(cfg.snapshotEntries||[]).map(parseEntry).filter(Boolean);finished=true;render();status.textContent=records.length?'Published-post snapshot \\u00b7 article cards link directly to the full posts':'No published non-news articles were available in the public feed at the last check';}\nelse load();"
 new="records=(cfg.snapshotEntries||[]).map(parseEntry).filter(Boolean);finished=true;render();status.textContent=records.length?'Archive ready \\u00b7 newest articles first \\u00b7 News excluded':'No non-news articles published yet';\nif(!preview)setTimeout(load,80);"
 if old in c:c=c.replace(old,new)
 c=c.replace("if(!preview)setTimeout(load,80);", "/* Authenticated snapshot is complete; no slower public-feed replacement. */")
 c=c.replace("setInterval(function(){if(!document.hidden&&!loading)load();},600000);", "/* Snapshot refresh is deployed by the authenticated two-hour repair workflow. */")
 c=re.sub(r'<p[^>]*>\s*<strong>Welcome to the Daily Article\.</strong>.*?The news stays in the Daily News\.</p>','',c,count=1,flags=re.I|re.S)
 # The Daily News hero establishes the publication pattern: editorial copy on
 # the left and one rotating, taped reference card on the right. Remove the
 # unrelated featured-photo card from V5 and retain the Article-specific note
 # deck in that complementary position.
 c=re.sub(r'<!-- DY_ARTICLE_FEATURE_START -->.*?<!-- DY_ARTICLE_FEATURE_END -->','',c,flags=re.S)
 if not eligible:raise RuntimeError('Daily Article has no eligible non-News posts')
 c=c.replace('<em>answers.</em>','<em class="ar-word" id="ar-word">answers.</em>')
 # Restore the intended Daily Yield editorial destination and a genuinely
 # continuous carousel. Every desk has 2–4 cards, so the old width guard hid
 # the duplicate loop whenever one group fitted the viewport and stopped motion.
 c=c.replace('requestAnimationFrame(function(){try{if(group.getBoundingClientRect().width<=viewport.clientWidth+1)duplicate.hidden=true;}catch(e){}});','requestAnimationFrame(function(){duplicate.hidden=false;});')
 old_tick="if(!s.visible)return;var w=s.group.getBoundingClientRect().width;if(w<=s.viewport.clientWidth+1){s.duplicate.hidden=true;return;}s.duplicate.hidden=false;s.carry=(s.carry||0)+dt*24;"
 new_tick="if(!s.visible||s.active||Date.now()<s.touchUntil)return;var w=s.group.getBoundingClientRect().width;if(w<=0)return;s.duplicate.hidden=false;s.carry=(s.carry||0)+dt*58;"
 c=c.replace(old_tick,new_tick)
 # Upgrade every prior repair version. Hover and passive pointer presence must
 # never stop the row; only an active drag/wheel gesture may suspend motion.
 for prior in [
  'if(!s.visible)return;var w=s.group.getBoundingClientRect().width;if(w<=s.viewport.clientWidth+1){s.duplicate.hidden=true;return;}s.duplicate.hidden=false;s.carry=(s.carry||0)+dt*52;',
  'if(!s.visible||s.hover||s.focus||Date.now()<s.touchUntil)return;var w=s.group.getBoundingClientRect().width;if(w<=0)return;s.duplicate.hidden=false;s.carry=(s.carry||0)+dt*58;']:
  c=c.replace(prior,new_tick)
 c=c.replace('hover:false,focus:false,touchUntil:0,visible:', 'hover:false,focus:false,active:false,touchUntil:0,visible:')
 old_events="viewport.addEventListener('pointerdown',function(){if(viewport._arState)viewport._arState.touchUntil=Date.now()+8000;},{passive:true});\n viewport.addEventListener('wheel',function(){if(viewport._arState)viewport._arState.touchUntil=Date.now()+5000;},{passive:true});"
 new_events="viewport.addEventListener('pointerdown',function(){if(viewport._arState){viewport._arState.active=true;viewport._arState.touchUntil=0;}},{passive:true});\n function arRelease(){if(viewport._arState){viewport._arState.active=false;viewport._arState.touchUntil=Date.now()+32;}}\n viewport.addEventListener('pointerup',arRelease);viewport.addEventListener('pointercancel',arRelease);viewport.addEventListener('lostpointercapture',arRelease);window.addEventListener('blur',arRelease);\n viewport.addEventListener('wheel',function(){if(viewport._arState)viewport._arState.touchUntil=Date.now()+48;},{passive:true});"
 c=c.replace(old_events,new_events)
 c=c.replace('v._arState.touchUntil=Date.now()+10000;', 'v._arState.touchUntil=Date.now()+180;')
 c=c.replace("im.alt='';im.loading='lazy'", "im.alt=post.title+' — Daily Yield article photograph';im.loading='lazy'")
 css=article_design_v7()
 return marked(c,css)

def news_item(post):
 labels=post.get('labels',[]);desk=next((x for x in labels if x!='News'),'Global News');flags={'US':'🇺🇸','China':'🇨🇳','Germany':'🇩🇪','India':'🇮🇳','Japan':'🇯🇵','UK':'🇬🇧','France':'🇫🇷','Italy':'🇮🇹','Russia':'🇷🇺','Canada':'🇨🇦','Brazil':'🇧🇷','Spain':'🇪🇸','Mexico':'🇲🇽','Australia':'🇦🇺','South Korea':'🇰🇷'}
 return {'title':post['title'],'labels':labels,'flag':flags.get(desk,'🌐'),'published':post.get('published',''),'link':post.get('url',''),'img':(srcs(post.get('content','')) or [''])[0]}

def news_static_fallback(items):
 payload=json.dumps(items,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
 countries=[('US','🇺🇸','United States'),('China','🇨🇳','China'),('Germany','🇩🇪','Germany'),('India','🇮🇳','India'),('Japan','🇯🇵','Japan'),('UK','🇬🇧','United Kingdom'),('France','🇫🇷','France'),('Italy','🇮🇹','Italy'),('Russia','🇷🇺','Russia'),('Canada','🇨🇦','Canada'),('Brazil','🇧🇷','Brazil'),('Spain','🇪🇸','Spain'),('Mexico','🇲🇽','Mexico'),('Australia','🇦🇺','Australia'),('South Korea','🇰🇷','South Korea')]
 specialties=[('Market and Trading','📈','Market & Trading'),('Economy and Macro Policy','🏦','Economy & Macro Policy'),('Corporate Finance and Industry','🏭','Corporate Finance & Industry'),('Personal Finance','💰','Personal Finance')]
 desks=json.dumps({'countries':countries,'specialties':specialties},ensure_ascii=False,separators=(',',':'))
 return '''<!-- DY_AUTHENTICATED_NEWS_FALLBACK_START --><style>/* DY_AUTHENTICATED_NEWS_FALLBACK_V3 */
.dy-auth-news{padding:10px 0 30px}.dy-auth-news-kicker{color:#a34d2c;font:700 9px/1.4 sans-serif;letter-spacing:.22em;text-transform:uppercase}.dy-auth-news-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 24px}.dy-auth-news-top h2{font-size:clamp(28px,5vw,44px)}.dy-auth-news-all,.dy-auth-news-more{border:1px solid #dfcdb9;border-radius:999px;padding:9px 14px;color:#9d4a2b;font:700 10px/1 sans-serif;white-space:nowrap}.dy-auth-desk{padding:18px 0 26px;border-top:1px solid #eadcca}.dy-auth-desk-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.dy-auth-desk h3{font-size:22px}.dy-auth-row{display:flex;gap:10px;overflow-x:auto;overscroll-behavior-inline:contain;scrollbar-width:none;cursor:grab;touch-action:pan-y}.dy-auth-row::-webkit-scrollbar{display:none}.dy-auth-row.dy-dragging{cursor:grabbing;user-select:none}.dy-auth-card{display:block;flex:0 0 calc((100% - 30px)/4);min-width:0;overflow:hidden;border:1px solid #eadcca;border-radius:12px;background:#fffdf8}.dy-auth-img{aspect-ratio:16/9;background:#f5e5cd;display:grid;place-items:center;color:#b36a41;font:700 28px Georgia,serif;overflow:hidden}.dy-auth-img img{width:100%;height:100%;object-fit:cover}.dy-auth-body{padding:11px}.dy-auth-body b{display:block;font:600 15px/1.25 Georgia,serif}.dy-auth-body small{display:block;margin-top:7px;color:#857261;font:700 9px/1.3 sans-serif}@media(max-width:700px){.dy-auth-row{gap:7px}.dy-auth-card{flex-basis:78%}.dy-auth-desk h3{font-size:19px}.dy-auth-body{padding:9px}.dy-auth-body b{font-size:13px}}
</style><script>(function(w,d){var items='''+payload+''',desks='''+desks+''';function findTitle(name){var hs=d.querySelectorAll('h1,h2,h3,h4');for(var i=0;i<hs.length;i++){if((hs[i].textContent||'').trim()===name)return hs[i];}return null;}function link(label){return '/search/label/'+encodeURIComponent(label)+'?max-results=50';}function makeCard(it){var a=d.createElement('a');a.className='dy-auth-card';a.href=it.link;var pic=d.createElement('div');pic.className='dy-auth-img';if(it.img){var im=d.createElement('img');im.src=it.img;im.alt=it.title||'Daily Yield news photograph';im.loading='lazy';pic.appendChild(im);}else pic.textContent=(it.title||'N').charAt(0);var body=d.createElement('div');body.className='dy-auth-body';var b=d.createElement('b');b.textContent=it.title;var sm=d.createElement('small');sm.textContent=(it.published||'').slice(0,10);body.appendChild(b);body.appendChild(sm);a.appendChild(pic);a.appendChild(body);return a;}function globalTitle(){var hs=d.querySelectorAll('h1,h2,h3,h4');for(var i=0;i<hs.length;i++){var t=(hs[i].textContent||'').trim().toLowerCase();if(t.indexOf('global')>=0&&(t.indexOf('news')>=0||t.indexOf('dispatch')>=0||t.indexOf('wire')>=0))return hs[i];}return null;}function wire(row){var originals=[].slice.call(row.children);if(!originals.length)return;originals.forEach(function(n){var c=n.cloneNode(true);c.setAttribute('aria-hidden','true');c.tabIndex=-1;row.appendChild(c);});var half=0,pausedUntil=0,last=0,drag=null,moved=false,hover=false;function measure(){half=row.scrollWidth/2;}requestAnimationFrame(measure);function delay(ms){pausedUntil=Date.now()+ms;}row.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.button!==0)return;drag={x:e.clientX,left:row.scrollLeft,id:e.pointerId};moved=false;pausedUntil=0;row.classList.add('dy-dragging');try{row.setPointerCapture(e.pointerId);}catch(_e){}});row.addEventListener('pointermove',function(e){if(!drag)return;var dx=e.clientX-drag.x;if(Math.abs(dx)>6)moved=true;row.scrollLeft=drag.left-dx;e.preventDefault();});function end(e){if(!drag)return;var id=drag.id;drag=null;row.classList.remove('dy-dragging');try{if(row.hasPointerCapture(id))row.releasePointerCapture(id);}catch(_e){}delay(180);}row.addEventListener('pointerup',end);row.addEventListener('pointercancel',end);row.addEventListener('lostpointercapture',end);w.addEventListener('blur',end);row.addEventListener('wheel',function(){delay(900);},{passive:true});row.addEventListener('pointerenter',function(e){if(e.pointerType==='mouse')hover=true;});row.addEventListener('pointerleave',function(e){if(e.pointerType==='mouse'){hover=false;delay(250);}});row.addEventListener('click',function(e){if(moved){e.preventDefault();e.stopPropagation();moved=false;}},true);function tick(ts){if(!last)last=ts;var dt=Math.min(.05,(ts-last)/1000);last=ts;if(!drag&&!hover&&Date.now()>pausedUntil&&!d.hidden&&half>0){row.scrollLeft+=72*dt;if(row.scrollLeft>=half)row.scrollLeft-=half;}requestAnimationFrame(tick);}requestAnimationFrame(tick);}function rebuild(title,kicker,list,forced){var h=forced||findTitle(title);if(!h)return null;var sec=h.closest('section')||h.parentElement;if(!sec)return null;sec.innerHTML='';sec.className=(sec.className||'')+' dy-auth-news';var k=d.createElement('p');k.className='dy-auth-news-kicker';k.textContent=kicker;var top=d.createElement('div');top.className='dy-auth-news-top';var hd=d.createElement('h2');hd.textContent=title;var all=d.createElement('a');all.className='dy-auth-news-all';all.href=link('News');all.textContent='All dispatches →';top.appendChild(hd);top.appendChild(all);sec.appendChild(k);sec.appendChild(top);list.forEach(function(spec){var label=spec[0],flag=spec[1],shown=spec[2],found=items.filter(function(it){return (it.labels||[]).indexOf(label)>=0;});if(!found.length)return;var block=d.createElement('div');block.className='dy-auth-desk';var head=d.createElement('div');head.className='dy-auth-desk-head';var name=d.createElement('h3');name.textContent=flag+' '+shown;var more=d.createElement('a');more.className='dy-auth-news-more';more.href=link(label);more.textContent='Read '+shown+' →';head.appendChild(name);head.appendChild(more);var row=d.createElement('div');row.className='dy-auth-row';found.forEach(function(it){row.appendChild(makeCard(it));});wire(row);block.appendChild(head);block.appendChild(row);sec.appendChild(block);});return sec;}function boot(){var g=globalTitle(),a=findTitle('Country dispatches'),b=findTitle('Specialty desks');if(g)rebuild('Global News','THE WORLD IN ONE WIRE',[['Global News','🌐','Global News']],g);if(!a||!b)return;var sa=a.closest('section'),sb=b.closest('section');if(sa&&sb&&sa===sb)return;rebuild('Country dispatches','EVERY ECONOMY, ITS OWN WIRE',desks.countries);rebuild('Specialty desks','FOLLOW A THEME ACROSS EDITIONS',desks.specialties);}if(d.readyState==='loading')d.addEventListener('DOMContentLoaded',boot,{once:true});else setTimeout(boot,0);})(window,document);</script><!-- DY_AUTHENTICATED_NEWS_FALLBACK_END -->'''

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
#enhancedSite .kn-rowwrap{overflow:visible!important}#enhancedSite .kn-track{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important;transform:none!important;animation:none!important;max-width:none!important}#enhancedSite .kn-card{min-width:0!important;width:auto!important}#enhancedSite .kn-cimg{aspect-ratio:16/9;max-height:150px}#enhancedSite .kn-cimg img{width:100%;height:100%;object-fit:cover}@media(max-width:700px){#enhancedSite .kn-track{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important}#enhancedSite .kn-card{padding:9px!important}#enhancedSite .kn-ctitle{font-size:15px!important}.kn-cfoot{font-size:8px!important}}
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
 article_current=bool(latest_article and latest_article['id'] in ap['content'] and "norm(label)===norm(cat.label)" in ap['content'] and "/search/label/'+encodeURIComponent(cat.label)" in ap['content'] and 'Authenticated snapshot is complete' in ap['content'] and 'Welcome to the Daily Article.' not in ap['content'] and 'DAILY ARTICLE EXPERIENCE V7' in ap['content'] and 'DY_ARTICLE_FEATURE_START' not in ap['content'] and "arNewsGrammar='7'" in ap['content'] and 's.active' in ap['content'] and 'Date.now()+32' in ap['content'] and 'dt*58' in ap['content'] and 'duplicate.hidden=false' in ap['content'] and '#articleHub .ar-track{display:flex!important' in ap['content'] and '#articleHub .ar-group{display:grid!important' not in ap['content'] and 'img alt=' in ap['content'] and START in ap['content'])
 news_snapshot_at=np['content'].find('window.ENH_NEWS_SNAPSHOT=');news_engine_at=np['content'].find("var w=window,d=document,root=d.getElementById('enhancedSite');")
 news_current=bool(latest_news and latest_news.get('url','') in np['content'] and news_snapshot_at>=0 and news_engine_at>=0 and news_snapshot_at<news_engine_at and "w.ENH_NEWS_SNAPSHOT||[]" in np['content'] and "'/search/label/'+encodeURIComponent(l)" in np['content'] and 'var globalItems=byLabel(items,GLOBAL)' in np['content'] and 'public feed must not replace it with a partial batch' in np['content'] and 'var loop=false;' in np['content'] and "else{setTimeout(main,0);}" in np['content'] and 'DY_AUTHENTICATED_NEWS_FALLBACK_V3' in np['content'] and "rebuild('Global News'" in np['content'] and 'row.scrollLeft+=72*dt' in np['content'] and 'lostpointercapture' in np['content'] and START in np['content'])
 ac=ap['content'] if article_current else repair_article_page(ap,posts,cfg)
 nc=np['content'] if news_current else repair_news_page(np,posts)
 pages_fixed=pages_hygiene
 if ac!=ap['content']:put('pages',ap,h,ac);pages_fixed+=1
 if nc!=np['content']:put('pages',np,h,nc);pages_fixed+=1
 # Authenticated verification; no public URL requests.
 verified=list_all('posts',h);heroes=[image_key((srcs(p.get('content','')) or [''])[0]) for p in verified];heroes=[x for x in heroes if x];dupes=len(heroes)-len(set(heroes))
 # Fail closed if even one canonical Article or Global News shelf would be empty.
 category_counts={cat:sum(any(norm(x)==norm(cat) for x in p.get('labels',[])) for p in posts if 'News' not in p.get('labels',[])) for cat in categories}
 news_counts={desk:sum(desk in p.get('labels',[]) for p in posts if 'News' in p.get('labels',[])) for desk in NEWS_LABELS}
 report={'status':'PASS' if dupes==0 and all(category_counts.values()) and news_counts.get('Global News',0)>0 else 'PARTIAL','zero_view':True,'posts_checked':len(posts),'labels_normalized':labels_fixed,'duplicate_heroes_replaced':images_fixed,'remaining_duplicate_heroes':dupes,'pages_repaired':pages_fixed,'article_snapshot_entries':sum('News' not in p.get('labels',[]) for p in posts),'news_snapshot_entries':sum('News' in p.get('labels',[]) for p in posts),'article_category_counts':category_counts,'news_desk_counts':news_counts}
 REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
 if report['status']!='PASS':raise RuntimeError('Content inventory still has an empty article category, missing Global News desk, or duplicate hero assignment')
if __name__=='__main__':
 try:main()
 except Exception as exc:
  prior={}
  try:prior=json.loads(REPORT.read_text())
  except Exception:pass
  prior.update({'status':'FAIL','zero_view':True,'error_type':type(exc).__name__,'error':str(exc)[:500]})
  REPORT.write_text(json.dumps(prior,indent=2),encoding='utf-8')
  raise
