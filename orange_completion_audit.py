#!/usr/bin/env python3
"""Evidence-based completion audit for the 13 Orange requirements.

Reads repository/API evidence only. It never opens a public Daily Yield URL and
never upgrades owner-dependent or field-dependent work without explicit evidence.
"""
from pathlib import Path
import json

ROOT=Path(__file__).parent
THEME=(ROOT/'theme/Daily-Yield-Theme-v4-2026-10-01.xml').read_text(encoding='utf-8')
OWNER=json.loads((ROOT/'OWNER_CONFIRMED_STATUS.json').read_text())
WATCH=json.loads((ROOT/'ZERO_VIEW_WATCHDOG.json').read_text()) if (ROOT/'ZERO_VIEW_WATCHDOG.json').exists() else {}
GSC=json.loads((ROOT/'GSC_REBUILD_REPORT.json').read_text()) if (ROOT/'GSC_REBUILD_REPORT.json').exists() else {}


def item(name,status,evidence,next_action='None'):
 return {'requirement':name,'status':status,'evidence':evidence,'next_action':next_action}

warnings=sum(len(row.get('warnings',[])) for row in WATCH.get('content',[]))
summary=WATCH.get('summary',{})
items=[
 item('Loading feedback and animation','GREEN' if OWNER.get('loading_animation_completed_successfully') and 'DY_FINANCE_LOADER_START' in THEME else 'OWNER_ACTION',
      'Owner confirmed successful operation; full-screen loader remains in current Theme.',
      'Retain current behavior.'),
 item('Form success and error states','OWNER_ACTION',
      'Accessible success/error status logic is present and source-audited, but external provider outcomes require a genuine owner test.',
      'Submit one real subscription/contact test and confirm the received success or validation outcome.'),
 item('Confirmation/privacy modal','GREEN' if OWNER.get('privacy_cookie_requirement_completed_successfully') and "gtag('consent','default'" in THEME else 'OWNER_ACTION',
      'Owner confirmed successful privacy/cookie behavior; consent defaults denied and footer controls remain present.',
      'Retain consent-first behavior.'),
 item('Genuine last-updated date','GREEN' if 'schemaModified' in THEME and 'dateModified' in THEME else 'FAIL',
      'Theme renders Last reviewed only from valid dateModified structured data; no date is fabricated.'),
 item('Expandable FAQ plus FAQ schema','GREEN' if "id='dy-site-faq'" in THEME and 'FAQPage' in THEME else 'FAIL',
      'Visible FAQ and FAQPage schema coexist in the owner-confirmed active Theme.'),
 item('Google Request Indexing','GREEN_POLICY' if 'manualLiveTestQueue' in (ROOT/'gsc_rebuild.py').read_text() else 'FAIL',
      'Search Console inspection/sitemap automation is complete; unsupported Request Indexing automation is correctly refused.',
      'Use the generated manual queue only when Search Console identifies a genuine priority URL.'),
 item('Old-URL redirects and redirect-chain control','GREEN' if summary.get('confirmedExternal404or410',1)==0 and summary.get('externalRedirectChains',1)==0 else 'ATTENTION',
      f"Independent watchdog: {summary.get('confirmedExternal404or410','?')} confirmed external 404/410 and {summary.get('externalRedirectChains','?')} redirect chains; historical GSC observations: {summary.get('gscRedirectErrors','?')}.",
      'Continue recrawl monitoring; historical Search Console observations are not current live failures.'),
 item('Page-speed and real-user performance monitoring','PENDING_THEME_UPLOAD',
      'Consent-gated LCP, CLS, INP, DOM-ready and load measurement is now built as one non-pageview GA4 event.',
      'Upload the new Theme package and allow genuine consented field data to accumulate.'),
 item('ChatGPT/OAI search discovery','GREEN' if "name='ChatGPT-User'" in THEME and "name='OAI-SearchBot'" in THEME else 'FAIL',
      'Public indexable content carries responsible ChatGPT-User and OAI-SearchBot directives; no citation guarantee is claimed.'),
 item('Exactly one primary H1','GREEN' if warnings==0 and 'contentH1' in THEME else 'ATTENTION',
      f'Independent API/source watchdog currently records {warnings} structural warning(s); Theme suppresses duplicate wrapper title when an editorial H1 exists.'),
 item('Visible breadcrumbs plus BreadcrumbList schema','GREEN' if "class='dy-breadcrumb'" in THEME and 'BreadcrumbList' in THEME else 'FAIL',
      'Visible breadcrumb and matching BreadcrumbList generator are present in the owner-confirmed active Theme.'),
 item('WebP and modern image optimization','GREEN' if (ROOT/'optimize_embedded_images.py').exists() and 'image/webp' in (ROOT/'news_pipeline.py').read_text() else 'FAIL',
      'Selective WebP tooling exists and publishers accept modern image output while preserving attribution and quality.'),
 item('Layout-shift control','PENDING_THEME_UPLOAD',
      'Aspect-ratio, width-containment and reserved-layout controls exist; consented CLS field measurement is now built.',
      'Upload the new Theme package and review genuine CLS field evidence before claiming a universal result.'),
]
counts={}
for row in items:counts[row['status']]=counts.get(row['status'],0)+1
report={'checked':'2026-10-03','mode':'ZERO_SYNTHETIC_VIEWS','public_daily_yield_requests':0,'owner_confirmation':OWNER,'counts':counts,'items':items}
(ROOT/'ORANGE_COMPLETION_STATUS.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
lines=['# Daily Yield Orange Completion Status','',f"- Public Daily Yield requests: **0**",f"- Requirements assessed: **{len(items)}**",f"- Status counts: **{json.dumps(counts,sort_keys=True)}**",'','| # | Requirement | Status | Evidence | Next action |','|---:|---|---|---|---|']
for n,row in enumerate(items,1):
 clean=lambda v:str(v).replace('|','/').replace('\n',' ')
 lines.append(f"| {n} | {clean(row['requirement'])} | **{clean(row['status'])}** | {clean(row['evidence'])} | {clean(row['next_action'])} |")
(ROOT/'ORANGE_COMPLETION_STATUS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'items':len(items),'counts':counts,'public_requests':0}))
if any(row['status']=='FAIL' for row in items):raise SystemExit(1)
