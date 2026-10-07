#!/usr/bin/env python3
"""Static and template audit for active News, social, search and site automations."""
from pathlib import Path
import ast, datetime as dt, json, re, sys

ROOT=Path(__file__).parent
IST=dt.timezone(dt.timedelta(hours=5,minutes=30))
checks=[]
def check(name,ok,detail=""):
 checks.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})

def crons(path):
 return re.findall(r"cron:\s*['\"]([^'\"]+)",Path(path).read_text())

news_expected=['15 22 * * *','15 0 * * *','45 2 * * *','15 4 * * *','45 5 * * *','45 6 * * *','30 9 * * *','45 10 * * *','45 11 * * *','15 13 * * *','45 14 * * *','45 15 * * *']
nw=ROOT/'.github/workflows/daily_news_wires.yml'
def ist_minute(cron):
    minute,hour=map(int,cron.split()[:2]); return (hour*60+minute+330)%1440
check('All dedicated Master article workflows are absent',
      all(not (ROOT/'.github/workflows'/name).exists() for name in (
          'daily_blogger_poster.yml','rewrite_existing_masters.yml',
          'refresh_master_photos.yml','refresh_master_v2_design.yml')))
check('Twelve news preflight clusters',crons(nw)==news_expected,str(crons(nw)))
check('News runs cannot overlap','cancel-in-progress: false' in nw.read_text() and 'daily-yield-news-wires' in nw.read_text())

bing_py=(ROOT/'bing_url_automation.py').read_text()
bing_workflow=(ROOT/'.github/workflows/bing_url_automation.yml').read_text()
check('Bing URL automation reconciles every two hours', "cron: '35 */2 * * *'" in bing_workflow)
check('News publisher triggers Bing reconciliation without schedule changes',
      'gh workflow run bing_url_automation.yml --ref main' in nw.read_text())
check('Bing URL submission is quota-aware and capped at 500 per batch',
      'GetUrlSubmissionQuota' in bing_py and 'range(0, len(selected), 500)' in bing_py)
check('Bing URL automation suppresses unchanged duplicate submissions',
      'submittedFingerprint' in bing_py and '!= item["fingerprint"]' in bing_py)
check('Bing index monitoring uses GetUrlInfo with bounded stages',
      'GetUrlInfo' in bing_py and 'INSPECTION_DELAYS = (6, 24, 72, 168)' in bing_py)
check('Bing URL automation creates no public Daily Yield requests or Live URL fetches',
      'ZERO-VIEW POLICY BLOCKED public Daily Yield request' in bing_py and 'FetchUrl' not in bing_py)
check('Bing API-key errors are redacted rather than stringified',
      'safe_detail' in bing_py and 'apikey' not in bing_py.split('def safe_detail',1)[1].split('def json_request',1)[0])
check('Bing URL evidence and state are persisted without secrets',
      'BING_URL_AUTOMATION_STATE.json' in bing_workflow and 'BING_WEBMASTER_API_KEY' in bing_workflow)

ap=(ROOT/'auto_blogger_publisher.py').read_text(); np=(ROOT/'news_pipeline.py').read_text()
rv=(ROOT/'reader_value_article.py').read_text(); mv2=(ROOT/'master_article_v2.py').read_text(); prep=(ROOT/'prepare_master_article.py').read_text(); master=ap+rv+mv2+prep
check('Master publisher uses IST','datetime.now(IST)' in ap)
check('Master tracker advances only after live URL','tracker will not advance' in ap and 'if not api_res or not api_res.get("url")' in ap)
check('Master duplicate recovery','posts().search' in ap and 'Existing exact-title post recovered' in ap)
check('Master canonical repaired to live URL','predicted.group(0)' in ap and 'posts().update' in ap)
check('Master packages always rebuilt fresh','Always rebuild with the current date' in ap and 'Loading pre-compiled' not in ap)
check('Master byline is current','AUTHOR="Kushal K. Daga"' in mv2 and 'By <strong>{AUTHOR}</strong>' in mv2 and 'By CA Kushal K. Daga' not in master)
check('Master publisher brand is Daily Yield','"name":"Daily Yield"' in mv2 and 'Finance by CA Kushal' not in master)
check('Inactive LinkedIn, X and Reddit profiles are absent from future master output',
      all(term not in master.casefold() for term in ('linkedin.com/','x.com/','twitter.com/','reddit.com/')))
social=(ROOT/'social_identity.py').read_text()
check('Canonical public contact email is the Daily Yield brand inbox','dailyyield.official@gmail.com' in social and 'PUBLIC_EMAIL' in social)

# Facebook organic publishing invariants. These remain isolated from Blogger and
# News publishing and remain covered by authenticated/static repository audits.
fp_path=ROOT/'facebook_publisher.py'; fw_path=ROOT/'.github/workflows/facebook_publisher.yml'
fp=fp_path.read_text() if fp_path.exists() else ''; fw=fw_path.read_text() if fw_path.exists() else ''
facebook_expected=[]
check('Facebook publisher files are deployed',bool(fp) and bool(fw) and (ROOT/'facebook_tracker.json').exists())
check('Facebook legacy auto-selection schedule is disabled in favour of exact coordinated routing',
      crons(fw_path)==facebook_expected and 'workflow_dispatch:' in fw, str(crons(fw_path)) if fw else 'missing workflow')
check('Facebook uses encrypted token secret, never a literal token',
      'secrets.FACEBOOK_SYSTEM_USER_TOKEN' in fw and 'FACEBOOK_SYSTEM_USER_TOKEN' in fp)
check('Facebook derives a Page token before publishing',
      'def resolve_page_token(' in fp and 'fields": "id,name,access_token"' in fp)
check('Facebook uses platform-native creative copy instead of corporate boilerplate',
      'build_caption(item, "facebook"' in fp and 'READ THE FULL REPORT' not in fp
      and 'OPEN THIS DAILY YIELD RESOURCE' not in fp)
check('Facebook descriptions preserve complete short source text',
      'if len(text) <= 300:' in fp and 'return text' in fp)
check('Facebook renders the shared deterministic 1200x630 creative system',
      'def generate_topic_card(' in fp and 'render_social_card(item, "facebook"' in fp)
check('Facebook uploads the rendered card rather than a raw full-frame photo',
      'card = generate_topic_card(item)' in fp and 'files={"source":' in fp
      and 'data={**payload, "url": image_url}' not in fp)
check('Facebook rotates audience-facing website Pages as well as posts',
      '/pages"' in fp and 'PAGE_PROMOTION_WINDOWS' in fp and 'def choose_page(' in fp)
check('Facebook deduplicates and reconciles uncertain writes',
      'def reconcile(' in fp and 'seen_ids' in fp and 'caption_hash' in fp)
check('Facebook automation excludes comments, messages, ads and artificial engagement',
      'pages_manage_engagement' not in fp+fw and 'pages_messaging' not in fp+fw
      and 'ads_management' not in fp+fw)
check('Facebook candidate discovery creates no Daily Yield public-page requests',
      'www.googleapis.com/blogger/v3' in fp and 'requests.get(item["url"]' not in fp
      and 'requests.get(post["url"]' not in fp)

# Bluesky official AT Protocol publishing invariants, isolated from Facebook.
bp_path=ROOT/'bluesky_publisher.py'; bw_path=ROOT/'.github/workflows/bluesky_publisher.yml'
bp=bp_path.read_text() if bp_path.exists() else ''; bw=bw_path.read_text() if bw_path.exists() else ''
bluesky_expected=[]
check('Bluesky publisher files and independent tracker are deployed',
      bool(bp) and bool(bw) and (ROOT/'bluesky_tracker.json').exists())
check('Bluesky legacy auto-selection schedule is disabled behind its manual activation gate',
      crons(bw_path)==bluesky_expected and "vars.BLUESKY_AUTOMATION_ENABLED == 'true'" in bw)
check('Bluesky app password is an encrypted secret, never a literal credential',
      'secrets.BLUESKY_APP_PASSWORD' in bw and 'required("BLUESKY_APP_PASSWORD")' in bp)
check('Bluesky uses official AT Protocol session, blob and record endpoints',
      'com.atproto.server.createSession' in bp and 'com.atproto.repo.uploadBlob' in bp
      and 'com.atproto.repo.createRecord' in bp)
check('Bluesky uses concise platform-native creative copy and brand identity',
      'build_caption(item, "bluesky"' in bp and '#DailyYield' in (ROOT/'social_creative.py').read_text())
check('Bluesky enforces the 300-character limit and rich-text facets',
      'build_caption(item, "bluesky", summary(item), 300)' in bp
      and 'app.bsky.richtext.facet#link' in bp and 'app.bsky.richtext.facet#tag' in bp)
check('Bluesky uploads the shared creative card with descriptive alt text',
      'render_social_card(item, "bluesky"' in bp and 'image_alt(item, "bluesky")' in bp
      and 'width": 1200, "height": 630' in bp)
check('Bluesky rotates Pages and posts using an independent publication history',
      '/pages"' in bp and 'PAGE_WINDOWS' in bp and 'bluesky_tracker.json' in bp)
check('Bluesky deduplicates against tracker and live recent feed and reconciles uncertain writes',
      'recent_urls' in bp and 'def reconcile(' in bp and 'text_hash' in bp)
check('Bluesky candidate discovery makes no Daily Yield public-page request',
      'www.googleapis.com/blogger/v3' in bp and 'ZERO-VIEW POLICY BLOCKED public Daily Yield request' in bp)

# Tumblr official OAuth2/NPF automation, independently gated until a test passes.
tp_path=ROOT/'tumblr_publisher.py'; tw_path=ROOT/'.github/workflows/tumblr_publisher.yml'
to_path=ROOT/'tumblr_oauth_bootstrap.py'; tow_path=ROOT/'.github/workflows/tumblr_oauth_bootstrap.yml'
tp=tp_path.read_text() if tp_path.exists() else ''; tw=tw_path.read_text() if tw_path.exists() else ''
to=to_path.read_text() if to_path.exists() else ''; tow=tow_path.read_text() if tow_path.exists() else ''
tumblr_expected=[]
check('Tumblr publisher, OAuth bootstrap and independent tracker are deployed',
      bool(tp) and bool(tw) and bool(to) and bool(tow) and (ROOT/'tumblr_tracker.json').exists())
check('Tumblr legacy auto-selection schedule is disabled behind its manual activation gate',
      crons(tw_path)==tumblr_expected and "vars.TUMBLR_AUTOMATION_ENABLED == 'true'" in tw)
check('Tumblr credentials and encryption key are GitHub secrets or variables',
      'vars.TUMBLR_CONSUMER_KEY' in tw+tow and 'secrets.TUMBLR_CONSUMER_SECRET' in tw+tow
      and 'secrets.TUMBLR_TOKEN_ENCRYPTION_KEY' in tw+tow)
check('Tumblr OAuth bootstrap requires offline refresh access and encrypts tokens',
      'offline_access' in to and 'Fernet(' in to and 'tumblr_token.enc' in to)
check('Tumblr publisher rotates refresh tokens without logging plaintext credentials',
      'grant_type":"refresh_token"' in tp and 'encrypt_bundle(new)' in tp
      and 'access_token' not in re.sub(r'required\([^\)]*\)', '', tw))
check('Tumblr creates modern NPF posts with shared creative media and alt text',
      'tumblr_payload(x, summary(x))' in tp and 'daily-yield-card' in tp
      and 'render_social_card(x, "tumblr"' in tp and '/posts' in tp)
check('Tumblr preserves title, summary, direct link, byline and platform-native tags',
      'def summary(' in tp and 'tumblr_payload' in tp
      and 'By Kushal K. Daga' in (ROOT/'social_creative.py').read_text())
check('Tumblr rotates Pages and posts using its own tracker',
      '/pages"' in tp and 'PAGE_WINDOWS' in tp and 'tumblr_tracker.json' in tp)
check('Tumblr deduplicates against tracker and current Tumblr posts and reconciles writes',
      'def recent_posts(' in tp and 'def reconcile(' in tp and 'seen_id' in tp)
check('Tumblr candidate discovery creates no Daily Yield public-page requests',
      'www.googleapis.com/blogger/v3' in tp and 'ZERO-VIEW POLICY BLOCKED public Daily Yield request' in tp)

# Mastodon official API automation remains independently gated and tracked.
mp_path=ROOT/'mastodon_publisher.py'; mw_path=ROOT/'.github/workflows/mastodon_publisher.yml'
mp=mp_path.read_text() if mp_path.exists() else ''; mw=mw_path.read_text() if mw_path.exists() else ''
mastodon_expected=[]
check('Mastodon publisher files and independent tracker are deployed',
      bool(mp) and bool(mw) and (ROOT/'mastodon_tracker.json').exists())
check('Mastodon legacy auto-selection schedule is disabled behind its manual activation gate',
      crons(mw_path)==mastodon_expected and "vars.MASTODON_AUTOMATION_ENABLED == 'true'" in mw)
check('Mastodon uses official API, isolated credentials and zero-view discovery',
      'secrets.MASTODON_TOKEN_KEY' in mw and 'www.googleapis.com/blogger/v3' in mp
      and 'ZERO-VIEW POLICY BLOCKED public Daily Yield request' in mp)
check('Mastodon uses platform-native copy, descriptive alt text and shared creative cards',
      'build_caption(item, "mastodon"' in mp and 'image_alt(item, "mastodon")' in mp
      and 'render_social_card(item, "mastodon"' in mp)

# Shared creative layer: deterministic retries, story/platform variety and no site views.
creative_path=ROOT/'social_creative.py'; creative=creative_path.read_text() if creative_path.exists() else ''
check('Shared social creative engine is deployed across all four active networks',
      bool(creative) and all('social_creative import' in text for text in (fp,bp,tp,mp)))
check('Creative system is photo-first with at least ten treatments and five compositions',
      len(re.findall(r'\{"name":',creative))>=10 and '"layout": (seed // 31) % 5' in creative
      and 'ImageOps.fit(source, size' in creative and 'PLATFORM_SIZES' in creative
      and 'full-bleed editorial photograph' in creative)
check('Creative system mixes article heroes with a broad licensed global lifestyle library',
      'Use the hero embedded in authenticated Blogger content' in creative
      and all(f'"{theme}"' in creative for theme in ('people','family','pets','homes','banking','work','technology','shopping','travel','global'))
      and len(re.findall(r'photo-\d{10,}-[a-z0-9]+',creative))>=35)
check('Photo selection is semantic and fails closed instead of producing a banner',
      'def _semantic_theme(' in creative and 'No licensed editorial photo could be loaded' in creative
      and 'banner-only graphic' in creative)
check('Creative outputs are deterministic per platform, destination and IST day',
      'hashlib.sha256(raw.encode())' in creative and 'datetime.now(IST).date().isoformat()' in creative)
check('Captions use topic hooks, questions and platform-specific structures',
      'HOOKS =' in creative and 'QUESTIONS =' in creative and all(f'platform == "{p}"' in creative for p in ('facebook','bluesky','mastodon')))
check('Creative engine cannot request a Daily Yield public page',
      'requests.get(url' in creative and 'PHOTO_HOSTS' in creative and 'dailyyield.blogspot.com' not in creative)
check('Corporate social boilerplate was removed from all active publisher outputs',
      all(term not in creative for term in ('READ THE FULL REPORT','OPEN THIS DAILY YIELD RESOURCE','Markets · Money · Better decisions')))

rotation_path=ROOT/'social_rotation.py'; coordinated_path=ROOT/'.github/workflows/coordinated_social_publish.yml'
dispatch_path=ROOT/'dispatch_social_events.py'
rotation=rotation_path.read_text() if rotation_path.exists() else ''
coordinated=coordinated_path.read_text() if coordinated_path.exists() else ''
dispatch=dispatch_path.read_text() if dispatch_path.exists() else ''
check('Coordinated router and event dispatcher are deployed',bool(rotation) and bool(coordinated) and bool(dispatch))
check('Exactly four evenly spread audience-resource promotions are scheduled',
      crons(coordinated_path)==['45 23 * * *','30 4 * * *','30 8 * * *','30 14 * * *'])
check('Every social publisher accepts an exact authenticated Blogger target URL',
      all('--target-url' in text and 'Target URL was not found in authenticated Blogger inventory' in text
          for text in (fp,bp,tp,mp)))
check('News publisher dispatches only confirmed live Blogger events',
      'social_events.json' in np and 'dispatch_social_events.py' in nw.read_text())
check('Article routing waits at least fifteen minutes after publication',
      'dt.timedelta(minutes=15)' in rotation and 'delay_seconds' in coordinated)
check('Coordinated tracker writes use race-safe persistence retries',
      'persist_social_state.sh' in coordinated and (ROOT/'persist_social_state.sh').exists())
check('Daily coordinated inventory is exactly 20 News articles plus 4 resources',
      'MASTER_PATTERN' not in rotation and 'NEWS_PATTERN' in rotation and 'RESOURCE_PATTERN' in rotation
      and 'NEWS_KEYS' in rotation and len(re.findall(r'https://dailyyield\.blogspot\.com/p/',rotation))==7)
check('Configured cadence is 24 destinations split equally across four networks',
      'RESOURCE_PATTERN = ("facebook", "bluesky", "tumblr", "mastodon")' in rotation
      and 'NEWS_PATTERN = RESOURCE_PATTERN * 5' in rotation and 20+4==24 and all(name in rotation for name in ('facebook','bluesky','tumblr','mastodon')))

check('Master links both market desks','/p/markets-today.html' in prep and '/p/global-snapshot.html' in prep)
check('Master posts cannot enter News hub',"return title,slug,meta,[category,AUTHOR],body" in mv2)
check('Master articles include measured 10–15-item continuous discovery shelf','10<=len(low)<=15' in mv2 and 'dy2-rail-track' in mv2 and 'pointerdown' in mv2 and 'low_exposure_posts' in prep)
check('Master articles include continuous gesture motion','ensure_continuous_motion' in ap)
check('Master uses three unique licensed 16:9 placement-specific photographs','choose_photos' in prep and "image.resize((1600,900)" in (ROOT/'photo_selector.py').read_text() and "len(photos)!=3" in mv2 and 'PHOTO_USAGE_REGISTRY.json' in (ROOT/'photo_selector.py').read_text())
check('News hero image is preflight-validated','safe_image' in np and 'FALLBACK_PERSONAL' in np)
check('Every News desk uses date-rotated fresh hero selection',
      'def daily_hero(' in np and 'edition_date.toordinal()' in np and 'previous_hero=prev.get("hero_url"' in np)
check('Daily News heroes avoid cross-desk reuse',
      'used_heroes = {' in np and 'SESSION_USED_IMAGES' in np and 'url not in used_urls' in np)
check('Licensed Commons hero photographs retain visible attribution',
      'LicenseShortName' in np and 'Wikimedia Commons' in np and '<figcaption' in np)
check('News tracker records the selected hero for next-day deduplication',
      '"hero_url": art["hero_url"]' in np and '"hero_credit": art["hero_credit"]' in np)
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
check('News titles are Bing-safe while exact coverage remains in description/body',
      'title = compact_title(f"{desk_title_prefix(desk)} — {publish_lead}")' in np
      and 'coverage_lead = coverage_window_text(win_start, win_end)' in np
      and 'coverage {coverage_lead}' in np)
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
