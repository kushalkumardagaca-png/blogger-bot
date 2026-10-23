#!/usr/bin/env python3
"""Cross-route integrity controls for a high-volume Blogger publication.

The module prevents duplicate topics and near-duplicate live posts, records an
explainable content/structure fingerprint, and makes retries recover the existing
Blogger object instead of creating another one. It performs no public page views.
"""
from __future__ import annotations
import datetime as dt,hashlib,html,json,re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

STOP=set('a an and are as at be by for from how in into is it of on or that the this to today versus via what when where which who why will with your'.split())
MARK='DY_EDITORIAL_INTEGRITY_V1'

def plain(value:str)->str:
 value=re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>',' ',value or '',flags=re.I|re.S)
 return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value))).strip()

def tokens(value:str)->list[str]:
 return [x for x in re.findall(r'[a-z0-9]+',plain(value).casefold()) if x not in STOP]

def normalized_title(value:str)->str:return ' '.join(tokens(value))
def digest(value:str)->str:return hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]
def content_fingerprint(content:str)->str:return digest(' '.join(tokens(content)))
def structure_fingerprint(content:str)->str:
 tags=re.findall(r'<(h[1-6]|section|figure|table|aside|details|ol|ul)\b[^>]*?(?:class=["\']([^"\']+))?',content or '',flags=re.I)
 return digest('|'.join(a.casefold()+':'+re.sub(r'\s+','.',b.strip().casefold()) for a,b in tags))
def topic_similarity(a:str,b:str)->float:
 aa=set(tokens(a));bb=set(tokens(b));return len(aa&bb)/len(aa|bb) if aa and bb else 0.0
def language_similarity(a:str,b:str)->float:
 aa=' '.join(tokens(a));bb=' '.join(tokens(b));return SequenceMatcher(None,aa,bb,autojunk=True).ratio() if aa and bb else 0.0

def assert_unique_plan(plan:dict)->bool:
 rows=[]
 for kind in ('trending','evergreen'):
  for slot,item in enumerate(plan.get(kind,[]) or []):rows.append((kind,slot,str(item.get('id','')),str(item.get('title',''))))
 issues=[]
 ids={}
 for kind,slot,ident,title in rows:
  if ident and ident in ids:issues.append(f'topic id {ident} repeated at {ids[ident]} and {kind}:{slot}')
  ids[ident]=f'{kind}:{slot}'
 for i,left in enumerate(rows):
  for right in rows[i+1:]:
   sim=topic_similarity(left[3],right[3])
   if normalized_title(left[3])==normalized_title(right[3]) or sim>=0.72:
    issues.append(f'near-duplicate planned topics {left[0]}:{left[1]} and {right[0]}:{right[1]} ({sim:.0%})')
 if issues:raise RuntimeError('DAILY TOPIC DIVERSITY GATE FAILED — '+'; '.join(issues))
 return True

def stamp(content:str,title:str,profile:str='')->str:
 marker=f'<!-- {MARK} topic={digest(normalized_title(title))} content={content_fingerprint(content)} structure={structure_fingerprint(content)} profile={re.sub(r"[^a-z0-9_-]","",profile.casefold()) or "standard"} -->'
 return content if MARK in content else marker+'\n'+content

def canonical_path(url:str)->str:
 # Blogger never overwrites a taken permalink: when a post is created twice - typically because the
 # first creation succeeded and the response was lost in a retry - the second copy lands beside the
 # first with the day's number glued to its slug, e.g. banking-...-2026-10_01450325346.html beside
 # banking-...-2026-10.html. Eight of those pairs were live on 22 October, both copies offered for
 # indexing. Stripping the glue here is what lets the publisher recognise its own lost response as the
 # post it should have updated, so it recovers the existing article instead of adding a second URL.
 try:
  path=urlsplit(url).path.rstrip('/')
  return re.sub(r'_\d{6,}(?=\.html$|$)','',path)
 except Exception:return ''

def duplicate_reason(title:str,content:str,post:dict,expected_url:str='')->str:
 prior_title=str(post.get('title',''));prior_content=str(post.get('content',''))
 if normalized_title(title)==normalized_title(prior_title):return 'same normalized title'
 if expected_url and canonical_path(expected_url)==canonical_path(str(post.get('url',''))):return 'same canonical path'
 if topic_similarity(title,prior_title)>=0.78:return 'near-duplicate topic title'
 # Full prose comparison is reserved for plausible title matches, avoiding a
 # quadratic cost against unrelated long articles.
 if topic_similarity(title,prior_title)>=0.42 and language_similarity(content,prior_content)>=0.86:return 'near-duplicate article content'
 return ''

def find_duplicate(title:str,content:str,posts:list[dict],expected_url:str='',ignore_ids:set[str]|None=None):
 ignore_ids=ignore_ids or set()
 for post in posts:
  if str(post.get('id','')) in ignore_ids:continue
  reason=duplicate_reason(title,content,post,expected_url)
  if reason:return post,reason
 return None,None

def _read_status(path:Path)->dict:
 try:return json.loads(path.read_text())
 except (OSError,json.JSONDecodeError) as exc:raise RuntimeError(f'GREEN OPERATING GATE FAILED — unreadable {path.name}: {exc}')
def _age_hours(value:str)->float:
 stamp=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=dt.timezone.utc)
 return (dt.datetime.now(dt.timezone.utc)-stamp).total_seconds()/3600

def assert_green_operating_state(root:Path|None=None,max_age_hours:float=36)->bool:
 """Fail publication closed when whole-site or official-policy monitoring is stale."""
 root=root or Path(__file__).parent
 corpus=_read_status(root/'BLOGGER_CORPUS_POLICY_STATUS.json');policy=_read_status(root/'BLOGGER_POLICY_MONITOR_STATUS.json')
 issues=[]
 if corpus.get('status')!='PASS':issues.append('live Blogger corpus status is not PASS')
 if corpus.get('remaining_live_policy_flags'):issues.append('live corpus has policy flags')
 if corpus.get('unsafe_active_links'):issues.append('live corpus has unsafe links')
 if int(corpus.get('image_rights_gap_posts') or 0):issues.append('live corpus has image-rights gaps')
 if policy.get('status')!='PASS' or policy.get('wording_changed'):issues.append('official Blogger policy requires review')
 for name,row in (('corpus',corpus),('policy',policy)):
  try:
   if _age_hours(row.get('checked_at',''))>max_age_hours:issues.append(f'{name} audit is stale')
  except Exception:issues.append(f'{name} audit timestamp is invalid')
 if issues:raise RuntimeError('GREEN OPERATING GATE FAILED — '+'; '.join(issues))
 return True

def assert_saved_green(post:dict)->bool:
 """Verify Blogger's stored response, not merely the pre-insert package."""
 from content_policy_guard import DISCLOSURE_MARKER,audit_text
 title=str(post.get('title',''));content=str(post.get('content',''));issues=[]
 if post.get('status') not in (None,'LIVE'):issues.append('Blogger post is not live')
 if DISCLOSURE_MARKER not in content:issues.append('current transparency disclosure missing')
 if MARK not in content:issues.append('editorial integrity fingerprint missing')
 if not post.get('url'):issues.append('canonical Blogger URL missing')
 for tag in re.findall(r'<img\b[^>]*>',content,re.I):
  alt=re.search(r'\balt=["\']([^"\']*)',tag,re.I)
  if not alt or not html.unescape(alt.group(1)).strip():issues.append('image alternative text missing');break
 issues.extend(audit_text(title,content,'stored-blogger-post',require_disclosure=True))
 if issues:raise RuntimeError('STORED BLOGGER GREEN VERIFICATION FAILED — '+'; '.join(sorted(set(issues))))
 return True

PROSE_BLOCKS=re.compile(r'(<(?:p|dd)\b[^>]*>)(.*?)(</(?:p|dd)>)',re.I|re.S)
def repair_repeated_prose(content:str)->tuple[str,int]:
 """Remove a later verbatim prose sentence so a late policy check cannot fail.

 Only paragraph-level editorial prose is touched; source ledgers, tables,
 navigation and captions keep their text. The first occurrence is never altered.
 A sentence is treated as repeated exactly as the publication gate treats it, so
 the repair can never leave behind something the gate would still reject. When a
 whole paragraph repeats, the paragraph itself is removed.
 """
 from content_policy_guard import normalize_sentence
 seen=set();removed=0
 def fix(match):
  nonlocal removed
  opening,body,closing=match.group(1),match.group(2),match.group(3)
  if '<' in body:return match.group(0)
  parts=[x for x in re.split(r'(?<=[.!?])\s+',body.strip()) if x.strip()]
  if not parts:return match.group(0)
  kept=[];dropped=0
  for sentence in parts:
   key=normalize_sentence(sentence)
   if len(key.split())>=10:
    if key in seen:
     removed+=1;dropped+=1
     continue
    seen.add(key)
   kept.append(sentence)
  if not kept:
   # Every sentence in this block already appeared earlier, so the duplicate
   # paragraph goes as a whole instead of being reported as unrepairable.
   return '' if dropped else match.group(0)
  return opening+' '.join(kept)+closing
 repaired=PROSE_BLOCKS.sub(fix,content)
 repaired=re.sub(r'<p\b[^>]*>\s*</p>','',repaired,flags=re.I)
 return repaired,removed

# Blocks that carry controlled, already-reviewed text. Their wording is unique and
# must never be rewritten by a repetition repair.
PROTECTED_BLOCKS=re.compile('|'.join((
 r'<script\b.*?</script\s*>',
 r'<style\b.*?</style\s*>',
 r'<!--\s*DY_ENGAGED_READER_V2.*?<!--\s*/DY_ENGAGED_READER_V2\s*-->',
 r'<!--\s*DY_RELATED_ARTICLES_START.*?<!--\s*DY_RELATED_ARTICLES_END\s*-->',
 r'<!--\s*DY_CONTINUOUS_MOTION_START.*?<!--\s*DY_CONTINUOUS_MOTION_END\s*-->',
 r'<!--\s*DY_PAGE_FAMILY_START.*',
 r'<aside\b[^>]*dy-policy-disclosure.*?</aside\s*>',
 # A photo's licence credit is functional attribution, not editorial prose. Three photographs taken at
 # one event by one photographer under one licence legitimately repeat the same sentence, and on
 # 22 October 2026 the repetition repair treated the second and third copies as plagiarism and deleted
 # their words out of the figcaption, leaving a link with nothing to read. Protected here like the rest
 # of the controlled furniture: the reader still sees it, this repair never rewrites it.
 r'<figcaption\b[^>]*>.*?</figcaption\s*>',
)),re.I|re.S)

def _visible_text(segment:str)->tuple[str,list[int]]:
    """Return the readable text of an HTML segment plus the source index of each character.

    Each tag becomes a single space, exactly as the publication gate reads the
    article, so a sentence that spans a link or an emphasis tag is still seen as
    one sentence. Synthetic characters carry index -1 and are never used as a
    deletion boundary.
    """
    characters:list[str]=[];index:list[int]=[];position=0;length=len(segment)
    while position<length:
        character=segment[position]
        if character=="<":
            closing=segment.find(">",position)
            if closing<0:break
            characters.append(" ");index.append(-1);position=closing+1;continue
        if character=="&":
            entity=re.match(r"&(?:#[0-9]{2,6}|#x[0-9a-fA-F]{2,6}|[a-zA-Z]{2,8});",segment[position:position+12])
            if entity:
                characters.append(html.unescape(entity.group(0)));index.append(position);position+=len(entity.group(0));continue
        characters.append(character);index.append(position);position+=1
    return "".join(characters),index


def _sentence_spans(text:str)->list[tuple[int,int]]:
    spans=[];start=0
    for match in re.finditer(r"[.!?]+(?=\s|$)",text):
        spans.append((start,match.end()));start=match.end()
    if start<len(text):spans.append((start,len(text)))
    return spans


def _source_bounds(index:list[int],start:int,end:int)->tuple[int,int]|None:
    """Translate a plain-text range into a safe source range, skipping synthetic gaps."""
    source_start=next((index[position] for position in range(start,min(end,len(index))) if index[position]>=0),None)
    source_end=next((index[position] for position in range(min(end,len(index))-1,start-1,-1) if index[position]>=0),None)
    if source_start is None or source_end is None or source_end<source_start:
        return None
    return source_start,source_end+1


def _drop_plain_ranges(segment:str,index:list[int],ranges:list[tuple[int,int]],replacement:str="")->str:
    """Delete (or overwrite) plain-text ranges inside an HTML segment, latest first."""
    for start,end in sorted(ranges,key=lambda x:x[0],reverse=True):
        if end<=start:continue
        bounds=_source_bounds(index,start,end)
        if not bounds:continue
        source_start,source_end=bounds
        while source_end<len(segment) and segment[source_end] in " \t\r\n":source_end+=1
        segment=segment[:source_start]+replacement+segment[source_end:]
    return segment


PARAGRAPH=re.compile(r"<p\b[^>]*>(.*?)</p\s*>",re.I|re.S)
def drop_repeated_paragraphs(segment:str)->tuple[str,int]:
    """Remove a stock repeating paragraph and every later duplicate paragraph.

    The publication gate refuses an article that repeats a whole substantive
    paragraph, and a paragraph made of one short phrase repeated is exactly the
    machine-generated padding Blogger's spam rules warn about. Both are removed
    here; the first real occurrence of any paragraph is always preserved.
    """
    seen=set();removed=0;pieces=[];cursor=0
    for match in PARAGRAPH.finditer(segment):
        body=match.group(1)
        if "<script" in body.casefold():
            continue
        text=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",body))).strip()
        key=text.casefold()
        drop=False
        words=re.findall(r"[a-z0-9']+",key)
        if len(words)>=6 and len(set(words))<=3:
            # A paragraph built from one phrase repeated is machine padding, not
            # reader value, so even its first occurrence is removed.
            drop=True
        elif len(text)>=100:
            if key in seen:drop=True
            else:seen.add(key)
        if drop:
            removed+=1
            pieces.append(segment[cursor:match.start()])
            cursor=match.end()
    if not removed:return segment,0
    pieces.append(segment[cursor:])
    return "".join(pieces),removed


SENTENCE_BLOCKS=re.compile(r"<(p|li|dd|blockquote|figcaption|h[2-4])\b([^>]*)>(.*?)</\1\s*>",re.I|re.S)
def scrub_repeated_sentences(content:str)->tuple[str,int]:
 """Remove banned stock sentences and every later duplicate sentence.

 The publication gate measures repetition on the rendered text of the whole
 article, so this repair reads every sentence as a reader sees it, including
 sentences that run across a link or an emphasis tag, and deletes the offending
 sentence from the markup. Paragraphs built from one repeated phrase are machine
 padding and are removed outright. Scripts, styles, headings of the article's own
 title and the controlled Daily Yield furniture are never touched, and the first
 real occurrence of a sentence and of a paragraph is always preserved.
 """
 from content_policy_guard import REPETITIVE_FALLBACK_PHRASES,normalize_sentence
 banned=[x for x in (normalize_sentence(item) for item in REPETITIVE_FALLBACK_PHRASES) if x]
 seen=set();removed=0
 def scrub_warnings_and_duplicates(inner:str)->tuple[str,int]:
  nonlocal removed
  plain,index=_visible_text(inner);drops=[]
  for start,end in _sentence_spans(plain):
   key=normalize_sentence(plain[start:end])
   if not key:continue
   if any(phrase in key for phrase in banned):
    drops.append((start,end));removed+=1;continue
   if len(key.split())>=10:
    if key in seen:
     drops.append((start,end));removed+=1;continue
    seen.add(key)
  if not drops:return inner,0
  return _drop_plain_ranges(inner,index,drops),len(drops)
 def fix_block(match:"re.Match[str]")->str:
  tag,attributes,inner=match.group(1),match.group(2),match.group(3)
  if "<script" in inner.casefold() or "<style" in inner.casefold():return match.group(0)
  repaired,_count=scrub_warnings_and_duplicates(inner)
  return match.group(0) if repaired==inner else f"<{tag}{attributes}>{repaired}</{tag}>"
 def scrub(segment:str)->str:
  nonlocal removed
  segment,paragraphs=drop_repeated_paragraphs(segment)
  removed+=paragraphs
  segment=SENTENCE_BLOCKS.sub(fix_block,segment)
  # Anything outside a recognised block (tables, plain containers, captions) is
  # scanned as a reader sees it, so no duplicate or stock sentence survives.
  plain,index=_visible_text(segment);drops=[];leftover_seen=set()
  for start,end in _sentence_spans(plain):
   key=normalize_sentence(plain[start:end])
   if not key:continue
   if any(phrase in key for phrase in banned):
    drops.append((start,end));removed+=1;continue
   if len(key.split())>=10:
    if key in leftover_seen:
     drops.append((start,end));removed+=1;continue
    leftover_seen.add(key)
  return _drop_plain_ranges(segment,index,drops) if drops else segment
 output=[];cursor=0
 for match in PROTECTED_BLOCKS.finditer(content or ""):
  output.append(scrub((content or "")[cursor:match.start()]));output.append(match.group(0));cursor=match.end()
 output.append(scrub((content or "")[cursor:]))
 cleaned="".join(output)
 cleaned=re.sub(r"<p\b[^>]*>\s*</p>","",cleaned,flags=re.I)
 return cleaned,removed


def replace_plain_ranges(segment:str,index:list[int],edits:list[tuple[int,int,str]])->str:
 """Rewrite reader-visible text ranges inside markup, without touching structure."""
 for start,end,replacement in sorted(edits,key=lambda x:x[0],reverse=True):
  if end<=start:continue
  bounds=_source_bounds(index,start,end)
  if not bounds:continue
  source_start,source_end=bounds
  segment=segment[:source_start]+replacement+segment[source_end:]
 return segment
