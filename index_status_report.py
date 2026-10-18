#!/usr/bin/env python3
"""Read Google's indexed-version results; never submit/reset or count API errors as unindexed."""
from __future__ import annotations
import datetime as dt
import json, os, time, urllib.error, urllib.parse, urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'INDEX_STATUS_REPORT.json'
SITE = 'sc-domain:dailyyield.blogspot.com'
BLOG = 'https://dailyyield.blogspot.com'


def required(name):
    value=os.environ.get(name,'').strip()
    if not value: raise RuntimeError('missing required secret: '+name)
    return value


def fetch(url, headers, method='GET', body=None):
    data=json.dumps(body).encode() if body is not None else None
    request=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(request,timeout=60) as response:
        raw=response.read()
        return json.loads(raw) if raw else {}


def oauth(prefix):
    form=urllib.parse.urlencode({'client_id':required(prefix+'_CLIENT_ID'),
        'client_secret':required(prefix+'_CLIENT_SECRET'),'refresh_token':required(prefix+'_REFRESH_TOKEN'),
        'grant_type':'refresh_token'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=form,method='POST'),timeout=30) as response:
        return json.load(response)['access_token']


def search_token(): return oauth('GSC')


def valid_url(value):
    try:
        parsed=urllib.parse.urlparse(str(value))
        return parsed.scheme=='https' and parsed.hostname=='dailyyield.blogspot.com' and not parsed.username and not parsed.password
    except ValueError:
        return False


def inventory():
    # A Search Console property label is not a URL. The homepage is a real URL.
    urls=[BLOG+'/']
    if all(os.environ.get('BLOGGER_'+s) for s in ('CLIENT_ID','CLIENT_SECRET','REFRESH_TOKEN','BLOG_ID')):
        access=oauth('BLOGGER')
        base='https://www.googleapis.com/blogger/v3/blogs/'+required('BLOGGER_BLOG_ID')
        for kind in ('pages','posts'):
            page=''
            while True:
                params={'maxResults':'50','fetchBodies':'false','status':'live','fields':'items(url),nextPageToken'}
                if page: params['pageToken']=page
                data=fetch(base+'/'+kind+'?'+urllib.parse.urlencode(params),{'Authorization':'Bearer '+access})
                urls.extend(row.get('url','') for row in data.get('items',[]))
                page=data.get('nextPageToken','')
                if not page: break
    else:
        # Feed reads, not public page renders. Honour actual pagination size.
        for kind in ('pages','posts'):
            start=1
            while True:
                data=fetch(f'{BLOG}/feeds/{kind}/default?alt=json&max-results=25&start-index={start}',{})
                entries=data.get('feed',{}).get('entry',[])
                if not entries: break
                urls.extend(next((x.get('href','') for x in e.get('link',[]) if x.get('rel')=='alternate'),'') for e in entries)
                start+=len(entries)
    return list(dict.fromkeys(u for u in urls if valid_url(u) and not u.endswith('/p/share-market_0718113516.html')))


def inspect(access,url):
    if not valid_url(url): raise ValueError('inspection target is not a valid Daily Yield HTTPS URL')
    result=fetch('https://searchconsole.googleapis.com/v1/urlInspection/index:inspect',
        {'Authorization':'Bearer '+access,'Content-Type':'application/json'},'POST',
        {'inspectionUrl':url,'siteUrl':SITE,'languageCode':'en-US'})
    status=result.get('inspectionResult',{}).get('indexStatusResult') or {}
    return {'url':url,'verdict':status.get('verdict','UNKNOWN'),'coverageState':status.get('coverageState',''),
            'lastCrawlTime':status.get('lastCrawlTime',''),'googleCanonical':status.get('googleCanonical',''),
            'pageFetchState':status.get('pageFetchState','')}


def summarise(rows):
    indexed=[r for r in rows if r.get('verdict')=='PASS']
    failed=[r for r in rows if r.get('verdict')=='ERROR']
    unknown=[r for r in rows if r.get('verdict')=='UNKNOWN']
    not_indexed=[r for r in rows if r.get('verdict') in ('FAIL','NEUTRAL')]
    return {'checkedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'property':SITE,
        'status':'UNAVAILABLE' if rows and len(failed)==len(rows) else ('PARTIAL' if failed or unknown else 'MEASURED'),
        'urls':len(rows),'indexed':len(indexed),'notIndexed':len(not_indexed),
        'inspectionErrors':len(failed),'unknown':len(unknown),
        'byCoverageState':Counter(r.get('coverageState') or 'unknown' for r in rows if r.get('verdict')!='ERROR').most_common(),
        'notIndexedUrls':not_indexed,'errors':failed,'rows':rows,
        'resultType':'Google indexed version, not a live-page availability test',
        'limits':'Not indexed is not an AdSense refusal. An API error is unknown, never evidence of non-indexing. Redirect results may describe an old crawl.',
        'syntheticViews':0,'publicDailyYieldRequests':0}


def main():
    access=search_token();rows=[]
    for url in inventory():
        try: rows.append(inspect(access,url))
        except Exception as exc:
            code=exc.code if isinstance(exc,urllib.error.HTTPError) else None
            rows.append({'url':url,'verdict':'ERROR','coverageState':'','errorType':type(exc).__name__,
                         'httpStatus':code,'error':'HTTP '+str(code) if code else 'inspection could not be completed'})
        time.sleep(.15)
    report=summarise(rows);OUT.write_text(json.dumps(report,indent=1,ensure_ascii=False)+'\n')
    print(json.dumps({k:report[k] for k in ('status','urls','indexed','notIndexed','inspectionErrors','unknown')}))
    return 0

if __name__=='__main__': raise SystemExit(main())
