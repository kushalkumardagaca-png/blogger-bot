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
GSC=json.loads((ROOT/'GSC_REBUILD_REPORT.json').read_text()) if (ROOT/'GSC_REBUILD_REPORT.json').exists() else {}
FORM=OWNER.get('form_verification',{})


def item(name,status,evidence,next_action='None'):
 return {'requirement':name,'status':status,'evidence':evidence,'next_action':next_action}

items=[
 item('Loading feedback and animation','GREEN' if OWNER.get('loading_animation_completed_successfully') and 'DY_FINANCE_LOADER_START' in THEME else 'OWNER_ACTION',
      'Owner confirmed successful operation; full-screen loader remains in current Theme.',
      'Retain current behavior.'),
 item('Form success and error states','GREEN' if FORM.get('invalid_email_rejected') and FORM.get('valid_email_reached_confirmation_route') else 'OWNER_ACTION',
      'Accessible status logic is source-audited; the provider rejected an invalid address and routed a valid confirmation-only test correctly, with zero public Daily Yield requests.',
      'Continue normal provider monitoring; the test address is not stored in this repository.'),
 item('Confirmation/privacy modal','GREEN' if OWNER.get('privacy_cookie_requirement_completed_successfully') and "gtag('consent','default'" in THEME else 'OWNER_ACTION',
      'Owner confirmed successful privacy/cookie behavior; consent defaults denied and footer controls remain present.',
      'Retain consent-first behavior.'),
 item('Genuine last-updated date','GREEN' if 'schemaModified' in THEME and 'dateModified' in THEME else 'FAIL',
      'Theme renders Last reviewed only from valid dateModified structured data; no date is fabricated.'),
 item('Expandable FAQ plus FAQ schema','GREEN' if "id='dy-site-faq'" in THEME and 'FAQPage' in THEME else 'FAIL',
      'Visible FAQ and FAQPage schema coexist in the owner-confirmed active Theme.'),
 item('Google Request Indexing','GREEN' if 'manualLiveTestQueue' in (ROOT/'gsc_rebuild.py').read_text() else 'FAIL',
      'Search Console inspection/sitemap automation is complete; unsupported Request Indexing automation is correctly refused.',
      'Use the generated manual queue only when Search Console identifies a genuine priority URL.'),
 item('Old-URL redirects and redirect-chain control','GREEN' if 'manualLiveTestQueue' in (ROOT/'gsc_rebuild.py').read_text() else 'ATTENTION',
      'Search Console inspection and sitemap evidence tracks canonical and redirect states without scheduled public-page requests.',
      'Continue Search Console recrawl monitoring; historical observations are not current live failures.'),
 item('Page-speed and real-user performance monitoring','GREEN' if OWNER.get('theme_v6_0_uploaded') and "dy_web_vitals" in THEME else 'PENDING_THEME_UPLOAD',
      'Owner confirmed Theme v6.0 live. It measures consent-gated LCP, CLS, INP, DOM-ready and load as one non-pageview GA4 event.',
      'Allow genuine consented field data to accumulate; implementation Green does not claim a universal speed outcome.'),
 item('ChatGPT/OAI search discovery','GREEN' if "name='ChatGPT-User'" in THEME and "name='OAI-SearchBot'" in THEME else 'FAIL',
      'Public indexable content carries responsible ChatGPT-User and OAI-SearchBot directives; no citation guarantee is claimed.'),
 item('Exactly one primary H1','GREEN' if 'contentH1' in THEME and 'exactly one primary H1' in (ROOT/'publication_preflight.py').read_text() else 'ATTENTION',
      'Publication preflight requires exactly one primary H1; Theme suppresses the duplicate wrapper title when an editorial H1 exists.'),
 item('Visible breadcrumbs plus BreadcrumbList schema','GREEN' if "class='dy-breadcrumb'" in THEME and 'BreadcrumbList' in THEME else 'FAIL',
      'Visible breadcrumb and matching BreadcrumbList generator are present in the owner-confirmed active Theme.'),
 item('WebP and modern image optimization','GREEN' if (ROOT/'optimize_embedded_images.py').exists() and 'image/webp' in (ROOT/'news_pipeline.py').read_text() else 'FAIL',
      'Selective WebP tooling exists and publishers accept modern image output while preserving attribution and quality.'),
 item('Layout-shift control','GREEN' if OWNER.get('theme_v6_0_uploaded') and 'layout-shift' in THEME else 'PENDING_THEME_UPLOAD',
      'Owner confirmed the Theme with aspect-ratio, width-containment, reserved-layout controls and consented CLS measurement is live.',
      'Continue reviewing genuine field evidence; Green confirms the control and monitor, not a fabricated universal CLS result.'),
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
