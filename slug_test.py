#!/usr/bin/env python3
"""Disposable live test: verify the 3-pass slug trick on Blogger.
1) insert DRAFT titled with the slug string  2) publish  3) rename to real title
Checks the permalink keeps the slug-derived path, then DELETES the test post.
"""
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
                                 data=json.dumps(body).encode() if body else None,
                                 method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")

slug = "slugtest-2026-09-24"
tok = token()
print("1) inserting draft titled:", slug)
d = call("/posts/", tok, "POST", {"kind": "blogger#post", "title": slug,
                                  "content": "<p>Disposable pipeline test. Will be deleted.</p>",
                                  "labels": ["test"]})
pid = d["id"]
print("   draft id:", pid, "| status:", d.get("status"))

print("2) publishing...")
live = call(f"/posts/{pid}/publish", tok, "POST")
url1 = live.get("url", "")
print("   live url:", url1)
ok1 = slug in url1
print("   SLUG IN URL:", "PASS" if ok1 else "FAIL")

print("3) renaming to real title...")
upd = call(f"/posts/{pid}", tok, "PUT", {"kind": "blogger#post", "id": pid,
                                          "title": "Pipeline Slug Test — deleted",
                                          "content": "<p>Disposable pipeline test. Deleted.</p>",
                                          "labels": ["test"]})
url2 = upd.get("url", "")
print("   url after rename:", url2)
ok2 = slug in url2
print("   SLUG RETAINED AFTER RENAME:", "PASS" if ok2 else "FAIL")

print("4) deleting test post...")
try:
    call(f"/posts/{pid}", tok, "DELETE")
    print("   deleted OK")
except Exception as e:
    print("   delete failed:", e, "— trying revert")
    try:
        call(f"/posts/{pid}/revert", tok, "POST")
        print("   reverted to draft (not live)")
    except Exception as e2:
        print("   revert also failed:", e2)

print("\nRESULT:", "PASS — slug trick works" if (ok1 and ok2) else "FAIL — use fallback auto-slug")
sys.exit(0 if (ok1 and ok2) else 1)
