#!/usr/bin/env python3
"""Master V3 orchestrator for independently generated Evergreen and Trending articles.

Live publication is fail-closed behind MASTER_PUBLICATION_ENABLED=true. Preparation
and publication are split so licensed photo assets are committed before Blogger
receives HTML referencing their repository URLs.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re
from pathlib import Path
from zoneinfo import ZoneInfo
from auto_blogger_publisher import publish_to_blogger
from brand_identity import ensure_brand_identity
from continuous_motion import ensure as ensure_continuous_motion
from master_article_v2 import render, validate
from time_budget import BUDGET
from publication_preflight import assert_publishable
from publication_timing import MASTER_LIVE, wait_for_release
from seo_meta import ensure_seo_meta
from social_identity import ensure_social_identity
from content_policy_guard import POLICY_VERSION
from editorial_integrity import assert_unique_plan,stamp
from master_topic_discovery import used_topic_ids
from master_taxonomy import EVERGREEN_CATEGORIES

ROOT=Path(__file__).parent;PLAN=ROOT/'MASTER_DAILY_PLAN.json';POOL=ROOT/'MASTER_TREND_POOL.json';PACKAGES=ROOT/'master_packages'/'dynamic';TRACKER=ROOT/'MASTER_AUTOMATION_TRACKER.json';STATUS=ROOT/'MASTER_AUTOMATION_STATUS.json';SOCIAL=ROOT/'social_events.json';IST=ZoneInfo('Asia/Kolkata');PRODUCTION_START=dt.date(2026,10,14)

def read(path,default):
 try:return json.loads(path.read_text())
 except (OSError,json.JSONDecodeError):return default
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
class EditionIdentityError(RuntimeError):
    """Blogger answered with a post that belongs to another day, not today's."""


def ist_day(value):
    """The IST calendar day a Blogger timestamp falls on, or None if unreadable."""
    if not value:
        return None
    try:
        moment = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(IST).date()


def blocked_topics(plan):
    """Topics this day already proved it cannot publish, so a retry substitutes."""
    return {str(key) for key in (plan.get("blockedTopics") or {})}


def replace_blocked_topic(plan, kind, slot, item):
    """Swap a blocked topic for another same-category topic and persist the plan."""
    excluded = used_topic_ids(read(ROOT / "MASTER_TOPIC_HISTORY.json", {"items": []}),
                              read(TRACKER, {})) | blocked_topics(plan)
    excluded |= {str(row.get("id")) for row in plan.get(kind, []) if row.get("id")}
    replacement = None
    pool = read(POOL, {}).get("topics", [])
    same_category = [row for row in pool
                     if row.get("category") == item.get("category") and str(row.get("id")) not in excluded]
    if kind == "trending":
        same_category = [row for row in same_category if row.get("discovered_from_live_internet")]
        if same_category:
            replacement = max(same_category, key=lambda row: float(row.get("overall_score") or 0))
    else:
        label = str(item.get("category") or "")
        # A category must be the real taxonomy object. Handing discovery a made-up
        # dict missing "signals" raised KeyError, and because that failure was
        # swallowed it was reported as "no topic remains" — twice on 19 October,
        # which cost two Evergreen slots whose real problem was only that the
        # fallback was never allowed to run.
        cat = next((row for row in EVERGREEN_CATEGORIES if str(row.get("label", "")).casefold() == label.casefold()), None)
        if cat is None:
            cat = next((row for row in EVERGREEN_CATEGORIES
                        if any(signal in label.casefold() or label.casefold() in signal
                               for signal in row.get("signals", []))), EVERGREEN_CATEGORIES[0])
        discovery_error = None
        try:
            from master_topic_discovery import evergreen_candidates
            found = evergreen_candidates([cat], excluded)
            if found:
                replacement = dict(found[0]); replacement["evergreen_category"] = label
        except Exception as exc:  # recorded below, never hidden
            discovery_error = exc
        if replacement is None:
            # The 500-topic Evergreen reserve, validated by live demand before use.
            try:
                from master_topic_discovery import revalidated_reference_evergreen, uid
                ref = revalidated_reference_evergreen(cat, excluded, rescue=True)
                if ref:
                    replacement = {"id": uid(ref["title"]), "title": ref["title"], "category": cat["label"],
                                   "evergreen_category": label, "demand_score": round(ref["demand"], 1),
                                   "content_gap_score": round(ref["gap"], 1),
                                   "overall_score": round(.25 * ref["demand"] + .20 * 90 + .15 * ref["gap"]
                                                          + .15 * 85 + .10 * 80 + .05 * 60 + .05 * 70 + .05 * 85, 1),
                                   "discovered_from_live_internet": bool(ref.get("reference_validated", True)),
                                   "from_evergreen_reserve": True,
                                   "reference_validated": bool(ref.get("reference_validated", True))}
            except Exception as exc:
                discovery_error = discovery_error or exc
    if replacement is None:
        raise RuntimeError(f"no unused {kind} topic remains for slot {slot}"
                           + (f"; the topic search itself failed ({discovery_error})" if discovery_error else "")
                           + "; the blocked topic is not republished")
    plan[kind][slot] = replacement
    write(PLAN, plan)
    print(f"Master {kind} slot {slot}: {str(item.get('title',''))[:50]!r} is blocked for today; "
          f"substituting {str(replacement.get('title',''))[:60]!r}")
    return replacement


def selected(kind,slot):
 plan=read(PLAN,{})
 if plan.get('status')!='READY':raise RuntimeError('daily dynamic Master plan is not READY')
 # Every Master route validates the whole ten-topic day before selecting one
 # slot, so two concurrent slots cannot intentionally publish the same subject.
 assert_unique_plan(plan)
 today=dt.datetime.now(IST).date();plan_date=dt.date.fromisoformat(str(plan.get('date')))
 if plan_date<PRODUCTION_START:raise RuntimeError('Master V3 intentionally does not publish 12 or 13 October backfill')
 if plan_date!=today:raise RuntimeError('Master V3 publishes only the current IST date; historical backfill is disabled')
 rows=plan.get(kind,[])
 if not 0<=slot<len(rows):raise RuntimeError(f'{kind} slot {slot} is unavailable')
 return plan,rows[slot]
def topic_for(kind,item):
 evergreen=item.get('evergreen_category') if kind=='trending' else item['category']
 return {'#':'dynamic-'+item['id'],'Punchy Title':item['title'],'Video Idea':item['title'],'Category':evergreen,'Trending Category':item.get('category') if kind=='trending' else ''}
def package_path(kind,item):
 plan_date=read(PLAN,{}).get('date') or str(dt.datetime.now(IST).date())
 return PACKAGES/f"{plan_date}-{kind}-{item['id']}.json"
def build_html(kind,item,package,check_remote_images=True):
 published_at=dt.datetime.now(IST);topic=topic_for(kind,item);title,slug,meta,labels,body=render(package,topic,published_at.strftime('%Y-%m-%d'),published_at.strftime('%H:%M'))
 if kind=='trending':labels=[item['category'],item['evergreen_category'],'Master Article','Kushal Daga']
 else:labels=[item['category'],'Master Article','Kushal Daga']
 first=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I);body=ensure_seo_meta(body,title,meta,first.group(1) if first else '');body=ensure_social_identity(ensure_brand_identity(body));body=ensure_continuous_motion(body);body=stamp(body,title,str(package.get('structure_profile','standard')))
 # A verbatim sentence can still collide across rendered modules (for example a
 # FAQ answer repeating body prose). Remove the later copy rather than failing a
 # safe article; if the collision is not a repeated sentence the error is re-raised.
 from editorial_integrity import repair_repeated_prose,scrub_repeated_sentences
 for attempt in range(8):
  try:
   assert_publishable(title,body,labels,check_remote_images=check_remote_images);break
  except RuntimeError as exc:
   message=str(exc)
   repeat_issue=('repeated substantive sentence' in message
                 or 'duplicated substantive paragraph' in message)
   if not repeat_issue or attempt==7:raise
   body,removed=repair_repeated_prose(body)
   if not removed:
    # The reader-visible duplicates the gate measures are always removable, so a
    # later copy is dropped outright rather than failing a safe article.
    body,removed=scrub_repeated_sentences(body)
   if not removed:raise
   print(f'Removed {removed} repeated rendered sentence(s) before publication.')
 return title,slug,meta,labels,body

def trending_candidates(plan,item):
 """Use only live-internet reserves from the same approved category."""
 published_ids=used_topic_ids(read(ROOT/'MASTER_TOPIC_HISTORY.json',{'items':[]}),read(TRACKER,{}))
 used={x.get('id') for x in plan.get('trending',[])} | published_ids
 rows=[x for x in read(POOL,{}).get('topics',[]) if x.get('category')==item.get('category') and x.get('id') not in used and x.get('discovered_from_live_internet')]
 def evidence_rank(row):
  names=' '.join(str(x.get('name','')) for x in row.get('sources',[])).casefold()
  newsroom=4 if 'reuters' in names else 3 if 'bbc' in names else 2 if 'bloomberg' in names else 0
  return (newsroom,int(row.get('observation_count') or 0),float(row.get('overall_score') or 0))
 # A topic already published on an earlier date must never be regenerated as
 # today's primary merely because it remains in a newly generated plan.
 primary=[] if item.get('id') in published_ids else [item]
 return primary+sorted(rows,key=evidence_rank,reverse=True)[:12]

def reuse_completed_slot(plan,kind,slot,emit_social=False):
 from master_slot_state import keeper_for_slot,seal_plan
 records=read(TRACKER,{}).get('published',[]);keeper=keeper_for_slot(plan,records,kind,slot)
 if not keeper:return False
 import news_pipeline
 token=news_pipeline.blogger_token()
 ok,reason=news_pipeline.master_edition_check(keeper['url'],token,dt.date.fromisoformat(plan['date']))
 if not ok:raise RuntimeError('Recorded published slot could not be confirmed; defer instead of creating a second article: '+reason)
 pool=read(POOL,{});candidates=pool.get('topics',[])
 canonical=seal_plan(plan,records,candidates);write(PLAN,canonical)
 write(STATUS,{'status':'ALREADY_PUBLISHED','publication_enabled':bool(emit_social),'date':plan['date'],'kind':kind,'slot':slot,
               'topic_id':keeper.get('topic_id'),'title':keeper.get('title'),'url':keeper['url'],'published_at':keeper.get('published_at')})
 if emit_social:write(SOCIAL,[{'item_key':f'master-{kind}-{slot}','target_url':keeper['url'],'content_mode':'post','published_at':keeper.get('published_at','')}])
 print('Daily slot already has a confirmed live article; no replacement article is prepared or published.',flush=True)
 return True


# A refusal by a content gate and a broken run are different events, and the pipeline used to treat them
# the same way: the plan kept the same topic, the retry rebuilt it, and the same gate refused it again.
# On 22 October that is how one Evergreen slot collected 80 failure files while its 30-minute budget ran
# out, and how tonight's 20:45 trending slot died on a reused sentence instead of moving to another topic.
GATE_REFUSALS = ("source gate", "originality gate", "photo search exhausted", "no evidence-ready")


def gate_refusal(exc) -> bool:
    """True when a quality gate refused *this topic*, which is a reason to change topic and nothing more.

    A plan that is not READY, a Blogger call that failed or an embargo that has not lifted is not a
    refusal, and the slot must not be quietly reassigned because of one.
    """
    text = str(exc).casefold()
    return any(needle in text for needle in GATE_REFUSALS)


def block_topic(plan, kind, slot, item, error) -> None:
    """Record in the day's plan that this topic could not be made publishable today, and why.

    The publish path has always blocked a topic it could not honour; the prepare path never did, so the
    rotation the plan supports was invisible to the failures that most needed it. The reason is stored
    beside the id so the next run, and anyone reading the plan afterwards, can see which gate refused.
    """
    blocked = plan.setdefault('blockedTopics', {})
    blocked[str(item.get('id') or item.get('title') or 'unknown')] = {
        'kind': kind, 'slot': slot, 'title': str(item.get('title') or '')[:120],
        'error': str(error)[:300], 'at': dt.datetime.now(IST).isoformat(timespec='seconds')}
    write(PLAN, plan)


def build_candidate(kind, slot, candidate):
    """Generate, validate and render one topic into today's package, or raise the gate's refusal."""
    import master_v3_generator as generator
    candidate = dict(candidate); candidate['_structure_slot'] = slot + (0 if kind == 'trending' else 5)
    target = package_path(kind, candidate)
    if target.exists():
        package = read(target, {})
        # Policy-versioned packages are immutable and reusable; older automated
        # prose is rebuilt rather than grandfathered into publication.
        if package.get('policy_version') != POLICY_VERSION: package = generator.build(candidate, kind, target)
        else: validate(package)
    else: package = generator.build(candidate, kind, target)
    validate(package)
    title, slug, meta, labels, body = build_html(kind, candidate, package, check_remote_images=False)
    return candidate, target, title, slug, meta, labels, body


def prepare(kind,slot):
 plan,item=selected(kind,slot)
 if str(item.get('id')) in blocked_topics(plan):item=replace_blocked_topic(plan,kind,slot,item);plan=read(PLAN,{})
 if reuse_completed_slot(plan,kind,slot):return
 original=item;attempts=trending_candidates(plan,item) if kind=='trending' else [item];last=None;built=None
 for candidate in attempts:
  try:
   built=build_candidate(kind,slot,candidate);break
  except RuntimeError as exc:
   last=exc
   if not gate_refusal(exc):raise
 if built is None:
  # Every topic the plan offered for this slot was refused by a gate, so this is the moment to block the
  # day's own choice and let the substitution machinery - the one publication already trusts - pick
  # another approved topic in the same category. The substitute faces the identical gates: eight
  # topic-specific sources, three subject-named photographs, the originality rule, the word limits.
  block_topic(plan,kind,slot,original,last or RuntimeError('no candidate was offered for this slot'))
  try:
   substitute=replace_blocked_topic(read(PLAN,{}),kind,slot,original)
   built=build_candidate(kind,slot,substitute);item=substitute
  except RuntimeError as exc:
   raise RuntimeError(f"{last or 'no evidence-ready candidate remained'}; and the substitute topic was "
                      f"refused too - {exc}") from exc
 item,target,title,slug,meta,labels,body=built
 if item.get('id')!=original.get('id'):
  # Keyed by kind. The line before this wrote into plan['trending'] whatever the kind was, so an
  # Evergreen substitution overwrote the trending row for the same slot number. The in-memory plan is
  # the complete one for this call, so it is the base, and only the block list is taken back from disk
  # - reading the file alone used to lose the blocks written a moment earlier, and could raise IndexError
  # for a slot whose row had not been written yet.
  stored=read(PLAN,{}) or {}
  if stored.get('blockedTopics'):plan['blockedTopics']=stored['blockedTopics']
  plan.setdefault(kind,[])[slot]=item;write(PLAN,plan)
 out=ROOT/'scheduled_ready'/f'{plan["date"]}-{kind}-{slot}-{slug}.html';out.parent.mkdir(exist_ok=True);out.write_text(body)
 write(STATUS,{'status':'PREPARED','publication_enabled':False,'date':plan['date'],'kind':kind,'slot':slot,'topic_id':item['id'],'replaced_topic_id':original.get('id') if item.get('id')!=original.get('id') else None,'title':title,'package':str(target.relative_to(ROOT)),'html':str(out.relative_to(ROOT)),**BUDGET.note()});print(f"Preparation used {BUDGET.elapsed_minutes()} of {BUDGET.minutes:.0f} budgeted minutes");print(target)

def _package_or_build(kind,slot,item):
    """A substituted topic has no package yet, so build it before publishing."""
    target=package_path(kind,item)
    if target.exists():return target
    prepare(kind,slot)
    target=package_path(kind,item)
    if not target.exists():raise RuntimeError('substituted topic package could not be prepared')
    return target


def _publish_once(kind,slot,timed_release=False):
 # Never allow an ignored event from a prior local attempt to be redispatched.
 write(SOCIAL,[])
 if os.environ.get('MASTER_PUBLICATION_ENABLED','').casefold()!='true':raise RuntimeError('Master publication remains intentionally paused; set MASTER_PUBLICATION_ENABLED=true only after owner activation')
 # The public release time is an embargo, not merely a scheduled-workflow hint.
 # Prewarm retries and manual recovery may finish early, but every publishing
 # path waits for the exact audience-facing slot before calling Blogger.
 wait_for_release(MASTER_LIVE[(kind,slot)],allow_early=(kind,slot))
 plan,item=selected(kind,slot)
 if str(item.get('id')) in blocked_topics(plan):
  item=replace_blocked_topic(plan,kind,slot,item);plan=read(PLAN,{})
 if reuse_completed_slot(plan,kind,slot,emit_social=True):return
 target=_package_or_build(kind,slot,item)  # proves the package exists or builds it
 package=read(target,{});validate(package);title,slug,meta,labels,body=build_html(kind,item,package);res=publish_to_blogger(title,body,labels)
 if not res or not res.get('url'):raise RuntimeError('Blogger did not confirm a live Master Article URL')
 # Blogger answers with an older article when a topic has been published before.
 # Recording that as today's slot left an Evergreen slot unpaid for hours on
 # 19 October and rewrote an earlier published article, so the day's own
 # publication is proved here and the topic is blocked so a retry substitutes.
 live_day=ist_day(res.get('published') or '')
 if live_day and live_day!=dt.date.fromisoformat(str(plan['date'])):
  blocked=plan.setdefault('blockedTopics',{});blocked[str(item['id'])]=(
   f"the live post at {res.get('url')} was published {live_day.isoformat()}, not {plan['date']}")
  write(PLAN,plan)
  raise EditionIdentityError(f"MASTER EDITION IDENTITY FAILED - the article at {res.get('url')} belongs to "
                     f"{live_day.isoformat()}, not {plan['date']}; the topic is blocked for today so a "
                     f"retry publishes another article instead of rewriting the older one")
 tracker=read(TRACKER,{'version':1,'published':[]});record={'topic_id':item['id'],'kind':kind,'slot':slot,'slot_key':f"{plan['date']}:{kind}:{slot}",'date':plan['date'],'category':item['category'],'evergreen_category':item.get('evergreen_category') or item['category'],'title':title,'url':res['url'],'published_at':res.get('published') or dt.datetime.now(dt.timezone.utc).isoformat()};tracker['publication_enabled']=True
 already=lambda rows: any(x.get('date')==plan['date'] and x.get('kind')==kind and x.get('slot')==slot for x in rows)
 if not already(tracker['published']):tracker['published'].append(record)
 write(TRACKER,tracker)
 history=read(ROOT/'MASTER_TOPIC_HISTORY.json',{'version':1,'items':[]})
 if not already(history['items']):history['items'].append(record)
 write(ROOT/'MASTER_TOPIC_HISTORY.json',history);write(SOCIAL,[{'item_key':f'master-{kind}-{slot}','target_url':res['url'],'content_mode':'post','published_at':record['published_at']}]);write(STATUS,{'status':'PASS','publication_enabled':True,**record});print(res['url'])

def publish(kind,slot,timed_release=False):
    """Publish today's article, substituting a topic that another day already owns.

    A repeated topic used to end three ways, all wrong: the older article was
    rewritten, the slot went unrecorded, and the recovery guard dispatched the same
    failing job over and over while every run reported success. Now the day is proved,
    the unusable topic is blocked for today, and another approved topic in the same
    category is prepared and published inside the same run.
    """
    first = None
    for attempt in range(3):
        try:
            return _publish_once(kind, slot, timed_release)
        except EditionIdentityError as exc:
            first = exc
            if attempt >= 2:
                raise
            print(f"Master {kind} slot {slot}: {exc}", flush=True)
            print("Master block recorded; preparing another approved topic for this slot now", flush=True)
        except RuntimeError as exc:
            if first is not None:
                raise RuntimeError(f"{first}; and the substitution also failed - {exc}") from exc
            raise
    raise first if first else RuntimeError('unreachable')


def main():
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=('trending','evergreen'),required=True);p.add_argument('--slot',type=int,choices=range(5),required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--publish',action='store_true');p.add_argument('--timed-release',action='store_true');a=p.parse_args()
 try:
  if a.prepare==a.publish:raise RuntimeError('choose exactly one of --prepare or --publish')
  if a.prepare:prepare(a.kind,a.slot)
  else:publish(a.kind,a.slot,timed_release=a.timed_release)
 except Exception as exc:
  try:
   stage='master-v3'
  except Exception:stage='master-v3'
  write(STATUS,{'status':'FAIL','publication_enabled':os.environ.get('MASTER_PUBLICATION_ENABLED','').casefold()=='true','kind':a.kind,'slot':a.slot,'stage':stage,'error_type':type(exc).__name__,'error':str(exc)[:1000],**BUDGET.note()});raise
if __name__=='__main__':main()
