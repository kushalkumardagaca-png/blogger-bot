#!/usr/bin/env python3
"""Read Google's indexed-version results; never submit/reset or count API errors as unindexed."""
from __future__ import annotations
import datetime as dt
import json, os, time, urllib.error, urllib.parse, urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
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


def fetch(url, headers, method='GET', body=None, timeout=60):
    data=json.dumps(body).encode() if body is not None else None
    request=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(request,timeout=timeout) as response:
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
        {'inspectionUrl':url,'siteUrl':SITE,'languageCode':'en-US'}, timeout=20)
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


class InspectionPacer:
    def __init__(self):
        self.lock=threading.Lock();self.next_at=0.0
    def wait(self):
        with self.lock:
            now=time.monotonic();pause=max(0,self.next_at-now)
            if pause:time.sleep(pause)
            self.next_at=time.monotonic()+.25  # at most 240 starts/minute


def inspect_inventory(access, urls, budget_seconds=900):
    targets=list(dict.fromkeys(u for u in urls if valid_url(u)))
    results={};pacer=InspectionPacer()
    def snapshot(complete=False):
        rows=[results.get(u,{'url':u,'verdict':'UNKNOWN','coverageState':'',
                            'inspectionDeferred':True,'reason':'Not inspected within this bounded run yet'}) for u in targets]
        report=summarise(rows)
        report['completedInspections']=len(results)
        report['deferredInspections']=len(targets)-len(results)
        report['runComplete']=complete and len(results)==len(targets)
        if not complete:report['status']='IN_PROGRESS'
        elif report['deferredInspections']:report['status']='PARTIAL'
        OUT.write_text(json.dumps(report,indent=1,ensure_ascii=False)+'\n')
        return report
    def work(url):
        pacer.wait()
        try:return inspect(access,url)
        except Exception as exc:
            code=exc.code if isinstance(exc,urllib.error.HTTPError) else None
            return {'url':url,'verdict':'ERROR','coverageState':'','errorType':type(exc).__name__,
                    'httpStatus':code,'error':'HTTP '+str(code) if code else 'inspection could not be completed'}
    snapshot()
    if budget_seconds<=0:return snapshot(True)
    executor=ThreadPoolExecutor(max_workers=4)
    futures={executor.submit(work,u):u for u in targets}
    try:
        for future in as_completed(futures,timeout=budget_seconds):
            url=futures[future];results[url]=future.result()
            if len(results)%25==0:
                snapshot();print(json.dumps({'inspectionProgress':len(results),'targets':len(targets)}),flush=True)
    except FuturesTimeout:
        pass
    finally:
        for future in futures:future.cancel()
        executor.shutdown(wait=False,cancel_futures=True)
    # Running HTTP requests have a 20-second timeout; queued requests are cancelled.
    # A durable local checkpoint survives any later runner timeout.
    return snapshot(True)


def main():
    # A code push needs tests, not another full crawl immediately after a complete
    # measurement. Preserve its original timestamp rather than spending quota.
    if os.environ.get('GITHUB_EVENT_NAME')=='push':
        try:
            recent=json.loads(OUT.read_text())
            stamp=dt.datetime.fromisoformat(recent.get('checkedAt','').replace('Z','+00:00'))
            fresh=dt.datetime.now(dt.timezone.utc)-stamp < dt.timedelta(hours=2)
            if fresh and recent.get('property')==SITE and recent.get('status')=='MEASURED' and recent.get('inspectionErrors',0)==0 and recent.get('unknown',0)==0:
                print('Preserving a recent complete index measurement; no duplicate push-time inspection. Original checkedAt='+recent['checkedAt'])
                return 0
        except (OSError,ValueError,TypeError):pass
    access=search_token();targets=inventory()
    report=inspect_inventory(access,targets,budget_seconds=min(900,max(30,int(os.environ.get('GSC_INSPECTION_BUDGET_SECONDS','900')))))
    print(json.dumps({k:report[k] for k in ('status','urls','indexed','notIndexed','inspectionErrors','unknown','completedInspections','deferredInspections')}))
    return 0

if __name__=='__main__': raise SystemExit(main())
