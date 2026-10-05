#!/usr/bin/env python3
"""Research and prepare one strict Master Article V2 package before publication.

Text is produced through GitHub Models from a topic-specific evidence packet.
Three AI photographs are generated through an OpenAI-compatible image provider,
cropped to a common 16:9 landscape ratio, and persisted in the repository before
Blogger publication. No public Daily Yield page is requested.
"""
from __future__ import annotations
import base64,csv,gzip,html,json,os,re,sys,urllib.parse,urllib.request
from pathlib import Path
from xml.etree import ElementTree
from PIL import Image
import io,requests
from master_article_v2 import validate

ROOT=Path(__file__).parent
PACKAGES=ROOT/'master_packages';ASSETS=ROOT/'assets/master'
BLOG='https://dailyyield.blogspot.com'
STAGE='startup'

def required(name):
 value=os.environ.get(name,'').strip()
 if not value:raise RuntimeError(f'{name} is required for compliant Master Article V2 preparation')
 return value

def load_next():
 tracker=json.loads((ROOT/'published_tracker.json').read_text())
 with open(ROOT/'500_topics_evenly_mixed.csv',encoding='utf-8') as f:topics=list(csv.DictReader(f))
 index=int(tracker.get('next_topic_index',0))
 if index>=len(topics):raise RuntimeError('master topic inventory exhausted')
 return index,topics[index]

def plain_page(url):
 if url.startswith(BLOG):return ''
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'DailyYieldResearch/2.0 (dailyyield.official@gmail.com)'})
  with urllib.request.urlopen(req,timeout=20) as r:
   if 'text' not in r.headers.get_content_type():return ''
   raw=r.read(500000).decode('utf-8','ignore')
  raw=re.sub(r'<script\b.*?</script>|<style\b.*?</style>',' ',raw,flags=re.I|re.S)
  return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',raw))).strip()[:7000]
 except Exception:return ''

def discover(topic):
 queries=[topic['Punchy Title']+' finance official research',topic['Video Idea']+' data regulator',topic['Category']+' statistics evidence']
 candidates=[]
 for query in queries:
  url='https://www.bing.com/search?format=rss&q='+urllib.parse.quote(query)
  try:
   root=ElementTree.fromstring(requests.get(url,headers={'User-Agent':'DailyYieldResearch/2.0'},timeout=20).text)
   for item in root.findall('.//item'):
    link=(item.findtext('link') or '').strip();title=(item.findtext('title') or '').strip()
    if link.startswith('https://') and 'dailyyield.blogspot.com' not in link:candidates.append((title,link))
  except Exception:pass
 seen=set();evidence=[]
 for title,url in candidates:
  host=(urllib.parse.urlparse(url).hostname or '').lower()
  if url in seen:continue
  seen.add(url);text=plain_page(url)
  if len(text)<500:continue
  score=5 if host.endswith(('.gov','.gov.in','.edu','.org')) or any(x in host for x in ('oecd','worldbank','imf','bis.org','investor.gov','rbi.org','sec.gov','ilo.org')) else 1
  evidence.append({'name':host,'title':title,'url':url,'text':text,'score':score})
  if len(evidence)>=12:break
 evidence.sort(key=lambda x:x['score'],reverse=True)
 if len(evidence)<6:raise RuntimeError(f'only {len(evidence)} usable topic-specific sources found; minimum 6')
 return evidence[:10]

def model_json(messages,max_tokens=16000):
 token=required('GITHUB_TOKEN');model=os.environ.get('MASTER_TEXT_MODEL','').strip() or 'openai/gpt-4.1'
 r=requests.post('https://models.github.ai/inference/chat/completions',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},json={'model':model,'messages':messages,'temperature':0.35,'max_tokens':max_tokens,'response_format':{'type':'json_object'}},timeout=600)
 r.raise_for_status()
 try:payload=r.json()
 except ValueError:raise RuntimeError(f"model endpoint returned non-JSON HTTP {r.status_code} ({r.headers.get('content-type','unknown')}): {r.text[:240]!r}")
 try:text=payload['choices'][0]['message']['content']
 except (KeyError,IndexError,TypeError):raise RuntimeError('model response omitted choices/message/content: '+json.dumps(payload)[:500])
 if isinstance(text,list):text=''.join(str(part.get('text','')) if isinstance(part,dict) else str(part) for part in text)
 text=str(text or '').strip();text=re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.I|re.S).strip()
 start=text.find('{');end=text.rfind('}')
 if start<0 or end<=start:raise RuntimeError('model returned no JSON object')
 return json.loads(text[start:end+1])

def internal_links():
 return [
  {'title':'Daily Article','url':BLOG+'/p/article.html','relevance':'More original Daily Yield explainers.'},
  {'title':'Calculators','url':BLOG+'/p/calculator_0908148622.html','relevance':'Model financial assumptions with Daily Yield tools.'},
  {'title':'Markets Today','url':BLOG+'/p/markets-today.html','relevance':'Current cross-asset context.'},
  {'title':'Global Snapshot','url':BLOG+'/p/global-snapshot.html','relevance':'Concise global market context.'},
  {'title':'Money Atlas','url':BLOG+'/p/money-atlas_01486068069.html','relevance':'Country-specific financial context.'},
 ]

def low_exposure_posts():
 # Blogger exposes aggregate Blog views, not per-Post views. Use genuine GSC page
 # performance when authorized; otherwise rank authenticated Blogger items by
 # zero comments and age as a transparent low-engagement discovery fallback.
 cid=os.environ.get('GSC_CLIENT_ID');secret=os.environ.get('GSC_CLIENT_SECRET');refresh=os.environ.get('GSC_REFRESH_TOKEN')
 blogger_token=requests.post('https://oauth2.googleapis.com/token',data={'client_id':required('BLOGGER_CLIENT_ID'),'client_secret':required('BLOGGER_CLIENT_SECRET'),'refresh_token':required('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'},timeout=30).json()['access_token']
 base=f"https://www.googleapis.com/blogger/v3/blogs/{required('BLOGGER_BLOG_ID')}"
 posts=[];page=None
 while len(posts)<300:
  params={'status':'live','fetchBodies':'true','maxResults':50,'fields':'items(id,title,url,content,labels,published,replies),nextPageToken'}
  if page:params['pageToken']=page
  data=requests.get(base+'/posts',headers={'Authorization':'Bearer '+blogger_token},params=params,timeout=60).json();posts+=data.get('items',[]);page=data.get('nextPageToken')
  if not page:break
 scores={}
 if cid and secret and refresh:
  access=requests.post('https://oauth2.googleapis.com/token',data={'client_id':cid,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=30).json().get('access_token')
  if access:
   from datetime import date,timedelta
   body={'startDate':str(date.today()-timedelta(days=90)),'endDate':str(date.today()-timedelta(days=1)),'dimensions':['page'],'rowLimit':25000}
   site=urllib.parse.quote(BLOG+'/',safe='')
   rr=requests.post(f'https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query',headers={'Authorization':'Bearer '+access},json=body,timeout=60)
   if rr.ok:
    for row in rr.json().get('rows',[]):scores[row['keys'][0].rstrip('/')]=(float(row.get('clicks',0)),float(row.get('impressions',0)))
 def rank(p):
  if scores:return (*scores.get(p.get('url','').rstrip('/'),(0,0)),p.get('published',''))
  replies=int((p.get('replies') or {}).get('totalItems',0) or 0);return (replies,0,p.get('published',''))
 chosen=sorted(posts,key=rank)[:15]
 out=[]
 for p in chosen:
  m=re.search(r'<img[^>]+src=["\']([^"\']+)',p.get('content',''),re.I)
  out.append({'title':p.get('title','Daily Yield article'),'url':p.get('url',''),'image':html.unescape(m.group(1)) if m else '','label':next((x for x in p.get('labels',[]) if x!='Kushal K. Daga'),'Daily Yield')})
 return out

def generate_text(topic,evidence):
 packet=[{k:v for k,v in e.items() if k!='score'} for e in evidence]
 prompt=f'''Create one original Daily Yield master article package as strict JSON. Topic: {json.dumps(topic,ensure_ascii=False)}. Evidence packet: {json.dumps(packet,ensure_ascii=False)}.
Rules: title 12-46 characters, punchy, no date. Build 8-12 genuinely topic-specific sections; never reuse generic fixed headings. The combined section paragraphs must be 3,900-4,300 actual words, excluding all later material. Do not begin with a summary or direct answer: establish background, problem, evidence, mechanisms, alternatives, advantages, disadvantages, limitations, jurisdiction and practical implications in the order this topic needs. Then supply a separate 600-800 word summary. Supply 5-10 topic-specific FAQs and 8-20 glossary entries. Use only facts supported by the evidence packet; distinguish fact, inference and uncertainty. No personal anecdote, invented quote, guarantee or mass-template prose.
Use contextual citation tokens [[S1|anchor text]] and internal tokens [[I1|anchor text]] in paragraphs. Each source number corresponds to evidence order. Create at least 3 appropriate data visual specifications from numbers present verbatim in evidence: type may be table, bar, line, histogram or pie; include labels, numeric values, title, caption, source number, and after_section. Do not invent numbers. Give three distinct photorealistic landscape prompts tied closely to different aspects of this exact topic, with no text, logos, charts or watermarks.
Return JSON keys: title, meta_description (110-158 chars), entities:[specific people/organizations/concepts], geography:[applicable countries/regions], temporal_coverage, sections:[{{heading,paragraphs:[plain text]}}], summary:[paragraphs], faq:[{{question,answer}}], glossary:[{{term,definition}}], visuals:[{{type,title,caption,source,after_section,labels,values}}], photo_prompts:[string]. Do not return markdown fences.'''
 return model_json([{'role':'system','content':'You are a meticulous financial editor. Accuracy, source fidelity, natural variation and reader value override speed.'},{'role':'user','content':prompt}])

def verify_evidence(draft,evidence):
 packet=[{k:v for k,v in e.items() if k!='score'} for e in evidence]
 review=model_json([{'role':'system','content':'Act as a hostile financial fact checker. Reject unsupported claims, invented numbers, misleading causal language and citations that do not support nearby prose.'},{'role':'user','content':'Compare this proposed article package with the evidence packet. Return JSON with pass (boolean) and unsupported_claims (array). Do not rewrite or excuse anything. PACKAGE: '+json.dumps(draft,ensure_ascii=False)+' EVIDENCE: '+json.dumps(packet,ensure_ascii=False)}],max_tokens=5000)
 if not review.get('pass') or review.get('unsupported_claims'):
  raise RuntimeError('independent evidence review rejected the package: '+json.dumps(review.get('unsupported_claims',[])[:10],ensure_ascii=False))

def image_call(prompt):
 endpoint=os.environ.get('MASTER_IMAGE_API_URL','').strip() or 'https://models.github.ai/inference/images/generations'
 token=os.environ.get('MASTER_IMAGE_API_KEY','').strip() or required('GITHUB_TOKEN');model=os.environ.get('MASTER_IMAGE_MODEL','').strip() or 'openai/gpt-image-1'
 r=requests.post(endpoint,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},json={'model':model,'prompt':prompt,'n':1,'size':'1536x1024','response_format':'b64_json'},timeout=600);r.raise_for_status();item=r.json()['data'][0]
 return base64.b64decode(item['b64_json']) if item.get('b64_json') else requests.get(item['url'],timeout=120).content

def prepare():
 global STAGE
 STAGE='load-topic';index,topic=load_next();target=PACKAGES/f"topic_{topic['#']}.json"
 if target.exists():
  package=json.loads(target.read_text());validate(package);print(target);return
 STAGE='source-discovery';evidence=discover(topic)
 STAGE='text-generation';draft=generate_text(topic,evidence)
 evidence_numbers=set()
 for match in re.findall(r'(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?', ' '.join(x['text'] for x in evidence)):
  try:evidence_numbers.add(round(float(match.replace(',','')),8))
  except ValueError:pass
 for chart in draft.get('visuals',[]):
  for value in chart.get('values',[]):
   try:number=round(float(value),8)
   except (TypeError,ValueError):raise RuntimeError('data visual contains a non-numeric value')
   if number not in evidence_numbers:raise RuntimeError(f'data visual value {value} is absent from the retrieved evidence')
 STAGE='evidence-verification';verify_evidence(draft,evidence)
 prior=[]
 for path in PACKAGES.glob('topic_*.json'):
  try:prior.append(json.loads(path.read_text()))
  except Exception:pass
 title_key=re.sub(r'[^a-z0-9]+',' ',draft.get('title','').casefold()).strip()
 if any(re.sub(r'[^a-z0-9]+',' ',p.get('title','').casefold()).strip()==title_key for p in prior):raise RuntimeError('generated master title duplicates an existing package')
 new_heads={x.get('heading','').casefold().strip() for x in draft.get('sections',[])}
 if prior and max((len(new_heads&{x.get('heading','').casefold().strip() for x in p.get('sections',[])})/max(1,len(new_heads)) for p in prior),default=0)>.5:raise RuntimeError('generated heading structure repeats an existing master package')
 slug=re.sub(r'[^a-z0-9]+','-',draft['title'].casefold()).strip('-');folder=ASSETS/slug;folder.mkdir(parents=True,exist_ok=True)
 photos=[]
 prompts=draft.pop('photo_prompts')
 if len(prompts)!=3:raise RuntimeError('text model did not provide exactly three photo prompts')
 STAGE='image-generation'
 for i,prompt in enumerate(prompts,1):
  raw=image_call('Photorealistic editorial finance photograph, horizontal landscape, topic-specific and realistic. '+prompt+' No text, no letters, no logos, no watermark, no charts.')
  image=Image.open(io.BytesIO(raw)).convert('RGB');w,h=image.size;ratio=16/9
  if w/h>ratio:new_w=int(h*ratio);image=image.crop(((w-new_w)//2,0,(w+new_w)//2,h))
  else:new_h=int(w/ratio);image=image.crop((0,(h-new_h)//2,w,(h+new_h)//2))
  image=image.resize((1600,900),Image.Resampling.LANCZOS);path=folder/f'photo-{i}.jpg';image.save(path,'JPEG',quality=88,optimize=True)
  url=f'https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/assets/master/{slug}/photo-{i}.jpg'
  photos.append({'url':url,'alt':f"{draft['title']} — topic-specific editorial photograph {i}",'caption':f"Editorial illustration for {draft['title']}",'width':1600,'height':900})
 draft['photos']=photos;draft['sources']=[{'name':e['name'],'title':e['title'],'url':e['url'],'date':'Accessed during article preparation','use':'Topic-specific evidence'} for e in evidence]
 STAGE='low-exposure-selection';draft['internal_links']=internal_links();draft['low_view_posts']=low_exposure_posts()
 STAGE='final-validation';validate(draft)
 PACKAGES.mkdir(exist_ok=True);target.write_text(json.dumps(draft,indent=2,ensure_ascii=False)+'\n');print(target)
if __name__=='__main__':
 try:
  prepare()
  Path('MASTER_PREPARATION_REPORT.json').write_text(json.dumps({'status':'PASS'},indent=2)+'\n')
 except Exception as exc:
  Path('MASTER_PREPARATION_REPORT.json').write_text(json.dumps({'status':'FAIL','stage':STAGE,'error_type':type(exc).__name__,'error':str(exc)[:1000]},indent=2)+'\n')
  raise
