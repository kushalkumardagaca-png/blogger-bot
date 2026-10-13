#!/usr/bin/env python3
"""Daily Yield Master V3 — fresh, checkpoint-free bounded-output production.

This replaces the monolithic Master generator. It never asks a small local model
for an entire 4,000-word JSON document. Nine independent evidence-bound sections
are generated and validated, then deterministic code assembles the summary,
FAQ, glossary and visuals. Existing Blogger, rendering, photo-licensing and
social components are reused only as stable delivery adapters.
"""
from __future__ import annotations
import argparse,datetime as dt,json,os,re
from pathlib import Path
from zoneinfo import ZoneInfo
from auto_blogger_publisher import publish_to_blogger
from brand_identity import ensure_brand_identity
from continuous_motion import ensure as ensure_continuous_motion
from master_article_v2 import render,validate,words
from photo_selector import choose_photos
from publication_preflight import assert_publishable
from publication_timing import MASTER_LIVE,wait_for_release
from seo_meta import ensure_seo_meta
from social_identity import ensure_social_identity
from prepare_master_article import discover,internal_links,low_exposure_posts,model_json,paragraph_list,trim_complete_sentences,verify_evidence

ROOT=Path(__file__).parent; PLAN=ROOT/'MASTER_DAILY_PLAN.json'; POOL=ROOT/'MASTER_TREND_POOL.json'; PACKAGES=ROOT/'master_packages'/'fresh'; TRACKER=ROOT/'MASTER_AUTOMATION_TRACKER.json'; STATUS=ROOT/'MASTER_AUTOMATION_STATUS.json'; SOCIAL=ROOT/'social_events.json'; IST=ZoneInfo('Asia/Kolkata')
SECTION_ANGLES=(
 "Why the subject matters now","What the evidence actually establishes","How the financial mechanism works",
 "Who is affected and in which jurisdiction","Where uncertainty changes the conclusion","Trade-offs readers should understand",
 "Signals worth monitoring","Decision boundaries and common mistakes","A durable framework for interpreting the evidence",
)

def read(path,default):
 try:return json.loads(path.read_text())
 except (OSError,json.JSONDecodeError):return default

def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def selected(kind,slot):
 plan=read(PLAN,{})
 if plan.get('status')!='READY':raise RuntimeError('daily Master plan is not READY')
 today=dt.datetime.now(IST).date();plan_date=dt.date.fromisoformat(str(plan.get('date')))
 if plan_date!=today:
  allowed=os.environ.get('MASTER_BACKFILL','').casefold()=='true' and plan_date==today-dt.timedelta(days=1)
  if not allowed:raise RuntimeError('daily Master plan is stale')
 rows=plan.get(kind,[])
 if not 0<=slot<len(rows):raise RuntimeError(f'{kind} slot {slot} is unavailable')
 return plan,rows[slot]

def topic_for(kind,item):
 evergreen=item.get('evergreen_category') if kind=='trending' else item['category']
 return {'#':'fresh-'+item['id'],'Punchy Title':item['title'],'Video Idea':item['title'],'Category':evergreen,'Trending Category':item.get('category') if kind=='trending' else ''}

def package_path(kind,item,plan_date):return PACKAGES/f'{plan_date}-{kind}-{item["id"]}.json'

def short_title(value):
 clean=re.sub(r'\s+[|–—]\s+.*$','',str(value)).strip(' .,:;–—-|')
 words_=clean.split();out=[]
 for word in words_:
  if len(' '.join(out+[word]))>46:break
  out.append(word)
 title=' '.join(out)
 if len(title)<12:title=(clean[:46].rsplit(' ',1)[0] or clean[:46]).strip()
 return title.rstrip(' .,:;–—-|')

def citation_numbers(text):return {int(x) for x in re.findall(r'\[\[S(\d+)\|',str(text))}

def unsupported_numbers(text,evidence,refs):
 # A material number may appear only when it exists in one of the paragraph's
 # cited source records. Citation indices and bare one-digit list markers are ignored.
 visible=re.sub(r'\[\[S\d+\|[^]]+\]\]',' ',str(text));claims=set(re.findall(r'(?<![A-Za-z])(?:\d[\d,.]*%?|\$\s*\d[\d,.]*)',visible))
 source=' '.join(str(evidence[i-1].get('text','')) for i in refs if 1<=i<=len(evidence))
 normalized=lambda x:re.sub(r'[^0-9.]','',x)
 available={normalized(x) for x in re.findall(r'(?<![A-Za-z])(?:\d[\d,.]*%?|\$\s*\d[\d,.]*)',source)}
 return [x for x in claims if normalized(x) not in available]

def generate_section(title,heading,index,evidence):
 refs=[index%len(evidence)+1,(index+3)%len(evidence)+1,(index+6)%len(evidence)+1]
 packet=[{'source':n,'name':evidence[n-1]['name'],'title':evidence[n-1]['title'],'text':evidence[n-1]['text'][:3200]} for n in refs]
 prompt=f'''Write one section of an evidence-grounded Daily Yield financial article.
ARTICLE: {title}\nHEADING: {heading}\nALLOWED EVIDENCE: {json.dumps(packet,ensure_ascii=False)}
Return strict JSON {{"paragraphs":[...]}} containing 430-470 actual words in 5-7 readable paragraphs. Every paragraph must include at least one contextual token [[S<number>|descriptive anchor]] referring only to an allowed source. Cover mechanisms, affected groups, jurisdiction and uncertainty relevant to this heading. Do not invent a number, quotation, prediction or recommendation. Do not introduce the article or summarize another section.'''
 last=''
 for attempt in range(4):
  try:paragraphs=paragraph_list(model_json([{'role':'system','content':'Write only one bounded, source-grounded financial section as strict JSON.'},{'role':'user','content':prompt+(f'\nPrior invalid result: {last}' if last else '')}],max_tokens=2600))
  except Exception as exc:last=type(exc).__name__+': '+str(exc)[:180];continue
  count=words(' '.join(paragraphs))
  if count>490:paragraphs=trim_complete_sentences(paragraphs,465,min_words=420);count=words(' '.join(paragraphs))
  all_refs=set().union(*(citation_numbers(p) for p in paragraphs))
  bad=[n for p in paragraphs for n in unsupported_numbers(p,evidence,citation_numbers(p))]
  if 400<=count<=490 and len(paragraphs)>=4 and all_refs and all_refs<=set(refs) and not bad:return {'heading':heading,'paragraphs':paragraphs}
  last=f'{count} words, {len(paragraphs)} paragraphs, citations {sorted(all_refs)}, unsupported numbers {bad[:5]}'
 raise RuntimeError(f'bounded section {index+1} did not pass after four provider attempts: {last}')

def interleaved_extract(sections,target=680):
 buckets=[]
 for section in sections:
  sentences=[]
  for p in section['paragraphs']:sentences.extend(x.strip() for x in re.split(r'(?<=[.!?])\s+',p) if x.strip())
  buckets.append(sentences)
 chosen=[];seen=set();position=0
 while words(' '.join(chosen))<target and any(position<len(x) for x in buckets):
  for bucket in buckets:
   if position>=len(bucket):continue
   sentence=bucket[position];key=' '.join(sentence.casefold().split())
   if key not in seen:chosen.append(sentence);seen.add(key)
   if words(' '.join(chosen))>=target:break
  position+=1
 out=[];part=[];count=0
 for sentence in chosen:
  n=words(sentence)
  if part and count+n>115:out.append(' '.join(part));part=[];count=0
  part.append(sentence);count+=n
 if part:out.append(' '.join(part))
 return trim_complete_sentences(out,750,min_words=620) if words(' '.join(out))>800 else out

def support_material(title,sections):
 faq=[]
 for i,section in enumerate(sections[:5]):
  answer=' '.join(re.split(r'(?<=[.!?])\s+',' '.join(section['paragraphs']))[:2])
  faq.append({'question':f'What should readers understand about {section["heading"].casefold()}?','answer':answer})
 tokens=[]
 for token in re.findall(r'[A-Za-z][A-Za-z-]{4,}',title+' '+' '.join(x['heading'] for x in sections)):
  if token.casefold() not in {x.casefold() for x in tokens} and token.casefold() not in {'about','understand','evidence','subject','readers','which','where','framework','interpreting'}:tokens.append(token)
 glossary=[]
 body=' '.join(' '.join(x['paragraphs']) for x in sections)
 for term in tokens[:8]:
  sentence=next((s for s in re.split(r'(?<=[.!?])\s+',body) if re.search(r'\b'+re.escape(term)+r'\b',s,re.I)),f'{term} is used in this article within the boundaries established by the cited evidence.')
  glossary.append({'term':term.title(),'definition':re.sub(r'\[\[[SI]\d+\|([^]]+)\]\]',r'\1',sentence)[:420]})
 while len(glossary)<8:
  n=len(glossary)+1;glossary.append({'term':f'Evidence boundary {n}','definition':'The limit beyond which the cited material does not support a broader financial conclusion.'})
 return faq,glossary

def visuals(evidence,sections):
 out=[]
 for i,item in enumerate(evidence[:3],1):
  excerpt=re.split(r'(?<=[.!?])\s+',str(item.get('text','')).strip())[0][:360]
  out.append({'type':'table','title':f'Evidence scope {i}: {str(item["title"])[:90]}','caption':f'Categorical scope from {item["name"]}; no unreported quantity is inferred.','source':i,'after_section':sections[min(i*2-1,len(sections)-1)]['heading'],'data':[{'Evidence field':'Document','Documented value':item['title']},{'Evidence field':'Provider','Documented value':item['name']},{'Evidence field':'Reported scope','Documented value':excerpt}]})
 return out

def build_package(kind,item):
 topic=topic_for(kind,item);evidence=discover(topic);title=short_title(item['title']);prefix=' '.join(title.split()[:4])
 headings=[f'{prefix}: {angle.casefold()}' for angle in SECTION_ANGLES]
 sections=[generate_section(title,heading,i,evidence) for i,heading in enumerate(headings)]
 total=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if total>4200:
  excess=total-4150
  for section in reversed(sections):
   if excess<=0:break
   before=words(' '.join(section['paragraphs']));section['paragraphs']=trim_complete_sentences(section['paragraphs'],max(400,before-excess),min_words=390);excess-=before-words(' '.join(section['paragraphs']))
 total=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if not 4000<=total<=4200:raise RuntimeError(f'fresh bounded assembly produced {total} words')
 # Independent hostile review sees the same evidence and cannot be bypassed.
 draft={'sections':sections,'summary':[],'faq':[],'visuals':[]};verify_evidence(draft,evidence)
 summary=interleaved_extract(sections);faq,glossary=support_material(title,sections)
 source_rows=[{'name':x['name'],'title':x['title'],'url':x['url'],'date':'','use':'Evidence for the article section carrying its source token'} for x in evidence]
 slug=re.sub(r'[^a-z0-9]+','-',title.casefold()).strip('-');briefs=[f'{title} {headings[i]} real people place or object directly illustrating this financial subject' for i in (0,4,8)]
 photos=choose_photos(briefs,slug,f'{kind}:{item["id"]}')
 meta=f'{title}: an evidence-grounded Daily Yield guide to mechanisms, affected readers, trade-offs, uncertainty and practical decision boundaries.'
 meta=(meta[:158].rsplit(' ',1)[0]+'.') if len(meta)>158 else meta
 if len(meta)<110:meta+=' Read the cited evidence, limitations and financial context before drawing a conclusion.'
 package={'version':'3.0','title':title,'meta_description':meta[:158].rstrip(' .')+'.','sections':sections,'summary':summary,'faq':faq,'glossary':glossary,'photos':photos,'photo_prompts':briefs,'visuals':visuals(evidence,sections),'sources':source_rows,'internal_links':internal_links(),'low_view_posts':low_exposure_posts(),'entities':[title,item['category']],'geography':['Global','India','Tier-1 markets'],'temporal_coverage':str(dt.datetime.now(IST).date()),'module_headings':{'contents':f'Inside {title}','summary':f'What {title} means','faq':f'Questions about {title}','glossary':f'Terms behind {title}','sources':f'Evidence behind {title}','internal_links':'Continue exploring on Daily Yield','external_sources':'Primary research trail'}}
 validate(package);return package

def build_html(kind,item,package,check_remote_images=True):
 stamp=dt.datetime.now(IST);topic=topic_for(kind,item);title,slug,meta,labels,body=render(package,topic,stamp.strftime('%Y-%m-%d'),stamp.strftime('%H:%M'))
 labels=[item['category'],item.get('evergreen_category') or item['category'],'Master Article','Kushal K. Daga'] if kind=='trending' else [item['category'],'Master Article','Kushal K. Daga']
 first=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I);body=ensure_seo_meta(body,title,meta,first.group(1) if first else '');body=ensure_social_identity(ensure_brand_identity(body));body=ensure_continuous_motion(body);assert_publishable(title,body,labels,check_remote_images=check_remote_images);return title,slug,labels,body

def prepare(kind,slot):
 plan,item=selected(kind,slot);target=package_path(kind,item,plan['date']);package=build_package(kind,item);title,slug,labels,body=build_html(kind,item,package,False);write(target,package);out=ROOT/'scheduled_ready'/f'{plan["date"]}-{kind}-{slot}-{slug}.html';out.parent.mkdir(exist_ok=True);out.write_text(body);write(STATUS,{'status':'PREPARED','engine':'master-v3-fresh','date':plan['date'],'kind':kind,'slot':slot,'topic_id':item['id'],'title':title,'package':str(target.relative_to(ROOT)),'html':str(out.relative_to(ROOT))})

def publish(kind,slot,timed=False):
 write(SOCIAL,[])
 if os.environ.get('MASTER_PUBLICATION_ENABLED','').casefold()!='true':raise RuntimeError('Master publication is not enabled')
 if timed:wait_for_release(MASTER_LIVE[(kind,slot)])
 plan,item=selected(kind,slot);target=package_path(kind,item,plan['date']);package=read(target,{});validate(package);title,slug,labels,body=build_html(kind,item,package,True);result=publish_to_blogger(title,body,labels)
 if not result or not result.get('url'):raise RuntimeError('Blogger did not confirm a live Master URL')
 record={'topic_id':item['id'],'kind':kind,'date':plan['date'],'category':item['category'],'evergreen_category':item.get('evergreen_category') or item['category'],'title':title,'url':result['url'],'published_at':result.get('published') or dt.datetime.now(dt.timezone.utc).isoformat(),'engine':'master-v3-fresh'}
 tracker=read(TRACKER,{'version':1,'published':[]});tracker['publication_enabled']=True
 if not any(x.get('url')==record['url'] or (x.get('topic_id')==item['id'] and x.get('date')==plan['date']) for x in tracker['published']):tracker['published'].append(record)
 write(TRACKER,tracker);history=read(ROOT/'MASTER_TOPIC_HISTORY.json',{'version':1,'items':[]})
 if not any(x.get('url')==record['url'] for x in history['items']):history['items'].append(record)
 write(ROOT/'MASTER_TOPIC_HISTORY.json',history);write(SOCIAL,[{'item_key':f'master-{kind}-{slot}','target_url':record['url'],'content_mode':'post','published_at':record['published_at']}]);write(STATUS,{'status':'PASS','publication_enabled':True,**record});print(record['url'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=('trending','evergreen'),required=True);p.add_argument('--slot',type=int,choices=range(5),required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--publish',action='store_true');p.add_argument('--timed-release',action='store_true');a=p.parse_args()
 try:
  if a.prepare==a.publish:raise RuntimeError('choose exactly one of --prepare or --publish')
  prepare(a.kind,a.slot) if a.prepare else publish(a.kind,a.slot,a.timed_release)
 except Exception as exc:
  write(STATUS,{'status':'FAIL','engine':'master-v3-fresh','kind':a.kind,'slot':a.slot,'error_type':type(exc).__name__,'error':str(exc)[:1500]});raise
if __name__=='__main__':main()
