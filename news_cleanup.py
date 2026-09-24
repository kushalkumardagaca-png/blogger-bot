#!/usr/bin/env python3
"""Remove today's (2026-09-24) premature news articles — news section starts Sept 25."""
import json, os, urllib.request, urllib.parse

BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
CID, CSEC, REF = (os.environ["BLOGGER_CLIENT_ID"], os.environ["BLOGGER_CLIENT_SECRET"],
                  os.environ["BLOGGER_REFRESH_TOKEN"])
TARGETS = ["australia-2026-09-24", "russia-2026-09-24", "south-korea-2026-09-24"]

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
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")

tok = token()
posts = call("/posts?labels=News&maxResults=50", tok)
deleted = []
for p in posts.get("items", []):
    if any(t in p.get("url", "") for t in TARGETS):
        call(f"/posts/{p['id']}", tok, "DELETE")
        deleted.append(p["url"])
        print("deleted:", p["url"])
print(f"\n{len(deleted)} of {len(TARGETS)} target posts deleted")
# verify nothing left
left = [p["url"] for p in call("/posts?labels=News&maxResults=50", tok).get("items", [])
        if any(t in p.get("url", "") for t in TARGETS)]
print("remaining targets:", left if left else "none — clean")
assert len(deleted) == len(TARGETS) and not left, "cleanup incomplete!"
