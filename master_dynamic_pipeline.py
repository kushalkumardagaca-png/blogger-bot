#!/usr/bin/env python3
"""Prepare or publish one dynamically discovered Master Article.

Live publication is fail-closed behind MASTER_PUBLICATION_ENABLED=true. Preparation
and publication are split so licensed photo assets are committed before Blogger
receives HTML referencing their repository URLs.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re
from pathlib import Path
from zoneinfo import ZoneInfo
from auto_blogger_publisher import publish_to_blogger
from brand_identity import ensure_brand_identity
from continuous_motion import ensure as ensure_continuous_motion
from master_article_v2 import render, validate
from publication_preflight import assert_publishable
from seo_meta import ensure_seo_meta
from social_identity import ensure_social_identity

ROOT=Path(__file__).parent;PLAN=ROOT/'MASTER_DAILY_PLAN.json';PACKAGES=ROOT/'master_packages'/'dynamic';TRACKER=ROOT/'MASTER_AUTOMATION_TRACKER.json';STATUS=ROOT/'MASTER_AUTOMATION_STATUS.json';SOCIAL=ROOT/'social_events.json';IST=ZoneInfo('Asia/Kolkata')

def read(path,default):
 try:return json.loads(path.read_text())
 except (OSError,json.JSONDecodeError):return default
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def selected(kind,slot):
 plan=read(PLAN,{})
 if plan.get('status')!='READY':raise RuntimeError('daily dynamic Master plan is not READY')
 if plan.get('date')!=str(dt.datetime.now(IST).date()):raise RuntimeError('daily dynamic Master plan is stale')
 rows=plan.get(kind,[])
 if not 0<=slot<len(rows):raise RuntimeError(f'{kind} slot {slot} is unavailable')
 return plan,rows[slot]
def topic_for(kind,item):
 evergreen=item.get('evergreen_category') if kind=='trending' else item['category']
 return {'#':'dynamic-'+item['id'],'Punchy Title':item['title'],'Video Idea':item['title'],'Category':evergreen,'Trending Category':item.get('category') if kind=='trending' else ''}
def package_path(kind,item):return PACKAGES/f"{dt.datetime.now(IST).date()}-{kind}-{item['id']}.json"
def build_html(kind,item,package):
 stamp=dt.datetime.now(IST);topic=topic_for(kind,item);title,slug,meta,labels,body=render(package,topic,stamp.strftime('%Y-%m-%d'),stamp.strftime('%H:%M'))
 if kind=='trending':labels=[item['category'],item['evergreen_category'],'Master Article','Kushal K. Daga']
 else:labels=[item['category'],'Master Article','Kushal K. Daga']
 first=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I);body=ensure_seo_meta(body,title,meta,first.group(1) if first else '');body=ensure_social_identity(ensure_brand_identity(body));body=ensure_continuous_motion(body);assert_publishable(title,body,labels);return title,slug,meta,labels,body

def prepare(kind,slot):
 from prepare_master_article import build_package
 plan,item=selected(kind,slot);target=package_path(kind,item);package=build_package(topic_for(kind,item),target);validate(package);title,slug,meta,labels,body=build_html(kind,item,package)
 out=ROOT/'scheduled_ready'/f'{plan["date"]}-{kind}-{slot}-{slug}.html';out.parent.mkdir(exist_ok=True);out.write_text(body)
 write(STATUS,{'status':'PREPARED','publication_enabled':False,'date':plan['date'],'kind':kind,'slot':slot,'topic_id':item['id'],'title':title,'package':str(target.relative_to(ROOT)),'html':str(out.relative_to(ROOT))});print(target)

def publish(kind,slot):
 if os.environ.get('MASTER_PUBLICATION_ENABLED','').casefold()!='true':raise RuntimeError('Master publication remains intentionally paused; set MASTER_PUBLICATION_ENABLED=true only after owner activation')
 plan,item=selected(kind,slot);target=package_path(kind,item)
 if not target.exists():raise RuntimeError('validated prepared package is absent')
 package=read(target,{});validate(package);title,slug,meta,labels,body=build_html(kind,item,package);res=publish_to_blogger(title,body,labels)
 if not res or not res.get('url'):raise RuntimeError('Blogger did not confirm a live Master Article URL')
 tracker=read(TRACKER,{'version':1,'published':[]});record={'topic_id':item['id'],'kind':kind,'date':plan['date'],'category':item['category'],'evergreen_category':item.get('evergreen_category') or item['category'],'title':title,'url':res['url'],'published_at':res.get('published') or dt.datetime.now(dt.timezone.utc).isoformat()};tracker['published'].append(record);write(TRACKER,tracker)
 history=read(ROOT/'MASTER_TOPIC_HISTORY.json',{'version':1,'items':[]});history['items'].append(record);write(ROOT/'MASTER_TOPIC_HISTORY.json',history);write(SOCIAL,[{'item_key':f'master-{kind}-{slot}','target_url':res['url'],'content_mode':'post','published_at':record['published_at']}]);write(STATUS,{'status':'PASS','publication_enabled':True,**record});print(res['url'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=('trending','evergreen'),required=True);p.add_argument('--slot',type=int,choices=range(5),required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--publish',action='store_true');a=p.parse_args()
 try:
  if a.prepare==a.publish:raise RuntimeError('choose exactly one of --prepare or --publish')
  (prepare if a.prepare else publish)(a.kind,a.slot)
 except Exception as exc:write(STATUS,{'status':'FAIL','publication_enabled':os.environ.get('MASTER_PUBLICATION_ENABLED','').casefold()=='true','kind':a.kind,'slot':a.slot,'error_type':type(exc).__name__,'error':str(exc)[:1000]});raise
if __name__=='__main__':main()
