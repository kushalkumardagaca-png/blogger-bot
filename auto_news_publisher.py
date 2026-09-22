#!/usr/bin/env python3
"""Create and publish the current 24-hour article for one of 20 fixed slots."""
from __future__ import annotations
import html, json, os, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

IST = ZoneInfo("Asia/Kolkata")
TRACKER = Path("daily_news_tracker.json")
# Use a broadly available Gemini model by default. The workflow can override this with GEMINI_MODEL.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
SCOPES = ["https://www.googleapis.com/auth/blogger"]
TOPICS = [
 ("08:00","Global News","global finance markets economy"),("09:00","US","United States finance markets economy"),
 ("10:00","China","China finance markets economy"),("11:00","Germany","Germany finance markets economy"),
 ("12:00","India","India finance markets economy"),("13:00","Japan","Japan finance markets economy"),
 ("14:00","UK","United Kingdom finance markets economy"),("15:00","France","France finance markets economy"),
 ("16:00","Italy","Italy finance markets economy"),("17:00","Russia","Russia finance markets economy"),
 ("18:00","Canada","Canada finance markets economy"),("19:00","Brazil","Brazil finance markets economy"),
 ("20:00","Spain","Spain finance markets economy"),("21:00","Mexico","Mexico finance markets economy"),
 ("22:00","Australia","Australia finance markets economy"),("23:00","South Korea","South Korea finance markets economy"),
 ("00:00","Market and Trading","global markets trading"),("01:00","Economy and Macro Policy","global economy macro policy"),
 ("02:00","Corporate Finance and Industry","global corporate finance industry"),("03:00","Personal Finance","global personal finance"),
]

def need(k):
 v=os.environ.get(k,"").strip()
 if not v: raise RuntimeError(f"Missing GitHub Secret or variable: {k}")
 return v

def slot_now():
 now=datetime.now(IST); key=now.strftime("%H:00")
 for time,label,query in TOPICS:
  if time==key: return time,label,query,now
 raise RuntimeError("Current time is not one of the 20 publishing slots")

def headlines(query):
 q=urllib.parse.quote(f"{query} when:1d")
 url=f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
 req=urllib.request.Request(url,headers={"User-Agent":"FinanceByCAKushal-DailyNews/1.0"})
 with urllib.request.urlopen(req,timeout=25) as r: root=ET.fromstring(r.read())
 out=[]; seen=set()
 for n in root.findall("./channel/item")[:20]:
  title=(n.findtext("title") or "").strip(); link=(n.findtext("link") or "").strip(); date=(n.findtext("pubDate") or "").strip()
  if title and link and title.casefold() not in seen:
   seen.add(title.casefold()); out.append({"title":title,"url":link,"published":date})
 if len(out)<3: raise RuntimeError("Fewer than three current headlines were found")
 return out

def gemini(topic, query, today, items):
 prompt=f'''You are the verified news desk of Finance by CA Kushal. Today is {today} IST.
Write one original, factual finance news article for the fixed topic {topic}. Cover only the previous 24 hours. Use ONLY the supplied headlines and URLs. Never invent facts, figures, quotes, dates, companies, images or sources. Clearly say when a point is reported rather than independently verified.
Return JSON only: title, description (max 155 chars), slug, html, sources. HTML must be body-only and include an opening answer, h2 headings, Key takeaways, What it means, Limitations, 3 FAQs, and a Sources heading with links. No script/style/markdown. The exact author is CA Kushal K. Daga. Avoid investment recommendations.
HEADLINES: {json.dumps(items,ensure_ascii=False)}'''
 payload={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"responseMimeType":"application/json","temperature":0.15}}
 key = need("GEMINI_API_KEY")
 # If the default model is unavailable for this API key, select an available
 # generateContent model automatically.
 model = MODEL
 try:
  with urllib.request.urlopen(f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(key)}", timeout=20) as r:
   available = json.loads(r.read()).get("models", [])
  names = {m.get("name", "").split("/")[-1]: m for m in available if "generateContent" in m.get("supportedGenerationMethods", [])}
  if model not in names:
   choices = [n for n in names if "flash" in n and not "embedding" in n]
   if choices: model = sorted(choices)[0]
 except Exception:
  pass
 endpoint=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={urllib.parse.quote(key)}"
 req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
 with urllib.request.urlopen(req,timeout=90) as r: data=json.loads(r.read())
 article=json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
 for k in ("title","description","slug","html","sources"):
  if k not in article: raise RuntimeError(f"Gemini response missing {k}")
 if "<script" in article["html"].lower(): raise RuntimeError("Unsafe script returned by Gemini")
 return article

def svg(topic,title):
 safe=html.escape(title[:80]); tag=html.escape(topic)
 return f'''<div style="margin:20px 0;max-width:100%;overflow:hidden"><svg viewBox="0 0 1200 420" role="img" aria-label="{safe}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;border-radius:12px"><defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#14213d"/><stop offset="1" stop-color="#2a9d8f"/></linearGradient></defs><rect width="1200" height="420" fill="url(#g)"/><path d="M0 320 C180 230 250 350 420 250 S700 300 850 180 S1050 220 1200 100" fill="none" stroke="#f4a261" stroke-width="9" opacity=".9"/><text x="70" y="95" fill="#f4a261" font-family="Arial" font-size="25" font-weight="700">FINANCE BY CA KUSHAL · {tag}</text><text x="70" y="190" fill="white" font-family="Arial" font-size="38" font-weight="700">{safe}</text><text x="70" y="360" fill="#d8f3dc" font-family="Arial" font-size="20">24-hour finance news briefing</text></svg></div>'''

def tracker():
 return json.loads(TRACKER.read_text()) if TRACKER.exists() else {"published_slots":[],"posts":[]}

def main():
 try:
  time,topic,query,now=slot_now(); today=now.strftime("%Y-%m-%d"); key=f"{today}|{time}"
  t=tracker()
  if key in t.get("published_slots",[]): print(f"Already published: {key}"); return 0
  article=gemini(topic,query,today,headlines(query)); desc=html.escape(article["description"],quote=True)
  body=f'''<meta name="description" content="{desc}"><div style="max-width:840px;margin:auto;font-family:Arial,sans-serif;line-height:1.75;color:#202124">{svg(topic,article["title"])}<h1>{html.escape(article["title"])}</h1><p style="color:#666">By CA Kushal K. Daga · {today} · {topic}</p>{article["html"]}<p style="border-top:1px solid #ddd;padding-top:14px;color:#666;font-size:13px">Disclaimer: For information and education only; not investment, tax or legal advice.</p></div>'''
  c=Credentials(token=None,refresh_token=need("BLOGGER_REFRESH_TOKEN"),token_uri="https://oauth2.googleapis.com/token",client_id=need("BLOGGER_CLIENT_ID"),client_secret=need("BLOGGER_CLIENT_SECRET"),scopes=SCOPES)
  service=build("blogger","v3",credentials=c,cache_discovery=False)
  post=service.posts().insert(blogId=need("BLOGGER_BLOG_ID"),body={"title":article["title"],"content":body,"labels":["Daily News",topic]},isDraft=False).execute()
  t.setdefault("published_slots",[]).append(key); t.setdefault("posts",[]).append({"slot":time,"topic":topic,"date":today,"url":post.get("url","")})
  TRACKER.write_text(json.dumps(t,indent=2,ensure_ascii=False)+"\n")
  print(f"Published {topic} at {time} IST: {post.get('url',post.get('id'))}"); return 0
 except Exception as e: print(f"Daily News failed: {e}",file=sys.stderr); return 1

if __name__=="__main__": raise SystemExit(main())
