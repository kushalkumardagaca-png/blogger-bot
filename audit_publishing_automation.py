#!/usr/bin/env python3
"""Static and template audit for the 5 master + 20 news Daily Yield automations."""
from pathlib import Path
import ast, datetime as dt, json, re, sys

ROOT=Path(__file__).parent
IST=dt.timezone(dt.timedelta(hours=5,minutes=30))
checks=[]
def check(name,ok,detail=""):
 checks.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})

def crons(path):
 return re.findall(r"cron:\s*['\"]([^'\"]+)",Path(path).read_text())

article_expected=['45 1 * * *','15 5 * * *','15 8 * * *','30 11 * * *','15 14 * * *']
news_expected=['15 22 * * *','15 0 * * *','45 2 * * *','15 4 * * *','45 5 * * *','45 6 * * *','30 9 * * *','45 10 * * *','45 11 * * *','15 13 * * *','45 14 * * *','45 15 * * *']
aw=ROOT/'.github/workflows/daily_blogger_poster.yml'; nw=ROOT/'.github/workflows/daily_news_wires.yml'
check('Five master-article triggers',crons(aw)==article_expected,str(crons(aw)))
check('Twelve news preflight clusters',crons(nw)==news_expected,str(crons(nw)))
# Verify UTC cron arithmetic, not just literal strings.
def ist_minute(cron):
    minute,hour=map(int,cron.split()[:2]); return (hour*60+minute+330)%1440
article_targets=[8*60,11*60+30,14*60+30,17*60+45,20*60+30]
check('Every master trigger is exactly 45 minutes early',
      all((target-ist_minute(cron))%1440==45 for cron,target in zip(article_expected,article_targets)))
check('Master runs cannot overlap','cancel-in-progress: false' in aw.read_text() and 'daily-yield-master-publisher' in aw.read_text())
check('News runs cannot overlap','cancel-in-progress: false' in nw.read_text() and 'daily-yield-news-wires' in nw.read_text())

ap=(ROOT/'auto_blogger_publisher.py').read_text(); np=(ROOT/'news_pipeline.py').read_text()
check('Master publisher uses IST','datetime.now(IST)' in ap)
check('Master tracker advances only after live URL','tracker will not advance' in ap and 'if not api_res or not api_res.get("url")' in ap)
check('Master duplicate recovery','posts().search' in ap and 'Existing exact-title post recovered' in ap)
check('Master canonical repaired to live URL','predicted.group(0)' in ap and 'posts().update' in ap)
check('Master packages always rebuilt fresh','Always rebuild with the current date' in ap and 'Loading pre-compiled' not in ap)
check('Master byline is current','By <strong>Kushal K. Daga</strong>' in ap and 'By CA Kushal K. Daga' not in ap)
check('Master publisher brand is Daily Yield','"name": "Daily Yield"' in ap and '"name": "Finance by CA Kushal"' not in ap)
check('Canonical social identity uses new LinkedIn and omits closed X','https://www.linkedin.com/in/dailyyeild' in ap and 'x.com/CAKUSHAL2509' not in ap and 'finance-by-kushal' not in ap)
check('Master links both market desks','/p/markets-today.html' in ap and '/p/global-snapshot.html' in ap)
check('Master posts cannot enter News hub','"News"' not in re.search(r'labels = \[(.*?)\]',ap,re.S).group(1))
check('Master articles include related-reading shelf','ensure_related_articles' in ap and 'fetch_public_posts' in ap)
check('Master articles include continuous gesture motion','ensure_continuous_motion' in ap)
check('Master hero image is preflight-validated','safe_image' in ap and 'FALLBACK_MARKET' in ap)
check('News hero image is preflight-validated','safe_image' in np and 'FALLBACK_PERSONAL' in np)
check('Master structure passes fail-closed publication preflight','assert_publishable(title, html, labels)' in ap)
check('News structure passes fail-closed publication preflight','assert_publishable(art["title"], art["html"], art["labels"])' in np)
check('Master packages retain comprehensive family directory','ensure_family(html)' in ap)
check('News packages retain comprehensive family directory','ensure_family(art["html"])' in np)
brand=(ROOT/'brand_identity.py').read_text(); family=(ROOT/'page_family.py').read_text()
check('All future master and News packages retain Daily Yield favicon identity','ensure_brand_identity(content)' in family and 'DY_BRAND_IDENTITY_START' in brand)
check('Brand runtime is self-contained and makes no public-site request','data:image/svg+xml;base64,' in brand and 'fetch(' not in brand and 'dailyyield.blogspot.com' not in brand)
check('News packages inject SEO and social metadata','ensure_seo_meta' in np and 'DY_SEO_META_START' in (ROOT/'seo_meta.py').read_text())
check('News editions include related-reading shelf','ensure_related_articles' in np and 'fetch_public_posts' in np)
check('News editions include continuous gesture motion','ensure_continuous_motion' in np)

# Literal DESKS inventory without executing network code.
tree=ast.parse(np); desks=None
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DESKS' for t in node.targets):
  desks=ast.literal_eval(node.value);break
check('Exactly 20 news desks',isinstance(desks,dict) and len(desks)==20,str(len(desks or {})))
nums=sorted(v[0] for v in desks.values()); labels=[v[1] for v in desks.values()]
check('News desk numbers are 1–20',nums==list(range(1,21)))
check('News labels are unique',len(labels)==len(set(labels))==20)
expected_clusters=[['australia','south-korea'],['global','india'],['market','macro'],['germany','france'],
                   ['uk','japan'],['china','spain'],['corporate','italy'],['brazil'],
                   ['us','canada'],['mexico'],['personal'],['russia']]
actual_clusters=[]
for cron in news_expected:
    start=ist_minute(cron)
    due=[]
    for desk,values in desks.items():
        hh,mm=map(int,values[3].split(':')); delta=(hh*60+mm-start)%1440
        if delta<=60: due.append(desk)
    actual_clusters.append(sorted(due))
expected_clusters=[sorted(group) for group in expected_clusters]
check('Each news preflight selects its intended desk cluster',actual_clusters==expected_clusters,str(actual_clusters))
check('News labels exactly two per post','"labels": ["News", label]' in np)
check('News launch gate is 2026-09-25','LAUNCH_DATE = dt.date(2026, 9, 25)' in np)
check('News cluster selector covers paired desks','PREFLIGHT_MINUTES = 60' in np)
check('News duplicate recovery uses Blogger API without synthetic pageviews',
      'live_post_exists(expected_url, token)' in np and '/posts/bypath?' in np
      and 'response.read().decode("utf-8"' not in np)
check('News source policy is current','official institutions plus established, reputable newsrooms' in np)
check('News finance filter enabled','FINANCE_RE.search' in np)
check('News requires at least one genuinely current item','if current_count == 0' in np)
check('Significance ranks rather than cancels a desk edition',
      'current = relevant[:selection_cap]' in np and 'finance_significant' not in np)
check('News selection is capped at the strongest fifteen current items',
      'selection_cap=15' in np and 'current = relevant[:selection_cap]' in np)
check('Every country desk has broad current-news discovery fallback',
      'def discovery_sources(desk)' in np and "med.append(discovery)" in np and "when:1d" in np)
check('Discovery fallback retains only approved named publishers',
      'GNR_ALLOWED_PUBLISHERS' in np and 'pub not in GNR_ALLOWED_PUBLISHERS' in np)
check('Older context is capped at three and explicitly labelled',
      'len(background) >= min(3, 10 - len(current))' in np
      and 'Background—not current-window news.' in np
      and 'Background Context — Not Current-Period News' in np)
check('News byline is current','By Kushal K. Daga' in np and 'By CA Kushal K. Daga' not in np)
check('News publisher brand is Daily Yield','"name": "Daily Yield"' in np and '"name": "Finance by CA Kushal"' not in np)
check('News schema uses actual build/publish time','win_end.isoformat(timespec="seconds")' in np)
check('News meta description capped','if len(meta) > 158' in np)
check('News titles show desk, publication date and exact coverage window first',
      'title = f"{desk_title_prefix(desk)} · {publish_lead} · Coverage {coverage_lead}' in np
      and 'coverage_window_text' in np)
check('Older dates never alter the stated current coverage window',
      'background_items = [i for i in items if i.get("background")]' in np
      and 'coverage_lead = coverage_window_text(win_start, win_end)' in np
      and 'extend back max 72h' not in np)
check('News links both market desks','/p/markets-today.html' in np and '/p/global-snapshot.html' in np)
check('Trusted links disclose source type','"Source:" if it.get("media") else "Official:"' in np)

tracker=json.loads((ROOT/'published_tracker.json').read_text()); news_tracker=json.loads((ROOT/'news_tracker.json').read_text())
master_next=tracker.get('next_topic_index')
check('Master tracker next-topic state is valid',isinstance(master_next,int) and 0 <= master_next <= 500,
      f"next index {master_next}")
launch_date=dt.date(2026,9,25); audit_today=dt.datetime.now(IST).date()
news_desks=news_tracker.get('desks',{}) if isinstance(news_tracker,dict) else {}
if audit_today < launch_date:
 tracker_ok = news_tracker == {'desks':{}}
else:
 tracker_ok = (set(news_desks).issubset(set(desks)) and all(
     isinstance(v,dict) and v.get('edition','') <= audit_today.isoformat()
     and v.get('url','').startswith('https://dailyyield.blogspot.com/') for v in news_desks.values()))
check('News tracker launch/state is valid',tracker_ok,f"{len(news_desks)} desk edition(s) recorded")
check('No obsolete blog URL in production engines','financebycakushal.blogspot.com' not in ap+np)
check('No obsolete market page in production engines','share-market_0718113516' not in ap+np and 'Market Explorer' not in ap+np)

failed=[x for x in checks if x['status']=='FAIL']
result={'checked_at_ist':dt.datetime.now(IST).isoformat(timespec='seconds'),'summary':{'pass':len(checks)-len(failed),'fail':len(failed)},'checks':checks}
if '--check-only' not in sys.argv:
 (ROOT/'PUBLISHING_AUTOMATION_AUDIT.json').write_text(json.dumps(result,indent=2))
 lines=['# Daily Yield Publishing Automation — Final Audit','',f"**Result:** {len(checks)-len(failed)} PASS · {len(failed)} FAIL",'',
 'Scope: five daily master articles and twenty daily news wires, including branding, timing, trackers, duplication, schema, sources, labels and current market-page links.','']
 for x in checks:lines.append(f"- {'✅' if x['status']=='PASS' else '❌'} **{x['name']}**"+(f" — {x['detail']}" if x['detail'] else ''))
 (ROOT/'PUBLISHING_AUTOMATION_AUDIT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(result['summary']))
if failed:
 for x in failed:print('FAIL',x['name'],x['detail'])
 raise SystemExit(1)
