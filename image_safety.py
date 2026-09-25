"""Remote editorial-image validation with verified Daily Yield fallbacks."""
import urllib.request,time
UA={'User-Agent':'Mozilla/5.0 (compatible; DailyYieldImageCheck/1.0)','Range':'bytes=0-2047'}
FALLBACK_MARKET='https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&h=900&q=85'
FALLBACK_PERSONAL='https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?auto=format&fit=crop&w=1600&h=900&q=85'
_cache={}
def image_works(url,tries=2):
 if url in _cache:return _cache[url]
 ok=False
 for attempt in range(tries):
  try:
   req=urllib.request.Request(url,headers=UA)
   with urllib.request.urlopen(req,timeout=20) as r:
    ok=r.status in (200,206) and (r.headers.get('Content-Type') or '').lower().startswith('image/')
   if ok:break
  except Exception:
   if attempt+1<tries:time.sleep(.7)
 _cache[url]=ok;return ok
def safe_image(url,fallback=FALLBACK_MARKET):
 """Return the candidate only after it serves image bytes; otherwise a known-good fallback."""
 if image_works(url):return url
 if not image_works(fallback):raise RuntimeError('Both selected image and verified fallback failed availability checks')
 print(f'Image preflight replaced unavailable asset: {url}')
 return fallback
