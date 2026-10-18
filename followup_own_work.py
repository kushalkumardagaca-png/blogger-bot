#!/usr/bin/env python3
"""Execute only the approved nine-archive/44-image follow-up, not owner account tasks."""
from __future__ import annotations
import argparse,collections,datetime as dt,gzip,hashlib,json,re,time,os
from pathlib import Path
import requests
from preapproval_audit import BloggerReader,corpus_audit
from followup_archive_review import REVIEW,review_content
from followup_image_review import correct_figures
from licence_evidence import rights_record_complete

ROOT=Path(__file__).resolve().parent
NOW=lambda:dt.datetime.now(dt.timezone.utc).isoformat()


def load(name):return json.loads((ROOT/name).read_text())

def save(name,data):(ROOT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def patch_existing(reader,item,after):
    current=reader.get('/posts/'+item['id'])
    if sha(current.get('content',''))!=sha(item.get('content','')):raise RuntimeError('concurrent edit detected; defer instead of overwriting')
    response=requests.patch(reader.base+'/posts/'+item['id'],headers=reader.headers,json={'content':after},timeout=70)
    if not response.ok:raise RuntimeError('Blogger content-only patch HTTP '+str(response.status_code))
    stored=reader.get('/posts/'+item['id'])
    for key in ('id','url','title','published'):
        if stored.get(key)!=item.get(key):raise RuntimeError('protected identity/publication field changed: '+key)
    if stored.get('content')!=after:raise RuntimeError('stored content differs from the exact approved correction')
    return stored


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    request=load('FOLLOWUP_OWN_WORK_REQUEST.json')
    if request.get('operation')=='VERIFY_ONLY':args.apply=False
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as outputs:outputs.write('effective_apply='+str(args.apply).lower()+'\n')
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).date().isoformat()
    if args.apply and today>request['validThroughIST']:
        print(json.dumps({'status':'REQUEST_EXPIRED','siteWrites':0}));return 0
    if request['ownerAccountSteps']!='DEFERRED_TOGETHER_WITH_TABLE_1':raise RuntimeError('unexpected account-step scope')
    images=load('FOLLOWUP_IMAGE_CORRECTION_PLAN.json')['patches'];rates=load('FOLLOWUP_ECB_EVIDENCE.json')['dates'];by_post=collections.defaultdict(list)
    for image in images:by_post[image['postId']].append(image)
    ids=set(REVIEW)|set(by_post)
    if len(images)!=44 or set(REVIEW)!=set(request['archiveIds']) or len(ids)>50:raise RuntimeError('review target scope differs')
    # New local assets must already be published to the existing repository asset
    # host before the live article can point to them. Source requests are asset
    # probes, not website page views or Analytics events.
    for url in sorted({x['newPhoto']['url'] for x in images if x['changeImage']}):
        if not url.startswith('https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/assets/review-20261018/'):
            raise RuntimeError('unexpected correction asset URL')
        r=requests.get(url,stream=True,timeout=30)
        if r.status_code!=200 or not r.headers.get('Content-Type','').startswith('image/'):
            r.close();raise RuntimeError('new correction asset not reachable')
        next(r.iter_content(2048),b'');r.close()
    reader=BloggerReader();live=reader.collect('posts',bodies=False);live_ids={r['id'] for r in live};results=[];backups=[]
    report={'startedAt':NOW(),'apply':args.apply,'scope':request,'newArticles':0,'deletedArticles':0,'newTracking':0,'themeChanges':0,
            'ownerAccountSettingsChanged':False,'rows':results,'deferred':[],'status':'RUNNING'}
    save('FOLLOWUP_OWN_WORK_STATUS.json',report)
    for ident in sorted(ids):
        if ident not in live_ids:
            report['deferred'].append({'id':ident,'reason':'not in authenticated LIVE inventory; no draft/scheduled post is restored'});continue
        try:
            item=reader.get('/posts/'+ident);old=item.get('content','');after=old;archive=None;photo_changes=[]
            if ident in REVIEW:after,archive=review_content(ident,after,rates)
            if ident in by_post:
                expected={x['postUrl'] for x in by_post[ident]}
                if item.get('url') not in expected:raise RuntimeError('canonical target URL does not match the reviewed record')
                after,photo_changes=correct_figures(after,by_post[ident])
            backup={'id':item['id'],'url':item.get('url'),'title':item.get('title'),'published':item.get('published'),'content':old}
            if after!=old:
                backups.append(backup)
                with gzip.open('/tmp/followup-before-corrections.json.gz','wt',encoding='utf-8') as stream:json.dump(backups,stream,ensure_ascii=False)
                if args.apply:patch_existing(reader,item,after)
            results.append({'id':ident,'url':item['url'],'changed':after!=old,'applied':bool(args.apply and after!=old),
                            'beforeSha256':sha(old),'afterSha256':sha(after),'archive':archive,'photoChanges':photo_changes})
        except Exception as exc:
            report['deferred'].append({'id':ident,'reason':str(exc)[:250],'errorType':type(exc).__name__})
        save('FOLLOWUP_OWN_WORK_STATUS.json',report);time.sleep(.2)
    # Fresh authenticated verification of actual stored content, not hypothetical
    # cleaned copies. Owner Analytics/AdSense account checks are not called.
    posts=reader.collect('posts');pages=reader.collect('pages');corpus,photo_audit=corpus_audit(posts,pages)
    save('TABLE3_CORPUS_AUDIT.json',corpus);save('TABLE3_PHOTO_AUDIT.json',photo_audit)
    target_after={r['id']:r for r in posts if r['id'] in ids};archive_left=[r for r in corpus['automatedPolicyFlags'] if r['id'] in REVIEW]
    image_left=[r for r in photo_audit['licenceEvidenceNeedsReview'] if r['postId'] in by_post]
    reviewed=[]
    for p in images:
        actual=target_after.get(p['postId'],{}).get('content','');url=p['newPhoto']['url']
        reviewed.append({'postId':p['postId'],'oldSrc':p['oldSrc'],'currentSrc':url,
                         'currentSourcePresent':url in actual or __import__('html').escape(url,quote=True) in actual,
                         'imageChanged':p['changeImage'],'termsDocumented':rights_record_complete(p['newPhoto'])})
    complete=not report['deferred'] and not archive_left and not image_left and all(x['currentSourcePresent'] and x['termsDocumented'] for x in reviewed)
    report.update(finishedAt=NOW(),status='COMPLETED_VERIFIED' if complete else 'COMPLETED_WITH_OPEN_ITEMS',
        verification={'livePostsRead':len(posts),'reviewedArchives':len(REVIEW),'reviewedImageRecords':len(reviewed),
                      'archiveFlagsRemaining':archive_left,'imageEvidenceGapsRemainingInScope':image_left,'images':reviewed,
                      'originalPublicationFieldsPreserved':True,'publicUrlsPreserved':True,'ownerAccountWorkDeferred':True})
    save('FOLLOWUP_OWN_WORK_STATUS.json',report)
    print(json.dumps({'status':report['status'],'postsChanged':sum(r['applied'] for r in results),'reviewedArchives':len(REVIEW),
          'reviewedImageRecords':len(reviewed),'deferred':len(report['deferred']),'archiveFlagsRemaining':len(archive_left),
          'imageGapsRemaining':len(image_left),'ownerAccountSettingsChanged':False}),flush=True)
    return 0 if complete else 1

if __name__=='__main__':raise SystemExit(main())
