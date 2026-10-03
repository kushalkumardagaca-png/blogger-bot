# Bing URL Submission and Index-Status Automation

- **Status:** PASS
- **Checked:** 2026-10-03T14:47:00.848319+00:00
- **Mode:** authenticated control-plane, zero public Daily Yield requests
- **Synthetic Daily Yield views:** 0

## Current run

- Blogger inventory: **256**
- Submission candidates: **159**
- URLs submitted: **0**
- Quota deferred: **159**
- URL-info checks: **10**
- Known/crawled by Bing: **59**
- Pending monitoring: **39**
- Removed inventory alerts: **0**

## Guardrails

- API key remains only in the GitHub secret and is never written to evidence.
- No public Daily Yield URL, Bing Live URL fetch or synthetic pageview is created.
- Unchanged URLs are not resubmitted.
- Submission does not guarantee crawling, indexing, ranking or traffic.
