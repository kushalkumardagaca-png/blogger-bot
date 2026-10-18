#!/usr/bin/env python3
"""Table 3 evidence: authenticated GET-only Blogger audit + bounded diagnostics.

Never modifies Blogger, installs tags, resets search, sends analytics events,
changes ads, or represents an automated check as a human financial review.
"""
from __future__ import annotations
import concurrent.futures,datetime as dt,hashlib,html,json,os,re,time
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import urlparse,unquote,urlencode
import requests
from bs4 import BeautifulSoup
from content_policy_guard import audit_text,DISCLOSURE_MARKER
from site_change_control import policy,is_frozen

ROOT=Path(__file__).resolve().parent
BLOG='https://dailyyield.blogspot.com'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36 DailyYield-Diagnostic/1.0'
NOW=lambda:dt.datetime.now(dt.timezone.utc).isoformat()


def load(name,default=None):
    try:return json.loads((ROOT/name).read_text())
    except (OSError,ValueError):return {} if default is None else default


def save(name,data):
    (ROOT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')


def oauth(prefix):
    keys=[os.environ.get(prefix+'_'+x,'') for x in ('CLIENT_ID','CLIENT_SECRET','REFRESH_TOKEN')]
    if not all(keys):raise RuntimeError('missing '+prefix+' reporting credentials')
    response=requests.post('https://oauth2.googleapis.com/token',data=dict(zip(('client_id','client_secret','refresh_token'),keys),grant_type='refresh_token'),timeout=30)
    if not response.ok:raise RuntimeError(prefix+' authorization HTTP '+str(response.status_code))
    return response.json()['access_token']


class BloggerReader:
    def __init__(self):
        self.base='https://www.googleapis.com/blogger/v3/blogs/'+os.environ['BLOGGER_BLOG_ID']
        self.headers={'Authorization':'Bearer '+oauth('BLOGGER')}
        self.reads=0
    def get(self,path='',params=None):
        if not (path=='' or re.fullmatch(r'/(?:posts|pages)(?:/[0-9]+)?',path)):
            raise ValueError('not an approved Blogger read path')
        for attempt in range(3):
            response=requests.get(self.base+path,headers=self.headers,params=params,timeout=90)
            self.reads+=1
            if response.status_code not in (429,500,502,503,504):break
            time.sleep(2*(attempt+1))
        if not response.ok:raise RuntimeError('Blogger read HTTP '+str(response.status_code))
        return response.json()
    def collect(self,kind,status='live',bodies=True):
        page='';out={}
        while True:
            params={'maxResults':'50','fetchBodies':str(bodies).lower()}
            if kind=='posts':params['status']=status
            if page:params['pageToken']=page
            data=self.get('/'+kind,params)
            for row in data.get('items',[]):out[row['id']]=row
            page=data.get('nextPageToken','')
            if not page:return list(out.values())


def page_source():
    # One diagnostic source read. No JavaScript, ads, tracking or links execute.
    try:response=requests.get(BLOG+'/',headers={'User-Agent':UA},timeout=50)
    except requests.RequestException as exc:return {'status':'UNAVAILABLE','httpStatus':0,'errorType':type(exc).__name__},''
    if response.status_code!=200:return {'status':'UNAVAILABLE','httpStatus':response.status_code},''
    source=response.text;soup=BeautifulSoup(source,'html.parser')
    scripts=soup.find_all('script');script_text='\n'.join(x.get_text() for x in scripts)
    srcs=[x.get('src','') for x in scripts if x.get('src')]
    tag_ids=sorted(set(re.findall(r'\bG-[A-Z0-9]{6,}\b',script_text+'\n'+'\n'.join(srcs))))
    gtms=sorted(set(re.findall(r'\bGTM-[A-Z0-9]+\b',script_text+'\n'+'\n'.join(srcs))))
    configs=re.findall(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]([^'\"]+)",script_text)
    adsense=sorted(set(re.findall(r'ca-pub-[0-9]+',source)))
    links=[{'text':x.get_text(' ',strip=True)[:100],'href':x.get('href','')} for x in soup.find_all('a',href=True)]
    meta={x.get('name') or x.get('property'):x.get('content','') for x in soup.find_all('meta') if x.get('name') or x.get('property')}
    consent_scripts=[x.get_text() for x in scripts if 'dy-consent' in x.get_text() and ('consent' in x.get_text() or 'localStorage' in x.get_text())]
    # Needed for offline replay/fact review only; never committed as live content.
    Path('/tmp/dy-table3-home.html').write_text(source)
    Path('/tmp/dy-table3-consent-scripts.json').write_text(json.dumps(consent_scripts))
    return {'status':'OBSERVED','httpStatus':200,'sourceSha256':hashlib.sha256(source.encode()).hexdigest(),
        'ga4IdsObserved':tag_ids,'tagManagerIdsObserved':gtms,'gtagConfigDestinations':configs,
        'analyticsLoaderSources':[u for u in srcs if re.search(r'googletagmanager|google-analytics|analytics\.google',u,re.I)],
        'adSensePublisherIds':adsense,'adsenseAccountMeta':meta.get('google-adsense-account',''),
        'consentScriptCount':len(consent_scripts),'hasConsentDefaults':bool(re.search(r"['\"]consent['\"]\s*,\s*['\"]default['\"]",script_text)),
        'certifiedConsentSignalsObserved':bool(re.search(r'fundingchoicesmessages|googlefc|__tcfapi|consent\.cookiebot|cdn\.cookielaw',source,re.I)),
        'reportAbuseLinks':[x for x in links if 'report abuse' in x['text'].lower() or ('blogger.com' in x['href'] and 'report' in x['href'])],
        'policyNavigation':{p:any(p in x['href'] for x in links) for p in ('/p/about-us_02080501126.html','/p/contact-us_01883938366.html','/p/privacy-policy.html','/p/disclaimer.html','/p/terms-and-conditions.html')},
        'scriptsExecuted':False,'accountApprovalVisible':False,
        'limits':'HTML observation is not proof of a collecting GA4 property or certified consent. No live visitor session was manufactured.'},source


def head_check(row):
    url=row['url'];out={'url':url,'oldGoogleCoverage':row.get('coverageState'),'oldLastCrawl':row.get('lastCrawlTime')}
    if urlparse(url).hostname!='dailyyield.blogspot.com':return {**out,'status':'INVALID_TARGET_SKIPPED'}
    for name,ua in [('desktop',UA),('crawlerUA','Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)')]:
        try:
            response=requests.head(url,headers={'User-Agent':ua},allow_redirects=True,timeout=20)
            out[name]={'httpStatus':response.status_code,'finalUrl':response.url,'redirects':[{'status':x.status_code,'from':x.url,'to':x.headers.get('Location','')} for x in response.history]}
        except requests.RequestException as exc:out[name]={'status':'UNKNOWN','errorType':type(exc).__name__}
    codes=[out[k].get('httpStatus') for k in ('desktop','crawlerUA')]
    out['status']='CURRENTLY_REACHABLE' if codes==[200,200] else 'NEEDS_RECHECK'
    out['method']='HEAD only; no page scripts; simulated user-agent is not a real Google crawl'
    return out


def editorial(post):
    soup=BeautifulSoup(post.get('content',''),'html.parser')
    for selector in ('script','style','noscript','template','.dy2-summary','.dy2-faq','.dy2-glossary','.dy2-links','.dy2-low','.dy2-follow','#dyPageFamily','.dy-policy-disclosure','.dy-related','.dy-context'):
        for node in soup.select(selector):node.decompose()
    if 'News' in post.get('labels',[]):
        selected=soup.select('p.fbk-description,p.fbk-context')
        if selected:return '<article>'+''.join(str(x) for x in selected)+'</article>'
    node=soup.select_one('article.dy2')
    return str(node or soup)


def pool_evidence():
    registry=load('PHOTO_USAGE_REGISTRY.json',{}).get('items',[])
    paths=list((ROOT/'photo_library').glob('**/*.json'))
    if not paths:
        paths=list((ROOT/'photo_pools').glob('**/*.json'))
    # Discover actual pool paths without treating status or article JSON as photos.
    from photo_library import MASTER_DIR,NEWS_DIR
    paths=list(MASTER_DIR.glob('*.json'))+list(NEWS_DIR.glob('*.json'))
    pool_rows=[];entries=[]
    for p in paths:
        d=json.loads(p.read_text());items=d.get('entries',[]);entries+=items
        pool_rows.append({'pool':str(p.relative_to(ROOT)),'type':'news' if p.parent==NEWS_DIR else 'master',
                          'count':len(items),'target':d.get('target'),'title':d.get('title','')[:100]})
    by_url={}
    for record in registry+entries:
        for key in ('url','original_url','download_url'):
            if record.get(key):by_url[html.unescape(record[key])]=record
    return pool_rows,by_url


def corpus_audit(posts,pages):
    flags=[];missing_disclosure=[];duplicates=[];fingerprints=defaultdict(list)
    photos=[];rights_review=[];fact_queue=[]
    pools,image_records=pool_evidence()
    for post in posts:
        content=post.get('content','');body=editorial(post);plain=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
        issues=[x for x in audit_text(post.get('title',''),body,'stored-live-audit',require_disclosure=False) if x!='insufficient sentence-level originality']
        if issues:flags.append({'id':post['id'],'url':post.get('url'),'title':post.get('title'),'issues':sorted(set(issues))})
        if DISCLOSURE_MARKER not in content:missing_disclosure.append({'id':post['id'],'url':post.get('url')})
        if len(plain.split())>100:
            key=hashlib.sha256(re.sub(r'\W+','',plain.casefold()).encode()).hexdigest();fingerprints[key].append({'id':post['id'],'url':post.get('url'),'title':post.get('title')})
        soup=BeautifulSoup(content,'html.parser');master=soup.select_one('article.dy2')
        if master:
            pictures=master.select('figure img[src]')
            photos.append({'id':post['id'],'url':post.get('url'),'published':post.get('published'),'editorialPhotographs':len(pictures),'required':10,'matchesRequiredCount':len(pictures)==10})
        for figure in soup.find_all('figure'):
            img=figure.find('img',src=True)
            if not img:continue
            src=html.unescape(img['src']);record=image_records.get(src,{})
            caption=figure.find('figcaption');links=[x.get('href','') for x in figure.find_all('a',href=True)]
            license_name=record.get('license') or record.get('licence') or ''
            license_url=record.get('license_url') or record.get('licence_url') or ''
            source=record.get('source_page') or ''
            evidence=bool(license_name and license_url and source and (record.get('creator') or record.get('artist')))
            if not (evidence and caption and img.get('alt','').strip()):
                rights_review.append({'postId':post['id'],'url':post.get('url'),'image':src,'altPresent':bool(img.get('alt','').strip()),'captionPresent':bool(caption),'metadataMatched':bool(record),'licenceRecordComplete':evidence,'captionLinks':links[:3]})
        if len(fact_queue)<6:
            sources=[]
            for a in soup.select('a.fbk-src[href],.dy2-links a[href]'):
                link=a.get('href','');host=urlparse(link).hostname or ''
                if host and host!='dailyyield.blogspot.com' and link not in sources:sources.append(link)
            statements=re.split(r'(?<=[.!?])\s+',plain)
            claims=[x for x in statements if re.search(r'\d|\b(?:tax|return|rate|deficit|inflation|guarantee)\b',x,re.I) and 50<len(x)<650][:4]
            fact_queue.append({'id':post['id'],'url':post.get('url'),'title':post.get('title'),'published':post.get('published'),'claimsForSourceReview':claims,'linkedSources':sources[:12]})
    for values in fingerprints.values():
        if len(values)>1:duplicates.append(values)
    identity=[]
    for page in pages:
        soup=BeautifulSoup(page.get('content',''),'html.parser')
        for node in soup.select('script,style,template'):node.decompose()
        text=soup.get_text(' ',strip=True)
        identity.append({'url':page.get('url'),'title':page.get('title'),'retiredInitialsFound':bool(re.search(r'Kushal\s+K\.?\s+Daga',text)),
            'unrelatedAliasFound':'Kushal Jain' in text,'claimsManualReview':bool(re.search(r'(?:personally|manually) (?:reviewed|approved) by Kushal',text,re.I)),
            'privacyMentionsAnalytics':'analytics' in text.casefold(),
            'privacyAnalyticsSentences':[x[:700] for x in re.split(r'(?<=[.!?])\s+',text) if 'analytics' in x.casefold()][:5]})
    return {'checkedAt':NOW(),'mode':'RAW_STORED_CONTENT_READ_ONLY','postsScanned':len(posts),'pagesScanned':len(pages),
        'automatedPolicyFlags':flags,'missingDisclosure':missing_disclosure,'exactEditorialDuplicateGroups':duplicates,
        'identityPages':identity,'factReviewSample':fact_queue,
        'financialFactCheckLimit':'Automated lexical/source checks are not a qualified human review of every factual claim. No claim of personal review by Kushal is made.',
        'siteWrites':0}, {'checkedAt':NOW(),'masterPhotoCounts':photos,'masterCountMismatches':sum(not r['matchesRequiredCount'] for r in photos),
        'licenceEvidenceNeedsReview':rights_review,'licenceEvidenceNeedsReviewCount':len(rights_review),'pools':pools,
        'newsPoolsBelow40':[p for p in pools if p['type']=='news' and p['count']<40],
        'masterPoolsBelow10':[p for p in pools if p['type']=='master' and p['count']<10],
        'geminiPhotoSelectionEnabled':False,'limits':'Metadata/caption audit, not a guarantee of copyright ownership. Missing evidence is a review item, not proof of infringement. No old photos changed.'}


def analytics_audit(observed):
    result={'checkedAt':NOW(),'siteTagsChanged':False,'newCollectionEnabled':False,'dataSubmitted':False,
            'observedGa4Ids':observed.get('ga4IdsObserved',[]),'observedTagManagerIds':observed.get('tagManagerIdsObserved',[]),
            'privatePropertyIdConfigured':bool(os.environ.get('GA4_PROPERTY_ID','').strip()),'status':'NOT_CONNECTED',
            'readers':None,'returningReaders':None,'ownerStep':'Do not install tags during freeze. Only an existing collection/report permission may be connected.'}
    prefix='GA4' if all(os.environ.get('GA4_'+x) for x in ('CLIENT_ID','CLIENT_SECRET','REFRESH_TOKEN')) else 'GSC'
    try:access=oauth(prefix)
    except Exception as exc:return {**result,'status':'NO_EXISTING_ANALYTICS_AUTH','detail':type(exc).__name__}
    headers={'Authorization':'Bearer '+access}
    response=requests.get('https://analyticsadmin.googleapis.com/v1beta/accountSummaries',headers=headers,timeout=40)
    result['adminReadHttpStatus']=response.status_code
    if not response.ok:
        return {**result,'status':'ANALYTICS_READ_PERMISSION_UNAVAILABLE','detail':'Current authorised token cannot list Analytics properties; no permission grant or installation was attempted.'}
    configured=os.environ.get('GA4_PROPERTY_ID','').strip();matching=[]
    summaries=[p for a in response.json().get('accountSummaries',[]) for p in a.get('propertySummaries',[])]
    for row in summaries:
        name=row.get('property','');display=row.get('displayName','')
        if not (name==('properties/'+configured) or 'daily yield' in display.casefold() or 'dailyyield' in display.casefold()):continue
        streams=requests.get('https://analyticsadmin.googleapis.com/v1beta/'+name+'/dataStreams',headers=headers,timeout=40)
        if not streams.ok:continue
        for stream in streams.json().get('dataStreams',[]):
            data=stream.get('webStreamData',{})
            if urlparse(data.get('defaultUri','')).hostname=='dailyyield.blogspot.com':matching.append((name,data))
    if len(matching)!=1:return {**result,'status':'NO_UNAMBIGUOUS_EXISTING_SITE_PROPERTY','matchingProperties':len(matching)}
    name,data=matching[0];measurement=data.get('measurementId','')
    if measurement not in observed.get('ga4IdsObserved',[]):
        return {**result,'status':'EXISTING_PROPERTY_BUT_SITE_COLLECTION_NOT_VERIFIED','measurementId':measurement,'propertyId':name.split('/')[-1]}
    end=(dt.date.today()-dt.timedelta(days=1)).isoformat()
    body={'dateRanges':[{'startDate':'28daysAgo','endDate':end}], 'dimensions':[{'name':'eventName'}], 'metrics':[{'name':'eventCount'},{'name':'totalUsers'}]}
    r=requests.post('https://analyticsdata.googleapis.com/v1beta/'+name+':runReport',headers=headers,json=body,timeout=60)
    result.update(dataReadHttpStatus=r.status_code,propertyId=name.split('/')[-1],measurementId=measurement)
    if not r.ok:return {**result,'status':'EXISTING_PROPERTY_REPORT_UNAVAILABLE'}
    result.update(status='EXISTING_COLLECTION_REPORT_CONNECTED',reportedEvents=r.json().get('rows',[]))
    save('EXISTING_ANALYTICS_CONNECTION.json',{'verifiedExisting':True,'propertyId':name.split('/')[-1],'measurementId':measurement,'defaultUri':data.get('defaultUri'),'verifiedAt':NOW()})
    return result


def plain_diagnostic(path):
    try:
        response=requests.get(BLOG+path,headers={'User-Agent':UA},timeout=25)
        text=response.text[:4000] if response.status_code==200 else ''
        return {'httpStatus':response.status_code,'text':text,'readOnly':True,'checkedAt':NOW()}
    except requests.RequestException as exc:return {'httpStatus':0,'errorType':type(exc).__name__,'text':'','readOnly':True,'checkedAt':NOW()}


def main():
    errors=[];reader=BloggerReader();blog=reader.get('',{'fields':'id,name,url,description'})
    posts=reader.collect('posts');pages=reader.collect('pages');drafts=reader.collect('posts','draft',False)
    observed,source=page_source()
    observed['adsTxt']=plain_diagnostic('/ads.txt')
    observed['adsTxt']['matchesRecordedPublisher']='google.com, pub-1083724733490660, DIRECT, f08c47fec0942fa0' in observed['adsTxt']['text']
    observed['robotsTxt']=plain_diagnostic('/robots.txt')
    save('TABLE3_SITE_SOURCE_STATUS.json',observed)
    corpus,photos=corpus_audit(posts,pages)
    save('TABLE3_CORPUS_AUDIT.json',corpus);save('TABLE3_PHOTO_AUDIT.json',photos)
    old=load('INDEX_STATUS_REPORT.json');redirects=[x for x in old.get('notIndexedUrls',[]) if x.get('coverageState')=='Redirect error']
    policy_paths=['/p/about-us_02080501126.html','/p/contact-us_01883938366.html','/p/privacy-policy.html','/p/disclaimer.html','/p/terms-and-conditions.html']
    targets={x['url']:x for x in redirects}
    for path in policy_paths:targets.setdefault(BLOG+path,{'url':BLOG+path})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:checks=list(executor.map(head_check,targets.values()))
    save('TABLE3_REDIRECT_CHECKS.json',{'checkedAt':NOW(),'rows':checks,'source':'Google stored indexed-version warnings; current diagnostics are HEAD only'})
    try:analytics=analytics_audit(observed)
    except Exception as exc:analytics={'status':'UNAVAILABLE','errorType':type(exc).__name__,'siteTagsChanged':False,'dataSubmitted':False}
    save('TABLE3_ANALYTICS_STATUS.json',analytics)
    state=load('BING_URL_AUTOMATION_STATE.json').get('urls',{})
    accepted=[{'url':u,**{k:v for k,v in row.items() if any(s in k.lower() for s in ('submit','attempt','status'))}} for u,row in state.items() if row.get('submittedFingerprint') or any(row.get(k) for k in ('lastSubmittedAt','submittedAt','lastSubmitAt'))]
    cfg=policy();held_cli=cfg.get('heldCliActions',{});held_workflows=cfg.get('heldWorkflows',[])
    private_issues=[]
    description=blog.get('description','')
    if re.search(r'Kushal\s+K\.?\s+Daga|Kushal Jain|Finance by CA Kushal',description,re.I):private_issues.append('Stored Blogger description still contains retired wording. This box needs the owner screen; do not replace the theme to hide it.')
    report={'checkedAt':NOW(),'status':'CHECKED_WITH_LIMITS','siteWrites':0,'analyticsEventsSent':0,'pageScriptsExecuted':False,
        'bloggerApiReads':reader.reads,'livePosts':len(posts),'livePages':len(pages),'drafts':len(drafts),
        'draftInventory':[{'id':x['id'],'title':x.get('title'),'updated':x.get('updated')} for x in drafts],
        'storedBlogDescription':description,'ownerOnlyFindings':private_issues,'sourceObservation':observed,
        'freeze':{'active':is_frozen(),'heldCliTools':len(held_cli),'heldWorkflows':len(held_workflows),
            'unprotectedHeldEntries':[name for name in held_workflows if '${{ false }}' not in (ROOT/'.github/workflows'/name).read_text()],
            'auditOnly':['harden_live_corpus','contextual_links_retrofit','site_content_audit_cleanup'],'routineUpdates':'Existing article/news hub cards and JSON data only; no old-post/theme/label rebuild.'},
        'corpusSummary':{k:corpus[k] for k in ('postsScanned','pagesScanned','automatedPolicyFlags','missingDisclosure','exactEditorialDuplicateGroups')},
        'photoSummary':{'masterCountMismatches':photos['masterCountMismatches'],'licenceEvidenceNeedsReviewCount':photos['licenceEvidenceNeedsReviewCount'],
                       'newsPoolsBelow40':photos['newsPoolsBelow40'],'masterPoolsBelow10':photos['masterPoolsBelow10']},
        'redirectSummary':{'checked':len(checks),'currentlyReachable':sum(x.get('status')=='CURRENTLY_REACHABLE' for x in checks),'needsRecheck':[x for x in checks if x.get('status')!='CURRENTLY_REACHABLE']},
        'analytics':analytics,'bing':{'lastRun':load('BING_URL_AUTOMATION_STATUS.json'),'durableAcceptedRecords':len(accepted),'acceptedSample':accepted[:5],
                                   'indexNowParked':bool(load('INDEXNOW_STATE.json').get('blocked'))},
        'limits':['Private AdSense review/account setup cannot be certified from public/API site checks.','Financial fact review and copyright ownership cannot be guaranteed by a scanner.','A current successful HEAD response is not a complete Google rendering test.','Actual provider bills/revenue are not connected; unknown costs are not zero.'],
        'errors':errors}
    save('TABLE3_AUDIT.json',report)
    # Compact public, factual source-review packet; no credentials or full copies.
    save('TABLE3_FACT_REVIEW_SAMPLE.json',{'checkedAt':NOW(),'samples':corpus['factReviewSample'],'reviewerClaimed':False})
    print(json.dumps({'status':report['status'],'posts':len(posts),'pages':len(pages),'drafts':len(drafts),
        'automatedPolicyFlags':len(corpus['automatedPolicyFlags']),'photoCountGaps':photos['masterCountMismatches'],
        'analytics':analytics['status'],'siteWrites':0}))
    return 0

if __name__=='__main__':raise SystemExit(main())
