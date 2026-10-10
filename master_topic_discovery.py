#!/usr/bin/env python3
"""Internet-driven Master Article topic discovery.

No CSV or predetermined article-title queue is used. Stable category definitions
provide search context; live feeds, trend velocity and first-party GSC queries
produce the article candidates. This module never requests a public Daily Yield URL.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, html, json, os, re, urllib.parse
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree
import requests
from master_taxonomy import TRENDING_CATEGORIES, EVERGREEN_CATEGORIES, evergreen_rotation

ROOT=Path(__file__).parent
POOL=ROOT/'MASTER_TREND_POOL.json';PLAN=ROOT/'MASTER_DAILY_PLAN.json';HISTORY=ROOT/'MASTER_TOPIC_HISTORY.json';STATUS=ROOT/'MASTER_DISCOVERY_STATUS.json'
UA='DailyYieldTopicDiscovery/1.0 (dailyyield.official@gmail.com)'
STOP={'the','and','for','with','from','into','after','before','about','amid','over','under','what','why','how','your','this','that','says','could','will','new','latest','today'}

def now():return dt.datetime.now(dt.timezone.utc)
def clean(v):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(v or '')))).strip()
def key(v):return ' '.join(x for x in re.findall(r'[a-z0-9]+',clean(v).casefold()) if x not in STOP)[:180]
def uid(v):return hashlib.sha256(key(v).encode()).hexdigest()[:16]
def read(path,default):
 try:return json.loads(path.read_text())
 except (OSError,json.JSONDecodeError):return default
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def recency(published):
 try:age=max(0,(now()-dt.datetime.fromisoformat(published.replace('Z','+00:00'))).total_seconds()/3600)
 except Exception:age=168
 return max(0,100-age*100/168)
def words(v):return {x for x in re.findall(r'[a-z0-9]{3,}',clean(v).casefold()) if x not in STOP}
def category_fit(text,cat):
 hay=words(text);signals=set()
 for phrase in cat['signals']:signals|=words(phrase)
 return len(hay&signals)/max(1,len(signals))
def parse_date(value):
 from email.utils import parsedate_to_datetime
 try:return parsedate_to_datetime(value).astimezone(dt.timezone.utc).isoformat()
 except Exception:return now().isoformat()

def rss(url,source,category=None):
 out=[]
 try:
  r=requests.get(url,headers={'User-Agent':UA},timeout=35);r.raise_for_status();root=ElementTree.fromstring(r.content)
  ns={'ht':'https://trends.google.com/trending/rss'}
  for rank,item in enumerate(root.findall('.//item')[:30],1):
   title=clean(item.findtext('title'));link=clean(item.findtext('link'));description=clean(item.findtext('description'));published=parse_date(item.findtext('pubDate') or '')
   traffic=clean(item.findtext('ht:approx_traffic',namespaces=ns));m=re.search(r'[\d,.]+',traffic);volume=float(m.group(0).replace(',','')) if m else 0
   if title:out.append({'title':title,'description':description,'url':link,'published':published,'source':source,'rank':rank,'volume':volume,'forced_category':category})
 except Exception:return []
 return out

def google_trends():
 out=[]
 for geo in ('IN','US','GB','CA','AU'):
  out+=rss('https://trends.google.com/trending/rss?geo='+geo,'Google Trends '+geo)
 return out

def category_news():
 out=[]
 for cat in TRENDING_CATEGORIES:
  # Each response is live and recency-sorted. The category signals are broad
  # discovery context, never predetermined article titles.
  query=' OR '.join('"'+x+'"' for x in cat['signals'][:5])
  google='https://news.google.com/rss/search?q='+urllib.parse.quote('('+query+') when:7d')+'&hl=en-IN&gl=IN&ceid=IN:en'
  bing='https://www.bing.com/news/search?format=rss&q='+urllib.parse.quote(query+' finance')
  out+=rss(google,'Google News',cat['label']);out+=rss(bing,'Bing News',cat['label'])
 return out

def gdelt():
 out=[]
 for cat in TRENDING_CATEGORIES:
  query=' OR '.join('"'+x+'"' for x in cat['signals'][:4])
  try:
   r=requests.get('https://api.gdeltproject.org/api/v2/doc/doc',params={'query':'('+query+') finance','mode':'ArtList','maxrecords':25,'format':'json','sort':'HybridRel'},headers={'User-Agent':UA},timeout=45);r.raise_for_status()
   for rank,item in enumerate(r.json().get('articles',[]),1):
    seen=str(item.get('seendate',''));published=now().isoformat()
    if re.fullmatch(r'\d{14}',seen):published=dt.datetime.strptime(seen,'%Y%m%d%H%M%S').replace(tzinfo=dt.timezone.utc).isoformat()
    title=clean(item.get('title'))
    if title:out.append({'title':title,'description':clean(item.get('domain')),'url':item.get('url',''),'published':published,'source':'GDELT','rank':rank,'volume':0,'forced_category':cat['label']})
  except Exception:continue
 return out

def cluster(raw):
 groups=[]
 for item in raw:
  tokens=words(item['title'])
  if len(tokens)<2:continue
  best=None;score=0
  for group in groups:
   other=group['tokens'];similar=len(tokens&other)/max(1,len(tokens|other))
   if similar>score:score=similar;best=group
  if best is not None and score>=.42:
   best['items'].append(item);best['tokens']|=tokens
  else:groups.append({'tokens':tokens,'items':[item]})
 return groups

def classify(text,categories):return max(categories,key=lambda c:category_fit(text,c))
def trend_candidates(raw):
 result=[]
 for group in cluster(raw):
  items=group['items'];title=max(items,key=lambda x:(x.get('volume',0),-x.get('rank',99)))['title'];text=' '.join(x['title']+' '+x.get('description','') for x in items)
  forced=[x.get('forced_category') for x in items if x.get('forced_category')]
  forced_label=max(set(forced),key=forced.count) if forced else None
  cat=next((c for c in TRENDING_CATEGORIES if c['label']==forced_label),None) or classify(text,TRENDING_CATEGORIES)
  source_count=len({x['source'] for x in items});coverage=len(items);fresh=max(recency(x['published']) for x in items);volume=max(x.get('volume',0) for x in items)
  search=min(100,25*(volume>0)+20*(volume>=1000)+20*(volume>=10000)+10*source_count+5*min(5,coverage))
  viral=min(100,source_count*20+coverage*8+max(0,20-min(x.get('rank',30) for x in items)))
  relevance=min(100,35+category_fit(text,cat)*160)
  score=.25*fresh+.25*search+.15*min(100,coverage*15)+.10*viral+.10*relevance+.10*80+.05*80
  result.append({'id':uid(title),'title':title,'category':cat['label'],'evergreen_category':classify(text,EVERGREEN_CATEGORIES)['label'],'recency_score':round(fresh,1),'search_score':round(search,1),'virality_score':round(viral,1),'overall_score':round(score,1),'first_seen':min(x['published'] for x in items),'last_seen':max(x['published'] for x in items),'sources':[{'name':x['source'],'url':x['url'],'published':x['published']} for x in items[:8]],'discovered_from_live_internet':True})
 return result

def weekly():
 raw=google_trends()+category_news()+gdelt();candidates=trend_candidates(raw);history={x.get('id') for x in read(HISTORY,{'items':[]}).get('items',[])}
 selected=[]
 for cat in TRENDING_CATEGORIES:
  rows=sorted((x for x in candidates if x['category']==cat['label'] and x['id'] not in history),key=lambda x:x['overall_score'],reverse=True)[:10]
  selected+=rows
 payload={'status':'PASS' if len(selected)>=35 else 'INSUFFICIENT','generated_at':now().isoformat(),'source_observations':len(raw),'candidate_clusters':len(candidates),'topics':selected[:50]}
 write(POOL,payload);write(STATUS,{'status':payload['status'],'stage':'weekly','generated_at':payload['generated_at'],'selected':len(payload['topics']),'source_observations':len(raw)})
 if len(selected)<35:raise RuntimeError(f'only {len(selected)} unique live trend topics qualified; minimum 35')
 return payload

def gsc_queries():
 required=('GSC_CLIENT_ID','GSC_CLIENT_SECRET','GSC_REFRESH_TOKEN')
 if not all(os.environ.get(x) for x in required):return []
 token=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['GSC_CLIENT_ID'],'client_secret':os.environ['GSC_CLIENT_SECRET'],'refresh_token':os.environ['GSC_REFRESH_TOKEN'],'grant_type':'refresh_token'},timeout=30);token.raise_for_status();access=token.json()['access_token']
 end=dt.date.today()-dt.timedelta(days=1);start=end-dt.timedelta(days=480);site=urllib.parse.quote(os.environ.get('GSC_SITE_PROPERTY','sc-domain:dailyyield.blogspot.com'),safe='')
 body={'startDate':str(start),'endDate':str(end),'dimensions':['query'],'rowLimit':25000}
 r=requests.post(f'https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query',headers={'Authorization':'Bearer '+access},json=body,timeout=60);r.raise_for_status()
 return [{'query':clean(x['keys'][0]),'clicks':x.get('clicks',0),'impressions':x.get('impressions',0),'position':x.get('position',100)} for x in r.json().get('rows',[])]

def evergreen_candidates(categories):
 queries=gsc_queries();out=[]
 for cat in categories:
  matched=[]
  for row in queries:
   fit=category_fit(row['query'],cat)
   if fit:matched.append((fit*50+min(40,row['impressions']/25)+max(0,10-row['position']/10),row))
  matched.sort(reverse=True,key=lambda x:x[0])
  if matched:
   row=matched[0][1];topic=row['query'];demand=min(100,20+row['impressions']/20);gap=min(100,35+row['position'])
  else:
   # Live web fallback: the returned headline/question is the topic, never the
   # category's search phrase itself.
   found=[]
   for signal in cat['signals'][:4]:found+=rss('https://www.bing.com/search?format=rss&q='+urllib.parse.quote(signal+' guide question'),'Bing Search',cat['label'])
   if not found:continue
   topic=found[0]['title'];demand=50;gap=55
  score=.25*demand+.20*90+.15*gap+.15*85+.10*80+.05*60+.05*70+.05*85
  out.append({'id':uid(topic),'title':topic,'category':cat['label'],'overall_score':round(score,1),'demand_score':round(demand,1),'content_gap_score':round(gap,1),'discovered_from_live_internet':True})
 return out

def daily(date=None):
 date=date or dt.date.today();pool=read(POOL,{})
 if len(pool.get('topics',[]))<35:pool=weekly()
 used={x.get('id') for x in read(HISTORY,{'items':[]}).get('items',[])};trending=[]
 for cat in TRENDING_CATEGORIES:
  rows=sorted((x for x in pool['topics'] if x['category']==cat['label'] and x['id'] not in used),key=lambda x:x['overall_score'],reverse=True)
  if not rows:raise RuntimeError('no unused current topic for '+cat['label'])
  trending.append(rows[0])
 evergreen=evergreen_candidates(evergreen_rotation(date.toordinal()))
 if len(evergreen)!=5:raise RuntimeError(f'only {len(evergreen)} evergreen topics qualified; expected 5')
 plan={'status':'READY','publication_enabled':False,'date':str(date),'generated_at':now().isoformat(),'trending':trending,'evergreen':evergreen,'total':10}
 write(PLAN,plan);write(STATUS,{'status':'PASS','stage':'daily','generated_at':plan['generated_at'],'trending':5,'evergreen':5,'publication_enabled':False});return plan

def main():
 p=argparse.ArgumentParser();p.add_argument('--weekly',action='store_true');p.add_argument('--daily',action='store_true');p.add_argument('--date');a=p.parse_args()
 try:
  result=weekly() if a.weekly else daily(dt.date.fromisoformat(a.date) if a.date else None)
  print(json.dumps({'status':result['status'],'topics':len(result.get('topics',[])),'total':result.get('total')},indent=2))
 except Exception as exc:
  write(STATUS,{'status':'FAIL','generated_at':now().isoformat(),'error_type':type(exc).__name__,'error':str(exc)[:1000]});raise
if __name__=='__main__':main()
