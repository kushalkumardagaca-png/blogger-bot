#!/usr/bin/env python3
"""Independent Daily Yield Tumblr NPF publisher using official Tumblr API v2.

Reads Daily Yield inventory only through authenticated Blogger API calls. It
never requests a public Daily Yield URL and keeps a Tumblr-only tracker.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from cryptography.fernet import Fernet
from PIL import Image, ImageDraw, ImageFont
from social_creative import render_social_card, tumblr_payload

IST=timezone(timedelta(hours=5,minutes=30),name="IST")
BLOG_ID=os.environ.get("BLOGGER_BLOG_ID","8911514070006792465")
TUMBLR_BLOG=os.environ.get("TUMBLR_BLOG_IDENTIFIER","dailyyield-official")
API="https://api.tumblr.com/v2"
TOKEN_FILE=Path("tumblr_token.enc")
TRACKER=Path("tumblr_tracker.json")
CARD=Path("/tmp/daily-yield-tumblr-card.jpg")
BRAND_MARK=Path("assets/brand/daily-yield-favicon-512.png")
TIMEOUT=(15,75); MAX_AGE=48
PAGE_WINDOWS=((12*60,14*60),(20*60,22*60))
LOW_PAGES=("privacy","terms","disclaimer","contact","correction policy")
WEIGHTS={"breaking":18,"rates":11,"inflation":11,"recession":12,"budget":10,"tax":10,"economy":9,"market":9,"policy":9,"trade":8,"oil":8,"stocks":8,"invest":8,"debt":8,"gold":7,"jobs":8,"earnings":7}


def required(name):
 v=os.environ.get(name,"").strip()
 if not v: raise RuntimeError(f"missing required encrypted secret: {name}")
 return v

def clean(s):
 s=re.sub(r"<script\b[^>]*>.*?</script>"," ",s or "",flags=re.I|re.S);s=re.sub(r"<style\b[^>]*>.*?</style>"," ",s,flags=re.I|re.S);s=re.sub(r"<[^>]+>"," ",s)
 return re.sub(r"\s+"," ",html.unescape(s)).strip()
def request(method,url,*,retries=3,**kw):
 if "dailyyield.blogspot.com" in url.lower(): raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
 last=None
 for n in range(retries):
  try:
   r=requests.request(method,url,timeout=TIMEOUT,**kw)
   if r.status_code>=500 and n+1<retries: time.sleep(2**n);continue
   r.raise_for_status();return r
  except requests.RequestException as e:
   last=e
   if n+1<retries: time.sleep(2**n);continue
   detail=getattr(getattr(e,"response",None),"text","")[:400]
   raise RuntimeError(f"request failed: {url}: {e} {detail}") from e
 raise RuntimeError(str(last))

def decrypt_bundle():
 if not TOKEN_FILE.exists(): raise RuntimeError("encrypted Tumblr token bundle has not been initialized")
 return json.loads(Fernet(required("TUMBLR_TOKEN_ENCRYPTION_KEY").encode()).decrypt(TOKEN_FILE.read_bytes().strip()))
def encrypt_bundle(bundle):
 TOKEN_FILE.write_bytes(Fernet(required("TUMBLR_TOKEN_ENCRYPTION_KEY").encode()).encrypt(json.dumps(bundle).encode())+b"\n")
def refresh_access():
 old=decrypt_bundle()
 r=request("POST",API+"/oauth2/token",retries=2,data={"grant_type":"refresh_token","refresh_token":old["refresh_token"],"client_id":required("TUMBLR_CONSUMER_KEY"),"client_secret":required("TUMBLR_CONSUMER_SECRET")})
 new=r.json()
 if not new.get("access_token"): raise RuntimeError("Tumblr refresh returned no access token")
 if not new.get("refresh_token"): new["refresh_token"]=old["refresh_token"]
 if not new.get("scope"): new["scope"]=old.get("scope","")
 encrypt_bundle(new);return new["access_token"]
def auth(token): return {"Authorization":"Bearer "+token}
def verify_account(token):
 data=request("GET",API+"/user/info",headers=auth(token)).json().get("response",{}).get("user",{})
 blogs=data.get("blogs",[]); names={str(x.get("name","")).lower() for x in blogs}; urls={str(x.get("url","")).lower() for x in blogs}
 if TUMBLR_BLOG.lower() not in names and not any(TUMBLR_BLOG.lower() in x for x in urls): raise RuntimeError("token does not control expected Tumblr blog")
 return data

def blogger_token():
 return request("POST","https://oauth2.googleapis.com/token",data={"client_id":required("BLOGGER_CLIENT_ID"),"client_secret":required("BLOGGER_CLIENT_SECRET"),"refresh_token":required("BLOGGER_REFRESH_TOKEN"),"grant_type":"refresh_token"}).json()["access_token"]
def inventory(token):
 headers=auth(token); cutoff=datetime.now(timezone.utc)-timedelta(hours=MAX_AGE)
 data=request("GET",f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts",headers=headers,params={"status":"live","fetchBodies":"true","maxResults":"50","orderBy":"published","fields":"items(id,title,url,published,updated,labels,content)"}).json()
 posts=[]
 for x in data.get("items",[]):
  try: published=datetime.fromisoformat(x["published"].replace("Z","+00:00"))
  except (KeyError,ValueError): continue
  if published>=cutoff and x.get("url","").startswith("https://dailyyield.blogspot.com/"): x["kind"]="post";posts.append(x)
 data=request("GET",f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages",headers=headers,params={"status":"live","fetchBodies":"true","maxResults":"50","fields":"items(id,title,url,published,updated,content)"}).json()
 pages=[]
 for x in data.get("items",[]):
  title=clean(x.get("title",""));url=x.get("url","")
  if title and url.startswith("https://dailyyield.blogspot.com/p/") and not any(t in title.lower() for t in LOW_PAGES): x.update(kind="page",labels=["Daily Yield Resources"]);pages.append(x)
 pages.append({"id":"homepage","kind":"page","title":"Daily Yield: Markets, Money and Better Decisions","url":"https://dailyyield.blogspot.com/","labels":["Daily Yield"],"content":"Financial reporting, practical money tools, market context and global News editions from Daily Yield."})
 return posts,pages

def load_tracker():
 if TRACKER.exists():
  d=json.loads(TRACKER.read_text());d.setdefault("published",[]);d.setdefault("pending",None);return d
 return {"version":1,"blog":TUMBLR_BLOG,"published":[],"pending":None}
def save_tracker(d):
 d["published"]=d.get("published",[])[-1000:];TRACKER.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n")
def parsed(v): return datetime.fromisoformat(v.replace("Z","+00:00"))
def score(x):
 now=datetime.now(timezone.utc);age=max(0,(now-parsed(x["published"])).total_seconds()/3600);labels=[str(v).lower() for v in x.get("labels",[])];hay=(x.get("title","")+" "+" ".join(labels)).lower()
 value=max(0,50-age)+(30 if "news" not in labels else 0)+(20 if parsed(x["published"]).astimezone(IST).date()==now.astimezone(IST).date() else 0)+sum(w for k,w in WEIGHTS.items() if k in hay)
 return round(value,3)
def page_score(x):
 t=x.get("title","").lower();return sum(w for k,w in {"calculator":50,"tool":45,"market":35,"global":30,"news":28,"article":25,"money":24,"learn":20,"resource":20}.items() if k in t)
def recent_posts(token):
 return request("GET",f"{API}/blog/{TUMBLR_BLOG}/posts",headers=auth(token),params={"npf":"true","limit":"20"},retries=2).json().get("response",{}).get("posts",[])
def post_urls(post):
 urls=set()
 if post.get("source_url"): urls.add(str(post["source_url"]).rstrip("/"))
 for block in post.get("content",[]):
  if block.get("type")=="link" and block.get("url"): urls.add(str(block["url"]).rstrip("/"))
  if block.get("type")=="text": urls.update(x.rstrip("/.,)") for x in re.findall(r"https://dailyyield\.blogspot\.com/[^\s<]+",block.get("text","")))
 return urls
def choose(posts,pages,tracker,recent,mode):
 recent_urls=set().union(*(post_urls(x) for x in recent)) if recent else set(); history=tracker.get("published",[])
 if mode=="auto":
  n=datetime.now(IST);m=n.hour*60+n.minute;mode="page" if any(a<=m<=b for a,b in PAGE_WINDOWS) else "post"
 if mode=="page":
  last={x.get("url","").rstrip("/"):x.get("published_at","") for x in history if x.get("kind")=="page"};available=[x for x in pages if x["url"].rstrip("/") not in recent_urls] or pages
  if available:return min(available,key=lambda x:(1 if x["url"].rstrip("/") in last else 0,last.get(x["url"].rstrip("/"),""),-page_score(x),x.get("title","")))
 seen_id={str(x.get("blogger_id")) for x in history if x.get("kind")=="post"};seen_url={x.get("url","").rstrip("/") for x in history if x.get("kind")=="post"}
 eligible=[x for x in posts if str(x.get("id")) not in seen_id and x["url"].rstrip("/") not in seen_url|recent_urls]
 return max(eligible,key=lambda x:(score(x),parsed(x["published"]))) if eligible else None

def summary(x):
 title=clean(x.get("title",""));content=x.get("content","")
 for p in (r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',r"<p\b[^>]*>(.*?)</p>"):
  m=re.search(p,content,flags=re.I|re.S)
  if m:
   s=clean(m.group(1))
   if len(s)>=35 and title.lower() not in s.lower(): return s[:420].rsplit(" ",1)[0]+("…" if len(s)>420 else "")
 return "Clear context, verified sources and practical implications from Daily Yield."
def tags(x):
 t=(x.get("title","")+" "+" ".join(x.get("labels",[]))).lower();out=["Daily Yield","Finance"]
 if any(k in t for k in ("market","stock","invest","fund")):out.append("Markets")
 if any(k in t for k in ("money","saving","tax","debt","personal")):out.append("Personal Finance")
 if any(k in t for k in ("economy","inflation","rates","policy")):out.append("Economy")
 return out[:5]
def font(size,bold=False):
 for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]:
  try:return ImageFont.truetype(p,size)
  except OSError:pass
 return ImageFont.load_default()
def card(x):
 return render_social_card(x, "tumblr", CARD, summary(x), "JPEG")

def payload(x):
 return tumblr_payload(x, summary(x))

def reconcile(token,url):
 for p in recent_posts(token):
  if url.rstrip("/") in post_urls(p):return p
 return None
def publish(token,x):
 existing=reconcile(token,x["url"])
 if existing:return {"id":existing.get("id_string") or str(existing.get("id")),"reconciled":True}
 image=card(x);body=payload(x)
 try:
  with image.open("rb") as fh:r=requests.post(f"{API}/blog/{TUMBLR_BLOG}/posts",headers=auth(token),files={"json":(None,json.dumps(body),"application/json"),"daily-yield-card":(image.name,fh,"image/jpeg")},timeout=TIMEOUT)
  if not r.ok:raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
  data=r.json().get("response",{});post_id=data.get("id_string") or data.get("id")
  if not post_id:raise RuntimeError(f"Tumblr returned no post id: {data}")
  return {"id":str(post_id)}
 except Exception as e:
  found=reconcile(token,x["url"])
  if found:return {"id":found.get("id_string") or str(found.get("id")),"reconciled":True}
  raise RuntimeError(f"Tumblr write failed and no matching post was found: {e}") from e

def main():
 p=argparse.ArgumentParser();p.add_argument("--verify-only",action="store_true");p.add_argument("--dry-run",action="store_true");p.add_argument("--content-mode",choices=("auto","post","page"),default="auto");p.add_argument("--target-url",default="",help="Publish this exact API-inventoried Daily Yield destination");a=p.parse_args()
 token=refresh_access();user=verify_account(token);print(f"Tumblr account verified for {TUMBLR_BLOG} ({user.get('name','account')}).")
 if a.verify_only:return 0
 posts,pages=inventory(blogger_token());tracker=load_tracker();recent=recent_posts(token)
 if a.target_url:
  wanted=a.target_url.rstrip("/");x=next((item for item in posts+pages if item.get("url","").rstrip("/")==wanted),None)
  if x is None:raise RuntimeError(f"Target URL was not found in authenticated Blogger inventory: {a.target_url}")
  if x.get("kind")!=a.content_mode:raise RuntimeError(f"Target kind {x.get('kind')} does not match requested mode {a.content_mode}")
 else:x=choose(posts,pages,tracker,recent,a.content_mode)
 if not x:print("No eligible Tumblr destination; no post created.");return 0
 rank=score(x) if x.get("kind")=="post" else page_score(x);print(f"Selected {x.get('kind')} score={rank}: {x.get('title')} [{x.get('id')}]")
 if a.dry_run:print(json.dumps(payload(x),ensure_ascii=False));return 0
 tracker["pending"]={"kind":x.get("kind"),"blogger_id":x["id"],"url":x["url"],"selected_at":datetime.now(IST).isoformat()};save_tracker(tracker)
 result=publish(token,x);pid=str(result["id"]);tracker["published"].append({"kind":x.get("kind"),"blogger_id":x["id"],"title":x.get("title"),"url":x["url"],"tumblr_post_id":pid,"tumblr_url":f"https://www.tumblr.com/{TUMBLR_BLOG}/{pid}","score":rank,"published_at":datetime.now(IST).isoformat(),"reconciled":bool(result.get("reconciled"))});tracker["pending"]=None;tracker["last_success_at"]=datetime.now(IST).isoformat();tracker["last_tumblr_post_id"]=pid;save_tracker(tracker);print(f"Published Tumblr post {pid} for Blogger {x.get('kind')} {x['id']}.");return 0
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as e:print(f"TUMBLR_PUBLISHER_ERROR: {e}",file=sys.stderr);raise
