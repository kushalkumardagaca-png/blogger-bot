#!/usr/bin/env python3
"""Research and prepare one strict Master Article V2 package before publication.

Text is produced through the repository's Gemini key (with an optional
OpenAI-compatible fallback) from a topic-specific evidence packet. Three distinct,
openly licensed photographs are selected for their exact editorial placements,
checked against the permanent global reuse registry, cropped to a common 16:9
landscape ratio, attributed, and persisted before Blogger publication. No public Daily Yield page is requested.
"""
from __future__ import annotations
import base64,csv,gzip,html,json,os,re,sys,time,urllib.parse,urllib.request
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from PIL import Image
import io,requests
from master_article_v2 import validate,words
from photo_selector import choose_photos

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

def _abstract(index):
 if not index:return ''
 size=max((max(v) for v in index.values() if v),default=-1)+1;tokens=['']*size
 for word,positions in index.items():
  for pos in positions:
   if 0<=pos<size:tokens[pos]=word
 return ' '.join(tokens)

def discover(topic):
 terms=[]
 for value in (topic.get('Punchy Title',''),topic.get('Video Idea','')):
  value=str(value).strip()
  if value and value not in terms:terms.append(value)
 subject=' '.join(terms)
 try:
  query_plan=model_json([{'role':'system','content':'Convert an editorial headline into neutral academic database search concepts. Remove hooks, commands and rhetoric.'},{'role':'user','content':'Return strict JSON {"query":"6 to 12 concrete financial research terms"} for: '+subject}],max_tokens=500)
  subject=str(query_plan.get('query') or subject)[:300]
 except Exception:pass
 evidence=[];seen=set()
 # OpenAlex provides topic-ranked scholarly metadata and abstracts without
 # screen-scraping or a private search key. Each work remains linked to its
 # DOI/publisher record so the evidence is auditable.
 try:
  r=requests.get('https://api.openalex.org/works',params={'search':subject,'filter':'has_abstract:true','per-page':25,'mailto':'dailyyield.official@gmail.com'},timeout=45);r.raise_for_status()
  for work in r.json().get('results',[]):
   abstract=_abstract(work.get('abstract_inverted_index'));year=int(work.get('publication_year') or 0)
   location=work.get('primary_location') or {};url=(location.get('landing_page_url') or work.get('doi') or work.get('id') or '').replace('http://','https://')
   source=(location.get('source') or {}).get('display_name') or 'OpenAlex scholarly record'
   if not url.startswith('https://') or url in seen or len(abstract)<450 or year>datetime.now().year:continue
   seen.add(url);text=f"{work.get('title','')}. Published {year}. {abstract} Cited by {int(work.get('cited_by_count') or 0)} works in the OpenAlex index."
   evidence.append({'name':source,'title':work.get('title') or subject,'url':url,'text':text[:7000],'score':7})
   if len(evidence)>=10:break
 except Exception:pass
 trusted=('irs.gov','dol.gov','sec.gov','investor.gov','consumerfinance.gov','federalreserve.gov','rbi.org.in','oecd.org','worldbank.org','imf.org','bis.org','ilo.org')
 queries=[subject+' official research data',subject+' regulator evidence',subject+' academic study statistics']
 for query in queries:
  try:
   root=ElementTree.fromstring(requests.get('https://www.bing.com/search?format=rss&q='+urllib.parse.quote(query),headers={'User-Agent':'DailyYieldResearch/2.0'},timeout=20).text)
   for item in root.findall('.//item'):
    url=(item.findtext('link') or '').strip();title=(item.findtext('title') or '').strip();host=(urllib.parse.urlparse(url).hostname or '').lower()
    if not url.startswith('https://') or url in seen:continue
    if not (host.endswith('.gov') or host.endswith('.gov.in') or host.endswith('.edu') or any(host==x or host.endswith('.'+x) for x in trusted)):continue
    text=plain_page(url)
    if len(text)<500:continue
    seen.add(url);evidence.append({'name':host,'title':title,'url':url,'text':text,'score':9})
  except Exception:pass
 evidence.sort(key=lambda x:x['score'],reverse=True)
 if len(evidence)<6:raise RuntimeError(f'only {len(evidence)} usable topic-specific scholarly/primary sources found; minimum 6')
 return evidence[:10]
def model_json(messages,max_tokens=16000):
 key=os.environ.get('GEMINI_API_KEY','').strip()
 if key:
  model=os.environ.get('GEMINI_MODEL','').strip() or 'gemini-3.5-flash-lite';last=None
  system='\n'.join(x['content'] for x in messages if x.get('role')=='system');conversation=[x for x in messages if x.get('role')!='system']
  contents=[{'role':'model' if x.get('role')=='assistant' else 'user','parts':[{'text':x['content']}]} for x in conversation]
  endpoint=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
  for attempt in range(5):
   body={'contents':contents+([{'role':'user','parts':[{'text':'Return one complete strict JSON object only. Do not use markdown.'}]}] if attempt else []),'generationConfig':{'responseMimeType':'application/json','temperature':0.2,'maxOutputTokens':max_tokens}}
   if system:body['systemInstruction']={'parts':[{'text':system}]}
   try:
    r=requests.post(endpoint,headers={'x-goog-api-key':key,'Content-Type':'application/json'},json=body,timeout=600)
    if not r.ok:raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
    payload=r.json();text=''.join(p.get('text','') for p in payload['candidates'][0]['content']['parts']);begin=text.find('{');finish=text.rfind('}')
    if begin<0 or finish<=begin:raise ValueError('Gemini returned no complete JSON object')
    return json.loads(text[begin:finish+1])
   except Exception as exc:
    last=exc
    if attempt<4:time.sleep(15*(attempt+1))
  raise RuntimeError(f'Gemini failed to return valid JSON after 5 attempts: {type(last).__name__}: {str(last)[:300]}')
 endpoint=required('MASTER_TEXT_API_URL');token=required('MASTER_TEXT_API_KEY');model=required('MASTER_TEXT_MODEL');headers={'Content-Type':'application/json','Authorization':'Bearer '+token};last=None
 for attempt in range(3):
  request_messages=list(messages)
  if attempt:request_messages.append({'role':'user','content':'Return one complete strict JSON object only; never truncate JSON.'})
  try:
   r=requests.post(endpoint,headers=headers,json={'model':model,'messages':request_messages,'temperature':0.25,'max_tokens':max_tokens,'response_format':{'type':'json_object'},'reasoning_effort':'low'},timeout=600);r.raise_for_status();payload=r.json();text=str(payload['choices'][0]['message'].get('content') or '').strip();begin=text.find('{');finish=text.rfind('}')
   if begin<0 or finish<=begin:raise ValueError('model returned no complete JSON object')
   return json.loads(text[begin:finish+1])
  except Exception as exc:last=exc
 raise RuntimeError(f'model failed to return valid JSON after 3 attempts: {type(last).__name__}: {str(last)[:300]}')

def paragraph_list(value):
 out=[]
 def walk(item):
  if isinstance(item,str) and item.strip():out.append(item.strip())
  elif isinstance(item,list):
   for child in item:walk(child)
  elif isinstance(item,dict):
   for key in ('text','paragraph','content'):
    if key in item:walk(item[key]);break
 walk(value);return out

def trim_paragraphs(value,limit=750):
 out=[];count=0
 for paragraph in paragraph_list(value):
  kept=[]
  for sentence in re.split(r'(?<=[.!?])\s+',paragraph):
   n=words(sentence)
   if count+n>limit:break
   kept.append(sentence);count+=n
  if kept:out.append(' '.join(kept))
  if count>=limit-35:break
 return out

def internal_links():
 return [
  {'title':'Daily Article','url':BLOG+'/p/article.html','relevance':'More original Daily Yield explainers.'},
  {'title':'Calculators','url':BLOG+'/p/calculator_0908148622.html','relevance':'Model financial assumptions with Daily Yield tools.'},
  {'title':'Markets Today','url':BLOG+'/p/markets-today.html','relevance':'Current cross-asset context.'},
  {'title':'Global Snapshot','url':BLOG+'/p/global-snapshot.html','relevance':'Concise global market context.'},
  {'title':'Money Atlas','url':BLOG+'/p/money-atlas_01486068069.html','relevance':'Country-specific financial context.'},
 ]

def low_exposure_posts():
 # Blogger exposes aggregate Blog views, not per-Post views. Use genuine GSC
 # per-URL clicks and impressions and fail closed if that evidence is unavailable.
 cid=required('GSC_CLIENT_ID');secret=required('GSC_CLIENT_SECRET');refresh=required('GSC_REFRESH_TOKEN')
 blogger_token=requests.post('https://oauth2.googleapis.com/token',data={'client_id':required('BLOGGER_CLIENT_ID'),'client_secret':required('BLOGGER_CLIENT_SECRET'),'refresh_token':required('BLOGGER_REFRESH_TOKEN'),'grant_type':'refresh_token'},timeout=30).json()['access_token']
 base=f"https://www.googleapis.com/blogger/v3/blogs/{required('BLOGGER_BLOG_ID')}"
 posts=[];page=None
 while len(posts)<300:
  params={'status':'live','fetchBodies':'true','maxResults':50,'fields':'items(id,title,url,content,labels,published,replies),nextPageToken'}
  if page:params['pageToken']=page
  data=requests.get(base+'/posts',headers={'Authorization':'Bearer '+blogger_token},params=params,timeout=60).json();posts+=data.get('items',[]);page=data.get('nextPageToken')
  if not page:break
 access_response=requests.post('https://oauth2.googleapis.com/token',data={'client_id':cid,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=30);access_response.raise_for_status();access=access_response.json()['access_token']
 from datetime import date,timedelta
 body={'startDate':str(date.today()-timedelta(days=90)),'endDate':str(date.today()-timedelta(days=1)),'dimensions':['page'],'rowLimit':25000}
 site=urllib.parse.quote(os.environ.get('GSC_SITE_PROPERTY','sc-domain:dailyyield.blogspot.com'),safe='')
 rr=requests.post(f'https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query',headers={'Authorization':'Bearer '+access},json=body,timeout=60);rr.raise_for_status()
 scores={row['keys'][0].rstrip('/'):(float(row.get('clicks',0)),float(row.get('impressions',0))) for row in rr.json().get('rows',[])}
 def rank(p):return (*scores.get(p.get('url','').rstrip('/'),(0,0)),p.get('published',''))
 chosen=sorted(posts,key=rank)[:15]
 out=[]
 for p in chosen:
  m=re.search(r'<img[^>]+src=["\']([^"\']+)',p.get('content',''),re.I)
  out.append({'title':p.get('title','Daily Yield article'),'url':p.get('url',''),'image':html.unescape(m.group(1)) if m else '','label':next((x for x in p.get('labels',[]) if x!='Kushal K. Daga'),'Daily Yield')})
 return out

def generate_text(topic,evidence):
 packet=[{k:v for k,v in e.items() if k!='score'} for e in evidence]
 evidence_json=json.dumps(packet,ensure_ascii=False)
 plan_prompt=f'''Design one original Daily Yield master article as strict JSON. Topic: {json.dumps(topic,ensure_ascii=False)}. Evidence packet: {evidence_json}.
Return a compact planning object only. Requirements: title 20-46 characters, punchy, no date; meta_description 110-158 characters; exactly 9 genuinely topic-specific section_plans with unique heading and focus; do not use universal template headings. Plan a background-first progression rather than opening with a summary or direct answer. Include entities, geography, temporal_coverage, 5-10 topic-specific FAQ questions, 8-20 glossary terms, exactly 3 distinct photorealistic landscape photo_prompts, and at least 3 evidence-appropriate visuals. The three photo_prompts must instead be precise placement-specific search briefs for real, openly licensed editorial photographs: opening context, the subject near 2,000 words, and the later section near 4,000 words. Every visual needs type, title, caption, source number, after_section, labels and numeric values copied verbatim from the evidence. No invented values. JSON keys: title,meta_description,entities,geography,temporal_coverage,section_plans,faq_questions,glossary_terms,visuals,photo_prompts.'''
 plan=model_json([{'role':'system','content':'You are a meticulous financial editor planning a deeply sourced, non-templated article. Accuracy and reader value override speed.'},{'role':'user','content':plan_prompt}],max_tokens=6000)
 section_plans=plan.pop('section_plans',[])
 if len(section_plans)!=9:raise RuntimeError('editorial planner did not return exactly nine topic-specific sections')
 sections=[]
 for number,item in enumerate(section_plans,1):
  heading=str(item.get('heading','')).strip();focus=str(item.get('focus','')).strip()
  if not heading or not focus:raise RuntimeError('editorial plan contains an incomplete section')
  prior=[x['heading'] for x in sections]
  prompt=f'''Write section {number} of 9 for a Daily Yield financial article titled {plan.get('title')!r}. Heading: {heading!r}. Focus: {focus}. Topic: {json.dumps(topic,ensure_ascii=False)}. Prior headings: {json.dumps(prior)}. Evidence packet: {evidence_json}.
Write 440-480 actual words in 4-7 natural paragraphs. Establish context before conclusions. Use only evidence-supported facts; identify uncertainty, jurisdiction and limitations naturally. Add contextual source tokens such as [[S1|descriptive anchor]] and useful Daily Yield internal tokens such as [[I1|descriptive anchor]]. Do not include the heading, summary, FAQ, glossary, generic method prose, invented quotation, unsupported number, personal anecdote or repeated material. Return strict JSON {{"paragraphs":[...]}} only.'''
  accepted=None
  for _ in range(3):
   result=model_json([{'role':'system','content':'Write rigorous, natural financial journalism. Obey the exact word budget and source boundaries.'},{'role':'user','content':prompt}],max_tokens=3500)
   parsed=paragraph_list(result.get('paragraphs'));count=words(' '.join(parsed))
   if 250<=count<=700:accepted=parsed;break
  if not accepted:raise RuntimeError(f'section {number} failed its substantive section gate; last count {count}')
  sections.append({'heading':heading,'paragraphs':accepted})
 core_count=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if core_count<4000:
  for _ in range(3):
   needed=4050-core_count;expand_prompt=f'''Add approximately {needed} words as 2-6 new paragraphs to the final section {sections[-1]['heading']!r}. Extend only its existing focus with evidence-supported nuance; do not repeat, summarize or introduce unsupported figures. Return strict JSON {{"paragraphs":[...]}}. EXISTING SECTION: {json.dumps(sections[-1],ensure_ascii=False)} EVIDENCE: {evidence_json}'''
   candidate=paragraph_list(model_json([{'role':'system','content':'Supply only the requested evidence-grounded expansion.'},{'role':'user','content':expand_prompt}],max_tokens=max(1200,needed*3)).get('paragraphs'));added=words(' '.join(candidate))
   if added>=80 and core_count+added<=4200:sections[-1]['paragraphs'].extend(candidate);core_count+=added
   if core_count>=4000:break
  if core_count<4000:raise RuntimeError(f'core expansion failed; assembled core remains {core_count} words')
 elif core_count>4200:
  excess=core_count-4100
  for section in reversed(sections):
   if excess<=0:break
   current=words(' '.join(section['paragraphs']));cut=min(excess,max(0,current-280))
   if cut<=0:continue
   target=current-cut;rewrite_prompt=f'''Rewrite this section in approximately {target} words, preserving its supported claims, citation tokens and distinct focus without repetition. Return strict JSON {{"paragraphs":[...]}}. SECTION: {json.dumps(section,ensure_ascii=False)} EVIDENCE: {evidence_json}'''
   replacement=None
   for _ in range(3):
    candidate=paragraph_list(model_json([{'role':'system','content':'Condense accurately near the requested word budget.'},{'role':'user','content':rewrite_prompt}],max_tokens=max(1500,target*3)).get('paragraphs'));count=words(' '.join(candidate))
    if target-50<=count<=target+50:replacement=candidate;break
   if not replacement:continue
   actual_cut=current-words(' '.join(replacement));section['paragraphs']=replacement;excess-=max(0,actual_cut)
  core_count=words(' '.join(' '.join(x['paragraphs']) for x in sections))
  if core_count>4200:raise RuntimeError(f'assembled core remains too large after safe condensation: {core_count} words')
 core_count=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if not 4000<=core_count<=4200:raise RuntimeError(f'normalized core is {core_count} words before validation')
 summary_prompt=f'''Using only this completed article and its evidence, write a 650-730 word after-article summary in 6-10 natural paragraphs. Do not add facts, headings, FAQ material or a new direct-answer opening. Return strict JSON {{"paragraphs":[...]}}. ARTICLE: {json.dumps(sections,ensure_ascii=False)} EVIDENCE: {evidence_json}'''
 summary=paragraph_list(model_json([{'role':'system','content':'Compress faithfully without introducing new claims.'},{'role':'user','content':summary_prompt}],max_tokens=3500).get('paragraphs'));summary_count=words(' '.join(summary))
 if summary_count<600:
  needed=700-summary_count;prompt=f'''Add approximately {needed} words in new summary paragraphs using only the completed article. Do not introduce facts or repeat existing summary wording. Return JSON {{"paragraphs":[...]}}. ARTICLE: {json.dumps(sections,ensure_ascii=False)} EXISTING SUMMARY: {json.dumps(summary,ensure_ascii=False)}''';addition=paragraph_list(model_json([{'role':'system','content':'Expand a faithful after-article summary.'},{'role':'user','content':prompt}],max_tokens=2500).get('paragraphs'));summary.extend(addition)
 elif summary_count>800:
  prompt=f'''Rewrite this after-article summary in 650-750 words, preserving only supported points and adding no facts. Return JSON {{"paragraphs":[...]}}. SUMMARY: {json.dumps(summary,ensure_ascii=False)}''';summary=paragraph_list(model_json([{'role':'system','content':'Condense faithfully.'},{'role':'user','content':prompt}],max_tokens=3000).get('paragraphs'))
 if words(' '.join(summary))>800:summary=trim_paragraphs(summary,750)
 if not 600<=words(' '.join(summary))<=800:raise RuntimeError(f'summary failed normalization at {words(" ".join(summary))} words')
 support_prompt=f'''Create reader-specific support material for the article below, using only the evidence packet. Answer these FAQ questions: {json.dumps(plan.pop('faq_questions',[]),ensure_ascii=False)}. Define these glossary terms: {json.dumps(plan.pop('glossary_terms',[]),ensure_ascii=False)}. Return strict JSON with faq:[{{question,answer}}] and glossary:[{{term,definition}}]. At least 5 FAQs and 8 definitions. Keep answers accurate, concise and non-repetitive. ARTICLE: {json.dumps(sections,ensure_ascii=False)} EVIDENCE: {evidence_json}'''
 support=model_json([{'role':'system','content':'Create accurate topic-specific reader support, not generic boilerplate.'},{'role':'user','content':support_prompt}],max_tokens=5000)
 plan['sections']=sections;plan['summary']=summary;plan['faq']=support.get('faq',[]);plan['glossary']=support.get('glossary',[])
 return plan
def verify_evidence(draft,evidence):
 packet=[{k:v for k,v in e.items() if k!='score'} for e in evidence]
 review_package={k:draft.get(k) for k in ('sections','summary','faq','visuals')}
 for review_round in range(3):
  review=model_json([{'role':'system','content':'Act as a hostile financial fact checker. Evaluate only visible prose and numeric visuals. Reject unsupported claims, invented numbers, misleading causal language and citations that do not support nearby prose. Never list evidence-source titles or photo-search briefs as article claims.'},{'role':'user','content':'Compare this proposed visible editorial content with the evidence packet. Return JSON with pass (boolean) and unsupported_claims (array of exact quoted text that actually occurs in the proposed content). Do not rewrite or excuse anything. CONTENT: '+json.dumps(review_package,ensure_ascii=False)+' EVIDENCE: '+json.dumps(packet,ensure_ascii=False)}],max_tokens=5000)
  editorial_plain=json.dumps(review_package,ensure_ascii=False).casefold();claims=[]
  for item in review.get('unsupported_claims',[]):
   claim=str(item).strip();needle=' '.join(re.sub(r'\[\[[^]]+\]\]',' ',claim).casefold().split()[:8])
   if claim and needle and needle in re.sub(r'\[\[[^]]+\]\]',' ',editorial_plain):claims.append(claim)
  if not claims:return
  repaired=False
  for section in draft.get('sections',[]):
   section_text=' '.join(paragraph_list(section.get('paragraphs')));matched=[]
   plain_section=re.sub(r'\[\[[^]]+\]\]',' ',section_text).casefold()
   for claim in claims:
    plain_claim=re.sub(r'\[\[[^]]+\]\]',' ',claim).casefold();needle=' '.join(plain_claim.split()[:10])
    if needle and needle in plain_section:matched.append(claim)
   if not matched:continue
   target=words(section_text);prompt=f'''Rewrite this article section in {target-50} to {target+50} words. Remove or accurately qualify every rejected claim. Use only the evidence packet, retain useful contextual source tokens, preserve the section's distinct purpose, and do not add new figures. Return strict JSON {{"paragraphs":[...]}}. HEADING: {section.get('heading')} REJECTED CLAIMS: {json.dumps(matched,ensure_ascii=False)} SECTION: {json.dumps(section,ensure_ascii=False)} EVIDENCE: {json.dumps(packet,ensure_ascii=False)}'''
   replacement=None
   for _ in range(3):
    candidate=paragraph_list(model_json([{'role':'system','content':'Repair unsupported financial prose conservatively and at the exact word budget.'},{'role':'user','content':prompt}],max_tokens=4000).get('paragraphs'))
    if target-60<=words(' '.join(candidate))<=target+60:replacement=candidate;break
   if not replacement:raise RuntimeError('evidence repair could not preserve the section word budget')
   section['paragraphs']=replacement;repaired=True
  if not repaired:raise RuntimeError('independent evidence review rejected claims that could not be located safely: '+json.dumps(claims[:5],ensure_ascii=False))
 raise RuntimeError('independent evidence review still rejected the package after two repair rounds')
def image_call(prompt):
 endpoint=required('MASTER_IMAGE_API_URL');token=required('MASTER_IMAGE_API_KEY');model=required('MASTER_IMAGE_MODEL')
 headers={'Content-Type':'application/json','Authorization':'Bearer '+token}
 r=requests.post(endpoint,headers=headers,json={'model':model,'prompt':prompt,'n':1,'size':'1536x1024','response_format':'b64_json'},timeout=600);r.raise_for_status();item=r.json()['data'][0]
 return base64.b64decode(item['b64_json']) if item.get('b64_json') else requests.get(item['url'],timeout=120).content

def build_package(topic,target):
 global STAGE
 target=Path(target)
 if target.exists():
  package=json.loads(target.read_text());validate(package);return package
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
 for path in PACKAGES.rglob('*.json'):
  if path.resolve()==target.resolve():continue
  try:prior.append(json.loads(path.read_text()))
  except Exception:pass
 title_key=re.sub(r'[^a-z0-9]+',' ',draft.get('title','').casefold()).strip()
 if any(re.sub(r'[^a-z0-9]+',' ',p.get('title','').casefold()).strip()==title_key for p in prior):raise RuntimeError('generated master title duplicates an existing package')
 new_heads={x.get('heading','').casefold().strip() for x in draft.get('sections',[])}
 if prior and max((len(new_heads&{x.get('heading','').casefold().strip() for x in p.get('sections',[])})/max(1,len(new_heads)) for p in prior),default=0)>.5:raise RuntimeError('generated heading structure repeats an existing master package')
 slug=re.sub(r'[^a-z0-9]+','-',draft['title'].casefold()).strip('-');raw_briefs=draft.pop('photo_prompts');briefs=[]
 for item in raw_briefs:
  if isinstance(item,str):briefs.append(item)
  elif isinstance(item,dict):briefs.append(' '.join(str(v) for v in item.values() if isinstance(v,(str,int,float))))
 if len(briefs)!=3 or any(len(x.strip())<20 for x in briefs):
  headings=[str(x.get('heading','')) for x in draft.get('sections',[])]
  briefs=[f"Opening editorial context for {draft['title']}: {'; '.join(headings[:2])}",f"Mid-article mechanism and evidence for {draft['title']}: {'; '.join(headings[3:6])}",f"Later implications and decisions for {draft['title']}: {'; '.join(headings[-3:])}"]
 STAGE='licensed-photo-selection';draft['photos']=choose_photos(briefs,slug,topic.get('#',slug));draft['sources']=[{'name':e['name'],'title':e['title'],'url':e['url'],'date':'Accessed during article preparation','use':'Topic-specific evidence'} for e in evidence]
 STAGE='low-exposure-selection';draft['internal_links']=internal_links();draft['low_view_posts']=low_exposure_posts()
 STAGE='final-validation';validate(draft)
 target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(draft,indent=2,ensure_ascii=False)+'\n');return draft

def prepare():
 global STAGE
 STAGE='load-topic';index,topic=load_next();target=PACKAGES/f"topic_{topic['#']}.json"
 package=build_package(topic,target);print(target);return package
if __name__=='__main__':
 try:
  prepare()
  Path('MASTER_PREPARATION_REPORT.json').write_text(json.dumps({'status':'PASS'},indent=2)+'\n')
 except Exception as exc:
  Path('MASTER_PREPARATION_REPORT.json').write_text(json.dumps({'status':'FAIL','stage':STAGE,'error_type':type(exc).__name__,'error':str(exc)[:1000]},indent=2)+'\n')
  raise
