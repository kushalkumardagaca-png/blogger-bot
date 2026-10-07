#!/usr/bin/env python3
"""Fail closed if Daily Yield automation can create synthetic pageviews."""
from pathlib import Path
import json

ROOT = Path(__file__).parent
WORKFLOW_ROOT = ROOT / ".github/workflows"
workflow_paths = sorted(WORKFLOW_ROOT.glob("*.yml"))
all_workflows = "\n".join(path.read_text() for path in workflow_paths)
news = (ROOT / "news_pipeline.py").read_text()
related = (ROOT / "related_articles.py").read_text()
rendered = (ROOT / "rendered_site_audit.py").read_text()
theme = (ROOT / "theme/Daily-Yield-Theme-v4-2026-10-01.xml").read_text()
checks = []


def check(name, condition):
    checks.append({"name": name, "status": "PASS" if condition else "FAIL"})


check("Scheduled watchdog workflow is removed", not (WORKFLOW_ROOT / "health_monitor.yml").exists())
check("No workflow invokes the removed watchdog", "zero_view_watchdog" not in all_workflows and "WATCHDOG_VERDICT" not in all_workflows and "ZERO_VIEW_WATCHDOG" not in all_workflows)
check("No repository workflow installs or launches a headless browser", not any(term in all_workflows.lower() for term in ("playwright", "puppeteer", "selenium", "headlesschrome", "chromium --headless")))
check("Rendered compatibility script cannot navigate", "page.goto" not in rendered and "DISABLED_ZERO_VIEW_POLICY" in rendered)
check("News duplicate recovery uses Blogger API", "/posts/bypath?" in news and "live_post_exists(expected_url, token)" in news)
check("News engine does not read Daily Yield public feeds", "dailyyield.blogspot.com/feeds" not in news)
check("Related shelf uses Blogger API", "www.googleapis.com/blogger/v3" in related and "dailyyield.blogspot.com/feeds" not in related)
check("Theme performs no speculative document prefetch", "link.rel='prefetch'" not in theme and "link.as='document'" not in theme and "rel='prerender'" not in theme)
check("Theme does not fetch Older or label-page documents", "className='dy-feed-sentinel'" not in theme and "fetch(href,{credentials:'same-origin'})" not in theme)
check("Theme declares reader-navigation-only policy", "data-dy-navigation-policy','reader-navigation-only'" in theme and "data-dy-synthetic-document-requests','0'" in theme)
check("Theme accelerator is restricted to non-document feed paths", "data-dy-safe-accelerator','feed-and-assets-only'" in theme and "/^\\/feeds\\//.test(u.pathname)" in theme and "DYFeedCache.get('/p/" not in theme and "DYFeedCache.get('/search/" not in theme)
check("Real-user metrics are consented non-pageview events", "data-dy-rum-policy','consent-only-non-pageview'" in theme and "gtag('event','dy_web_vitals'" in theme and "gtag('event','page_view'" not in theme)

failed = [item for item in checks if item["status"] == "FAIL"]
report = {"policy": "ZERO_SYNTHETIC_VIEWS", "pass": len(checks) - len(failed), "fail": len(failed), "checks": checks}
Path("ZERO_VIEW_POLICY_AUDIT.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"pass": report["pass"], "fail": report["fail"]}))
if failed:
    for item in failed:
        print("FAIL", item["name"])
    raise SystemExit(1)
