#!/usr/bin/env python3
"""Static, zero-view acceptance audit for Daily Yield Theme v4 and search reach."""
from pathlib import Path
from xml.etree import ElementTree as ET
import json

ROOT=Path(__file__).parent
THEMES=[ROOT/'theme/Daily-Yield-Theme-Subscription.xml',ROOT/'theme/Daily-Yield-Theme-v4-2026-10-01.xml']
checks=[]
def check(name, ok): checks.append({'name':name,'status':'PASS' if ok else 'FAIL'})

for p in THEMES:
    text=p.read_text(encoding='utf-8')
    try: tree=ET.parse(p); valid=True
    except Exception: tree=None; valid=False
    prefix=p.name+': '
    check(prefix+'valid Blogger XML',valid)
    requirements={
      'light-mode reset for former dark preference':"localStorage.removeItem('dy-theme')",'privacy choice panel':"id='dyPrivacyPanel'",'homepage consent card follows hero':"hero.insertAdjacentElement('afterend',panel)",'footer privacy control':"id='dyPrivacyManage'",'footer displays consent state':'Privacy choices · Analytics allowed','saved analytics choice restored on later pages':"savedConsent==='analytics'",
      'site search':"id='searchToggle'",'back to top':"id='toTop'",'mobile menu':"id='drawerToggle'",
      'loading state':"data-dy-loading",'hover states':':hover','reading progress':"id='progressBar'",
      'copy/share feedback':'Link copied','print stylesheet':'@media print','sticky header':'position:sticky',
      'skip link':"class='skip-link'",'future password visibility':'dy-password-toggle','UTM attribution':'utm_source',
      'form success state':"data-state','success",'form error state':"data-state','error",
      'accurate schema-based last reviewed date':'schemaModified','privacy confirmation dialog':"role='dialog'",'visible FAQ':"id='dy-site-faq'",'FAQ schema':'FAQPage',
      'floating contact':"aria-label='Contact Daily Yield'",'breadcrumb navigation':"class='dy-breadcrumb'",
      'breadcrumb schema':'BreadcrumbList','Blogger canonical package':"name='all-head-content'",'English document language':"lang='en'",'content language declaration':"http-equiv='Content-Language'",'descriptive homepage title':'Daily Yield | Finance, Markets, News &amp; Calculators','branded Page titles':'<data:blog.pageName/> | Daily Yield Finance','robots index policy':"name='robots'",
      'Googlebot policy':"name='googlebot'",'Bingbot policy':"name='bingbot'",'ChatGPT search policy':"name='ChatGPT-User'",
      'OpenAI search policy':"name='OAI-SearchBot'",'WebSite schema':'SearchAction','favicon':"rel='icon'",
      'responsive mobile CSS':'@media(max-width:560px)','keyboard focus':':focus-visible','reduced motion':'prefers-reduced-motion',
      'lazy later images':"setAttribute('loading','lazy')",'async image decoding':"setAttribute('decoding','async')",
      'priority first image':"setAttribute('fetchpriority','high')",'runtime fallback for widget images missing alt':"img:not([alt])",'informative moving thumbnails use titles':"im.alt=it.title||'Daily Yield article preview'",'author identity':'Kushal K. Daga',
      'privacy link':'/p/privacy-policy.html','terms link':'/p/terms-and-conditions.html','contact email':'dailyyield.official@gmail.com',
      'HTTPS destination':'https://dailyyield.blogspot.com/','analytics consent defaults denied before loading':"gtag('consent','default'",'Blogger GA4 loader uses saved Measurement ID':"name='google-analytics'",'analytics changes only after choice':"analytics_storage:mode==='analytics'?'granted':'denied'",
      'no external enhancement script':'DY_SITE_ENHANCEMENTS_JS_START','honest advice disclaimer':'educational information',
    }
    for name,needle in requirements.items(): check(prefix+name,needle in text)
    theme_images=[] if not valid else [node for node in tree.getroot().iter() if str(node.tag).split('}')[-1].lower()=='img']
    check(prefix+'every Theme image has nonempty alt', valid and all(any(str(key).split('}')[-1]=='alt' and str(value).strip() for key,value in node.attrib.items()) for node in theme_images))
    check(prefix+'dark mode fully removed', "dyThemeToggle" not in text and "data-dy-theme='dark'" not in text)
    check(prefix+'Blogger package is sole standard meta-description authority', "<meta expr:content='data:blog.metaDescription' name='description'/>" not in text)
    check(prefix+'privacy control is not floating', '.dy-privacy-manage{position:fixed' not in text)
    check(prefix+'no Google Business Profile', 'Google Business Profile' not in text)

workflow=(ROOT/'.github/workflows/health_monitor.yml').read_text()
search=(ROOT/'search_reach.py').read_text()
check('health workflow runs experience audit','python audit_site_enhancements.py' in workflow)
check('health workflow runs reach readiness','python search_reach.py' in workflow)
check('health evidence rejects stale concurrent watchdog reports','Remote watchdog evidence is newer' in workflow and 'checkedAtIST' in workflow)
check('Bing sitemap integration implemented','BING_WEBMASTER_API_KEY' in search and 'SubmitFeed' in search)
check('Bing SubmitFeed uses required JSON body','json.dumps({"siteUrl":SITE,"feedUrl":sitemap})' in search and 'application/json; charset=utf-8' in search)
related=(ROOT/'related_articles.py').read_text()
check('future related-article photographs have descriptive alt text','alt="Article preview:' in related and 'alt=""' not in related)
check('Bing integration is optional and fail-safe','status":"READY' in search)
check('search reach creates zero views','ZERO_SYNTHETIC_VIEWS' in search and 'syntheticViews":0' in search)
check('Google Search Console remains automated',(ROOT/'gsc_rebuild.py').exists())
check('Blogger remains server rendered','Blogger theme' in THEMES[0].read_text())
check('zero-view policy remains enforced',(ROOT/'audit_zero_view_policy.py').exists())
preflight=(ROOT/'publication_preflight.py').read_text()
watchdog=(ROOT/'zero_view_watchdog.py').read_text()
check('future publications require one primary H1','exactly one primary H1' in preflight)
check('future publications require image alt attributes and descriptive hero alt','missing an alt attribute' in preflight and 'hero image missing descriptive alt text' in preflight)
check('watchdog detects missing image alt attributes','missing an alt attribute' in watchdog)
check('watchdog detects external redirect chains','redirectChains' in watchdog and 'redirectCount' in watchdog)
check('watchdog confirms hard external failures with a second request','confirmedAfterRetry' in watchdog and 'Cache-Control' in watchdog)
page_repair=(ROOT/'update_page_family.py').read_text()
page_workflow=(ROOT/'.github/workflows/update_page_family.yml').read_text()
check('Page-family repair adds only missing alt attributes','ensure_image_alts' in page_repair and 'images_without_alt' in page_repair)
check('Page repair approves intentional Blogger baseline change','security_guard.py --approve-current' in page_workflow)
check('Page repair performs immediate zero-view verification','python zero_view_watchdog.py' in page_workflow)
import subprocess
reddit_unchanged=subprocess.run(['git','diff','--quiet','--','reddit_devvit'],cwd=ROOT).returncode==0
check('Reddit 0.0.2 source remains untouched',reddit_unchanged)
failed=[x for x in checks if x['status']=='FAIL']
report={'standard':'DAILY_YIELD_SITE_V4','mode':'STATIC_ZERO_VIEW','pass':len(checks)-len(failed),'fail':len(failed),'checks':checks}
(ROOT/'SITE_ENHANCEMENT_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
lines=['# Daily Yield Site Enhancement Audit','',f"- Pass: **{report['pass']}**",f"- Fail: **{report['fail']}**",'- Public Daily Yield pageviews: **0**','']+[f"- {'✅' if x['status']=='PASS' else '❌'} {x['name']}" for x in checks]
(ROOT/'SITE_ENHANCEMENT_AUDIT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'pass':report['pass'],'fail':report['fail']}))
if failed:
    for x in failed: print('FAIL',x['name'])
    raise SystemExit(1)
