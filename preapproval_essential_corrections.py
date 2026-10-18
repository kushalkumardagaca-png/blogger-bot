#!/usr/bin/env python3
"""Narrow Table 3 B6/B14 corrections, not an optional bulk redesign.

Only: correct proven false GA4-off privacy wording and remove extra exact copies
of the existing WHY template inside legacy News <em> blocks. Facts, numbers,
links, titles, layout, scripts, photographs and URLs are invariant. Retain a
complete before-copy; refuse if the live copy changed since it was inspected.
"""
from __future__ import annotations
import argparse,datetime as dt,gzip,hashlib,html,json,os,re
from pathlib import Path
from urllib.parse import urlparse
import requests
from preapproval_audit import BloggerReader,editorial
from content_policy_guard import audit_text,normalize_sentence
from news_pipeline import WHY

ROOT=Path(__file__).resolve().parent
PRIVACY_URL='https://dailyyield.blogspot.com/p/privacy-policy.html'
MARK='DY_EXISTING_ANALYTICS_DISCLOSURE_20261018'
OLD1='No separately added Google Analytics, advertising/AdSense or email newsletter service is currently enabled. Blogger platform processing and the tool-provider connections described here are separate from those optional services.'
NEW1="Google Analytics 4 is configured through Blogger. Google AdSense code is also present for Google's verification and advertising processes; its presence alone does not confirm approval or that ads are serving. Blogger hosting and the external tool providers also receive technical browser requests as described below."
OLD2='No added advertising, Google Analytics or newsletter service is currently enabled. The site does use Blogger hosting and external tool providers, described in the processing map below. Those services may receive browser request information under their own policies.'
NEW2="Google Analytics 4 and Google's AdSense-related code may load on this site. The footer Privacy choices control communicates your choices for optional analytics and advertising storage. When that storage is denied, Google's tags may still process consent-related or cookieless signals. Advertising remains subject to Google approval, your choices and applicable requirements."
OLD3='No separately added Google Analytics is currently enabled. Blogger platform statistics and requests to the tools’ external providers are separate from added Analytics.'
NEW3='Google Analytics 4 is configured through Blogger to help measure website use. This is separate from Blogger platform statistics and technical requests made to external tool providers. See the analytics-and-consent explanation below for your choices.'
DISCLOSURE='''<!-- DY_EXISTING_ANALYTICS_DISCLOSURE_20261018 --><aside aria-label="Google Analytics and privacy choices"><h3>Google Analytics and your choices</h3><p>Google Analytics may process page addresses, interactions, device/browser information, approximate location and consent-related signals to help measure site use. Our privacy controls communicate storage choices; denied optional storage is not a promise that no technical or cookieless request is sent. You can choose essential-only storage or change your choice using Privacy choices in the footer. Please do not put identifying or private financial information in searches or public page addresses.</p><p>Read <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">how Google uses data from sites using its services</a> and the <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener" target="_blank">Google Analytics opt-out option</a>. These explanations do not claim that a custom cookie panel is a Google-certified advertising consent platform.</p></aside><!-- /DY_EXISTING_ANALYTICS_DISCLOSURE_20261018 -->'''


def sha(value):return hashlib.sha256(value.encode()).hexdigest()


def invariants(before,after,privacy=False):
    for pattern in (r'<script\b.*?</script>',r'<style\b.*?</style>',r'<img\b[^>]*>',r'<h1\b.*?</h1>'):
        if re.findall(pattern,before,re.I|re.S)!=re.findall(pattern,after,re.I|re.S):raise RuntimeError('correction changed protected scripts/styles/images/H1')
    if not privacy:
        for pattern in (r'<a\b[^>]*>',r'\d+'):
            if re.findall(pattern,before,re.I|re.S)!=re.findall(pattern,after,re.I|re.S):raise RuntimeError('dedupe changed a link, date, number or attribute')


def privacy_correction(content,ga4_observed):
    if not ga4_observed:raise RuntimeError('refusing a GA4 disclosure change without observed existing tag evidence')
    out=content;changes=[]
    for old,new in ((OLD1,NEW1),(OLD2,NEW2),(OLD3,NEW3)):
        if old in out:out=out.replace(old,new);changes.append({'old':old,'new':new})
    badge='<div class="kvP-swrow"><span>Added Analytics</span><span class="kvP-sw off"><em>OFF</em><i></i></span></div>'
    fixed='<div class="kvP-swrow"><span>Google Analytics</span><span class="kvP-sw on"><em>ON</em><i></i></span></div>'
    if badge in out:out=out.replace(badge,fixed);changes.append({'old':'Added Analytics OFF badge','new':'Google Analytics ON, with storage-choice explanation'})
    if MARK not in out and changes:
        if NEW2 not in out:raise RuntimeError('exact privacy section was not recognised')
        out=out.replace(NEW2+'</p>',NEW2+'</p>'+DISCLOSURE,1)
        changes.append({'new':'Actual Analytics/storage/cookieless explanation and official opt-out links'})
    if out!=content:invariants(content,out,True)
    return out,changes


def dedupe_known_stock_em(content):
    known={normalize_sentence(x) for values in WHY.values() for x in values}
    seen=set();removed=[]
    # Preserve executable strings and styles verbatim; act only on literal HTML.
    parts=re.split(r'(<script\b.*?</script>|<style\b.*?</style>)',content,flags=re.I|re.S)
    for i in range(0,len(parts),2):
        def replace(match):
            text=html.unescape(re.sub(r'<[^>]+>',' ',match.group(1))).strip();key=normalize_sentence(text)
            if key not in known or re.search(r'\d|<a\b|<img\b',match.group(0),re.I):return match.group(0)
            if key in seen:removed.append(text);return ''
            seen.add(key);return match.group(0)
        parts[i]=re.sub(r'<em\b[^>]*>(.*?)</em>',replace,parts[i],flags=re.I|re.S)
    out=''.join(parts)
    if removed:invariants(content,out)
    return out,removed


def fresh_item(reader,kind,item):return reader.get('/'+kind+'/'+item['id'])


def apply_one(reader,kind,item,before,after):
    # Last-moment conflict check: do not overwrite a concurrent publication.
    fresh=fresh_item(reader,kind,item)
    if sha(fresh.get('content',''))!=sha(before):raise RuntimeError('live content changed; correction deferred instead of overwriting it')
    response=requests.patch(reader.base+'/'+kind+'/'+item['id'],headers=reader.headers,json={'content':after},timeout=60)
    if not response.ok:raise RuntimeError('targeted Blogger PATCH HTTP '+str(response.status_code))
    stored=fresh_item(reader,kind,item)
    if stored.get('url')!=item.get('url') or stored.get('title')!=item.get('title'):raise RuntimeError('unexpected URL/title change after content-only correction')
    if stored.get('content')!=after:raise RuntimeError('stored correction differs; retained evidence requires inspection')
    return stored


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    scope=json.loads((ROOT/'ESSENTIAL_CORRECTION_SCOPE.json').read_text())
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).date().isoformat()
    if args.apply and today>scope['validThroughIST']:
        print(json.dumps({'status':'SCOPE_EXPIRED','siteWrites':0}));return 0
    reader=BloggerReader();pages=reader.collect('pages');posts=reader.collect('posts')
    supplemental=json.loads((ROOT/'TABLE3_LOCAL_SOURCE_EVIDENCE.json').read_text()) if (ROOT/'TABLE3_LOCAL_SOURCE_EVIDENCE.json').exists() else {}
    observed=scope['knownGa4Id'] in supplemental.get('ga4IdsObserved',[])
    report={'checkedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'apply':args.apply,
      'authorization':'Owner request to complete Table 3, specifically B6 confirmed originality problems and B14 confirmed privacy mismatch; no optional rebuild.',
      'newUrls':0,'newTracking':0,'themeChanges':0,'privacy':[],'legacyNews':[],'deferred':[],'status':'CHECKED'}
    backups=[]
    def backup(kind,item):
        backups.append({'kind':kind,**item})
        with gzip.open('/tmp/table3-essential-before.json.gz','wt',encoding='utf-8') as archive:json.dump(backups,archive,ensure_ascii=False)
    page=next((p for p in pages if p.get('url')==PRIVACY_URL),None)
    if not page:raise RuntimeError('known privacy URL was not found; no page is created')
    old=page.get('content','');new,changes=privacy_correction(old,observed)
    if changes:
        record={'id':page['id'],'url':page['url'],'changes':changes,'beforeSha256':sha(old),'afterSha256':sha(new),'applied':False}
        backup('pages',page)
        if args.apply:
            apply_one(reader,'pages',page,old,new);record['applied']=True
        report['privacy'].append(record)
    for post in posts:
        if 'News' not in post.get('labels',[]):continue
        try:published=dt.datetime.fromisoformat(post['published'].replace('Z','+00:00'))
        except (KeyError,ValueError):continue
        # Never interfere with today's preparing/publishing editions.
        if published.astimezone(dt.timezone(dt.timedelta(hours=5,minutes=30))).date()>=dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).date():continue
        old=post.get('content','')
        if 'repeated substantive sentence within the content' not in audit_text(post.get('title',''),editorial(post),'stored-live-audit',require_disclosure=False):continue
        new,removed=dedupe_known_stock_em(old)
        if not removed:continue
        record={'id':post['id'],'url':post['url'],'removedExactStockCommentary':removed,'beforeSha256':sha(old),'afterSha256':sha(new),'applied':False}
        backup('posts',post)
        if args.apply:
            try:apply_one(reader,'posts',post,old,new);record['applied']=True
            except Exception as exc:report['deferred'].append({'id':post['id'],'reason':type(exc).__name__});continue
        report['legacyNews'].append(record)
        # Persist progress even if the runner is interrupted later.
        (ROOT/'ESSENTIAL_PREAPPROVAL_CORRECTIONS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    report['status']='APPLIED_NARROW_CORRECTIONS' if args.apply else 'DRY_RUN'
    (ROOT/'ESSENTIAL_PREAPPROVAL_CORRECTIONS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':report['status'],'privacyPages':sum(x['applied'] for x in report['privacy']),
       'legacyNewsPosts':sum(x['applied'] for x in report['legacyNews']),'deferred':len(report['deferred']),
       'newUrls':0,'newTracking':0,'themeChanges':0}))
    return 0

if __name__=='__main__':raise SystemExit(main())
