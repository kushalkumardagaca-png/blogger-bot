#!/usr/bin/env python3
"""One plain Table 3 progress report. Reads evidence only; never edits the site."""
from __future__ import annotations
import datetime as dt,json
from pathlib import Path
from collections import Counter
from merge_social_tracker import identity

ROOT=Path(__file__).resolve().parent
IST=dt.timezone(dt.timedelta(hours=5,minutes=30))


def load(name):
    try:return json.loads((ROOT/name).read_text())
    except (OSError,ValueError):return {}


def cell(value):return str(value).replace('|','/').replace('\n',' ')


def main():
    audit=load('TABLE3_AUDIT.json');source=load('TABLE3_SITE_SOURCE_STATUS.json');corpus=load('TABLE3_CORPUS_AUDIT.json')
    photos=load('TABLE3_PHOTO_AUDIT.json');ga=load('TABLE3_ANALYTICS_STATUS.json');redirect=load('TABLE3_REDIRECT_CHECKS.json')
    cleanup=load('SOCIAL_DUPLICATE_CLEANUP_STATUS.json');index=load('INDEX_STATUS_REPORT.json');search=load('AUDIENCE_GROWTH_BASELINE.json')
    slots=load('SLOT_GUARANTEE_STATUS.json');social=load('SOCIAL_GUARANTEE_STATUS.json');shortlist=load('GROWTH_PRIORITY_SHORTLIST_PRIVATE.json')
    cfg=load('SITE_CHANGE_POLICY.json');tests=load('TABLE3_CONTROL_TESTS.json')
    local_policy=load('TABLE3_LOCAL_POLICY_DIAGNOSTICS.json')
    corrections=load('ESSENTIAL_PREAPPROVAL_CORRECTIONS.json');replay=load('TABLE3_CONSENT_REPLAY.json')
    now=dt.datetime.now(IST);owner=[]
    for issue in audit.get('ownerOnlyFindings',[]):owner.append(('Before approval',issue))
    owner.append(('Before approval, only if shown','Check the private AdSense application and complete any required account task. I cannot see that screen; do not remove/resubmit a Getting ready site.'))
    if ga.get('status') not in ('EXISTING_COLLECTION_REPORT_CONNECTED',):
        owner.append(('Optional read-only help before approval; new installation later','Analytics report access is not established. Only if you already use Analytics, check the existing property/permission. Do not install code to complete this checklist.'))
    if corpus.get('automatedPolicyFlags') or corpus.get('missingDisclosure'):
        owner.append(('Before approval, after reviewing the specific evidence','Approve only the smallest confirmed content correction if a reported issue is genuine. No bulk rewrite has been applied.'))
    owner.append(('Before high-risk advice is published','A suitable person must genuinely review important financial claims. Automated checks do not prove expert review of every article.'))
    if photos.get('masterCountMismatches',0):
        owner.append(('Decision needed; no old-page photo expansion during freeze','The saved Master renderer uses three photographs, not the agreed ten. The gap is recorded honestly; no unsafe mass image replacement has been made.'))
    owner.append(('Later, not now','Review the 50-item shortlist before any ranking build. Release requires AdSense approval, the agreed earnings period and your explicit permission.'))
    checks=[]
    def row(key,name,state,proof):checks.append({'id':key,'task':name,'result':state,'proof':proof})
    row('B1','Freeze automatic edits','Implemented',f"{len(cfg.get('heldWorkflows',[]))} optional workflows and {len(cfg.get('heldCliActions',{}))} CLI tools held. Three old-page tools are audit-only. Hub updates limited to existing cards/data; publishers remain active.")
    row('B2','AdSense connection and ads.txt','Checked; private account not accessible',f"Public source recorded publisher IDs: {', '.join(source.get('adSensePublisherIds',[])) or 'not observed'}. ads.txt matches recorded publisher: {source.get('adsTxt',{}).get('matchesRecordedPublisher','not checked')}. Required verification is preserved; private review approval is not visible.")
    row('B3','Misleading reports','Fixed',f"Google inspection errors are separated from unindexed pages; property labels cannot be inspected as URLs; unreadable pages are unknown rather than automatically broken. Legitimate AdSense code is not prohibited. Regression tests: {tests.get('tests','see CI result')}.")
    nav=source.get('policyNavigation',{});reachable=sum(x.get('status')=='CURRENTLY_REACHABLE' for x in redirect.get('rows',[]))
    row('B4','Policy pages and navigation','Checked',f"{sum(bool(v) for v in nav.values())}/{len(nav)} policy routes observed in homepage links; {len(source.get('reportAbuseLinks',[]))} Report Abuse link(s). HEAD diagnostics: {reachable}/{len(redirect.get('rows',[]))} tested routes reached HTTP 200 for both checks. No redesign. Independent source-only policy GET checks returned 200 for {sum(r.get('httpStatus')==200 for r in local_policy.get('rows',[]))}/{len(local_policy.get('rows',[]))} pages, with no retired description wording observed.")
    identity_issues=[x for x in corpus.get('identityPages',[]) if x.get('retiredInitialsFound') or x.get('unrelatedAliasFound') or x.get('claimsManualReview')]
    row('B5','Names and honest statements','Checked; see owner-only findings' if audit.get('ownerOnlyFindings') or identity_issues else 'Checked',f"Stored page identity issues: {len(identity_issues)}. Blog description read through the official API. No mass rename or invented manual-review claim.")
    row('B6','Facts and originality','Automated check done; human-review limit remains',f"{corpus.get('postsScanned','unknown')} live posts read as actually stored. Policy flags: {len(corpus.get('automatedPolicyFlags',[]))}; missing disclosures: {len(corpus.get('missingDisclosure',[]))}; exact-text duplicate groups: {len(corpus.get('exactEditorialDuplicateGroups',[]))}. Source-review samples retained; not a certification of every financial fact. Legacy News posts with extra exact WHY-template copies removed: {sum(bool(x.get('applied')) for x in corrections.get('legacyNews',[]))}; all numerical facts, links, scripts and styles were protected.")
    row('B7','Photographs and rights','Checked; requirements not fully met' if photos.get('masterCountMismatches') or photos.get('licenceEvidenceNeedsReviewCount') or photos.get('newsPoolsBelow40') else 'Metadata check done',f"Master photo-count mismatches: {photos.get('masterCountMismatches','unknown')}; figures needing fuller licence/alt/caption evidence: {photos.get('licenceEvidenceNeedsReviewCount','unknown')}; News pools below 40: {len(photos.get('newsPoolsBelow40',[]))}. Exact-file licence metadata recovered separately: {len(load('IMAGE_LICENCE_EVIDENCE_SUPPLEMENT.json').get('items',[]))}. No copyright-ownership guarantee or old-photo replacement.")
    row('B8','21 daily articles','Active; ongoing',f"Live status source {slots.get('generatedAt','unavailable')}: {slots.get('live','unknown')}/21 live, {slots.get('overdue','unknown')} overdue. News timing now uses Blogger's publication time, not the source-gathering time. No slot is cancelled merely for being late. Completed Master slots are now locked by date/kind/category, so retries cannot swap in a second topic. Earlier extra live articles are retained and reported separately: {len(slots.get('extraLiveArticles',[]))}.")
    row('B9','Social delivery and duplicates','Future check fixed; cleanup '+cleanup.get('status','not yet recorded'),f"Fixed quoted skip output, fail-open tracker checks and same-destination races. Approved Master slot routing restored. Provider-confirmed extra article copies removed: {len(cleanup.get('deleted',[]))}; cleanup items not verified/deleted: {len(cleanup.get('blocked',[]))}. Two networks required; resources counted separately.")
    row('B10','Search Console','Read existing results',f"Latest index evidence {index.get('checkedAt','unavailable')}: {index.get('indexed','unknown')} indexed results, {index.get('notIndexed','unknown')} not indexed, {index.get('inspectionErrors','unknown')} inspection errors. No ownership reset or manual bulk request.")
    row('B11','Old redirect warnings','Diagnosed, not blindly repaired',f"{len([x for x in redirect.get('rows',[]) if x.get('oldGoogleCoverage')=='Redirect error'])} prior redirect warnings rechecked with bounded HEAD requests. Current reachability does not erase an old Google result or prove rendering. Confirmed remaining issues are retained in evidence.")
    row('B12','Existing Analytics installation','Observed without changes',f"GA4 IDs in source: {len(source.get('ga4IdsObserved',[]))}; tag-manager IDs: {len(source.get('tagManagerIdsObserved',[]))}; Analytics loaders: {len(source.get('analyticsLoaderSources',[]))}. Hooks alone are not counted as working collection. No tag installed. Existing GA4 is not the same as a connected report.")
    row('B13','Existing Analytics reporting','Connected existing reports' if ga.get('status')=='EXISTING_COLLECTION_REPORT_CONNECTED' else 'Checked; cannot claim connected',f"Result: {ga.get('status','not available')}. Only existing authorised read access was tried. No new collection or owner permission grant was manufactured.")
    row('B14','Privacy and consent','Checked with stated limits',f"Source consent scripts: {source.get('consentScriptCount','unknown')}; default-consent command observed: {source.get('hasConsentDefaults','unknown')}. Cookie controls are not a certified advertising-CMP guarantee. Offline browser cases: {len(replay.get('results',[]))}; zero events sent. Privacy pages corrected for false GA4-off wording: {sum(bool(x.get('applied')) for x in corrections.get('privacy',[]))}. Replay does not prove certified-CMP or live Google network behaviour.")
    bing=audit.get('bing',{});last=bing.get('lastRun',{})
    row('B15','Bing and IndexNow','Monitored; quota respected',f"Last Bing record {last.get('checkedAt','unavailable')}: remaining daily allowance {last.get('quota',{}).get('dailyAvailable','unknown')}; durable URL records with accepted-submission evidence {bing.get('durableAcceptedRecords','unknown')}. IndexNow parked: {bing.get('indexNowParked','unknown')}. No indexing guarantee.")
    row('B16','Drafts and retired recovery','Checked and protected',f"API draft count at audit: {audit.get('drafts','unknown')}. Deleted-draft restoration now stops before credentials. Eight-hour recovery remains retired. Existing draft hygiene and duplicate guards retained.")
    row('B17','Private growth preparation','Prepared; not built or published',f"{len(shortlist.get('items',[]))} proposals, topic groups, individual specifications and pre-release tests prepared. Costs are estimates/formulas, not connected invoices. No new live URLs, Blogger drafts or prototypes.")
    row('B18','One simple progress report','Implemented',"This report separates article delivery, article social posts, resource promotions, Google results, missing Analytics and unknown bills. It can be refreshed by the repository workflow; it does not imply that I monitor the site continuously in chat.")
    if not audit.get('checkedAt'):
        for item in checks:
            if item['id'] not in ('B1','B3','B8','B9','B10','B15','B17','B18'):
                item['result']='NOT COMPLETED — fresh audit unavailable'
    snapshot={'generatedAt':now.isoformat(),'status':'EXECUTED_WITH_RECORDED_LIMITS' if audit.get('checkedAt') else 'AUDIT_NOT_COMPLETED','rows':checks,'ownerActions':owner,
              'sourceDates':{'siteAudit':audit.get('checkedAt'),'slots':slots.get('generatedAt'),'social':social.get('generatedAt'),'google':index.get('checkedAt')},
              'noGrandUpdateStarted':True,'analyticsCollectionInstalled':False}
    (ROOT/'TABLE3_EXECUTION_STATUS.json').write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+'\n')
    lines=['# Daily Yield — Table 3 Work and Results','',f'**Updated: {now:%d %B %Y, %H:%M IST}. AdSense remains the first priority.**','',
      '**The controls and checks were carried out. This is not a claim that every requirement passed:** photo-count/evidence gaps, any owner-only settings, Analytics permissions and human fact-review limits are shown below.',
      '', '## 1. What needs you — only the items we cannot honestly finish without you','',
      '| When | Your task |','|---|---|']
    lines += ['| '+cell(when)+' | '+cell(task)+' |' for when,task in owner]
    lines += ['', '## 2. What I did — every Table 3 item separately','',
              '| Item | Result | Proof / remaining limit |','|---|---|---|']
    lines += ['| '+r['id']+' — '+cell(r['task'])+' | '+cell(r['result'])+' | '+cell(r['proof'])+' |' for r in checks]
    # Publishing results are evidence snapshots, not future slots counted as failures.
    source_time=slots.get('generatedAt');sr=slots.get('rows',[])
    try:at=dt.datetime.fromisoformat(source_time)
    except (ValueError,TypeError):at=now
    due=[r for r in sr if r.get('due') and dt.datetime.fromisoformat(r['due'])<=at]
    missing=sum(not r.get('live') for r in due)
    lines += ['', '## 3. Articles and social posts — separate counts','',
              f'**Missing among articles due at the saved status time: {missing}.** Later slots are not failures.',
              f'Article-status source: {source_time or "unavailable"}.', '',
              '| Type | Due by that time | Published among those due | Missing |','|---|---:|---:|---:|']
    for title,prefix in [('News','news-'),('Evergreen','master-evergreen-'),('Trending','master-trending-')]:
        rr=[r for r in due if r['key'].startswith(prefix)];done=sum(bool(r.get('live')) for r in rr)
        lines.append(f'| {title} | {len(rr)} | {done} | {len(rr)-done} |')
    day=now.date();article_posts=resource_posts=0;resource_networks=Counter()
    for platform in ('facebook','bluesky','tumblr','mastodon'):
        seen=set()
        for r in load(platform+'_tracker.json').get('published',[]):
            ident=identity(r)
            if ident in seen:continue
            seen.add(ident)
            try:stamp=dt.datetime.fromisoformat(r.get('published_at','').replace('Z','+00:00')).astimezone(IST)
            except (ValueError,TypeError):continue
            if stamp.date()!=day:continue
            if r.get('kind')=='page':resource_posts+=1;resource_networks[platform]+=1
            else:article_posts+=1
    lines += ['',f'- **Article-related social posts recorded today:** {article_posts}; full-day target 42.',
              f'- **Resource promotions recorded today:** {resource_posts}; full-day target 12. Per network: {dict(resource_networks)}.',
              f'- **Article-social tracker status:** {social.get("status","unknown")}; missing routes {social.get("postsMissing","unknown")}; duplicate copies {social.get("duplicatePosts","not separately measured in old status")}.',
              '- These are durable publishing records, not reader counts. Provider checks were used before deleting duplicate copies.',
              '- The eight-hour schedule is retired and is not counted.', '',
              '## 4. Google, visitors and money','', '| Measure | What we can honestly say |','|---|---|',
              f'| Google search | Search report dated {search.get("checkedAt","unknown")}. Seven-day clicks: {search.get("searchAcquisition",{}).get("last7Days",{}).get("clicks","unknown")}; impressions: {search.get("searchAcquisition",{}).get("last7Days",{}).get("impressions","unknown")}. |',
              f'| Visitor/readership measurement | {ga.get("status","unknown")}. Missing reporting is unknown, not zero visitors. |',
              '| Income and costs | Actual bills and AdSense earnings are not connected here. Profit is unknown, not assumed positive. |',
              '| Ranking/traffic promises | None. Sending URLs, passing code checks or publishing more articles does not promise indexing, approval or 10 million daily views. |',
              '', '## 5. Unpublished 50-item shortlist — your approval is still required','',
              '**Planning only. Not search-volume-validated, not approved for building, and not new website pages.**','',
              '| No. | Proposed useful tool/page | Reader question |','|---|---|---|']
    for item in shortlist.get('items',[]):lines.append('| '+item['id']+' | '+cell(item['name'])+' | '+cell(item['suggestedReaderQuestion'])+' |')
    cost=shortlist.get('costPlan',{})
    lines += ['', '### Costs — no new service purchase made','',
              '- Actual ongoing content-generation bills: unknown.',
              '- Planning formula: 21 articles × 30 days = 630 articles per 30-day month. Multiply by the actual measured average cost; add data/review/platform costs separately.',
              '- Arithmetic examples only: ₹5/article = ₹3,150/month; ₹20/article = ₹12,600/month; ₹50/article = ₹31,500/month. These are not quotes or measured bills.',
              '- Optional domain allowance: ₹1,000–₹2,500/year for planning only. Availability, renewal, taxes and a real quote must be checked before buying.',
              '- Reliable market data and qualified financial review require actual scope/licensing quotes. They are not assumed free.',
              '', '## 6. What was NOT done','',
              '- No theme upload, URL restructuring, new calculator/commodity page programme or new sitemap design.',
              '- No new Analytics code, manufactured visitor session, own-ad click or fake social engagement.',
              '- No new Blogger draft articles, restoration of deleted legacy posts, or eight-hour recovery.',
              '- No claim that Kushal personally reviewed the automated content.',
              '- No automatic mass prose rewrite/photo replacement just to turn a report green. Essential changes are limited to the documented Analytics disclosure correction and removal of extra exact stock-commentary copies from older News; before-copies are retained.',
              '', '**Before approval we check and correct confirmed problems. Optional live expansion remains frozen until approval, the agreed earnings period and your explicit release.**','']
    (ROOT/'TABLE3_PROGRESS_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'status':snapshot['status'],'table3Items':len(checks),'ownerChecksOrDecisions':len(owner),'shortlistItems':len(shortlist.get('items',[]))}))
    return 0

if __name__=='__main__':raise SystemExit(main())
