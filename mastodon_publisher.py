#!/usr/bin/env python3
"""Independent Daily Yield Mastodon publisher using the official Mastodon API.

Reads inventory only through authenticated Blogger APIs, never requests public
Daily Yield pages, and maintains a separate Mastodon tracker.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from cryptography.fernet import Fernet
from PIL import Image, ImageDraw, ImageFont
from social_creative import build_caption, image_alt, render_social_card

IST=timezone(timedelta(hours=5,minutes=30),name="IST")
BLOG_ID=os.environ.get("BLOGGER_BLOG_ID","8911514070006792465")
INSTANCE=os.environ.get("MASTODON_INSTANCE","https://mastodon.social").rstrip("/")
MASTODON_ACCT="dailyyield@mastodon.social"
TOKEN_FILE=Path("mastodon_token.enc")
TRACKER_PATH=Path("mastodon_tracker.json")
CARD_PATH=Path("/tmp/daily-yield-mastodon-card.jpg")
BRAND_MARK=Path("assets/brand/daily-yield-favicon-512.png")
MAX_AGE_HOURS=48
TIMEOUT=(15,75)
PAGE_WINDOWS=((9*60,10*60+15),(21*60+30,22*60+30))
LOW_VALUE_PAGES=("privacy","terms","disclaimer","contact","correction policy")
PAGE_PRIORITY={"calculator":50,"tool":45,"market":35,"global":30,"news":28,"article":25,"money":24,"learn":20,"resource":20,"start":15,"about":5}
HIGH_IMPACT={"breaking":18,"rates":11,"inflation":11,"recession":12,"budget":10,"tax":10,"economy":9,"market":9,"policy":9,"trade":8,"oil":8,"stocks":8,"invest":8,"debt":8,"gold":7,"jobs":8,"earnings":7}

def required(name:str)->str:
 value=os.environ.get(name,"").strip()
 if not value:raise RuntimeError(f"missing required encrypted secret: {name}")
 return value

def api(method:str,endpoint:str,*,token:str="",retries:int=3,**kwargs):
 if "dailyyield.blogspot.com" in endpoint.lower():raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
 headers=dict(kwargs.pop("headers",{}))
 if token:headers["Authorization"]="Bearer "+token
 last=None
 for attempt in range(retries):
  try:
   r=requests.request(method,endpoint,headers=headers,timeout=TIMEOUT,**kwargs)
   if r.status_code>=500 and attempt+1<retries:time.sleep(2**attempt);continue
   r.raise_for_status();return r.json()
  except (requests.RequestException,ValueError) as exc:
   last=exc
   if attempt+1<retries:time.sleep(2**attempt);continue
   detail=getattr(getattr(exc,"response",None),"text","")[:500]
   raise RuntimeError(f"API request failed: {endpoint}: {exc} {detail}") from exc
 raise RuntimeError(str(last))

def decrypt_token():
 if not TOKEN_FILE.exists():raise RuntimeError("encrypted Mastodon token has not been initialized")
 return json.loads(Fernet(required("MASTODON_TOKEN_KEY").encode()).decrypt(TOKEN_FILE.read_bytes().strip()))

def verify_account(token:str)->dict:
 account=api("GET",INSTANCE+"/api/v1/accounts/verify_credentials",token=token,retries=2)
 if account.get("username","").lower()!="dailyyield" or account.get("url","").rstrip("/")!="https://mastodon.social/@dailyyield":
  raise RuntimeError("Mastodon token does not control the expected @dailyyield account")
 return account

def blogger_token() -> str:
    result = api("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    })
    return result["access_token"]


def clean(fragment: str) -> str:
    fragment = re.sub(r"<script\b[^>]*>.*?</script>", " ", fragment or "", flags=re.I | re.S)
    fragment = re.sub(r"<style\b[^>]*>.*?</style>", " ", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def inventory(token: str) -> tuple[list[dict], list[dict]]:
    auth = {"Authorization": "Bearer " + token}
    posts_data = api("GET", f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts", headers=auth, params={
        "status": "live", "fetchBodies": "true", "maxResults": "50", "orderBy": "published",
        "fields": "items(id,title,url,published,updated,labels,content)",
    })
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    posts = []
    for item in posts_data.get("items", []):
        try:
            published = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if published >= cutoff and item.get("url", "").startswith("https://dailyyield.blogspot.com/"):
            item["kind"] = "post"
            posts.append(item)
    page_data = api("GET", f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages", headers=auth, params={
        "status": "live", "fetchBodies": "true", "maxResults": "50",
        "fields": "items(id,title,url,published,updated,content)",
    })
    pages = []
    for item in page_data.get("items", []):
        title, url = clean(item.get("title", "")), item.get("url", "")
        if title and url.startswith("https://dailyyield.blogspot.com/p/") and not any(x in title.lower() for x in LOW_VALUE_PAGES):
            item.update(kind="page", labels=["Daily Yield Resources"])
            pages.append(item)
    pages.append({
        "id": "homepage", "kind": "page", "title": "Daily Yield: Markets, Money and Better Decisions",
        "url": "https://dailyyield.blogspot.com/", "labels": ["Daily Yield"],
        "content": "Explore financial reporting, practical money tools, market context and global News editions from Daily Yield.",
        "updated": datetime.now(IST).isoformat(),
    })
    return posts, pages


def load_tracker() -> dict:
    if TRACKER_PATH.exists():
        data = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
        data.setdefault("published", [])
        data.setdefault("pending", None)
        return data
    return {"version": 1, "handle": MASTODON_ACCT, "published": [], "pending": None}


def save_tracker(data: dict) -> None:
    data["published"] = data.get("published", [])[-1000:]
    TRACKER_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parsed(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def score(item: dict) -> float:
    now = datetime.now(timezone.utc)
    age = max(0.0, (now - parsed(item["published"])).total_seconds() / 3600)
    labels = [str(x).lower() for x in item.get("labels", [])]
    haystack = (item.get("title", "") + " " + " ".join(labels)).lower()
    value = max(0.0, 50 - age) + (30 if "news" not in labels else 0)
    if parsed(item["published"]).astimezone(IST).date() == now.astimezone(IST).date():
        value += 20
    value += sum(weight for term, weight in HIGH_IMPACT.items() if term in haystack)
    return round(value, 3)


def page_score(item: dict) -> int:
    title = item.get("title", "").lower()
    return sum(weight for term, weight in PAGE_PRIORITY.items() if term in title)


def choose(posts: list[dict], pages: list[dict], tracker: dict, mode: str, recent_urls: set[str] | None = None) -> dict | None:
    history = tracker.get("published", [])
    recent_urls = {x.rstrip("/") for x in (recent_urls or set())}
    if mode == "auto":
        now = datetime.now(IST)
        minute = now.hour * 60 + now.minute
        mode = "page" if any(start <= minute <= end for start, end in PAGE_WINDOWS) else "post"
    if mode == "page":
        last = {x.get("url", "").rstrip("/"): x.get("published_at", "") for x in history if x.get("kind") == "page"}
        available_pages = [x for x in pages if x["url"].rstrip("/") not in recent_urls] or pages
        if available_pages:
            return min(available_pages, key=lambda x: (1 if x["url"].rstrip("/") in last else 0, last.get(x["url"].rstrip("/"), ""), -page_score(x), x.get("title", "")))
    seen_ids = {str(x.get("blogger_id")) for x in history if x.get("kind") == "post"}
    seen_urls = {x.get("url", "").rstrip("/") for x in history if x.get("kind") == "post"}
    eligible = [x for x in posts if str(x.get("id")) not in seen_ids and x.get("url", "").rstrip("/") not in seen_urls and x.get("url", "").rstrip("/") not in recent_urls]
    return max(eligible, key=lambda x: (score(x), parsed(x["published"]))) if eligible else None


def summary(item: dict) -> str:
    content, title = item.get("content", ""), clean(item.get("title", ""))
    for pattern in (r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)', r"<p\b[^>]*>(.*?)</p>"):
        match = re.search(pattern, content, flags=re.I | re.S)
        if match:
            value = clean(match.group(1))
            if len(value) >= 35 and title.lower() not in value.lower():
                return value
    return "Clear context and practical implications from Daily Yield."


def post_text(item:dict)->str:
 return build_caption(item, "mastodon", summary(item), 500)

def richtext_facets(text: str, url: str) -> list[dict]:
    link_start = text.index(url)
    tag = "#DailyYield"
    tag_start = text.rindex(tag)
    return [
        {"index": {"byteStart": len(text[:link_start].encode()), "byteEnd": len(text[:link_start + len(url)].encode())},
         "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]},
        {"index": {"byteStart": len(text[:tag_start].encode()), "byteEnd": len(text[:tag_start + len(tag)].encode())},
         "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "DailyYield"}]},
    ]


def font(size: int, bold: bool = False):
    names = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def generate_card(item: dict) -> Path:
    path = render_social_card(item, "mastodon", CARD_PATH, summary(item), "JPEG")
    if path.stat().st_size > 1_000_000:
        raise RuntimeError("Mastodon card exceeds image upload limit")
    return path

def recent_statuses(token:str,account_id:str)->list[dict]:
 # Public statuses need no timeline-reading scope. Omitting Authorization keeps
 # the publisher least-privileged while still permitting duplicate checks.
 return api("GET",f"{INSTANCE}/api/v1/accounts/{account_id}/statuses",retries=2,params={"limit":"40","exclude_replies":"true","exclude_reblogs":"true"})

def status_urls(status:dict)->set[str]:
 content=status.get("content","")
 urls=set(re.findall(r'href=["\'](https://dailyyield\.blogspot\.com/[^"\']+)',content,re.I))
 urls.update(re.findall(r"https://dailyyield\.blogspot\.com/[^\s<]+",html.unescape(content)))
 return {x.rstrip("/.,)") for x in urls}

def post_text(item:dict)->str:
 return build_caption(item, "mastodon", summary(item), 500)

def reconcile(token:str,account_id:str,url:str)->dict|None:
 try:
  for status in recent_statuses(token,account_id):
   if url.rstrip("/") in status_urls(status):return status
 except Exception as exc:print(f"Mastodon reconciliation read failed: {exc}",file=sys.stderr)
 return None

def upload_media(token:str,item:dict)->str:
 card=generate_card(item);alt=image_alt(item, "mastodon")[:1500]
 with card.open("rb") as fh:
  data=api("POST",INSTANCE+"/api/v2/media",token=token,retries=2,files={"file":(card.name,fh,"image/jpeg")},data={"description":alt})
 media_id=str(data.get("id", ""))
 if not media_id:raise RuntimeError("Mastodon media upload returned no id")
 for _ in range(10):
  current=api("GET",INSTANCE+"/api/v1/media/"+media_id,token=token,retries=2)
  if current.get("url") or current.get("preview_url"):return media_id
  time.sleep(2)
 return media_id

def publish(token:str,account_id:str,item:dict,text:str)->dict:
 existing=reconcile(token,account_id,item["url"])
 if existing:return {**existing,"reconciled":True}
 media_id=upload_media(token,item);key=hashlib.sha256((MASTODON_ACCT+"|"+text).encode()).hexdigest()
 try:
  return api("POST",INSTANCE+"/api/v1/statuses",token=token,retries=1,headers={"Idempotency-Key":key},data={"status":text,"media_ids[]":media_id,"visibility":"public","language":"en"})
 except Exception as exc:
  found=reconcile(token,account_id,item["url"])
  if found:return {**found,"reconciled":True}
  raise RuntimeError(f"Mastodon write failed and no matching status was found: {exc}") from exc

def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--verify-only",action="store_true");p.add_argument("--dry-run",action="store_true");p.add_argument("--content-mode",choices=("auto","post","page"),default="auto");p.add_argument("--target-url",default="",help="Publish this exact API-inventoried Daily Yield destination");a=p.parse_args()
 bundle=decrypt_token();token=bundle["access_token"];account=verify_account(token);account_id=str(account["id"])
 print(f"Mastodon account verified: @{account.get('acct')} ({account_id})")
 if a.verify_only:return 0
 posts,pages=inventory(blogger_token());tracker=load_tracker();recent=recent_statuses(token,account_id);recent_urls=set().union(*(status_urls(x) for x in recent)) if recent else set()
 if a.target_url:
  wanted=a.target_url.rstrip("/");item=next((candidate for candidate in posts+pages if candidate.get("url","").rstrip("/")==wanted),None)
  if item is None:raise RuntimeError(f"Target URL was not found in authenticated Blogger inventory: {a.target_url}")
  if item.get("kind")!=a.content_mode:raise RuntimeError(f"Target kind {item.get('kind')} does not match requested mode {a.content_mode}")
 else:item=choose(posts,pages,tracker,a.content_mode,recent_urls)
 if not item:print("No eligible Mastodon destination; no status created.");return 0
 text=post_text(item);rank=score(item) if item.get("kind")=="post" else page_score(item)
 print(f"Selected {item.get('kind')} score={rank}: {item.get('title')} [{item.get('id')}]")
 if a.dry_run:print(text);return 0
 tracker["pending"]={"kind":item.get("kind"),"blogger_id":item["id"],"url":item["url"],"selected_at":datetime.now(IST).isoformat()};save_tracker(tracker)
 result=publish(token,account_id,item,text);sid=str(result.get("id",""))
 if not sid:raise RuntimeError(f"Mastodon returned no status id: {result}")
 status_url=result.get("url") or f"https://mastodon.social/@dailyyield/{sid}"
 tracker["published"].append({"kind":item.get("kind"),"blogger_id":item["id"],"title":item.get("title"),"url":item["url"],"mastodon_status_id":sid,"mastodon_url":status_url,"score":rank,"published_at":datetime.now(IST).isoformat(),"reconciled":bool(result.get("reconciled"))})
 tracker["pending"]=None;tracker["last_success_at"]=datetime.now(IST).isoformat();tracker["last_mastodon_status_id"]=sid;save_tracker(tracker)
 print(f"Published Mastodon status {sid} for Blogger {item.get('kind')} {item['id']}.");return 0
if __name__=="__main__":
 try:raise SystemExit(main())
 except Exception as exc:print(f"MASTODON_PUBLISHER_ERROR: {exc}",file=sys.stderr);raise
