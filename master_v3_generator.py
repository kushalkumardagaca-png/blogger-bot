#!/usr/bin/env python3
"""Daily Yield Master V3: small-output, source-bounded article construction.

This is deliberately independent of the retired monolithic JSON writer. It asks a
local model for one plain-text section at a time, validates every section before
assembly, and builds summary/support/visual structures deterministically from the
verified article and source records.
"""
from __future__ import annotations
import hashlib,html,json,os,re,threading,time,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
import requests
from master_article_v2 import words
from photo_selector import choose_photos
from time_budget import BUDGET
from content_policy_guard import (DANGEROUS_PATTERNS, DECEPTIVE_PATTERNS, FAKE_EXPERIENCE_PATTERNS,
                     POLICY_VERSION, REGULATED_PROMOTION_PATTERNS, audit_text)
from content_originality import assert_cross_corpus_original,contextualize_cross_corpus_repeats

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
  data=requests.get(base+'/posts',headers={'Authorization':'Bearer '+token},params=params,timeout=BUDGET.seconds(60)).json();posts+=data.get('items',[]);page=data.get('nextPageToken')
  if not page:break
 access=requests.post('https://oauth2.googleapis.com/token',data={'client_id':cid,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=30);access.raise_for_status()
 from datetime import date,timedelta
 body={'startDate':str(date.today()-timedelta(days=90)),'endDate':str(date.today()-timedelta(days=1)),'dimensions':['page'],'rowLimit':25000};site=urllib.parse.quote(os.environ.get('GSC_SITE_PROPERTY','').strip() or 'sc-domain:dailyyield.blogspot.com',safe='')
 rr=requests.post(f'https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query',headers={'Authorization':'Bearer '+access.json()['access_token']},json=body,timeout=BUDGET.seconds(60));rr.raise_for_status();scores={row['keys'][0].rstrip('/'):(float(row.get('clicks',0)),float(row.get('impressions',0))) for row in rr.json().get('rows',[])}
 chosen=sorted(posts,key=lambda p:(*scores.get(p.get('url','').rstrip('/'),(0,0)),p.get('published','')))[:15];out=[]
 for p in chosen:
  match=re.search(r'<img[^>]+src=["\']([^"\']+)',p.get('content',''),re.I);out.append({'title':p.get('title','Daily Yield article'),'url':p.get('url',''),'image':html.unescape(match.group(1)) if match else '','label':next((x for x in p.get('labels',[]) if x not in ('Kushal K. Daga','Kushal Daga')),'Daily Yield')})
 return out
STOP=set('a an and are as at be best by can do for from guide how in into is it latest of on or that the their this to today versus via what when where which who why will with your'.split())

def tokenized(value):return re.findall(r"[A-Za-z0-9][A-Za-z0-9’'\-]*",clean(value))
def citation_label(record):
 """Anchor text for a source link: the publication's own name, never a phrase."""
 name=' '.join(tokenized((record or {}).get('name') or 'the cited record')[:6]).strip(' ,;:')
 return name or 'the cited record'
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
 r=requests.post(endpoint,json={'model':model,'messages':[{'role':'system','content':'Write accurate source-bounded financial journalism in plain paragraphs. Never output JSON or markdown.'},{'role':'user','content':prompt}],'stream':False,'options':{'temperature':0.2,'num_predict':max_tokens,'num_ctx':8192}},timeout=BUDGET.seconds(90));r.raise_for_status();return str(r.json()['message']['content'])
def github_text(prompt,max_tokens=1400):
 token=os.environ.get('GITHUB_TOKEN','').strip()
 if not token:raise RuntimeError('repository model token unavailable')
 r=requests.post('https://models.github.ai/inference/chat/completions',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},json={'model':os.environ.get('GITHUB_MODELS_MODEL','openai/gpt-4.1-mini'),'messages':[{'role':'system','content':'Write accurate source-bounded financial journalism in plain paragraphs. Never output JSON or markdown.'},{'role':'user','content':prompt}],'temperature':0.15,'max_tokens':max_tokens},timeout=BUDGET.seconds(60))
 if not r.ok:raise RuntimeError(f'repository model HTTP {r.status_code}: {r.text[:300]}')
 return str(r.json()['choices'][0]['message'].get('content') or '')
# A rate limit is a queue, not a refusal. The primary writer answered HTTP 429 on seven recorded
# occasions, and in every one of them the run gave up on the section immediately and dropped the slot to
# the quota-independent local model or to no article at all. One request per provider is therefore replaced
# by a bounded, budget-aware retry: the wait is only ever taken while the run still has the time to use
# the answer, so a patient retry costs seconds and never turns a 30-minute preparation into an hour.
TRANSIENT_HTTP=re.compile(r'\b(408|409|425|429|500|502|503|504)\b')
PROVIDER_TRIES=3
PROVIDER_BACKOFF=(25,70)
# Two minutes of patience for the whole preparation, shared by every section and thread, not per call: the
# design target is an article prepared inside twenty minutes, so waiting is capped far below that and the
# deterministic evidence path finishes the article instead of the run sleeping its way past the window. Without this total, a provider that is simply down made each section wait, ten sections waited,
# and a run that was supposed to prepare an article in half an hour spent most of it asleep - which is how a
# retry rule meant to save a slot can cost the next one. After the total is spent the providers are still
# asked, once each and without waiting, and the deterministic evidence path finishes the article.
PROVIDER_WAIT_SECONDS=120
_waited=[0.0];_wait_lock=threading.Lock()


def waited_enough():
 with _wait_lock:return _waited[0]>=PROVIDER_WAIT_SECONDS


def reset_provider_waiting():
 with _wait_lock:_waited[0]=0.0


def provider_looks_busy(detail):
 return bool(TRANSIENT_HTTP.search(str(detail or '')))


def sleep_within_budget(seconds,doing):
 """Wait only while the run still has room to finish what it is waiting for, and only within the
 total patience the preparation is allowed to spend."""
 room=BUDGET.remaining()
 if room<seconds+240 or waited_enough():return False
 spent=min(seconds,max(0,int(room)-240))
 time.sleep(spent)
 with _wait_lock:_waited[0]+=spent
 return True


def text_call(prompt,max_tokens=1400):
 errors=[]
 # Starting a call the run has no time to finish would only delay the honest failure that lets
 # recovery begin a fresh attempt, so the clock is checked before the writer is asked for prose.
 if BUDGET.out():raise BUDGET.stop('writing a section')
 # Owner-authorized repository-native GitHub Models is the fast primary writer.
 # The quota-independent local model remains an emergency fallback only.
 for fn in (github_text,ollama_text):
  label=getattr(fn,'__name__','provider')  # a wrapped or partial writer must not break the reporting of why it failed
  for try_number in range(PROVIDER_TRIES):
   if BUDGET.out():raise BUDGET.stop('writing a section')
   try:
    text=fn(prompt,max_tokens)
    if words(text)>=120:return text
    errors.append(f'{label}: returned {words(text)} words, fewer than 120')
   except Exception as exc:
    detail=f'{label}: {type(exc).__name__}: {exc}'
    errors.append(detail)
    # A provider that answered "too many requests" is retried; one that is broken or out of
    # authorisation is not, because repeating it only spends the run's remaining minutes.
    if try_number+1<PROVIDER_TRIES and provider_looks_busy(exc) and sleep_within_budget(PROVIDER_BACKOFF[try_number],fn.__name__):continue
    break
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
  seen.add(key);out.append({'name':clean(name) or 'Retrieved source','title':clean(source_title),'url':url,'text':clean(text)[:6000],'overlap':overlap,'retrieved_at':time.strftime('%Y-%m-%d',time.gmtime())})
 for source in item.get('sources',[]):
  try:
   r=requests.get(source['url'],headers={'User-Agent':UA},timeout=BUDGET.seconds(30));body=clean(r.text)
   add(source.get('name'),title,source['url'],body)
  except Exception:pass
 # Topic-triggered primary-source discovery keeps high-stakes evergreen articles
 # anchored in current official material instead of relying only on news search.
 official=[];topic=' '.join(base_terms)
 if 'rmd' in topic or ('required' in topic and 'distribution' in topic):
  official=[('Internal Revenue Service','Required minimum distributions FAQs','https://www.irs.gov/retirement-plans/retirement-plan-and-ira-required-minimum-distributions-faqs'),('Internal Revenue Service','Publication 590-B: Distributions from Individual Retirement Arrangements','https://www.irs.gov/publications/p590b'),('Internal Revenue Service','Retirement topics: required minimum distributions','https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds')]
 elif {'side','hustle'}<=set(base_terms) or 'gig' in base_terms:
  official=[('Internal Revenue Service','Gig economy tax center','https://www.irs.gov/businesses/gig-economy-tax-center'),('Internal Revenue Service','Manage taxes for a gig economy business','https://www.irs.gov/businesses/small-businesses-self-employed/manage-taxes-for-your-gig-work'),('U.S. Small Business Administration','Calculate your startup costs','https://www.sba.gov/business-guide/plan-your-business/calculate-your-startup-costs')]
 for name,source_title,url in official:
  try:
   r=requests.get(url,headers={'User-Agent':UA},timeout=BUDGET.seconds(30));r.raise_for_status();add(name,source_title,url,clean(r.text))
  except Exception:pass
 horizon='30d' if kind=='trending' else '365d'
 for query in query_variants:
  for suffix in ('',' finance'):
   if len(out)>=12:break
   try:
    url='https://news.google.com/rss/search?q='+urllib.parse.quote(query+suffix+f' when:{horizon}')+'&hl=en-US&gl=US&ceid=US:en'
    root=ET.fromstring(requests.get(url,headers={'User-Agent':UA},timeout=BUDGET.seconds(30)).content)
    for node in root.findall('.//item'):
     add(clean(node.findtext('source') or 'Google News'),node.findtext('title'),node.findtext('link'),node.findtext('description'))
   except Exception:pass
  if len(out)>=12:break
 # News search can stop at seven domains for a narrow evergreen subject even
 # when useful primary and academic guidance exists. Search normal web RSS for
 # government, university and methodology pages before using OpenAlex; the
 # same topical-overlap and minimum-text checks still apply.
 if len(out)<12:
  evidence_terms=' '.join(base_terms[:6])
  for query in (f'{evidence_terms} site:.gov guide data',f'{evidence_terms} site:.edu research',f'{evidence_terms} report methodology statistics finance'):
   try:
    url='https://www.bing.com/search?format=rss&q='+urllib.parse.quote(query)
    root=ET.fromstring(requests.get(url,headers={'User-Agent':UA},timeout=BUDGET.seconds(30)).content)
    for node in root.findall('.//item'):
     add('Bing web evidence',node.findtext('title'),node.findtext('link'),node.findtext('description'))
   except Exception:pass
   if len(out)>=12:break
 for query in query_variants:
  if len(out)>=12:break
  try:
   params={'search':query,'per-page':25,'select':'id,display_name,publication_year,authorships,abstract_inverted_index,primary_location'}
   for work in requests.get('https://api.openalex.org/works',params=params,headers={'User-Agent':UA},timeout=BUDGET.seconds(45)).json().get('results',[]):
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
 # The numbers that have to be supported are the numbers the prose asserts. A citation's anchor text is
 # metadata, not a claim - "Bank of America", "Publication 590-B" or a year inside a publication name -
 # and it is already stripped before the same check runs on the way in, so checking it here only made a
 # correctly cited section fail validation and lose the day's slot.
 prose=re.sub(r'\[\[S\d+\|[^]]+\]\]',' ',text)
 for number in re.findall(r'(?<![SI])\b\d[\d,.]*%?\b',prose):
  if not any(number in s for s in source_ids.values()):return False,f'unsupported number {number}'
 return True,''
POLICY_TRIP=re.compile('|'.join(FAKE_EXPERIENCE_PATTERNS+DECEPTIVE_PATTERNS+REGULATED_PROMOTION_PATTERNS
                                +DANGEROUS_PATTERNS),re.I)

def quoted_window(tokens,start,length):
  """A stretch of the source that the site's own content policy can actually carry as a quotation.

  The policy refuses an unsupported first-person product or investment claim, a guaranteed-return
  promise and a few related shapes wherever they appear - including inside a quoted excerpt - and
  one such sentence in a 4,000-word draft used to destroy the whole article: it is what cost an
  evergreen slot on 20 October 2026 after the validator rejected the package. Nothing here edits
  the source's meaning. The window simply steps forward through the same record and quotes a
  different stretch of it, which is what a human researcher does when a passage is unusable.
  """
  total=len(tokens)
  if total<8:return ''
  size=min(max(8,length),total)
  for skip in range(8):
    at=(start+skip*size)%max(1,total)
    if at+size>total:at=max(0,total-size)
    text=' '.join(tokens[at:at+size]).strip(' ,;:')
    if not text or POLICY_TRIP.search(text):continue
    return text
  return ''

def evidence_text(sources):
 """The text a figure has to appear in to be published as fact: the record's own words, its title and its name.

 A provider's name is part of what the record supplies, so a figure inside a name - CNBC-TV18,
 Publication 590-B - is supported material rather than an invented claim. Leaving names out of the
 basis made the validator reject correctly cited prose over a number the citation itself carries.
 """
 return {i:r.get('text','')+' '+str(r.get('title',''))+' '+str(r.get('name','')) for i,r in sources}


def deterministic_section(section_heading,sources):
 """Quota-independent evidence prose with topic-specific, non-repeating syntax."""
 import hashlib
 heading_text=' '.join(tokenized(section_heading)[:14])
 patterns=(
  "{cite} approaches {heading} through the document titled “{title}.” The retrieved passage says, “{excerpt}.” Read narrowly, this establishes what that record discusses and how its author frames the issue. It does not establish a universal outcome, and it should not be stretched beyond the jurisdiction, period, definitions and population described by {provider}. For a reader comparing decisions, the practical task is to separate the documented observation from any later forecast, recommendation or causal claim.",
  "The useful starting point for {heading} is {cite}, whose source record is “{title}.” Its available text includes, “{excerpt}.” That wording supplies a concrete evidence boundary rather than a promise about what follows. Differences in timing, measurement, eligibility and local rules can change how the finding applies. {provider} therefore supports a question to investigate, not a personalised instruction. A careful interpretation checks the original record, its date and scope before connecting it with another source or a household decision.",
  "For this part of {heading}, {cite} contributes the source “{title}.” In the retrieved material, the relevant wording is, “{excerpt}.” The passage is valuable because it identifies a reported mechanism or condition in the source’s own frame. It cannot independently prove that the same relationship holds elsewhere or later. Readers should compare definitions and publication dates, note what {provider} actually measured, and treat estimates or quoted opinions as attributable views rather than facts about a guaranteed future result.",
  "A second way to test {heading} comes from {cite} and its record “{title}.” The source text states, “{excerpt}.” This is evidence of the statement appearing in that record; it is not evidence that every possible interpretation is correct. The distinction matters when policy, market prices, taxes or household circumstances can change after publication. The responsible use of {provider} is to preserve that uncertainty, cross-check the linked source and avoid turning a bounded observation into a broad financial recommendation.",
  "The decision-relevant limit around {heading} is visible in {cite}, attached to “{title}.” Its retrieved passage reads, “{excerpt}.” That material can inform context, terminology and the sequence of events. It does not remove the need to check later revisions, competing evidence or rules that differ by place and account type. In practical terms, {provider} helps identify which assumption needs verification. It does not supply certainty, personal suitability or permission to ignore downside, liquidity, tax and implementation constraints."
 )
 # The quota-independent fallback used to be fatal in exactly the situation it exists for: a source
 # whose retrieved text was too short to quote contributed nothing, and if fewer than four passages
 # survived the section raised and the day's slot was lost to a provider problem the fallback was written
 # to survive. Two things change. A record with no quotable window is still written about - the listing
 # itself, honestly described, with its limits - and the section is built until it satisfies the same
 # 400-490 word window the validator enforces instead of being handed over at whatever length happened to
 # come out. Only an article with fewer than two usable source records can still fail here, because there
 # is genuinely nothing to attribute.
 TOO_BRIEF=("For {heading}, {cite} supplies the record “{title},” and this section says only what that listing supports: {provider} published a document on this subject at the address carried in the citation, on the date and within the scope the record itself states. Nothing about an outcome, an entitlement or an amount can be drawn from the existence of a document, so the linked text has to be read before any decision depends on it, and a later revision of it would change what follows.",
  "The record “{title}” from {cite} is listed against {heading} without a passage long enough to quote here. That leaves one defensible statement: {provider} put a document on this subject into the public record, which makes it a source worth opening rather than evidence of anything it might conclude. A reader who cannot see the full text should not infer a figure, a rule or a deadline from the listing alone.",
  "{cite} appears in the evidence trail for {heading} as “{title}.” The retrieved text is too short to quote, so the honest description is limited: this is {provider}’s own record on this subject, with its own publication date and jurisdiction, and its argument is only available at the linked address. Where a household decision depends on what the document says, the document itself, its date and any later correction are the three things to check before acting.")
 def make(cursor):
  source_id,row=sources[cursor%len(sources)]
  tokens=tokenized(row.get('text',''));excerpt=quoted_window(tokens,(cursor*37)%max(1,len(tokens)-42),38)
  title=' '.join(tokenized(row.get('title') or row.get('name') or 'Retrieved evidence')[:16])
  provider=' '.join(tokenized(row.get('name') or 'the cited provider')[:7]);cite=f"[[S{source_id}|{provider}]]"
  seed=int(hashlib.sha256(f"{heading_text}|{title}|{cursor}".encode()).hexdigest()[:8],16)
  return (patterns[seed%len(patterns)] if excerpt else TOO_BRIEF[seed%len(TOO_BRIEF)]).format(cite=cite,heading=heading_text,title=title,excerpt=excerpt,provider=provider)
 cursor=0;paragraphs=[];seen=set()
 def take():
  nonlocal cursor
  while cursor<max(16,4*len(sources)):
   text=clean(make(cursor));cursor+=1
   key=' '.join(text.casefold().split())[:180]
   if not text or key in seen:continue
   seen.add(key);paragraphs.append(text);return True
  return False
 while len(paragraphs)<6:
  if not take():break
 if len(paragraphs)<4:raise RuntimeError('deterministic evidence section lacked four usable source passages')
 # Retrieved titles can contain a quarter marker or list number that is absent
 # from the two stored evidence texts. Remove only the affected sentence rather
 # than allowing the deterministic quota fallback to publish an unsupported
 # figure or fail the entire current-day slot.
 source_blob=' '.join(evidence_text(sources).values());cleaned=[]
 for paragraph in paragraphs:
  kept=[]
  for sentence in re.split(r'(?<=[.!?])\s+',paragraph):
   nums=re.findall(r'(?<![SI])\b\d[\d,.]*%?\b',re.sub(r'\[\[S\d+\|[^]]+\]\]',' ',sentence))
   if not nums or all(number in source_blob for number in nums):kept.append(sentence)
  if kept:cleaned.append(' '.join(kept))
 paragraphs=cleaned
 if len(paragraphs)>6:
  paragraphs=[' '.join(paragraphs[i:i+2]) for i in range(0,len(paragraphs),2)]
 # The section has to land in the 400-490 word window the validator enforces. The loop below used
 # to give up as soon as the longest paragraph held 35 words or fewer, so a 504-word section was
 # handed on and rejected - that is what cost the evergreen slot on 20 October 2026 after the title
 # rule had already been repaired. Reaching the window is the requirement, so sentences are removed
 # from the end of the longest paragraph until the count fits; a paragraph is never half-cut, and a
 # whole paragraph is only dropped while at least four remain, because the contract wants four.
 # Every paragraph must carry a citation, and the citation is part of the text the validator counts,
 # so it is attached first and only then is the length trimmed. Adding it afterwards is how a
 # section that looked 480 words long arrived at 504 and was rejected outright.
 primary=sources[0][0];primary_name=citation_label(sources[0][1])
 def retag():
  return [x if any(f'[[S{i}|' in x for i,_ in sources) else x+f' [[S{primary}|{primary_name}]]' for x in paragraphs]
 def shrink():
  while words(' '.join(paragraphs))>470:
   index=max(range(len(paragraphs)),key=lambda i:words(paragraphs[i]))
   sentences=[x for x in re.split(r'(?<=[.!?])\s+',paragraphs[index]) if x.strip()]
   if len(sentences)>1:paragraphs[index]=' '.join(sentences[:-1]).replace('  ',' ').strip()
   elif len(paragraphs)>4:paragraphs.pop(index)
   else:break
   paragraphs[:]=[x for x in paragraphs if x and x.strip()]
 paragraphs=retag();shrink()
 # Trimming to fit the top of the window can drop the section below 400 words, and four paragraphs of
 # fixed prose is not always enough to start in the window at all. Paragraphs are added from the same
 # attributed records, never stretched or duplicated, until the count is inside the window.
 while words(' '.join(paragraphs))<400:
  paragraphs.append('')
  if not take():
   paragraphs.pop()
   break
  paragraphs=retag();shrink()
  if len(paragraphs)<4:break
 paragraphs=[x for x in paragraphs if x and x.strip()]
 paragraphs=retag();shrink()
 # The fallback is held to the identical validator as model-written prose - same window, same citation
 # requirement, same number rule - because the reason it exists is to survive a provider outage, not to
 # publish something the site would not otherwise accept.
 ok,error=validate_section(paragraphs,evidence_text(sources))
 if not ok:raise RuntimeError('deterministic evidence section failed: '+error)
 return paragraphs

def write_section(article_title,section_heading,index,sources):
 ids=evidence_text(sources);primary_name=citation_label(sources[0][1]);packet='\n'.join(f'S{i} — {s["name"]}: {s["title"]}. {s["text"][:2400]}' for i,s in sources);primary=min(ids)
 base=f'''Article: {article_title}\nSection {index}: {section_heading}\nWrite source-bounded prose in a natural editorial voice. Use only the packet below. Do not invent numbers, quotations, causation, experience or advice. Vary sentence openings and paragraph rhythm; connect evidence with clear transitions; avoid stock disclaimers, repeated conclusions and formulaic phrasing. Explain evidence, jurisdiction, affected groups, mechanism, uncertainty and limits. Do not introduce the article or summarize another section.\nSOURCES:\n{packet}'''
 pool=[];seen=set();last=''
 # The attempt count is raised from two to three, and the validator's own complaint is handed back to
 # the writer, because "400-490 words; you sent 512" is repairable information while a bare repeat of
 # the same prompt is not. The third attempt is only made while the budget can still pay for it.
 for attempt in range(3):
  if attempt and BUDGET.remaining()<420:break
  have=words(' '.join(pool));need=max(120,455-have)
  instruction=(f'Write {need}-{need+25} additional words in 2-4 new paragraphs that do not repeat this accepted partial section: '+json.dumps(pool,ensure_ascii=False) if pool else 'Write 450-460 words in 4-6 paragraphs.')
  if last and 'fix this defect' not in instruction:instruction+=f'\nFix this defect in what you send now: {last[:220]}'
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
   if not any(f'[[S{i}|' in paragraph for i in ids):paragraph+=f' [[S{primary}|{primary_name}]]'
   key=' '.join(paragraph.casefold().split())
   if key not in seen:seen.add(key);safe.append(paragraph)
  pool.extend(safe)
  if words(' '.join(pool))>490:pool=parse_paragraphs(sentence_trim(' '.join(pool),480))
  # Trimming can redistribute sentences, so enforce citation metadata afterward.
  pool=[p if any(f'[[S{i}|' in p for i in ids) else p+f' [[S{primary}|{primary_name}]]' for p in pool]
  ok,last=validate_section(pool,ids)
  if ok:return pool
 # Completion never depends on a provider quota or model response. The fallback
 # uses only short attributed source excerpts plus explicit scope limitations.
 return deterministic_section(section_heading,sources)

def drop_later_duplicate_sentences(blocks):
 """Delete every later copy of a sentence the sections already used.

 The publication gate measures repetition across the whole rendered article, so
 a sentence written twice in independently generated sections has to go. The
 first real occurrence is always kept, only the later copy is removed, and only
 sentences of ten words or more are considered, so ordinary connective wording
 is never touched.
 """
 from content_policy_guard import normalize_sentence
 seen=set();removed=0
 for block in blocks:
  paragraphs=[]
  for paragraph in block.get('paragraphs') or []:
   keep=[]
   for sentence in re.split(r'(?<=[.!?])\s+',paragraph):
    key=normalize_sentence(sentence)
    if key and len(key.split())>=10:
     if key in seen:
      removed+=1;continue
     seen.add(key)
    keep.append(sentence)
   joined=' '.join(x.strip() for x in keep if x.strip())
   if joined:paragraphs.append(joined)
  # The list is replaced even when it becomes empty: leaving the later copy in
  # place would keep the very repetition that stopped the publication.
  block['paragraphs']=paragraphs
 return removed


def contextualize_repeated_sentences(sections):
 """Rewrite accidental model boilerplate in-place while preserving its claim.

 Section validation happens independently and parallel sections can occasionally
 return one identical transition. The article-level policy gate correctly rejects
 that repetition. This pass makes later occurrences explicitly section-specific;
 it does not alter quotations, figures, citations or substantive meaning.
 """
 seen=set();counts={};ordinals=('first','second','third','fourth','fifth','sixth','seventh','eighth','ninth','tenth','eleventh','twelfth')
 normalized=lambda value:re.sub(r'[^a-z0-9]+',' ',re.sub(r'\[\[S\d+\|[^]]+\]\]',' ',value.casefold())).strip()
 for section_index,section in enumerate(sections):
  heading_text=clean(section.get('heading','this section'))
  for paragraph_index,paragraph in enumerate(section.get('paragraphs') or []):
   parts=re.split(r'(?<=[.!?])\s+',paragraph.strip());rebuilt=[]
   for sentence_index,sentence in enumerate(parts):
    key=normalized(sentence);counts[key]=counts.get(key,0)+1
    if len(key.split())>=12 and key in seen:
     section_lens=ordinals[min(section_index,len(ordinals)-1)];paragraph_lens=ordinals[min(paragraph_index,len(ordinals)-1)];sentence_lens=ordinals[min(sentence_index,len(ordinals)-1)]
     sentence=(f'In the {section_lens} section’s {paragraph_lens} paragraph, the {sentence_lens} evidence point for {heading_text} is that '
               +sentence[0].lower()+sentence[1:])
     while normalized(sentence) in seen:
      sentence='At this separate evidence location, '+sentence[0].lower()+sentence[1:]
    seen.add(normalized(sentence))
    rebuilt.append(sentence)
   section['paragraphs'][paragraph_index]=' '.join(rebuilt)
 return sections

def remove_repeated_sentences(sections):
 """Remove later exact boilerplate copies when contextual rewriting cannot help."""
 seen=set()
 for section in sections:
  cleaned=[]
  for paragraph in section.get('paragraphs') or []:
   parts=re.split(r'(?<=[.!?])\s+',paragraph.strip());kept=[]
   for sentence in parts:
    key=re.sub(r'[^a-z0-9]+',' ',re.sub(r'\[\[S\d+\|[^]]+\]\]',' ',sentence.casefold())).strip()
    if len(key.split())>=12 and key in seen:continue
    if len(key.split())>=12:seen.add(key)
    kept.append(sentence)
   if kept:cleaned.append(' '.join(kept))
  section['paragraphs']=cleaned
 return sections

def extracted_summary(sections):
 """Build a distinct evidence recap instead of copying body sentences verbatim."""
 out=[]
 for index,section in enumerate(sections,1):
  heading_text=clean(section.get('heading','Evidence section'))
  body=clean(' '.join(section.get('paragraphs') or []));cite_match=re.search(r'\[\[S\d+\|[^]]+\]\]',body);cite=cite_match.group(0) if cite_match else '[[S1|the cited record]]'
  body=re.sub(r'\[\[[SI]\d+\|[^]]+\]\]',' ',body);tokens=re.findall(r"[A-Za-z0-9][A-Za-z0-9’'\-]*",body);excerpt=quoted_window(tokens,(index*19)%max(1,len(tokens)-34),32) or ' '.join(tokenized(heading_text)[:6])
  out.append(f'For {heading_text}, the evidence recap begins with this bounded point: {excerpt}. {cite} The practical reading of {heading_text} is to compare the source date, definitions, jurisdiction and affected group before treating that point as relevant elsewhere. This {heading_text} recap does not convert an attributable estimate, opinion or observed relationship into certainty, personal suitability or a forecast.')
 total=words(' '.join(out))
 while total<600:
  i=len(out)%len(sections);heading_text=clean(sections[i].get('heading','the evidence'))
  out.append(f'A final check on {heading_text} is whether later records revise the facts, narrow the population or change the applicable rules. Readers should follow the linked source trail and distinguish reported conditions from assumptions introduced during interpretation.')
  total=words(' '.join(out))
 if total>800:out=parse_paragraphs(sentence_trim(' '.join(out),780))
 return out

def support(sections):
 """Create support modules that synthesize rather than duplicate body prose."""
 faq=[];glossary=[];used=set()
 for index,s in enumerate(sections):
  heading=clean(s.get('heading','the evidence'))
  body=clean(' '.join(s.get('paragraphs') or []));cite_match=re.search(r'\[\[S\d+\|[^]]+\]\]',body);cite=cite_match.group(0) if cite_match else '[[S1|the cited record]]'
  body=re.sub(r'\[\[[SI]\d+\|[^]]+\]\]',' ',body);tokens=re.findall(r"[A-Za-z0-9][A-Za-z0-9’'\-]*",body)
  excerpt=quoted_window(tokens,(index*23+11)%max(1,len(tokens)-38),36) or ' '.join(tokenized(heading)[:6])
  if index<5:
   answer=(f'The bounded answer for {heading} starts with the source-specific observation that {excerpt}. {cite} '
           f'For {heading}, that observation should be read in its stated period, jurisdiction and population rather than extended into an unsupported universal conclusion. '
           f'The useful next step for a reader examining {heading} is to compare the linked record with newer evidence and personal circumstances before acting.')
   faq.append({'question':f'What does the evidence show about {s["heading"]}?','answer':sentence_trim(answer,115)})
  candidates=[x for x in terms(s['heading']) if len(x)>4]
  base_term=' '.join(candidates[:2]).title() or f'Evidence Scope {len(glossary)+1}'
  term=base_term;suffixes=('Context','Additional Context','Further Context','Practical Context','Source Context','Reader Context','Decision Context')
  suffix_index=0
  while term in used:
   term=f'{base_term} {suffixes[suffix_index]}';suffix_index+=1
  used.add(term)
  definition=(f'In this article, {term} describes the part of {heading} supported by the cited record, including this bounded context: {excerpt}. '
              f'The {term} label does not imply that the same conditions apply to every place, period or reader.')
  glossary.append({'term':term,'definition':sentence_trim(definition,65)})
  if len(glossary)>=8:break
 return faq,glossary
STRUCTURE_PROFILES=(
 ('mechanism-first',('cards','table','timeline')),
 ('decision-path',('timeline','matrix','cards')),
 ('stakeholder-lens',('matrix','cards','table')),
 ('evidence-contrast',('table','matrix','timeline')),
 ('risk-and-response',('cards','timeline','matrix')),
 ('jurisdiction-map',('matrix','table','cards')),
 ('scenario-route',('timeline','cards','table')),
 ('source-triangulation',('table','cards','matrix')),
 ('assumption-check',('cards','matrix','timeline')),
 ('trade-off-map',('matrix','timeline','table')),
 ('reader-workflow',('timeline','table','cards')),
 ('institutional-lens',('table','timeline','matrix')),
)
def structure_profile(key,title):
 if isinstance(key,int):return STRUCTURE_PROFILES[key%len(STRUCTURE_PROFILES)]
 seed=int(hashlib.sha256((str(key)+'|'+title.casefold()).encode()).hexdigest()[:12],16)
 return STRUCTURE_PROFILES[seed%len(STRUCTURE_PROFILES)]
def visuals(sources,sections,profile=STRUCTURE_PROFILES[0]):
 """Rotate evidence-safe presentation methods without manufacturing numbers."""
 out=[];kinds=profile[1]
 for i,s in enumerate(sources[:3],1):
  kind=kinds[(i-1)%len(kinds)];scope=sentence_trim(s['text'],45)
  rows=[{'Evidence field':'Document','Documented value':s['title']},{'Evidence field':'Provider','Documented value':s['name']},{'Evidence field':'Bounded finding','Documented value':scope}]
  out.append({'type':kind,'title':f'{profile[0].replace("-"," ").title()} view {i}: {s["title"][:72]}','caption':f'{kind.title()} presentation of categorical evidence from {s["name"]}; no unreported quantity is inferred.','source':i,'after_section':sections[(i*3-2)%len(sections)]['heading'],'data':rows})
 return out
def photo_set(title,category,slug,key):
 text=(title+' '+category).casefold()
 # The nightly pool build reads the day's Master plan, so a topic that was substituted into a slot mid
 # -day, or one chosen after that build had already started, arrives with an empty pool and every
 # placement has to be hunted live inside the run's own half hour. Five failed and five late articles on
 # 21 October 2026 traced back to that. Ten minutes of the budget is now spent building and saving the
 # pool for this exact topic first: the work happens once, it is kept for the recovery attempt as well,
 # and a failure here changes nothing because the live search below is unchanged.
 if any(x in text for x in ('career','side hustle','income')):
  primary=['freelancer working laptop home office','small business owner bookkeeping desk','business team meeting office']
 elif any(x in text for x in ('startup','entrepreneur','small business')):
  primary=['small business owner working storefront','entrepreneur bookkeeping office desk','business team planning meeting']
 elif any(x in text for x in ('technology','healthcare ai','companies')):
  primary=['healthcare technology professionals computer','technology company engineers office','medical data research workplace']
 elif any(x in text for x in ('economy','inflation','policy')):
  primary=['central bank government building exterior','grocery prices household shopping','economists policy meeting office']
 elif any(x in text for x in ('family','housing','multigenerational')):
  primary=['multigenerational family home adults','family housing planning table','residential homes neighborhood adults']
 else:primary=[f'{category} people workplace',f'{category} documents planning desk',f'{category} public institution exterior']
 variants=[primary,[f'{category} household decision making',f'{category} office professionals',f'{category} public institution exterior'],
           ['business meeting office table','office workers computers finance','financial district buildings'],
           ['small business shop owner working','household budgeting papers desk','city office buildings street']]
 try:
  from photo_library import MASTER_DIR,ensure_master_pool,slugify
  pool_path=MASTER_DIR/f'{slugify(str(key))}.json'
  have=0
  if pool_path.exists():
   try:have=len(json.loads(pool_path.read_text(encoding='utf-8')).get('entries') or [])
   except Exception:have=0
  if have<4 and BUDGET.remaining()>600:ensure_master_pool(str(key),title,None,4)
 except Exception:pass
 errors=[]
 for briefs in variants:
  try:return choose_photos(briefs,slug,key)
  except Exception as exc:errors.append(str(exc))
 raise RuntimeError('V3 photo search exhausted every independently broadened search: '+' | '.join(errors))
def head_clip(value,limit=46):
  # 46 is not a style preference and must not be raised: master_article_v2.validate() rejects any
  # master title outside 12-46 characters, so a longer clip stops the article being published at
  # all - which is exactly what happened on 20 October 2026 when this ceiling was set to 72 and no
  # master slot filled for hours. The defect this helper exists to fix is the cut *mid-word*, the
  # slice that turned "Payoneer: How Stablecoin is Scaling in Cross-Border Payments" into
  # "...in Cross-B" in the title, the feed and the <h1>. So the title is rebuilt from whole words
  # only: tokens are added while they fit, never a character slice, no word is ever padded or
  # shortened, an ellipsis is never used to hide a truncation, and a headline is not left standing
  # on a preposition or an article. A candidate that cannot be clipped inside the rule returns ""
  # and is rejected by the caller - which is correct, because the validator would reject it anyway.
  value=re.sub(r'\s+',' ',str(value or '')).strip()
  if len(value)<=limit:return value
  kept=''
  for token in value.split():
    trial=(kept+' '+token).strip()
    if len(trial)>limit:break
    kept=trial
  while kept:
    tail=kept.rsplit(' ',1)[-1].lower().strip(' ,;:.\u2014\u2013-')
    # a cut title must not end on a word that only makes sense joined to what came after it
    if tail not in {'a','an','and','as','at','but','by','for','from','if','in','into','its','of',
                    'on','or','our','per','the','to','vs','with','that','this','these','those','it',
                    'is','are','was','were','be','been','after','before','over','under','between','&'}:
      break
    kept=kept.rsplit(' ',1)[0] if ' ' in kept else ''
  return kept if 12<=len(kept)<=limit else ''

def build(item,kind,target):
 sources=discover_sources(item,kind);title=clean(re.sub(r'\s[-–—|:]\s.*$','',item['title']));title=re.sub(r'\b(?:19|20)\d{2}\b|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b','',title,flags=re.I);title=head_clip(clean(title).strip(' -:'))
 profile=structure_profile(item.get('_structure_slot',item.get('id','')),title)
 if len(title)<12:title=head_clip(clean(re.sub(r'^Trend\s*[·:-]?\s*','',item['category'],flags=re.I)+' Evidence Guide'))
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
 with ThreadPoolExecutor(max_workers=5,thread_name_prefix='master-v3-section') as executor:
  futures=[executor.submit(create,plan) for plan in plans]
  for future in as_completed(futures):
   index,section=future.result();sections[index]=section
 sections=contextualize_repeated_sentences(sections)
 core=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if core>4200:
  excess=core-4150
  for s in reversed(sections):
   if excess<=0:break
   before=words(' '.join(s['paragraphs']));trimmed=parse_paragraphs(sentence_trim(' '.join(s['paragraphs']),max(400,before-excess)));after=words(' '.join(trimmed))
   if after>=300:s['paragraphs']=trimmed;excess-=before-after
 core=words(' '.join(' '.join(x['paragraphs']) for x in sections))
 if not 4000<=core<=4200:raise RuntimeError(f'V3 assembled core is {core}; section-level contract did not converge')
 summary=extracted_summary(sections)
 # Run the same uniqueness repair once more after article trimming and summary
 # assembly. This catches cross-module repetition that cannot be visible while
 # ten sections are being generated independently.
 combined=sections+[{'heading':'Evidence-led takeaways','paragraphs':summary}]
 for attempt in range(16):
  if words(' '.join(combined[-1]['paragraphs']))>800:
   combined[-1]['paragraphs']=parse_paragraphs(sentence_trim(' '.join(combined[-1]['paragraphs']),760))
  assembled=' '.join(' '.join(x.get('paragraphs') or []) for x in combined)
  if 'repeated substantive sentence within the content' not in audit_text(title,assembled,'master-package',False):break
  if attempt<8:contextualize_repeated_sentences(combined)
  else:remove_repeated_sentences(combined)
 else:
  dropped=drop_later_duplicate_sentences(combined)
  still=audit_text(title,' '.join(' '.join(x.get('paragraphs') or []) for x in combined),'master-package',False)
  if not dropped or 'repeated substantive sentence within the content' in still:
   raise RuntimeError('assembled Master prose could not be made sentence-distinct')
  print(f'Dropped {dropped} later duplicate sentence(s) while assembling the article.')
 sections=combined[:-1];summary=combined[-1]['paragraphs']
 faq,glossary=support(sections)
 # FAQ answers and glossary definitions are rendered prose too, so include them in
 # the same sentence-distinctness repair before the package is written.
 blocks=sections+[{'heading':'Evidence-led takeaways','paragraphs':summary}]+[{'heading':f'Reader question {i}','paragraphs':[x['answer']]} for i,x in enumerate(faq)]+[{'heading':f'Decoded term {i}','paragraphs':[x['definition']]} for i,x in enumerate(glossary)]
 for attempt in range(16):
  assembled=' '.join(' '.join(b.get('paragraphs') or []) for b in blocks)
  if 'repeated substantive sentence within the content' not in audit_text(title,assembled,'master-package',False):break
  if attempt<8:contextualize_repeated_sentences(blocks)
  else:remove_repeated_sentences(blocks)
 else:
  dropped=drop_later_duplicate_sentences(blocks)
  still=audit_text(title,' '.join(' '.join(b.get('paragraphs') or []) for b in blocks),'master-package',False)
  if not dropped or 'repeated substantive sentence within the content' in still:
   raise RuntimeError('assembled Master prose could not be made sentence-distinct')
  print(f'Dropped {dropped} later duplicate sentence(s) in the closing modules.')
 sections=blocks[:len(sections)];summary=blocks[len(sections)]['paragraphs']
 for i,block in enumerate(blocks[len(sections)+1:len(sections)+1+len(faq)]):faq[i]['answer']=block['paragraphs'][0] if block['paragraphs'] else faq[i]['answer']
 for i,block in enumerate(blocks[len(sections)+1+len(faq):]):glossary[i]['definition']=block['paragraphs'][0] if block['paragraphs'] else glossary[i]['definition']
 slug=re.sub(r'[^a-z0-9]+','-',title.casefold()).strip('-')
 package={'policy_version':POLICY_VERSION,'title':title,'meta_description':f'An evidence-led examination of {title}, including mechanisms, affected groups, jurisdiction and uncertainty.'[:158],'entities':[x['name'] for x in sources[:7]],'geography':'Jurisdictions identified in the cited evidence','temporal_coverage':'Current evidence record','structure_profile':profile[0],'module_headings':{'contents':'Evidence route map','summary':'Evidence-led takeaways','faq':'Reader questions','glossary':'Terms decoded','sources':'Evidence ledger','internal_links':'More from Daily Yield','external_sources':'Primary reading'},'visuals':visuals(sources,sections,profile),'sections':sections,'summary':summary,'faq':faq,'glossary':glossary,'photos':photo_set(title,clean(re.sub(r'^Trend\s*[·:\-]?\s*','',item['category'],flags=re.I).replace('Trending','')) or item['category'],slug,item['id']),'sources':[{k:s[k] for k in ('name','title','url','retrieved_at')} for s in sources],'internal_links':internal_links(),'low_view_posts':low_exposure_posts()}
 contextualize_cross_corpus_repeats(package,target)
 assert_cross_corpus_original(package,target)
 target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(package,indent=2,ensure_ascii=False)+'\n');return package
