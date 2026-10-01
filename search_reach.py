#!/usr/bin/env python3
"""Zero-view search reach readiness and optional Bing sitemap submission.

No Daily Yield public page is opened. Google state is handled by gsc_rebuild.py;
this companion records crawler policy and uses Bing's official API only when the
repository owner has configured BING_WEBMASTER_API_KEY.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, os, urllib.parse, urllib.request

SITE="https://dailyyield.blogspot.com/"
SITEMAPS=[SITE+"sitemap.xml",SITE+"sitemap-pages.xml"]


def bing_submit(key, sitemap):
    query=urllib.parse.urlencode({"apikey":key,"siteUrl":SITE,"feedUrl":sitemap})
    req=urllib.request.Request("https://ssl.bing.com/webmaster/api.svc/json/SubmitFeed?"+query,method="POST",headers={"User-Agent":"DailyYield-SearchReach/1.0"})
    with urllib.request.urlopen(req,timeout=30) as response:
        return response.status


def main():
    key=os.environ.get("BING_WEBMASTER_API_KEY","").strip()
    rows=[]
    today=datetime.now(timezone.utc).date().isoformat()
    prior={}
    try: prior=json.loads(Path("SEARCH_REACH_STATUS.json").read_text())
    except Exception: pass
    already=bool(key and prior.get("bingConfigured") and str(prior.get("checkedAt","")).startswith(today) and any(x.get("status") in ("SUBMITTED","ALREADY_SUBMITTED") for x in prior.get("sitemaps",[])))
    if key and already:
        rows=[{"sitemap":x,"status":"ALREADY_SUBMITTED","detail":"Daily duplicate submission suppressed."} for x in SITEMAPS]
    elif key:
        for sitemap in SITEMAPS:
            try: rows.append({"sitemap":sitemap,"status":"SUBMITTED","http":bing_submit(key,sitemap)})
            except Exception as exc: rows.append({"sitemap":sitemap,"status":"ERROR","detail":str(exc)[:180]})
    else:
        rows=[{"sitemap":x,"status":"READY","detail":"Set repository secret BING_WEBMASTER_API_KEY after site ownership is verified in Bing Webmaster Tools."} for x in SITEMAPS]
    report={"checkedAt":datetime.now(timezone.utc).isoformat(),"mode":"ZERO_SYNTHETIC_VIEWS","syntheticViews":0,"site":SITE,"bingConfigured":bool(key),"sitemaps":rows,"crawlerPolicy":{"Googlebot":"allow public indexable content","bingbot":"allow public indexable content","ChatGPT-User":"allow discovery","OAI-SearchBot":"allow discovery","GPTBot":"publisher choice; not required for ChatGPT search"},"notes":["Blogger controls robots.txt from its Search preferences; this job never requests the public robots.txt URL.","No crawler permission guarantees indexing, citation, ranking or traffic."]}
    Path("SEARCH_REACH_STATUS.json").write_text(json.dumps(report,indent=2)+"\n")
    lines=["# Daily Yield Search Reach","",f"- Checked: {report['checkedAt']}","- Mode: zero synthetic views","- Google Search Console: managed by `gsc_rebuild.py` and the 12x-daily watchdog",f"- Bing API configured: {'yes' if key else 'no — implementation ready for the owner API key'}","","## Sitemaps"]+[f"- `{x['sitemap']}` — {x['status']}" for x in rows]+["","## Responsible crawler policy","- Permit Googlebot and bingbot on public indexable content.","- Permit ChatGPT-User and OAI-SearchBot for discovery if the publisher wants AI-search visibility.","- Keep private, duplicate, internal-search and administrative URLs out of the index.","- Crawler access does not guarantee reach or citation.",""]
    Path("SEARCH_REACH_STATUS.md").write_text("\n".join(lines))
    print(json.dumps({"bingConfigured":bool(key),"sitemaps":len(rows),"syntheticViews":0}))
    return 1 if any(x['status']=="ERROR" for x in rows) else 0

if __name__=="__main__": raise SystemExit(main())
