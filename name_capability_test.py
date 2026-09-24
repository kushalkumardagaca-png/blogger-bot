#!/usr/bin/env python3
"""Safe test: can the Blogger API update the blog name/description? (no-op with same values)"""
import json, os, urllib.request, urllib.parse
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
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")
tok = token()
blog = call("", tok)
print("current name:", blog.get("name"))
print("current description:", repr(blog.get("description"))[:100])
print("current url:", blog.get("url"))
print("pages:", blog.get("pages", {}).get("totalItems"), "| posts:", blog.get("posts", {}).get("totalItems"))
# no-op update attempt (identical values)
try:
    upd = call("", tok, "PUT", {"kind": "blogger#blog", "id": BLOG_ID,
                                "name": blog.get("name"),
                                "description": blog.get("description") or ""})
    print("UPDATE ENDPOINT: WORKS ->", upd.get("name"))
    print("VERDICT: blog name CAN be changed via API")
except Exception as e:
    print("UPDATE ENDPOINT FAILED:", str(e)[:120])
    print("VERDICT: name change needs the web dashboard (Kushal only)")
