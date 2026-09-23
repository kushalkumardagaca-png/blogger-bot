#!/usr/bin/env python3
"""Diagnostic: does our existing OAuth token reach Google Search Console?"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

cid = os.environ["BLOGGER_CLIENT_ID"]
csec = os.environ["BLOGGER_CLIENT_SECRET"]
rt = os.environ["BLOGGER_REFRESH_TOKEN"]

# 1. Exchange refresh token -> access token (response reveals granted scopes)
data = urllib.parse.urlencode({
    "client_id": cid, "client_secret": csec,
    "refresh_token": rt, "grant_type": "refresh_token",
}).encode()
req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
with urllib.request.urlopen(req, timeout=30) as r:
    tok = json.load(r)
print("GRANTED SCOPES:", tok.get("scope", "(none)"))
access = tok["access_token"]

# 2. Try the Search Console API: list verified sites
req = urllib.request.Request(
    "https://www.googleapis.com/webmasters/v3/sites",
    headers={"Authorization": "Bearer " + access})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        sites = json.load(r)
    print("\nSEARCH CONSOLE SITES VISIBLE TO THIS TOKEN:")
    for s in sites.get("siteEntry", []):
        print("  -", s.get("siteUrl"), "| permission:", s.get("permissionLevel"))
    blog_site = next((s["siteUrl"] for s in sites.get("siteEntry", [])
                      if "financebycakushal" in s.get("siteUrl", "")), None)
    if blog_site:
        enc = urllib.parse.quote(blog_site, safe="")
        # 3. Sitemap status
        try:
            req2 = urllib.request.Request(
                f"https://www.googleapis.com/webmasters/v3/sites/{enc}/sitemaps",
                headers={"Authorization": "Bearer " + access})
            with urllib.request.urlopen(req2, timeout=30) as r2:
                sm = json.load(r2)
            print("\nSITEMAP STATUS:")
            for m in sm.get("sitemap", []):
                print("  -", m.get("path"), "|", m.get("type"), "|",
                      m.get("lastSubmitted"), "| isPending:", m.get("isPending"),
                      "| errors:", m.get("errors"), "| warnings:", m.get("warnings"))
        except urllib.error.HTTPError as e:
            print("SITEMAP CHECK ERROR:", e.code, e.read().decode()[:300])
        # 4. Search analytics (last 7 days)
        try:
            body = json.dumps({
                "startDate": "2026-09-17", "endDate": "2026-09-23",
                "dimensions": ["page"], "rowLimit": 10,
            }).encode()
            req3 = urllib.request.Request(
                f"https://www.googleapis.com/webmasters/v3/sites/{enc}/searchAnalytics/query",
                data=body, method="POST",
                headers={"Authorization": "Bearer " + access,
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req3, timeout=30) as r3:
                print("\nSEARCH ANALYTICS (last 7 days):")
                print(json.dumps(json.load(r3), indent=2)[:1500])
        except urllib.error.HTTPError as e:
            print("ANALYTICS ERROR:", e.code, e.read().decode()[:300])
    else:
        print("\nBlog property not in visible sites list.")
except urllib.error.HTTPError as e:
    print("\nSEARCH CONSOLE API ERROR:", e.code)
    print(e.read().decode()[:600])
