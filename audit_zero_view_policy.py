#!/usr/bin/env python3
"""Fail closed if scheduled Daily Yield monitoring can create pageviews."""
from pathlib import Path
import json

ROOT = Path(__file__).parent
workflow = (ROOT / ".github/workflows/health_monitor.yml").read_text()
zero = (ROOT / "zero_view_watchdog.py").read_text()
news = (ROOT / "news_pipeline.py").read_text()
related = (ROOT / "related_articles.py").read_text()
rendered = (ROOT / "rendered_site_audit.py").read_text()
theme = (ROOT / "theme/Daily-Yield-Theme-v4-2026-10-01.xml").read_text()
all_workflows = "\n".join(path.read_text() for path in (ROOT / ".github/workflows").glob("*.yml"))
checks = []


def check(name, condition):
    checks.append({"name": name, "status": "PASS" if condition else "FAIL"})


check("Watchdog invokes the zero-view auditor", "python zero_view_watchdog.py" in workflow)
check("Watchdog does not install or launch a browser", "playwright" not in workflow.lower())
check("Watchdog does not invoke legacy live crawlers", "python rendered_site_audit.py" not in workflow and "python comprehensive_site_audit.py" not in workflow and "python health_monitor/health_monitor.py" not in workflow)
check("Zero-view auditor blocks own public host", "ZERO-VIEW POLICY BLOCKED" in zero and "is_own_public_host" in zero)
check("Zero-view auditor blocks redirects to own host", "ZeroViewRedirectHandler" in zero and "SAFE_OPENER" in zero)
check("Zero-view auditor reads content through Blogger API", "www.googleapis.com/blogger/v3" in zero)
check("Rendered compatibility script cannot navigate", "page.goto" not in rendered and "DISABLED_ZERO_VIEW_POLICY" in rendered)
check("News duplicate recovery uses Blogger API", "/posts/bypath?" in news and "live_post_exists(expected_url, token)" in news)
check("News engine does not read Daily Yield public feeds", "dailyyield.blogspot.com/feeds" not in news)
check("Related shelf uses Blogger API", "www.googleapis.com/blogger/v3" in related and "dailyyield.blogspot.com/feeds" not in related)
check("Theme performs no speculative document prefetch", "link.rel='prefetch'" not in theme and "link.as='document'" not in theme and "rel='prerender'" not in theme)
check("Theme does not fetch Older or label-page documents", "className='dy-feed-sentinel'" not in theme and "fetch(href,{credentials:'same-origin'})" not in theme)
check("Theme declares reader-navigation-only policy", "data-dy-navigation-policy','reader-navigation-only'" in theme and "data-dy-synthetic-document-requests','0'" in theme)
check("Theme accelerator is restricted to non-document feed paths", "data-dy-safe-accelerator','feed-and-assets-only'" in theme and "/^\\/feeds\\//.test(u.pathname)" in theme and "DYFeedCache.get('/p/" not in theme and "DYFeedCache.get('/search/" not in theme)
check("No repository workflow installs or launches a headless browser",  not any(term in all_workflows.lower() for term in ("playwright", "puppeteer", "selenium", "headlesschrome", "chromium --headless")))

failed = [item for item in checks if item["status"] == "FAIL"]
report = {"policy": "ZERO_SYNTHETIC_VIEWS", "pass": len(checks) - len(failed), "fail": len(failed), "checks": checks}
Path("ZERO_VIEW_POLICY_AUDIT.json").write_text(json.dumps(report, indent=2))
print(json.dumps({"pass": report["pass"], "fail": report["fail"]}))
if failed:
    for item in failed:
        print("FAIL", item["name"])
    raise SystemExit(1)
