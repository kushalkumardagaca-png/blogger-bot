#!/usr/bin/env python3
"""Add hero photos to the Daily News hub country cards (one-off page patch)."""
import json, os, sys, urllib.request, urllib.parse

BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
CID, CSEC, REF = (os.environ["BLOGGER_CLIENT_ID"], os.environ["BLOGGER_CLIENT_SECRET"],
                  os.environ["BLOGGER_REFRESH_TOKEN"])

def token():
    data = urllib.parse.urlencode({"client_id": CID, "client_secret": CSEC,
                                   "refresh_token": REF, "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=20) as r:
        return json.load(r)["access_token"]

def call(path, tok, method="GET", body=None):
    req = urllib.request.Request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}{path}",
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body else None, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")

tok = token()
pages = call("/pages?maxResults=50", tok)
target = None
for p in pages.get("items", []):
    if "daily-news" in p.get("url", ""):
        target = p
        break
if not target:
    print("PAGE NOT FOUND"); sys.exit(1)
print("page:", target["url"], "| title:", target["title"])

page = call(f"/pages/{target['id']}", tok)
content = page["content"]
orig_len = len(content)

# ---- surgical replacements (each must appear exactly once) ----
REPL = [
 # 1. parseFeed: extract first <img> from post content
 ("""out.push({title:title,labels:cats,flag:flag,published:published,link:link});""",
  """var img='';var im=/<img[^>]+src=\\"([^\\"]+)\\"/.exec((e.content&&e.content.$t)||'');if(im)img=im[1]; out.push({title:title,labels:cats,flag:flag,published:published,link:link,img:img});"""),
 # 2. fillTrack: build image HTML for the card
 ("""var h=hoursAgo(it.published);var badge=""",
  """var h=hoursAgo(it.published);var imgHTML=(it.img?'<div class=\\"kn-cimg\\"><img src=\\"'+it.img+'\\" alt=\\"\\" loading=\\"lazy\\" decoding=\\"async\\"/></div>':'');var badge="""),
 # 3. fillTrack: render image at top of card
 ("""'<div class=\\"kn-cmeta\\">'""",
  """imgHTML+'<div class=\\"kn-cmeta\\">'"""),
]
for old, new in REPL:
    n = content.count(old)
    if n != 1:
        print(f"ABORT: pattern found {n} times (need exactly 1): {old[:70]}...")
        sys.exit(1)
    content = content.replace(old, new)

# 4. CSS for the image (append style block at end of content)
css = ('<style>.kn-cimg{width:100%;aspect-ratio:16/9;overflow:hidden;border-radius:10px;'
       'background:#F1E5D3;flex:0 0 auto}.kn-cimg img{width:100%;height:100%;object-fit:cover;'
       'display:block}</style>')
if ".kn-cimg{" not in content:  # only add once
    content = content + "\n" + css

call(f"/pages/{target['id']}", tok, "PUT", {
    "kind": "blogger#page", "id": target["id"], "title": page["title"],
    "content": content})
print(f"PATCHED: {orig_len} -> {len(content)} chars")
print("verify markers:", content.count("kn-cimg"), "kn-cimg refs |",
      "img:img" in content, "img field |", "imgHTML" in content, "imgHTML")
