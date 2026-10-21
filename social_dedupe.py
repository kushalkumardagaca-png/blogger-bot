#!/usr/bin/env python3
"""Fresh durable-state dedupe. A failed check defers posting, never permits a blind repeat."""
from __future__ import annotations
import argparse,datetime as dt,json,subprocess,sys,urllib.parse,urllib.request,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
IST=dt.timezone(dt.timedelta(hours=5,minutes=30))
RAW='https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/{platform}_tracker.json'


def fresh_tracker(platform):
    name=platform+'_tracker.json'
    if (ROOT/'.git').exists():
        subprocess.run(['git','fetch','--quiet','origin','main'],cwd=ROOT,check=True,capture_output=True,timeout=60)
        text=subprocess.run(['git','show','origin/main:'+name],cwd=ROOT,check=True,capture_output=True,text=True,timeout=20).stdout
        return json.loads(text)
    request=urllib.request.Request(RAW.format(platform=platform)+'?fresh='+str(time.time_ns()),headers={'Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)


def target_key(url,kind='post'):
    parts=urllib.parse.urlsplit(str(url))
    # Article query/fragment variants are the same article. A page's selected
    # section may be an intentional resource destination (e.g. #spotlight).
    return urllib.parse.urlunsplit((parts.scheme.lower(),parts.netloc.lower(),parts.path.rstrip('/'),'',parts.fragment if kind=='page' else ''))


def already_posted(platform,url,kind='post',now=None):
    current=(now or dt.datetime.now(IST)).date()
    target=target_key(url,kind)
    rows=fresh_tracker(platform).get('published',[])
    for row in rows:
        if target_key(row.get('url',''),kind)!=target:continue
        if kind!='page':return True
        if row.get('kind')!='page':continue
        try:day=dt.datetime.fromisoformat(row.get('published_at','').replace('Z','+00:00')).astimezone(IST).date()
        except (ValueError,TypeError):raise RuntimeError('matching resource history has an invalid date; refusing a blind repeat')
        if day==current:return True
    return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--platform',required=True,choices=('facebook','bluesky','mastodon'))
    parser.add_argument('--url',required=True);parser.add_argument('--content-mode',choices=('post','page'),default='post')
    args=parser.parse_args()
    try:posted=already_posted(args.platform,args.url,args.content_mode)
    except Exception as exc:
        print('DEFER: unable to check durable social history ('+type(exc).__name__+'); recovery can retry safely.',file=sys.stderr)
        return 75
    if posted:print('skip: this destination is already covered on '+args.platform);return 78
    print('clear: destination is not already covered on '+args.platform);return 0

if __name__=='__main__':raise SystemExit(main())
