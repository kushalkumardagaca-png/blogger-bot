# Bing URL Submission and Index-Status Automation

- **Status:** PASS
- **Checked:** 2026-10-23T15:36:34.463565+00:00
- **Mode:** authenticated control-plane, zero public Daily Yield requests
- **Synthetic Daily Yield views:** 0

## Current run

- Blogger inventory: **632**
- Submission candidates: **221**
- URLs submitted: **0**
- Quota deferred: **221**
- Performance-monitor records checked: **10**
- Known/crawled by Bing: **0**
- Pending monitoring: **415**
- Removed inventory alerts: **19**

## Guardrails

- API key remains only in the GitHub secret and is never written to evidence.
- No public Daily Yield URL, Bing Live URL fetch or synthetic pageview is created.
- Unchanged URLs are not resubmitted.
- Submission does not guarantee crawling, indexing, ranking or traffic.

## Provider warnings

- sitemap feed not refreshed: /sitemap.xml: SafeApiError; /sitemap-pages.xml: SafeApiError
