#!/usr/bin/env python3
"""Licence-safe, placement-aware, globally non-repeating editorial photography."""
from __future__ import annotations
import hashlib,html,json,re,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
import imagehash,requests
from PIL import Image,ImageStat
from io import BytesIO
ROOT=Path(__file__).parent;REGISTRY=ROOT/'PHOTO_USAGE_REGISTRY.json';UA='DailyYieldPhotoEditor/1.0 (dailyyield.official@gmail.com)'
ALLOW=('cc0','public domain','cc by 2.0','cc by 2.5','cc by 3.0','cc by 4.0')
STOP={'the','and','with','from','into','that','this','photo','photograph','editorial','landscape','horizontal','realistic','without','showing','financial','finance','opening','context','article','subject','mid','later','mechanism','evidence','implications','decisions','stop','maxing'}
def clean(v):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(v or '')))).strip()
def load_registry():
 if REGISTRY.exists():return json.loads(REGISTRY.read_text())
 return {'version':1,'baseline_complete':False,'items':[]}
def save_registry(r):REGISTRY.write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
def terms(text):return [x for x in re.findall(r'[a-z0-9]{3,}',str(text).casefold()) if x not in STOP][:14]
def commons_candidates(brief):
 tokens=terms(brief);queries=[' '.join(tokens[:3])]+tokens[:6]
 text=str(brief).casefold();lexicons=((('retirement','pension','401','ira'),('retirement','older couple','financial planning','workplace meeting')),(('housing','mortgage','property','real estate'),('residential houses','home buying','apartment buildings')),(('career','salary','job','workplace'),('office workers','workplace meeting','professional working')),(('invest','stock','market','portfolio'),('stock exchange','financial district','business analysis')),(('saving','budget','debt','credit'),('household budgeting','savings','payment card')),(('tax','government','regulation'),('government office','tax forms','parliament building')))
 for keys,extra in lexicons:
  if any(k in text for k in keys):queries.extend(extra)
 pages={}
 for q in dict.fromkeys(x for x in queries if x.strip()):
  params={'action':'query','format':'json','generator':'search','gsrnamespace':6,'gsrlimit':25,'gsrsearch':q,'prop':'imageinfo','iiprop':'url|size|extmetadata','iiurlwidth':1600}
  try:
   r=requests.get('https://commons.wikimedia.org/w/api.php',params=params,headers={'User-Agent':UA},timeout=60);r.raise_for_status();pages.update(r.json().get('query',{}).get('pages',{}))
  except Exception:continue
 out=[]
 for p in pages.values():
  info=(p.get('imageinfo') or [{}])[0];m=info.get('extmetadata') or {};val=lambda k:clean((m.get(k) or {}).get('value',''))
  license_name=val('LicenseShortName') or val('UsageTerms');license_url=val('LicenseUrl');desc=val('ImageDescription');artist=val('Artist') or info.get('user','Unknown creator')
  combined=(license_name+' '+license_url).casefold()
  if not any(x in combined for x in ALLOW):continue
  if any(x in combined for x in ('noncommercial','no derivatives','gfdl')):continue
  w=int(info.get('width') or 0);h=int(info.get('height') or 0)
  if w<1400 or h<700 or w/h<1.35:continue
  out.append({'source_id':'commons:'+str(p.get('pageid')),'title':clean(p.get('title','').replace('File:','')),'description':desc,'creator':artist,'license':license_name,'license_url':license_url,'source_page':info.get('descriptionurl'),'download_url':info.get('thumburl') or info.get('url'),'original_url':info.get('url'),'width':w,'height':h})
 return out
def distance(a,b):
 try:return imagehash.hex_to_hash(a)-imagehash.hex_to_hash(b)
 except Exception:return 999
def choose_photos(briefs,slug,article_key):
 if len(briefs)!=3:raise RuntimeError('exactly three placement-specific photo briefs required')
 registry=load_registry()
 if not registry.get('baseline_complete'):raise RuntimeError('global photo baseline is not complete')
 used_ids={x.get('source_id') for x in registry['items']};used_urls={x.get('original_url') or x.get('url') for x in registry['items']};used_hashes={x.get('sha256') for x in registry['items']};used_phashes=[x.get('phash') for x in registry['items'] if x.get('phash')]
 folder=ROOT/'assets'/'master'/slug;folder.mkdir(parents=True,exist_ok=True);selected=[]
 for placement,brief in enumerate(briefs,1):
  candidates=commons_candidates(brief);bt=set(terms(brief));ranked=[]
  for c in candidates:
   if c['source_id'] in used_ids or c['original_url'] in used_urls:continue
   text=(c['title']+' '+c['description']).casefold();overlap=len(bt&set(terms(text)));ratio=c['width']/c['height'];crop_penalty=abs(ratio-16/9)
   ranked.append((overlap*20+min(c['width'],5000)/500-crop_penalty*5,c))
  ranked.sort(key=lambda x:x[0],reverse=True);winner=None
  for semantic,c in ranked[:12]:
   try:
    rr=requests.get(c['download_url'],headers={'User-Agent':UA},timeout=35);rr.raise_for_status();raw=rr.content
    image=Image.open(BytesIO(raw)).convert('RGB');w,h=image.size
    if w<1200 or h<650:continue
    gray=image.resize((256,144)).convert('L');contrast=ImageStat.Stat(gray).stddev[0]
    if contrast<22:continue
    sha=hashlib.sha256(raw).hexdigest();ph=str(imagehash.phash(image))
    if sha in used_hashes or any(distance(ph,x)<=6 for x in used_phashes):continue
    winner=(c,image,sha,ph,semantic+contrast/10);break
   except Exception:continue
  if not winner:raise RuntimeError(f'no unique licensed professional photograph passed for placement {placement}')
  c,image,sha,ph,score=winner;w,h=image.size;target=16/9
  if w/h>target:nw=int(h*target);image=image.crop(((w-nw)//2,0,(w+nw)//2,h))
  else:nh=int(w/target);image=image.crop((0,(h-nh)//2,w,(h+nh)//2))
  image=image.resize((1600,900),Image.Resampling.LANCZOS);path=folder/f'photo-{placement}.jpg';image.save(path,'JPEG',quality=90,optimize=True)
  url=f'https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/assets/master/{slug}/photo-{placement}.jpg';credit=f"Photo: {c['creator']} / {c['license']}"
  selected.append({'url':url,'alt':clean(brief)[:220],'caption':credit,'width':1600,'height':900,'source_page':c['source_page'],'license':c['license'],'license_url':c['license_url'],'creator':c['creator']})
  item={**c,'url':url,'sha256':sha,'phash':ph,'article_key':str(article_key),'placement':placement,'brief':brief,'selection_score':round(score,2),'selected_at':datetime.now(timezone.utc).isoformat()};registry['items'].append(item);used_ids.add(c['source_id']);used_urls.add(c['original_url']);used_hashes.add(sha);used_phashes.append(ph)
 save_registry(registry);return selected
