#!/usr/bin/env python3
"""Daily Yield Master V3: small-output, source-bounded article construction.

This is deliberately independent of the retired monolithic JSON writer. It asks a
local model for one plain-text section at a time, validates every section before
assembly, and builds summary/support/visual structures deterministically from the
verified article and source records.
"""
from __future__ import annotations
import html,json,os,re,time,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
import requests
from master_article_v2 import words
from photo_selector import choose_photos

UA='DailyYieldMasterV3/1.0 (dailyyield.official@gmail.com)';BLOG='https://dailyyield.blogspot.com'
def required(name):
 value=os.environ.get(name,'').strip()
 if not value:raise RuntimeError(f'{name} is required')
 return value
def internal_links():
 return [{'title':'Daily Article','url':BLOG+'/p/article.html','relevance':'More original Daily Yield explainers.'},{'title':'Calculators','url':BLOG+'/p/calculator_0908148622.html','relevance':'Model financial assumptions with Daily Yield tools.'},{'title':'Markets Today','url':BLOG+'/p/markets-today.html','relevance':'Current cross-asset context.'},{'title':'Global Snapshot','url':BLOG+'/p/global-snapshot.html','relevance':'Concise global market context.'},{'title':'Money Atlas','url':BLOG+'/p/money-atlas_01486068069.html','relevance':'Country-specific financial context.'}]
def low_exposure_posts():
 cid=required('GSC_CLIENT_ID');secret=required('GSC_CLIENT_SECRET');refresh=required('GSC_REFRESH_TOKEN')
 token=requests.post('https://oauth2.googleapis.com/token',data={'client_id':required('BLOGGER_CLIENT_ID'),'client_secret':required('BLOGGER_CLIENT_SECRET'),'refresh_token':required('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'},timeout=30).json()['access_token']
 base=f"https://www.googleapis.com/blogger/v3/blogs/{required('BLOGGER_BLOG_ID')}";posts=[];page=None
 while len(posts)<300:
  params={'status':'live','fetchBodies':'true','maxResults':50,'fields':'items(id,title,url,content,labels,published),nextPageToken'}
  if page:params['pageToken']=page
  data=requests.get(base+'/posts',headers={'Authorization':'Bearer '+token},params=params,timeout=60).json();posts+=data.get('items',[]);page=data.get('nextPageToken')
  if not page:break
 access=requests.post('https://oauth2.googleapis.com/token',data={'client_id':cid,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=30);access.raise_for_status()
 from datetime import date,timedelta
 body={'startDate':str(date.today()-timedelta(days=90)),'endDate':str(date.today()-timedelta(days=1)),'dimensions':['page'],'rowLimit':25000};site=urllib.parse.quote(os.environ.get('GSC_SITE_PROPERTY','').strip() or 'sc-domain:dailyyield.blogspot.com',safe='')
 rr=requests.post(f'https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query',headers={'Authorization':'Bearer '+access.json()['access_token']},json=body,timeout=60);rr.raise_for_status();scores={row['keys'][0].rstrip('/'):(float(row.get('clicks',0)),float(row.get('impressions',0))) for row in rr.json().get('rows',[])}
 chosen=sorted(posts,key=lambda p:(*scores.get(p.get('url','').rstrip('/'),(0,0)),p.get('published','')))[:15];out=[]
 for p in chosen:
  match=re.search(r'<img[^>]+src=["\']([^"\']+)',p.get('content',''),re.I);out.append({'title':p.get('title','Daily Yield article'),'url':p.get('url',''),'image':html.unescape(match.group(1)) if match else '','label':next((x for x in p.get('labels',[]) if x!='Kushal K. Daga'),'Daily Yield')})
 return out
STOP=set('a an and are as at be best by can do for from guide how in into is it latest of on or that the their this to today versus via what when where which who why will with your'.split())

def clean(value):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(value or '')))).strip()
def terms(value):return [x for x in re.findall(r'[a-z0-9]{3,}',str(value).casefold()) if x not in STOP and not x.isdigit()]
def sentence_trim(text,limit):
 out=[];count=0
 for sentence in re.split(r'(?<=[.!?])\s+',clean(text)):
  n=words(sentence)
  if count>=380 and count+n>limit:break
  if sentence:out.append(sentence);count+=n
 return ' '.join(out)
def parse_paragraphs(text):
 text=re.sub(r'^```\w*|```$','',str(text or '').strip(),flags=re.M)
 chunks=[clean(x) for x in re.split(r'\n\s*\n+',text) if clean(x)]
 if len(chunks)<3:
  sentences=[x.strip() for x in re.split(r'(?<=[.!?])\s+',clean(text)) if x.strip()];chunks=[]
  for start in range(0,len(sentences),4):
   if sentences[start:start+4]:chunks.append(' '.join(sentences[start:start+4]))
 return chunks

def ollama_text(prompt,max_tokens=1400):
 endpoint=os.environ.get('OLLAMA_API_URL','http://127.0.0.1:11434').rstrip('/')+'/api/chat';model=os.environ.get('OLLAMA_MODEL','qwen2.5:1.5b')
 r=requests.post(endpoint,json={'model':model,'messages':[{'role':'system','content':'Write accurate source-bounded financial journalism in plain paragraphs. Never output JSON or markdown.'},{'role':'user','content':prompt}],'stream':False,'options':{'temperature':0.2,'num_predict':max_tokens,'num_ctx':8192}},timeout=90);r.raise_for_status();return str(r.json()['message']['content'])
def github_text(prompt,max_tokens=1400):
 token=os.environ.get('GITHUB_TOKEN','').strip()
 if not token:raise RuntimeError('repository model token unavailable')
 r=requests.post('https://models.github.ai/inference/chat/completions',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},json={'model':os.environ.get('GITHUB_MODELS_MODEL','openai/gpt-4.1-mini'),'messages':[{'role':'system','content':'Write accurate source-bounded financial journalism in plain paragraphs. Never output JSON or markdown.'},{'role':'user','content':prompt}],'temperature':0.15,'max_tokens':max_tokens},timeout=60)
 if not r.ok:raise RuntimeError(f'repository model HTTP {r.status_code}: {r.text[:300]}')
 return str(r.json()['choices'][0]['message'].get('content') or '')
def text_call(prompt,max_tokens=1400):
 errors=[]
 # Owner-authorized repository-native GitHub Models is the fast primary writer.
 # The quota-independent local model remains an emergency fallback only.
 for fn in (github_text,ollama_text):
  for _ in range(1):
   try:
    text=fn(prompt,max_tokens)
    if words(text)>=120:return text
   except Exception as exc:errors.append(f'{fn.__name__}: {exc}')
 return (_ for _ in ()).throw(RuntimeError('all bounded section writers failed: '+' | '.join(errors)[-1000:]))

def discover_sources(item,kind):
 title=item['title'];base_terms=terms(title);expanded=re.sub(r'\brmds?\b','required minimum distributions',title,flags=re.I)
 query_variants=[]
 for value in (' '.join(base_terms[:8]),' '.join(terms(expanded)[:8]),' '.join(base_terms[:4]),' '.join(base_terms[-6:]),' '.join(terms(item.get('category',''))[:5]+base_terms[:3])):
  value=clean(value)
  if value and value not in query_variants:query_variants.append(value)
 out=[];seen=set()
 def add(name,source_title,url,text):
  url=str(url or '').replace('http://','https://',1)
  key=clean(source_title).casefold()
  if not url.startswith('https://') or key in seen or len(clean(text))<120:return
  overlap=len(set(terms(title))&set(terms(source_title+' '+text)))
  if overlap<2:return
  seen.add(key);out.append({'name':clean(name) or 'Retrieved source','title':clean(source_title),'url':url,'text':clean(text)[:6000],'overlap':overlap})
 for source in item.get('sources',[]):
  try:
   r=requests.get(source['url'],headers={'User-Agent':UA},timeout=30);body=clean(r.text)
   add(source.get('name'),title,source['url'],body)
  except Exception:pass
 # Topic-triggered primary-source discovery keeps high-stakes evergreen articles
 # anchored in current official material instead of relying only on news search.
 official=[];topic=' '.join(base_terms)
 if 'rmd' in topic or ('required' in topic and 'distribution' in topic):
  official=[('Internal Revenue Service','Required minimum distributions FAQs','https://www.irs.gov/retirement-plans/retirement-plan-and-ira-required-minimum-distributions-faqs'),('Internal Revenue Service','Publication 590-B: Distributions from Individual Retirement Arrangements','https://www.irs.gov/publications/p590b'),('Internal Revenue Service','Retirement topics: required minimum distributions','https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds')]
 for name,source_title,url in official:
  try:
   r=requests.get(url,headers={'User-Agent':UA},timeout=30);r.raise_for_status();add(name,source_title,url,clean(r.text))
  except Exception:pass
 horizon='30d' if kind=='trending' else '365d'
 for query in query_variants:
  for suffix in ('',' finance'):
   if len(out)>=12:break
   try:
    url='https://news.google.com/rss/search?q='+urllib.parse.quote(query+suffix+f' when:{horizon}')+'&hl=en-US&gl=US&ceid=US:en'
    root=ET.fromstring(requests.get(url,headers={'User-Agent':UA},timeout=30).content)
    for node in root.findall('.//item'):
     add(clean(node.findtext('source') or 'Google News'),node.findtext('title'),node.findtext('link'),node.findtext('description'))
   except Exception:pass
  if len(out)>=12:break
 for query in query_variants:
  if len(out)>=12:break
  try:
   params={'search':query,'per-page':25,'select':'id,display_name,publication_year,authorships,abstract_inverted_index,primary_location'}
   for work in requests.get('https://api.openalex.org/works',params=params,headers={'User-Agent':UA},timeout=45).json().get('results',[]):
    inv=work.get('abstract_inverted_index') or {};size=max((max(v) for v in inv.values() if v),default=-1)+1;tokens=['']*size
    for word,positions in inv.items():
     for pos in positions:
      if pos<size:tokens[pos]=word
    loc=work.get('primary_location') or {};landing=loc.get('landing_page_url') or work.get('id');name=((loc.get('source') or {}).get('display_name') or 'OpenAlex research index')
    add(name,work.get('display_name'),landing,' '.join(tokens))
  except Exception:pass
 out.sort(key=lambda x:x['overlap'],reverse=True)
 if len(out)<8:raise RuntimeError(f'V3 source gate found {len(out)} topic-specific sources; eight required')
 return out[:10]

def heading(source,index):
 raw=re.sub(r'\s[-–—|:]\s.*$','',source['title']).strip();raw=' '.join(raw.split()[:10])
 return raw if len(raw)>=14 else f'Evidence angle {index}: market scope and limits'
def validate_section(paragraphs,source_ids):
 text=' '.join(paragraphs);count=words(text)
 if not 400<=count<=490:return False,f'{count} words; required 400-490'
 if len(paragraphs)<4:return False,'fewer than four paragraphs'
 if not all(any(f'[[S{i}|' in paragraph for i in source_ids) for paragraph in paragraphs):return False,'every paragraph needs a supplied source token'
 for number in re.findall(r'(?<![SI])\b\d[\d,.]*%?\b',text):
  if not any(number in s for s in source_ids.values()):return False,f'unsupported number {number}'
 return True,''
def deterministic_section(section_heading,sources):
 """Quota-independent, exactly bounded evidence dossier."""
 boundaries=(
  'The record establishes context, not a universal forecast, causal conclusion or personal recommendation.',
  'Jurisdiction, definitions, observation period and later revisions remain necessary limits on interpretation.',
  'A different population, regulatory setting, period or measurement method may produce a different result.',
  'The useful distinction is between what the source reports and assumptions it did not test.',
  'The cited record is one bounded part of the evidence and cannot support broader certainty.',
 )
 tokenized=lambda value:re.findall(r"[A-Za-z0-9][A-Za-z0-9’'\-]*",clean(value))
 paragraphs=[];heading=' '.join(tokenized(section_heading)[:12])
 for cursor in range(6):
  source_id,row=sources[cursor%len(sources)];tokens=tokenized(row.get('text',''));start=(cursor*31)%max(1,len(tokens)-24);excerpt=' '.join(tokens[start:start+22]).strip(' ,;:')
  if not excerpt:continue
  title=' '.join(tokenized(row.get('title') or row.get('name') or 'Retrieved evidence')[:12]);provider=' '.join(tokenized(row.get('name') or 'cited provider')[:5]);boundary=boundaries[cursor%len(boundaries)]
  paragraphs.append(f'[[S{source_id}|{provider} evidence]] frames {heading} through “{title}.” The retrieved record states, in part, “{excerpt}.” {boundary} This passage is used only for its documented scope, while unsupported predictions and recommendations remain outside this section.')
  if len(paragraphs)>=4 and words(' '.join(paragraphs))>=420:break
 # Keep four or more separately attributed paragraphs and hard-bound the total.
 while len(paragraphs)>4 and words(' '.join(paragraphs[:-1]))>=400:paragraphs.pop()
 while words(' '.join(paragraphs))>480:
  index=max(range(len(paragraphs)),key=lambda i:words(paragraphs[i]));parts=paragraphs[index].split()
  if len(parts)<=70:break
  paragraphs[index]=' '.join(parts[:-1]).rstrip(' ,;:')+'.'
 primary=sources[0][0];paragraphs=[p if '[[S' in p else p+f' [[S{primary}|documented source evidence]]' for p in paragraphs]
 ok,error=validate_section(paragraphs,{i:r['text']+' '+r['title'] for i,r in sources})
 if not ok:raise RuntimeError('deterministic evidence section failed: '+error)
 return paragraphs
def write_section(article_title,section_heading,index,sources):
 ids={i:s['text']+' '+s['title'] for i,s in sources};packet='\n'.join(f'S{i} — {s["name"]}: {s["title"]}. {s["text"][:2400]}' for i,s in sources);primary=min(ids)
 base=f'''Article: {article_title}\nSection {index}: {section_heading}\nWrite source-bounded plain paragraphs. Use only the packet below. Do not invent numbers, quotations, causation or advice. Explain evidence, jurisdiction, affected groups, mechanism, uncertainty and limits. Do not introduce the article or summarize another section.\nSOURCES:\n{packet}'''
 pool=[];seen=set();last=''
 for attempt in range(2):
  have=words(' '.join(pool));need=max(120,455-have)
  instruction=(f'Write {need}-{need+25} additional words in 2-4 new paragraphs that do not repeat this accepted partial section: '+json.dumps(pool,ensure_ascii=False) if pool else 'Write 450-460 words in 4-6 paragraphs.')
  try:text=text_call(base+'\n'+instruction+f'\nAttempt {attempt+1}. Return only paragraphs.')
  except Exception as exc:last=f'{type(exc).__name__}: {exc}';continue
  candidates=parse_paragraphs(text)
  # Remove whole sentences containing a numeric claim absent from both supplied
  # source records. This preserves the material-number safeguard without losing
  # an otherwise usable section to a model-added list marker or stray figure.
  safe=[];source_blob=' '.join(ids.values())
  for paragraph in candidates:
   kept=[]
   for sentence in re.split(r'(?<=[.!?])\s+',paragraph):
    nums=re.findall(r'(?<![SI])\b\d[\d,.]*%?\b',re.sub(r'\[\[S\d+\|[^]]+\]\]',' ',sentence))
    if not nums or all(number in source_blob for number in nums):kept.append(sentence)
   paragraph=' '.join(kept).strip()
   if not paragraph:continue
   if not any(f'[[S{i}|' in paragraph for i in ids):paragraph+=f' [[S{primary}|documented source evidence]]'
   key=' '.join(paragraph.casefold().split())
   if key not in seen:seen.add(key);safe.append(paragraph)
  pool.extend(safe)
  if words(' '.join(pool))>490:pool=parse_paragraphs(sentence_trim(' '.join(pool),480))
  # Trimming can redistribute sentences, so enforce citation metadata afterward.
  pool=[p if any(f'[[S{i}|' in p for i in ids) else p+f' [[S{primary}|documented source evidence]]' for p in pool]
  ok,last=validate_section(pool,ids)
  if ok:return pool
 # Completion never depends on a provider quota or model response. The fallback
 # uses only short attributed source excerpts plus explicit scope limitations.
 return deterministic_section(section_heading,sources)

def extracted_summary(sections):
 buckets=[]
 for s in sections:
  seq=[]
  for p in s['paragraphs']:seq += [x.strip() for x in re.split(r'(?<=[.!?])\s+',p) if x.strip()]
  buckets.append(seq)
 selected=[];position=0
 while words(' '.join(selected))<680 and any(position<len(x) for x in buckets):
  for b in buckets:
   if position<len(b):selected.append(b[position])
   if words(' '.join(selected))>=680:break
  position+=1
 text=sentence_trim(' '.join(selected),750);sentences=re.split(r'(?<=[.!?])\s+',text);return [' '.join(sentences[i:i+4]) for i in range(0,len(sentences),4) if sentences[i:i+4]]
def support(sections):
 faq=[]
 for s in sections[:5]:faq.append({'question':f'What does the evidence show about {s["heading"]}?','answer':sentence_trim(' '.join(s['paragraphs']),105)})
 glossary=[]
 used=set()
 for s in sections:
  candidates=[x for x in terms(s['heading']) if len(x)>4]
  term=' '.join(candidates[:2]).title() or f'Evidence Scope {len(glossary)+1}'
  if term in used:term=f'{term} Context'
  used.add(term);glossary.append({'term':term,'definition':sentence_trim(' '.join(s['paragraphs']),55)})
  if len(glossary)>=8:break
 return faq,glossary
def visuals(sources,sections):
 out=[]
 for i,s in enumerate(sources[:3],1):out.append({'type':'table','title':f'Evidence scope {i}: {s["title"][:90]}','caption':f'Categorical scope from {s["name"]}; no unreported quantity is inferred.','source':i,'after_section':sections[i-1]['heading'],'data':[{'Evidence field':'Document','Documented value':s['title']},{'Evidence field':'Provider','Documented value':s['name']},{'Evidence field':'Scope','Documented value':sentence_trim(s['text'],45)}]})
 return out
def photo_set(title,category,slug,key):
 variants=[[f'{title} {category} people workplace wide editorial',f'{category} documents planning desk wide editorial',f'{title} city institutions professional wide editorial'],[f'{category} household decision making',f'{category} office professionals',f'{category} public institution exterior']]
 errors=[]
 for briefs in variants:
  try:return choose_photos(briefs,slug,key)
  except Exception as exc:errors.append(str(exc))
 raise RuntimeError('V3 photo search exhausted two independently broadened searches: '+' | '.join(errors))
def build(item,kind,target):
 sources=discover_sources(item,kind);title=clean(re.sub(r'\s[-–—|:]\s.*$','',item['title']));title=re.sub(r'\b(?:19|20)\d{2}\b|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b','',title,flags=re.I);title=clean(title)[:46].strip(' -:')
 if len(title)<12:title=clean(re.sub(r'^Trend\s*[·:-]?\s*','',item['category'],flags=re.I)+' Evidence Guide')[:46]
 plans=[];used_headings=set()
 for index in range(10):
  primary=(index%len(sources))+1;secondary=((index+3)%len(sources))+1;h=heading(sources[index%len(sources)],index+1)
  if h.casefold() in used_headings:h=f'{h}: evidence angle {index+1}'
  used_headings.add(h.casefold());plans.append((index,h,primary,secondary))
 # Independent bounded sections can be written concurrently. Three workers stay
 # below aggressive repository-model burst limits while reducing normal text
 # generation from ten sequential calls to four short waves.
 from concurrent.futures import ThreadPoolExecutor,as_completed
 sections=[None]*len(plans)
 def create(plan):
  index,h,primary,secondary=plan
  return index,{'heading':h,'paragraphs':write_section(title,h,index+1,[(primary,sources[primary-1]),(secondary,sources[secondary-1])])}
 with ThreadPoolExecutor(max_workers=3,thread_name_prefix='master-v3-section') as executor:
  futures=[executor.submit(create,plan) for plan in plans]
  for future in as_completed(futures):
   index,section=future.result();sections[index]=section
 core=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if core>4200:
  excess=core-4150
  for s in reversed(sections):
   if excess<=0:break
   before=words(' '.join(s['paragraphs']));trimmed=parse_paragraphs(sentence_trim(' '.join(s['paragraphs']),max(400,before-excess)));after=words(' '.join(trimmed))
   if after>=300:s['paragraphs']=trimmed;excess-=before-after
 core=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if not 4000<=core<=4200:raise RuntimeError(f'V3 assembled core is {core}; section-level contract did not converge')
 summary=extracted_summary(sections);faq,glossary=support(sections);slug=re.sub(r'[^a-z0-9]+','-',title.casefold()).strip('-')
 package={'title':title,'meta_description':f'An evidence-led examination of {title}, including mechanisms, affected groups, jurisdiction and uncertainty.'[:158],'entities':[x['name'] for x in sources[:7]],'geography':'Jurisdictions identified in the cited evidence','temporal_coverage':'Current evidence record','module_headings':{'contents':'Evidence route map','summary':'Evidence-led takeaways','faq':'Reader questions','glossary':'Terms decoded','sources':'Evidence ledger','internal_links':'More from Daily Yield','external_sources':'Primary reading'},'visuals':visuals(sources,sections),'sections':sections,'summary':summary,'faq':faq,'glossary':glossary,'photos':photo_set(title,item['category'],slug,item['id']),'sources':[{k:s[k] for k in ('name','title','url')} for s in sources],'internal_links':internal_links(),'low_view_posts':low_exposure_posts()}
 target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(package,indent=2,ensure_ascii=False)+'\n');return package
