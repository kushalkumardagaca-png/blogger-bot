#!/usr/bin/env python3
"""Static and template audit for active News, social, search and site automations."""
from pathlib import Path
import re
import ast, datetime as dt, json, re, sys

ROOT=Path(__file__).parent
IST=dt.timezone(dt.timedelta(hours=5,minutes=30))
checks=[]
def check(name,ok,detail=""):
 checks.append({"name":name,"status":"PASS" if ok else "FAIL","detail":detail})

def crons(path):
 return re.findall(r"cron:\s*['\"]([^'\"]+)",Path(path).read_text())

news_expected=['30 21 * * *','30 22 * * *','30 0 * * *','30 3 * * *','30 5 * * *','0 6 * * *','30 6 * * *','30 10 * * *','0 11 * * *','30 11 * * *','0 12 * * *']
nw=ROOT/'.github/workflows/daily_news_wires.yml'
def ist_minute(cron):
    minute,hour=map(int,cron.split()[:2]); return (hour*60+minute+330)%1440
retired_master=('daily_blogger_poster.yml','rewrite_existing_masters.yml','refresh_master_photos.yml','refresh_master_v2_design.yml')
new_master=('master_topic_discovery.yml','master_trending_writer.yml','master_evergreen_writer.yml')
check('Rejected legacy Master workflows remain absent and approved dynamic workflows exist',
      all(not (ROOT/'.github/workflows'/name).exists() for name in retired_master)
      and all((ROOT/'.github/workflows'/name).exists() for name in new_master))
master_expected={
 'master_topic_discovery.yml':['35 18 * * 6','50 18 * * *'],
 'master_trending_writer.yml':['0 22 * * *','0 1 * * *','0 6 * * *','0 8 * * *','30 12 * * *'],
 'master_evergreen_writer.yml':['30 0 * * *','30 3 * * *','30 7 * * *','0 12 * * *','30 14 * * *'],
}
for name,expected in master_expected.items():
 workflow=(ROOT/'.github/workflows'/name).read_text()
 check(f'{name} has its complete live schedule',crons(ROOT/'.github/workflows'/name)==expected and 'workflow_dispatch:' in workflow,str(crons(ROOT/'.github/workflows'/name)))
prewarmer=ROOT/'.github/workflows/master_daily_prewarmer.yml';prewarm_text=prewarmer.read_text() if prewarmer.exists() else ''
check('All ten Master packages are prepared in five staggered overnight batches',
      crons(prewarmer)==['10 19 * * *','25 19 * * *','40 19 * * *','55 19 * * *','10 20 * * *']
      and prewarm_text.count('publish=false')>=1 and 'master_trending_writer.yml' in prewarm_text and 'master_evergreen_writer.yml' in prewarm_text)
check('Dynamic Master publication has both code gate and explicit live workflow enablement',
      'MASTER_PUBLICATION_ENABLED' in (ROOT/'master_dynamic_pipeline.py').read_text()
      and "!='true'" in (ROOT/'master_dynamic_pipeline.py').read_text()
      and all("MASTER_PUBLICATION_ENABLED: 'true'" in (ROOT/'.github/workflows'/name).read_text() for name in new_master))
check('Eleven news preflight runs',crons(nw)==news_expected,str(crons(nw)))
check('News desks have independent non-cancelling precision runs','cancel-in-progress: false' in nw.read_text() and 'daily-yield-news-${{' in nw.read_text() and 'timeout-minutes: 180' in nw.read_text())

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
taxonomy=(ROOT/'master_taxonomy.py').read_text(); discovery=(ROOT/'master_topic_discovery.py').read_text(); dynamic=(ROOT/'master_dynamic_pipeline.py').read_text()
check('Master taxonomy is exactly five trending plus fifteen evergreen categories',
      taxonomy.count('"type": "trending"')==5 and taxonomy.count('"type": "evergreen"')==15)
check('Historical evergreen references are never a blind topic queue',
      'revalidated_reference_evergreen' in discovery and 'len(urls)>=2' in discovery
      and 'discovered_from_live_internet' in discovery and 'recent_news_headlines()' in discovery)
check('Dynamic Master daily plan is five trending plus five evergreen topics',
      "if len(evergreen)!=5" in discovery and "for cat in TRENDING_CATEGORIES" in discovery and "'total':10" in discovery)
check('Trending Master articles receive one trend and one permanent label',
      "item['category'],item['evergreen_category']" in dynamic)
check('Every article routes to two distinct networks with exact 42-post weighting',
      'DAILY_PLATFORM_PAIRS' in (ROOT/'social_rotation.py').read_text()
      and "{'facebook':13,'bluesky':11,'mastodon':10,'tumblr':8}" in (ROOT/'test_social_rotation.py').read_text()
      and 'for route_index in (0,1)' in (ROOT/'dispatch_social_events.py').read_text())
check('Each dynamic Master package requires three licensed photos',
      'choose_photos(briefs' in (ROOT/'prepare_master_article.py').read_text() and 'if len(briefs)!=3' in (ROOT/'photo_selector.py').read_text())
rv=(ROOT/'reader_value_article.py').read_text(); mv2=(ROOT/'master_article_v2.py').read_text(); prep=(ROOT/'prepare_master_article.py').read_text(); master=ap+rv+mv2+prep
check('Master publisher uses IST','datetime.now(IST)' in ap)
check('Master tracker advances only after live URL','tracker will not advance' in ap and 'if not api_res or not api_res.get("url")' in ap)
check('Master duplicate recovery','find_duplicate(title,content,posts)' in ap and 'no duplicate published' in ap and 'fetchBodies=True' in ap)
check('Master canonical repaired to live URL','predicted.group(0)' in ap and 'posts().update' in ap)
check('Master packages always rebuilt fresh','Always rebuild with the current date' in ap and 'Loading pre-compiled' not in ap)
check('Master byline is current','AUTHOR="Kushal Daga"' in mv2 and 'By <strong>{AUTHOR}</strong>' in mv2 and 'By CA Kushal Daga' not in master)
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
      and 'By Kushal Daga' in (ROOT/'social_creative.py').read_text())
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
      len(re.findall(r'\{"name":',creative))>=10 and 'layout=(seed // 31) % 5' in creative
      and 'int(choice.get("layout",layout))%5' in creative
      and 'ImageOps.fit(source, size' in creative and 'PLATFORM_SIZES' in creative
      and 'full-bleed editorial photograph' in creative)
check('Organic social attribution and guarded evidence-led optimization are active',
      'utm_campaign' in creative and 'dy_growth' in creative and 'seed%5' in creative
      and (ROOT/'social_growth_optimizer.py').exists()
      and 'SOCIAL_OPTIMIZER_STATE.json' in (ROOT/'.github/workflows/social_performance.yml').read_text())
check('Creative system mixes article heroes with a broad licensed global lifestyle library',
      'Use the hero embedded in authenticated Blogger content' in creative
      and all(f'"{theme}"' in creative for theme in ('people','family','pets','homes','banking','work','technology','shopping','travel','global'))
      and len(re.findall(r'photo-\d{10,}-[a-z0-9]+',creative))>=35)
check('Photo selection is semantic and fails closed instead of producing a banner',
      'def _semantic_theme(' in creative and 'No licensed editorial photo could be loaded' in creative
      and 'banner-only graphic' in creative)
check('Creative outputs are deterministic per platform, destination and IST day',
      'hashlib.sha256(raw.encode())' in creative and 'datetime.now(IST).date().isoformat()' in creative)
check('Captions use one image lead, two supporting ideas, link-first copy and platform-specific calls to action',
      'def content_highlights(' in creative and 'lead,second,third=' in creative
      and 'link above' in creative and all(f'platform=="{p}"' in creative for p in ('facebook','bluesky','mastodon')))
check('Creative engine uses authenticated inventory and cannot request a Daily Yield public page',
      'requests.get(url' in creative and 'PHOTO_HOSTS' in creative and '_allowed_photo_host' in creative
      and 'def select_inventory_target(' in creative and 'target is outside Daily Yield' in creative)
check('Corporate social boilerplate was removed from all active publisher outputs',
      all(term not in creative for term in ('READ THE FULL REPORT','OPEN THIS DAILY YIELD RESOURCE','Markets · Money · Better decisions')))

rotation_path=ROOT/'social_rotation.py'; coordinated_path=ROOT/'.github/workflows/coordinated_social_publish.yml'
dispatch_path=ROOT/'dispatch_social_events.py'
rotation=rotation_path.read_text() if rotation_path.exists() else ''
coordinated=coordinated_path.read_text() if coordinated_path.exists() else ''
dispatch=dispatch_path.read_text() if dispatch_path.exists() else ''
check('Coordinated router and event dispatcher are deployed',bool(rotation) and bool(coordinated) and bool(dispatch))
check('Exactly three rotating resource promotions per platform are scheduled daily',
      crons(coordinated_path)==['15 23 * * *','15 1 * * *','15 3 * * *','15 5 * * *','30 6 * * *','15 8 * * *','15 10 * * *','30 11 * * *','30 13 * * *','30 14 * * *','0 16 * * *','45 17 * * *']
      and 'Audience-local global windows' in coordinated)
check('Every social publisher accepts an exact authenticated Blogger target URL',
      all('--target-url' in text and 'Target URL was not found in authenticated Blogger inventory' in text
          for text in (fp,bp,tp,mp)))
check('News publisher dispatches only confirmed live Blogger events',
      'social_events.json' in np and 'dispatch_social_events.py' in nw.read_text())
check('Concurrent News desk writes use semantic merge and retry',
      'merge_news_state.py' in nw.read_text() and (ROOT/'merge_news_state.py').exists()
      and 'git reset --hard FETCH_HEAD' in nw.read_text())
check('Both article social routes release within five minutes after publication',
      'dt.timedelta(minutes=4)' in rotation and 'route_index' in coordinated and 'delay_seconds' in coordinated)
persist_social=(ROOT/'persist_social_state.sh').read_text() if (ROOT/'persist_social_state.sh').exists() else ''
check('Coordinated tracker writes use semantic race-safe persistence retries',
      'persist_social_state.sh' in coordinated and 'merge_social_tracker.py' in persist_social
      and (ROOT/'merge_social_tracker.py').exists())
recovery_path=ROOT/'.github/workflows/publishing_recovery.yml';recovery_script=ROOT/'publishing_recovery.py'
recovery=recovery_path.read_text() if recovery_path.exists() else '';recovery_code=recovery_script.read_text() if recovery_script.exists() else ''
check('Every new URL is announced to the search engines without human submission',
      (ROOT/'indexnow_submit.py').exists()
      and 'indexnow_submit.py' in (ROOT/'.github/workflows/daily_news_wires.yml').read_text(encoding='utf-8')
      and 'indexnow_submit.py' in (ROOT/'.github/workflows/master_evergreen_writer.yml').read_text(encoding='utf-8')
      and 'indexnow_submit.py' in (ROOT/'.github/workflows/master_trending_writer.yml').read_text(encoding='utf-8')
      and 'submit_feed' in (ROOT/'bing_url_automation.py').read_text(encoding='utf-8')
      and 'blocked' in (ROOT/'indexnow_submit.py').read_text(encoding='utf-8')
      and 'pending' in (ROOT/'indexnow_submit.py').read_text(encoding='utf-8'))

check('Permanent all-slot and social dead-letter recovery replaces the one-time recovery workflow',
      not (ROOT/'.github/workflows/missed_publication_recovery.yml').exists()
      and bool(recovery) and bool(recovery_code) and "cron: '7,17,27,37,47,57 * * * *'" in recovery
      and 'MAX_RETRIES=3' in recovery_code and 'SOCIAL_GRACE' in recovery_code
      and 'implementation_revision' in recovery_code and "row.get('revision')!=revision" in recovery_code
      and "key.startswith(('source:','prewarm:','cleanup:'))" in recovery_code
      and 'PREWARM=dt.timedelta(hours=3,minutes=15)' in recovery_code and 'ARTICLE_RETRY=dt.timedelta(minutes=10)' in recovery_code and 'source_dispatched' in recovery_code and 'has_overdue_master' in recovery_code and "'publish=false'" in recovery_code
      and 'publicDailyYieldRequests' in recovery_code)
check('Daily coordinated inventory covers all 21 articles plus twelve rotating resource posts',
      'DAILY_ARTICLE_KEYS' in rotation and 'DAILY_PLATFORM_PAIRS' in rotation and 'RESOURCE_DESTINATIONS' in rotation
      and len(re.findall(r'https://dailyyield\.blogspot\.com/p/',rotation))==5
      and 'https://dailyyield.blogspot.com/#spotlight' in rotation and 'https://dailyyield.blogspot.com/' in rotation
      and 'RESOURCE_SCHEDULES' in rotation and 'position not in (0,1,2)' in rotation)
check('Configured article cadence is exactly 42 weighted social posts daily',
      'Facebook 13, Bluesky 11, Mastodon 10, Tumblr 8' in rotation
      and 21*2==42 and all(name in rotation for name in ('facebook','bluesky','tumblr','mastodon')))
check('Article and Page application choices rotate across all four networks by IST day',
      'ROTATION_PLATFORMS' in rotation and 'rotate_platform(base_platform,current.date())' in rotation
      and 'platform_pair_for(item_key,day)' in rotation)

master_workflows=(ROOT/'.github/workflows/master_trending_writer.yml').read_text()+(ROOT/'.github/workflows/master_evergreen_writer.yml').read_text()
v3_generator=(ROOT/'master_v3_generator.py').read_text();v3_pipeline=(ROOT/'master_v3_pipeline.py').read_text()
check('Both live Master categories have replaced the monolithic pipeline with Master V3',
      master_workflows.count('python master_v3_pipeline.py')==4
      and 'python master_dynamic_pipeline.py' not in master_workflows)
check('Master V3 uses independently validated plain-text sections, not one long JSON response',
      'def write_section' in v3_generator and "400<=count<=490" in v3_generator
      and 'Never output JSON or markdown' in v3_generator
      and 'prepare_master_article' not in v3_generator)
check('Short section attempts accumulate instead of discarding usable prose',
      'pool=[];seen=set()' in v3_generator and 'for attempt in range(2)' in v3_generator
      and 'deterministic_section(section_heading,sources)' in v3_generator)
check('Fast model acceleration has a quota-independent completion path',
      'for fn in (github_text,ollama_text)' in v3_generator
      and 'def deterministic_section' in v3_generator
      and master_workflows.count('models: read')>=2
      and master_workflows.count('GITHUB_TOKEN: ${{ github.token }}')>=2)
check('Bounded provider waits preserve the under-thirty-minute generation target',
      # the waits are no longer fixed numbers but what the run's own clock allows, so a slow
      # network cannot spend minutes the preparation no longer has
      'timeout=BUDGET.seconds(60)' in v3_generator and 'timeout=BUDGET.seconds(90)' in v3_generator
      and 'for attempt in range(2)' in v3_generator)
check('Ten bounded sections use controlled five-worker parallel generation',
      'ThreadPoolExecutor(max_workers=5' in v3_generator and 'as_completed(futures)' in v3_generator)
check('Overnight pair dispatch retries each category independently',
      'for attempt in 1 2 3 4 5' in prewarm_text
      and 'dispatch master_trending_writer.yml' in prewarm_text
      and 'dispatch master_evergreen_writer.yml' in prewarm_text)
check('Master V3 preserves strict Blogger publication and package compilation gates',
      'MASTER_PUBLICATION_ENABLED' in v3_pipeline and 'validate(package)' in v3_pipeline
      and 'assert_publishable' in v3_pipeline)
check('Master V3 permanently excludes 12/13 October and all historical backfill',
      'PRODUCTION_START=dt.date(2026,10,14)' in v3_pipeline
      and 'publishes only the current IST date' in v3_pipeline
      and 'master_day=day' in (ROOT/'publishing_recovery.py').read_text())
check('Scheduled Master release reuses a complete advance package',
      'if target.exists()' in v3_pipeline and 'package=read(target,{})' in v3_pipeline
      and 'validate(package)' in v3_pipeline)
check('Every Master publishing path enforces the public release embargo',
      'wait_for_release(MASTER_LIVE[(kind,slot)])' in v3_pipeline
      and 'if timed_release:wait_for_release' not in v3_pipeline)
check('Master retries are centrally ordered rather than self-dispatched',
      'gh workflow run master_' not in master_workflows
      and 'has_overdue_master' in recovery_code)
check('Master V3 deterministically assembles summary, support and three evidence visuals',
      'def extracted_summary' in v3_generator and 'def support' in v3_generator
      and 'def visuals' in v3_generator)
check('Duplicate Master attempts are serialized without cross-slot embargo blocking',
      'group: daily-yield-master-v3-trending-${{ inputs.slot' in master_workflows
      and 'group: daily-yield-master-v3-evergreen-${{ inputs.slot' in master_workflows
      and "github.event.schedule == '0 6 * * *' && '2'" in master_workflows
      and "github.event.schedule == '30 7 * * *' && '2'" in master_workflows
      and 'group: daily-yield-master-v3-state-writer' not in master_workflows
      and master_workflows.count('cancel-in-progress: false')>=2)
check('Concurrent Master package, photo, plan and tracker writes use semantic merge and retry',
      master_workflows.count('merge_master_state.py')>=4 and (ROOT/'merge_master_state.py').exists()
      and master_workflows.count('merge_master_preparation.py')>=2 and (ROOT/'merge_master_preparation.py').exists()
      and 'git reset --hard FETCH_HEAD' in master_workflows and 'files.tar' in master_workflows)
check('Persistence and Blogger failures return to permanent ordered recovery',
      master_workflows.count('gh workflow run master_')==0
      and 'ARTICLE_RETRY=dt.timedelta(minutes=10)' in recovery_code
      and 'source_dispatched' in recovery_code and 'master_deferred' in recovery_code)
check('Master generation is quota-independent with model-independent research fallback',
      'OLLAMA_API_URL' in prep and '_heuristic_queries' in prep
      and master_workflows.count('Start quota-independent local text model')==2
      and 'GEMINI_API_KEY' not in master_workflows and 'qwen2.5:1.5b' in master_workflows)
check('Local Master generation is bounded for the publication window',
      'def _compact_evidence_packet' in prep and "for attempt in range(2)" in prep
      and "'num_ctx':16384" in prep and 'max_tokens=2500' in prep)
check('Evergreen source discovery can use relevant established reporting without weakening review',
      "when:365d" in prep and 'established-reporting sources found' in prep
      and 'verify_evidence(draft,evidence)' in prep)
check('Omitted local-model sections use attributed evidence rather than filler',
      'def _evidence_bridge_section' in prep and 'does not by itself establish causation' in prep
      and '_evidence_bridge_section(heading,focus,rotated,section_target)' in prep)
check('Transient Ollama failures use fallback only after bounded local attempts',
      'Local Ollama remains primary' in prep and 'try:return _emergency_model_json(messages,max_tokens)' in prep
      and 'except Exception:result={}' in prep)
check('Master workflows actually expose the repository model token to generation',
      master_workflows.count('GITHUB_TOKEN: ${{ github.token }}')>=2)
check('Both live Master categories use the independent V3 engine exclusively',
      master_workflows.count('python master_v3_pipeline.py')==4
      and 'python master_dynamic_pipeline.py' not in master_workflows
      and 'python master_fresh_pipeline.py' not in master_workflows)
check('Live Master V3 avoids monolithic 4,000-word model responses',
      'def write_section' in v3_generator and 'Write 450-460 words' in v3_generator
      and "'engine':'master-v3-fresh'" not in v3_pipeline)
check('Pre-validation short cores have a deterministic evidence-only completion path',
      'core evidence completion failed' in prep and 'additional documented scope and uncertainty' in prep)
check('Summary and visual structure have non-generative evidence-preserving fallbacks',
      'summary extraction failed normalization' in prep and 'Categorical source scope reported by' in prep)
check('Verified short cores complete from attributed evidence without model padding',
      'bridge_round=0' in prep and 'while current<4000' in prep
      and 'additional documented scope and uncertainty' in prep)
check('Scholarly evidence must contain a finance-domain concept',
      '_FINANCE_EVIDENCE_TERMS' in prep and 'or not domain_terms:continue' in prep)
check('Current Master generation has no custom age timeout or age cancellation',
      'timeout-minutes:' not in master_workflows
      and '13800' not in (ROOT/'.github/workflows/master_stale_run_reaper.yml').read_text()
      and 'age=' not in (ROOT/'.github/workflows/master_stale_run_reaper.yml').read_text())
check('Trending starts 150 minutes plus 15 spare before release',
      'Trending generation budget: 150 minutes plus 15 minutes spare' in master_workflows
      and 'Prepare 03:30 IST → live 06:15' in master_workflows
      and 'Prepare 18:00 IST → live 20:45' in master_workflows)
check('Evergreen starts 120 minutes plus 15 spare before release',
      'Evergreen generation budget: 120 minutes plus 15 minutes spare' in master_workflows
      and 'Prepare 06:00 IST → live 08:15' in master_workflows
      and 'Prepare 20:00 IST → live 22:15' in master_workflows)
check('Superseded pre-repair Master runs cannot block repaired same-slot recovery',
      'repair_epoch' in (ROOT/'.github/workflows/master_stale_run_reaper.yml').read_text()
      and 'started" -lt "$repair_epoch' in (ROOT/'.github/workflows/master_stale_run_reaper.yml').read_text())
check('Master links both market desks','/p/markets-today.html' in prep and '/p/global-snapshot.html' in prep)
# A Master post must never carry the News label. The label line is read straight
# from the render function, so the check follows the real code.
_master_label_line = mv2.split('labels=list(dict.fromkeys(')[1].split(')')[0] if 'labels=list(dict.fromkeys(' in mv2 else ''
check('Master posts cannot enter News hub', bool(_master_label_line) and 'News' not in _master_label_line)
check('Master articles include continuous gesture motion','ensure_continuous_motion' in ap)
# Three photographs per Master article is the owner's decision of 19 October 2026 and
# it lives in one constant, so the audit checks the constant and both call sites
# instead of a duplicated literal that a refactor can silently orphan.
_pf=(ROOT/'publication_preflight.py').read_text(encoding='utf-8')
check('Master uses three unique licensed 16:9 placement-specific photographs','choose_photos' in prep and "image.resize((1600,900)" in (ROOT/'photo_selector.py').read_text() and 'PHOTOS_PER_MASTER_ARTICLE = 3' in mv2 and 'len(photos)!=PHOTOS_PER_MASTER_ARTICLE' in mv2 and '{PHOTOS_PER_MASTER_ARTICLE} distinct' in mv2 and "content.count('class=\"dy2-photo\"')!=PHOTOS_PER_MASTER_ARTICLE" in _pf and 'PHOTO_USAGE_REGISTRY.json' in (ROOT/'photo_selector.py').read_text())
# The owner is a CA articleship student, not a Chartered Accountant (answer of 19
# October 2026). The qualification guard can only be switched off by an environment
# variable, so no scheduled job may ever set it.
_workflows='\n'.join(f.read_text(encoding='utf-8',errors='replace') for f in (ROOT/'.github/workflows').glob('*.yml'))
check('No automation may claim a professional qualification','DY_VERIFIED_PROFESSIONAL_QUALIFICATION' not in _workflows)
check('Advice risk gate blocks publication','advice_risk_gate' in (ROOT/'publication_preflight.py').read_text() and 'ADVICE RISK GATE BLOCKED' in (ROOT/'advice_risk_gate.py').read_text() and 'HUMAN_REVIEWER = False' in (ROOT/'advice_risk_gate.py').read_text())
# The Instagram route was built and then withdrawn by owner decision on 20 October 2026, because
# connecting a personal Meta login to a brand Instagram account through the official API could not
# be completed. The fixed rule of two posts per article across four networks stands, and this guard
# is what keeps a half-removed route from coming back silently or being registered by accident.
check('No Instagram route is registered, scheduled or left behind in the repository',
      'instagram' not in _block and '"instagram":' not in _block
      and not (ROOT/'instagram_publisher.py').exists()
      and not (ROOT/'instagram_oauth_bootstrap.py').exists()
      and not (ROOT/'INSTAGRAM_PLAN.json').exists()
      and not (ROOT/'.github/workflows/instagram_publisher.yml').exists()
      and not (ROOT/'.github/workflows/instagram_oauth_bootstrap.yml').exists()
      and 'instagram' not in (ROOT/'INSTAGRAM_ROUTE_STATUS.json').read_text().lower()
      if (ROOT/'INSTAGRAM_ROUTE_STATUS.json').exists() else True)
check('Publishing volume is bounded by the measured index, not by ambition',
      (ROOT/'indexing_capacity_gate.py').exists()
      and 'currently not indexed' in (ROOT/'indexing_capacity_gate.py').read_text()
      and 'def template_of' in (ROOT/'indexing_capacity_gate.py').read_text()
      and 'INDEX_PRIORITY.json' in (ROOT/'.github/workflows/search_indexing.yml').read_text())
check('Tumblr keeps its access token instead of burning a refresh grant on every run',
      # the two-day outage of 18-20 October 2026: every run exchanged the refresh token, Tumblr
      # rotates it at each exchange, and one run that failed before its state was committed left
      # the repository holding a consumed token - after which every attempt answered invalid_grant
      'def access_token_or_refresh' in (ROOT/'tumblr_publisher.py').read_text()
      and 'token=access_token_or_refresh()' in (ROOT/'tumblr_publisher.py').read_text()
      and 'retries=1' in (ROOT/'tumblr_publisher.py').read_text().split('def refresh_access')[1].split('\ndef ')[0]
      and 'invalid_grant' in (ROOT/'tumblr_publisher.py').read_text()
      and 'tumblr_oauth_bootstrap.py' in (ROOT/'tumblr_publisher.py').read_text()
      and 'obtained_at' in (ROOT/'tumblr_oauth_bootstrap.py').read_text()
      and (ROOT/'.github/workflows/coordinated_social_publish.yml').read_text().count('if: ${{ !cancelled() }}') == 4)
check('A social network that cannot publish says so in the repository, not only in a job log',
      # 22 social runs failed on 20 October 2026 with nothing but "exit code 1" to show for it, and
      # nine of the day's 36 posts were never delivered. The guard already refuses to dispatch to a
      # network recorded as unusable; this makes sure the record is written and persisted by every
      # channel, so the reason is readable from the repository without log access.
      (ROOT/'social_credential_health.py').exists()
      and all(f'--platform {name} ' in (ROOT/'.github/workflows/coordinated_social_publish.yml').read_text()
              for name in ('facebook', 'bluesky', 'tumblr', 'mastodon'))
      and 'files+=(SOCIAL_CREDENTIAL_HEALTH.json)' in (ROOT/'.github/workflows/coordinated_social_publish.yml').read_text()
      and 'blocked_platforms' in (ROOT/'social_guard.py').read_text()
      and 'def reason_from' in (ROOT/'social_credential_health.py').read_text()
      and '[redacted]' in (ROOT/'social_credential_health.py').read_text())
check('A quoted source passage cannot smuggle a rejected claim into a Master article',
      'def quoted_window' in v3_generator
      and "' '.join(tokens[start:start+" not in v3_generator)
check('A Master preparation run works to a stated clock, not an open-ended timeout',
      # the owner's rule of 20 October 2026: preparation is planned in 10-50 minutes and must
      # never pass 40, so a stalled download or a hung model call fails the slot fast and the
      # ten-minute recovery cycle gets a fresh attempt instead of the rest of the day
      (ROOT/'time_budget.py').exists()
      and 'from time_budget import BUDGET' in v3_generator
      and 'from time_budget import BUDGET' in (ROOT/'photo_selector.py').read_text()
      and 'from time_budget import BUDGET' in (ROOT/'master_v3_pipeline.py').read_text()
      and all("MASTER_PREPARATION_BUDGET_MINUTES: '30'" in (ROOT/'.github/workflows'/w).read_text()
              for w in ('master_evergreen_writer.yml','master_trending_writer.yml'))
      and 'timeout-minutes:' not in master_workflows  # the run stops itself; nothing is killed by age
      and '1800-second budget' in (ROOT/'.github/workflows/master_evergreen_writer.yml').read_text()
      and 'timeout=90' not in v3_generator and 'timeout=35' not in (ROOT/'photo_selector.py').read_text())
check('A deterministic section is measured with its citations attached, not before',
      # the 400-490 word contract is enforced on the final text; measuring first and appending
      # '[[S1|provider]]' afterwards produced a 504-word section and a lost slot on 20 Oct 2026
      v3_generator.index("primary=sources[0][0];primary_name=citation_label(sources[0][1])")
      < v3_generator.index("while words(' '.join(paragraphs))>470:"))
check('Master headlines are clipped on a word boundary, never inside a word',
      'def head_clip' in v3_generator and '[:46]' not in v3_generator
      and 'for token in value.split():' in v3_generator
      and '\u2026' not in v3_generator.split('def head_clip')[1].split('def build')[0])
check('No generator or repair job may write a master title outside the validator\'s own 12-46 rule',
      # this is the guard for the 20 October 2026 outage: a title ceiling of 72 characters in the
      # generator passed its own tests while master_article_v2.validate() refused every candidate,
      # so no master article was published for the rest of the day. The validator's number, not a
      # search-result estimate, is the only number allowed in these two files.
      'def head_clip(value,limit=46)' in v3_generator
      and 'MIN_TITLE_CHARS, MAX_TITLE_CHARS = 12, 46' in (ROOT/'headline_repair.py').read_text()
      and 'MAX_REPAIRED = MAX_TITLE_CHARS' in (ROOT/'headline_repair.py').read_text()
      and 'if not 12<=len(title)<=46' in (ROOT/'master_article_v2.py').read_text()
      and 'limit=72' not in v3_generator and 'MAX_REPAIRED = 72' not in (ROOT/'headline_repair.py').read_text())
check('Headline repair reads only the article\'s own words and writes only on an explicit apply',
      'def heading_candidates' in (ROOT/'headline_repair.py').read_text()
      and 'def fitted' in (ROOT/'headline_repair.py').read_text()
      and 'AUDIT_ONLY' in (ROOT/'headline_repair.py').read_text()
      and '--apply' in (ROOT/'headline_repair.py').read_text()
      and 'heldBackCollisions' in (ROOT/'headline_repair.py').read_text()
      and "default: 'audit'" in (ROOT/'.github/workflows/headline_repair.yml').read_text())
check('The hub pages hand out real crawlable links and the freeze rules still hold',
      'def link_index' in (ROOT/'frozen_hub_refresh.py').read_text()
      and 'DY_HUB_LINK_INDEX_START' in (ROOT/'frozen_hub_refresh.py').read_text()
      and 'HUB_LINK_CAP = 12' in (ROOT/'frozen_hub_refresh.py').read_text()
      and 'linkIndexHrefs' in (ROOT/'frozen_hub_refresh.py').read_text()
      and 'def place_link_index' in (ROOT/'frozen_hub_refresh.py').read_text())
check('The nightly clean-ups act by themselves but never delete, and a person must choose to delete',
      '== \"schedule\" ]]; then action=\"apply\"; fi' in (ROOT/'.github/workflows/headline_repair.yml').read_text()
      and "default: 'audit'" in (ROOT/'.github/workflows/headline_repair.yml').read_text()
      and 'echo refresh || echo audit' in (ROOT/'.github/workflows/blogger_duplicate_purge.yml').read_text()
      and 'duplicate_refresh.py --apply' in (ROOT/'.github/workflows/blogger_duplicate_purge.yml').read_text()
      and 'delete)  python blogger_duplicate_purge.py --apply' in (ROOT/'.github/workflows/blogger_duplicate_purge.yml').read_text()
      and "default: 'audit'" in (ROOT/'.github/workflows/blogger_duplicate_purge.yml').read_text())
check('A duplicate is answered with fresh material, and the refresh job cannot delete anything',
      'def unique_sentences' in (ROOT/'duplicate_refresh.py').read_text()
      and 'def new_title' in (ROOT/'duplicate_refresh.py').read_text()
      and 'ARCHIVE' in (ROOT/'duplicate_refresh.py').read_text()
      and 'DELETE' not in (ROOT/'duplicate_refresh.py').read_text()
      and '"deletions": 0' in (ROOT/'duplicate_refresh.py').read_text())
check('Google News readiness is measured from the public feed, and an unreadable feed stays unreadable',
      'FEED_UNREADABLE' in (ROOT/'google_news_readiness.py').read_text()
      and 'nothing is assumed' in (ROOT/'google_news_readiness.py').read_text()
      and 'os.environ' not in (ROOT/'google_news_readiness.py').read_text()
      and 'googleapis.com/blogger' not in (ROOT/'google_news_readiness.py').read_text()
      and 'GOOGLE_NEWS_READINESS.json' in (ROOT/'.github/workflows/indexing_capacity_gate.yml').read_text())
check('Indexing starts at the front doors: the main pages, not all 551 URLs',
      'MAIN_PAGE_URL' in (ROOT/'indexing_capacity_gate.py').read_text()
      and 'mainPagePolicy' in (ROOT/'indexing_capacity_gate.py').read_text()
      and '--include-articles' in (ROOT/'indexing_capacity_gate.py').read_text()
      and 'owner decision, 20 October 2026' in (ROOT/'indexing_capacity_gate.py').read_text())
check('The milestone is counted in readers, not in pageviews',
      'engagedSessions' in (ROOT/'ga4_measurement.py').read_text()
      and 'dailyReaders' in (ROOT/'ga4_measurement.py').read_text()
      and 'dailyReadersBasis' in (ROOT/'growth_ladder.py').read_text()
      and 'UNMEASURABLE_UNTIL_GA4_IS_READABLE' in (ROOT/'growth_ladder.py').read_text())
check('The growth ladder is judged on measured evidence and cannot invent a verdict',
      'NOT_ENOUGH_MEASUREMENT' in (ROOT/'growth_ladder.py').read_text()
      and 'MIN_POINTS_FOR_RATE = 3' in (ROOT/'growth_ladder.py').read_text()
      and 'FUTURE' in (ROOT/'growth_ladder.py').read_text()
      and 'GROWTH_LADDER.json' in (ROOT/'.github/workflows/indexing_capacity_gate.yml').read_text()
      and 'GROWTH_LADDER_HISTORY.json' in (ROOT/'.github/workflows/indexing_capacity_gate.yml').read_text())
check('The audience counter is public-endpoint only and never calls an unanswered endpoint zero',
      'os.environ' not in (ROOT/'audience_channels.py').read_text()
      and 'PUBLIC_OPEN_ENDPOINTS_ONLY' in (ROOT/'audience_channels.py').read_text()
      and 'AUDIENCE_CHANNELS.json' in (ROOT/'.github/workflows/indexing_capacity_gate.yml').read_text())
check('The view counter reads Google numbers without touching the blog',
      'googleapis.com/blogger' not in (ROOT/'ga4_measurement.py').read_text()
      and 'DELETE' not in (ROOT/'ga4_measurement.py').read_text()
      and 'BLOGGER_' not in (ROOT/'ga4_measurement.py').read_text()
      and 'CREDENTIALS_MISSING' in (ROOT/'ga4_measurement.py').read_text()
      and 'no number is invented' in (ROOT/'ga4_measurement.py').read_text()
      and 'analytics.readonly' in (ROOT/'get_analytics_token.py').read_text())
check('The growth ladder names the basis of every view number it reports',
      'viewsBasis' in (ROOT/'growth_ladder.py').read_text()
      and 'GA4_PAGEVIEWS_7_DAY_AVERAGE' in (ROOT/'growth_ladder.py').read_text()
      and 'ga4_measurement.py' in (ROOT/'.github/workflows/indexing_capacity_gate.yml').read_text())
check('The duplicate pile is audited daily and only deleted on an explicit apply',
      '--apply' in (ROOT/'blogger_duplicate_purge.py').read_text()
      and 'AUDIT_ONLY' in (ROOT/'blogger_duplicate_purge.py').read_text()
      and 'def protected_urls' in (ROOT/'blogger_duplicate_purge.py').read_text()
      and 'batchCap' in (ROOT/'blogger_duplicate_purge.py').read_text()
      and "default: 'audit'" in (ROOT/'.github/workflows/blogger_duplicate_purge.yml').read_text())
check('News hero image is preflight-validated','safe_image' in np and 'FALLBACK_PERSONAL' in np)
check('News adaptive polish can deepen sparse but sourced editions before failing',
      'base_context + 380' in np and 'summary_target + 54' in np
      and 'reduce_news_context' in np and 'NEWS_MIN_WORDS = 3800' in np)
check('Timed News publication refreshes an expired Blogger access token once',
      'exc.code == 401 and _auth_retry' in np and '_auth_retry=False' in np)
check('Every News desk uses date-rotated fresh hero selection',
      'def daily_hero(' in np and 'edition_date.toordinal()' in np
      and 'previous_url=prev.get("hero_url"' in np and 'hero_override=hero' in np)
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

# Balanced activity cadence: 21 hourly article releases and 12 two-hour Page windows.
from publication_timing import NEWS_LIVE as _NEWS_LIVE, MASTER_LIVE as _MASTER_LIVE
def _minute(v):
 h,m=map(int,v.split(':'));return h*60+m
def _cron_ist(v):
 m,h=map(int,v.split()[:2]);return (h*60+m+330)%1440
_article_minutes=sorted([_minute(x) for x in _NEWS_LIVE.values()]+[_minute(x) for x in _MASTER_LIVE.values()])
_article_gaps=[b-a for a,b in zip(_article_minutes,_article_minutes[1:])]+[1440-_article_minutes[-1]+_article_minutes[0]]
check('Twenty-one articles preserve audience windows with one six-hour overnight gap',len(_article_minutes)==21 and _article_gaps.count(60)==14 and _article_gaps.count(30)==5 and _article_gaps.count(90)==1 and _article_gaps.count(360)==1)
_resource_crons=re.findall(r'\"([^\"]+\")', '') if False else []
from social_rotation import RESOURCE_SCHEDULES as _RESOURCE_SCHEDULES
_resource_minutes=sorted(_cron_ist(x) for x in _RESOURCE_SCHEDULES)
check('Twelve Page promotions cover Asia, Europe, India and US reader windows',_resource_minutes==[285,405,525,645,720,825,945,1020,1140,1200,1290,1395])

# Literal DESKS inventory without executing network code.
tree=ast.parse(np); desks=None
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DESKS' for t in node.targets):
  desks=ast.literal_eval(node.value);break
check('Exactly 11 consolidated news desks',isinstance(desks,dict) and len(desks)==11,str(len(desks or {})))
nums=sorted(v[0] for v in desks.values()); labels=[v[1] for v in desks.values()]
check('News desk numbers are 1–11',nums==list(range(1,12)))
check('News labels are unique',len(labels)==len(set(labels))==11)
check('Each News schedule explicitly selects one precision-timed desk',
      all(f'value={desk}' in nw.read_text() for desk in desks)
      and '--timed-release' in nw.read_text() and 'NEWS_LIVE' in np)
check('News labels encode edition family and canonical taxonomy within Blogger limit',
      '"Category Edition"' in np and '"Geographic Edition"' in np
      and 'TOPIC_LABELS[desk]' in np and 'GEOGRAPHY_LABELS[desk]' in np
      and 'Blogger caps the combined label text' in np)
check('News launch gate is 2026-09-25','LAUNCH_DATE = dt.date(2026, 9, 25)' in np)
check('News precision timing is independent of Search Console audience measurements',
      'from publication_timing import NEWS_LIVE' in np and 'GSC' not in (ROOT/'publication_timing.py').read_text())
check('News duplicate recovery uses Blogger API without synthetic pageviews',
      'live_current_edition(expected_url, token, now.date(), alt_dates)' in np
      and '/posts/bypath?' in np
      and 'response.read().decode("utf-8"' not in np)
check('News treats a post at today\'s address as published only when it carries today\'s edition',
      'def live_current_edition(' in np and 'assert_saved_green(post)' in np
      and "markers = [f\"{day.day} {day.strftime('%B %Y')}\"" in np)
check('News repairs or refreshes a duplicate instead of stopping on it',
      'interrupted-run post repaired and verified' in np and 'older-edition post refreshed' in np)
check('News widens its window rather than leaving a country or sub-section short',
      'coverage widened with' in np and 'news_coverage.enforce(current + extras, desk)' in np)
check('News source policy is current','official institutions plus established, reputable newsrooms' in np)
check('News finance filter enabled','FINANCE_RE.search' in np)
check('News requires at least one genuinely current item','if current_count == 0' in np)
check('Significance ranks rather than cancels a desk edition',
      'balanced_take(relevant' in np and 'finance_significant' not in np)
check('News uses adaptive 24–28 geographic and 30–34 category headline ranges',
      'maximum = 34 if is_category else 28' in np
      and 'desired = 30 if is_category else 24' in np
      and 'range(first_count, len(current) + 1)' in np
      and 'source-integrity gate excluded' in np)
check('News adaptive polish protects summaries and sentence-trims only context',
      'def reduce_news_context(' in np and 'summary_target=summary_target' in np
      and 'class="fbk-context"' in np and 'class="fbk-description"' in np)
check('Every geographic edition is organised into four canonical topic sections',
      'SECTION_ORDER' in np and 'TOPIC_LABELS' in np and 'topic_targets' in np)
check('Every category edition is balanced across canonical geographies',
      'geography_targets' in np and '("americas", 7)' in np and '("europe", 7)' in np)
check('Every country desk has broad current-news discovery fallback',
      'def discovery_sources(desk)' in np and "med.append(discovery)" in np and "when:1d" in np)
check('Discovery fallback retains only approved named publishers',
      'GNR_ALLOWED_PUBLISHERS' in np and 'pub not in GNR_ALLOWED_PUBLISHERS' in np)
check('Older context is capped at three and explicitly labelled',
      'len(background) >= min(3, 10 - len(current))' in np
      and 'Background, not current-window news:' in np
      and 'Background Context — Not Current-Period News' in np)
check('News editorial length is fail-closed at 3,800–4,100 visible words',
      'NEWS_MIN_WORDS = 3800' in np and 'NEWS_MAX_WORDS = 4100' in np
      and 'assert_news_editorial_length(art["html"])' in np)
check('News forecasts and analysis remain explicitly attributable',
      'Reported outlook' in np and 'not an observed future result' in np
      and 'ANALYSIS_TERMS' in np)
check('News byline is current','By Kushal Daga' in np and 'By CA Kushal Daga' not in np)
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

# A workflow step that bash cannot parse never reaches its error handling: it dies with
# "unexpected EOF while looking for matching", so the refusal is reported as exit code 2 and the
# publish result, the health record and the repair hint all vanish with it. That happened to the
# Tumblr authorisation step on 21 October, found by nobody but the owner reading a screenshot.
import re as _re, subprocess as _sp, yaml as _yaml
_bad_steps=[]
for _wf in sorted((ROOT/'.github/workflows').glob('*.yml')):
  try: _doc=_yaml.safe_load(_wf.read_text(encoding='utf-8')) or {}
  except Exception as _exc: _bad_steps.append(f"{_wf.name}: unreadable YAML ({_exc})"); continue
  for _jid,_job in (_doc.get('jobs') or {}).items():
    for _st in (_job.get('steps') or []):
      _run=_st.get('run')
      if not isinstance(_run,str): continue
      _r=_sp.run(['bash','-n'],input=_re.sub(r'\$\{\{.*?\}\}','zzz',_run,flags=_re.S),text=True,capture_output=True)
      if _r.returncode: _bad_steps.append(f"{_wf.name}/{_jid}/{_st.get('name') or 'step'}: {_r.stderr.strip()[:120]}")
check('Every workflow shell step parses before it can fail',not _bad_steps,
      '; '.join(_bad_steps[:3]) or 'every run block in every workflow is valid bash')

failed=[x for x in checks if x['status']=='FAIL']
result={'checked_at_ist':dt.datetime.now(IST).isoformat(timespec='seconds'),'summary':{'pass':len(checks)-len(failed),'fail':len(failed)},'checks':checks}
if '--check-only' not in sys.argv:
 (ROOT/'PUBLISHING_AUTOMATION_AUDIT.json').write_text(json.dumps(result,indent=2))
 lines=['# Daily Yield Publishing Automation — Final Audit','',f"**Result:** {len(checks)-len(failed)} PASS · {len(failed)} FAIL",'',
 'Scope: retained Master production code and eleven daily News editions, including branding, timing, trackers, taxonomy, social routing, schema, sources, labels and current market-page links.','']
 for x in checks:lines.append(f"- {'✅' if x['status']=='PASS' else '❌'} **{x['name']}**"+(f" — {x['detail']}" if x['detail'] else ''))
 (ROOT/'PUBLISHING_AUTOMATION_AUDIT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(result['summary']))
if failed:
 for x in failed:print('FAIL',x['name'],x['detail'])
 raise SystemExit(1)
