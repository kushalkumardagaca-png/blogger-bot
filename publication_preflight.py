"""Fail-closed structural checks run immediately before every Blogger publish."""
import html,json,re
from image_safety import image_works

def assert_publishable(title,content,labels):
 issues=[]; labels=labels or []
 if not title or len(title.strip())<8:issues.append('missing/short title')
 if len(content)<8000:issues.append(f'content package too small ({len(content)} bytes)')
 if 'Kushal K. Daga' not in content:issues.append('current byline missing')
 if 'challenge-platform' in content or '/cdn-cgi/challenge-platform/' in content:issues.append('invalid copied challenge script')
 if 'class="dy-context"' not in content:issues.append('contextual internal-link card missing')
 if 'class="dy-related"' not in content:issues.append('related-reading shelf missing')
 if 'id="dyPageFamily"' not in content:issues.append('comprehensive Daily Yield family directory missing')
 if 'metaDesc' not in content and 'DY_SEO_META_START' not in content:issues.append('SEO/meta description package missing')
 if 'DY_CONTINUOUS_MOTION_START' not in content:issues.append('continuous gesture controller missing')
 ids=re.findall(r'\bid=["\']([^"\']+)',content,re.I)
 dup=sorted({x for x in ids if ids.count(x)>1})
 if dup:issues.append('duplicate HTML ids: '+', '.join(dup[:8]))
 imgs=[html.unescape(x) for x in re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',content,re.I)]
 if not imgs:issues.append('hero image missing')
 elif imgs[0].startswith(('http://','https://')) and not image_works(imgs[0]):issues.append('hero image failed final availability check')
 schemas=re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',content,re.I|re.S)
 if not schemas:issues.append('JSON-LD schema missing')
 for n,raw in enumerate(schemas,1):
  try:json.loads(html.unescape(raw).strip())
  except Exception as e:issues.append(f'JSON-LD schema {n} invalid: {e}')
 if 'News' in labels and 'class="fbk-src' not in content:issues.append('news source links missing')
 if issues:raise RuntimeError('PUBLICATION PREFLIGHT FAILED — '+'; '.join(issues))
 print(f'Publication preflight PASS: {title[:70]}')
 return True
