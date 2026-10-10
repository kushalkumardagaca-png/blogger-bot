"""Fail-closed structural checks run immediately before every Blogger publish."""
import html,json,re
from urllib.parse import urlsplit
from image_safety import image_works

MASS_TEMPLATE_PHRASES=(
 'This forensic framework eliminates redundant intermediary friction',
 'strict institutional baseline assumptions','Zero Emotional Bias',
 '100-Yr Empirical Return','Forensic Simplified System',
 'mathematically proven execution protocols',
)
UNSUPPORTED_ABSOLUTES=('guaranteed returns','always outperforms','risk-free investment','100% systematic autopilot')

def _plain(content):
 value=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',content or '',flags=re.I|re.S)
 return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value))).strip()

def _source_domains(content):
 own='dailyyield.blogspot.com';ignore={'facebook.com','www.facebook.com','bsky.app','www.tumblr.com','mastodon.social'};out=set()
 for url in re.findall(r'<a\b[^>]*href=["\'](https?://[^"\']+)',content or '',flags=re.I):
  host=(urlsplit(html.unescape(url)).hostname or '').lower()
  if host and host!=own and host not in ignore:out.add(host)
 return out

def assert_publishable(title,content,labels):
 issues=[]; labels=labels or []
 if not title or len(title.strip())<20:issues.append('missing/short SEO title (minimum 20 characters)')
 if len(title.strip())>46:issues.append(f'Bing title budget exceeded ({len(title.strip())} characters; maximum 46)')
 if len(content)<8000:issues.append(f'content package too small ({len(content)} bytes)')
 text=_plain(content);word_count=len(re.findall(r"[A-Za-z][A-Za-z'-]+",text));is_news='News' in labels;master_v2='<!-- DY_MASTER_V2 -->' in content
 minimum_words=350 if is_news else (4500 if master_v2 else 900)
 if word_count<minimum_words:issues.append(f'insufficient reader-value depth ({word_count} words; minimum {minimum_words})')
 paragraphs=[]
 for raw in re.findall(r'<p\b[^>]*>(.*?)</p>',content or '',flags=re.I|re.S):
  value=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',raw))).strip().casefold()
  if len(value)>=100:paragraphs.append(value)
 if len(paragraphs)!=len(set(paragraphs)):
  seen=set();duplicate=next((p for p in paragraphs if p in seen or seen.add(p)), '')
  issues.append('duplicated substantive paragraph detected: '+duplicate[:180])
 source_minimum=2 if is_news else 3
 if len(_source_domains(content))<source_minimum:issues.append(f'insufficient independent/primary source domains (minimum {source_minimum})')
 for phrase in MASS_TEMPLATE_PHRASES:
  if phrase.casefold() in text.casefold():issues.append('mass-template phrase prohibited: '+phrase)
 for phrase in UNSUPPORTED_ABSOLUTES:
  if phrase.casefold() in text.casefold():issues.append('unsupported absolute claim prohibited: '+phrase)
 if not is_news and not master_v2:
  if 'Worked example with disclosed assumptions' not in content:issues.append('transparent worked example missing')
  if 'Editorial method' not in content:issues.append('editorial method disclosure missing')
 if master_v2:
  for marker,name in (("class=\"dy2-toc\"","table of contents"),("class=\"dy2-summary\"","600–800 word summary"),("class=\"dy2-faq\"","topic FAQ"),("class=\"dy2-glossary\"","glossary"),("class=\"dy2-low\"","10–15 item discovery shelf"),("class=\"dy2-follow\"","separate follow section")):
   if marker not in content:issues.append(name+' missing')
  if content.count('class="dy2-photo"')!=3:issues.append('exactly three editorial landscape photos required')
  if content.count('class="dy2-data ')<3:issues.append('at least three evidence-based data representations required')
  order=[content.find(x) for x in ('class="dy2-summary"','class="dy2-faq"','class="dy2-glossary"','class="dy2-low"','class="dy2-follow"','DY_PAGE_FAMILY_START')]
  if any(x<0 for x in order) or order!=sorted(order):issues.append('Master V2 closing-section order is invalid')
 if 'Kushal K. Daga' not in content:issues.append('current byline missing')
 if 'challenge-platform' in content or '/cdn-cgi/challenge-platform/' in content:issues.append('invalid copied challenge script')
 if not master_v2 and 'class="dy-context"' not in content:issues.append('contextual internal-link card missing')
 if not master_v2 and 'class="dy-related"' not in content:issues.append('related-reading shelf missing')
 if 'id="dyPageFamily"' not in content:issues.append('comprehensive Daily Yield family directory missing')
 if 'metaDesc' not in content and 'DY_SEO_META_START' not in content:issues.append('SEO/meta description package missing')
 if 'DY_CONTINUOUS_MOTION_START' not in content:issues.append('continuous gesture controller missing')
 ids=re.findall(r'\bid=["\']([^"\']+)',content,re.I)
 dup=sorted({x for x in ids if ids.count(x)>1})
 if dup:issues.append('duplicate HTML ids: '+', '.join(dup[:8]))
 h1_count=len(re.findall(r'<h1\b',content,re.I))
 if h1_count!=1:issues.append(f'content must contain exactly one primary H1 (found {h1_count})')
 img_tags=re.findall(r'<img\b[^>]*>',content,re.I)
 imgs=[html.unescape(x) for x in re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',content,re.I)]
 missing_alt=[]
 for tag in img_tags:
  alt=re.search(r'\balt\s*=\s*["\']([^"\']*)["\']',tag,re.I)
  if not alt or not html.unescape(alt.group(1)).strip():missing_alt.append(tag)
 if missing_alt:issues.append(f'{len(missing_alt)} image(s) missing descriptive alt text')
 if not imgs:issues.append('hero image missing')
 else:
  hero_alt=re.search(r'\balt=["\']([^"\']*)["\']',img_tags[0],re.I) if img_tags else None
  if not hero_alt or not hero_alt.group(1).strip():issues.append('hero image missing descriptive alt text')
  if imgs[0].startswith(('http://','https://')) and not image_works(imgs[0]):issues.append('hero image failed final availability check')
 schemas=re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',content,re.I|re.S)
 if not schemas:issues.append('JSON-LD schema missing')
 for n,raw in enumerate(schemas,1):
  try:json.loads(html.unescape(raw).strip())
  except Exception as e:issues.append(f'JSON-LD schema {n} invalid: {e}')
 if 'News' in labels and 'class="fbk-src' not in content:issues.append('news source links missing')
 if issues:raise RuntimeError('PUBLICATION PREFLIGHT FAILED — '+'; '.join(issues))
 print(f'Publication preflight PASS: {title[:70]}')
 return True
