"""Topic-weighted, continuously moving related-article shelf for Daily Yield posts."""
import html,re,json,os,urllib.parse,urllib.request
START='<!-- DY_RELATED_ARTICLES_START -->';END='<!-- DY_RELATED_ARTICLES_END -->'
STYLE='''<style id="dyRelatedStyle">
.dy-related{max-width:1120px;margin:46px auto 24px;padding:22px 0;border-top:1px solid #eadcc8;border-bottom:1px solid #eadcc8;color:#241610;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}.dy-related-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin:0 14px 16px}.dy-related-head b{display:block;color:#9c4522;font-size:9px;letter-spacing:.16em;text-transform:uppercase}.dy-related-head h2{margin:5px 0 0;font:700 clamp(23px,4vw,34px)/1.1 Georgia,serif}.dy-related-head span{color:#6e5d4b;font-size:11px}.dy-related-viewport{overflow:hidden;padding:4px 14px 14px}.dy-related-track{display:flex!important;flex-wrap:nowrap!important;width:max-content!important;min-width:max-content!important;max-width:none!important;gap:12px;will-change:transform}.dy-related-group{display:flex!important;flex:0 0 auto!important;flex-wrap:nowrap!important;width:max-content!important;min-width:max-content!important;max-width:none!important;gap:12px}.dy-related-card{display:flex;flex:0 0 clamp(235px,31vw,290px)!important;flex-direction:column;width:clamp(235px,31vw,290px)!important;min-width:235px!important;max-width:290px!important;min-height:220px;overflow:hidden;border:1px solid #eadcc8;border-radius:13px;background:#fffdf8;color:#241610;text-decoration:none;box-shadow:0 8px 22px -18px rgba(36,22,16,.45)}.dy-related-card:hover{border-color:#bc5b33;box-shadow:0 15px 28px -18px rgba(156,69,34,.42)}.dy-related-thumb{height:112px;background:linear-gradient(135deg,#f6e3d3,#fff8ee);overflow:hidden}.dy-related-thumb img{width:100%;height:100%;object-fit:cover;display:block}.dy-related-copy{display:flex;flex:1;flex-direction:column;padding:12px}.dy-related-copy small{color:#9c4522;font-size:8px;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.dy-related-copy strong{margin-top:6px;font:700 16px/1.25 Georgia,serif}.dy-related-copy em{margin-top:auto;padding-top:10px;color:#9c4522;font-size:9px;font-style:normal;font-weight:900;letter-spacing:.1em;text-transform:uppercase}@media(max-width:560px){.dy-related-head{align-items:start;flex-direction:column}.dy-related-head span{display:none}.dy-related-card{width:242px}}
</style>'''
STOP={'the','and','for','with','from','that','this','your','into','what','why','how','about','news','finance','financial','daily','yield','2026','september','coverage','policy'}
def words(text):return {x for x in re.findall(r"[a-z0-9]+",html.unescape(re.sub(r'<[^>]+>',' ',text or '')).lower()) if len(x)>2 and x not in STOP}
def fetch_public_posts(limit=100):
 """Read related-post candidates through Blogger API, never public blog URLs."""
 try:
  form=urllib.parse.urlencode({'client_id':os.environ['BLOGGER_CLIENT_ID'],'client_secret':os.environ['BLOGGER_CLIENT_SECRET'],'refresh_token':os.environ['BLOGGER_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
  with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=form,method='POST'),timeout=25) as r:token=json.load(r)['access_token']
  out=[];page_token=''
  while len(out)<limit:
   params={'status':'live','fetchBodies':'true','maxResults':min(50,limit-len(out)),'fields':'items(id,title,content,labels,published,url),nextPageToken'}
   if page_token:params['pageToken']=page_token
   url=f"https://www.googleapis.com/blogger/v3/blogs/{os.environ['BLOGGER_BLOG_ID']}/posts?"+urllib.parse.urlencode(params)
   req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'User-Agent':'DailyYield-related/2.0'})
   with urllib.request.urlopen(req,timeout=30) as r:data=json.load(r)
   out.extend({'id':e.get('id',''),'title':e.get('title',''),'content':e.get('content',''),'labels':e.get('labels',[]),'published':e.get('published',''),'url':e.get('url','')} for e in data.get('items',[]))
   page_token=data.get('nextPageToken','')
   if not page_token:break
  return out[:limit]
 except Exception as exc:
  print(f'Related-article Blogger API unavailable: {exc}')
  return []

def select(current,posts,limit=4):
 base=words(current.get('title','')+' '+' '.join(current.get('labels',[]))+' '+current.get('content','')[:2500]);out=[]
 for p in posts:
  if p.get('id')==current.get('id') or 'News' in p.get('labels',[]):continue
  pw=words(p.get('title','')+' '+' '.join(p.get('labels',[])));shared=base&pw
  label_overlap=len(set(current.get('labels',[]))&set(p.get('labels',[])))
  score=len(shared)*8+label_overlap*12
  # Recency resolves ties and guarantees useful fallback variety.
  out.append((score,p.get('published',''),p))
 out.sort(key=lambda x:(x[0],x[1]),reverse=True)
 return [x[2] for x in out[:limit]]
def _card(p):
 body=p.get('content','');m=re.search(r'<img[^>]+src=["\']([^"\']+)',body,re.I);img=(f'<img src="{html.escape(m.group(1),quote=True)}" alt="Article preview: {html.escape(p.get("title", "Daily Yield article"), quote=True)}" loading="lazy" decoding="async">' if m else '')
 label=next((x for x in p.get('labels',[]) if x not in ('News','Kushal K. Daga')), 'Daily Article')
 return f'<a class="dy-related-card" href="{html.escape(p.get("url", ""),quote=True)}"><span class="dy-related-thumb">{img}</span><span class="dy-related-copy"><small>{html.escape(label)}</small><strong>{html.escape(p.get("title","Daily Yield article"))}</strong><em>Read next →</em></span></a>'
def shelf(current,posts):
 picks=select(current,posts);cards=''.join(_card(p) for p in picks)
 if not cards:return ''
 return START+STYLE+f'''<section class="dy-related" aria-labelledby="dyRelatedTitle"><div class="dy-related-head"><div><b>Continue reading</b><h2 id="dyRelatedTitle">More from Daily Yield</h2></div><span>Swipe, drag or keep watching</span></div><div class="dy-related-viewport"><div class="dy-related-track"><div class="dy-related-group">{cards}</div><div class="dy-related-group" aria-hidden="true">{cards}</div></div></div></section>'''+END

def ensure(content,current,posts):
 content=re.sub(re.escape(START)+r'.*?'+re.escape(END),'',content,flags=re.S)
 block=shelf(current,posts)
 if not block:return content
 # Keep the full publication directory as the final destination when present.
 marker='<!-- DY_PAGE_FAMILY_START -->';i=content.find(marker)
 return content[:i]+block+'\n'+content[i:] if i>=0 else content+'\n'+block
