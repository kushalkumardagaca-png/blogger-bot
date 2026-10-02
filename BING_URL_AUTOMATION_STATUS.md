# Bing URL Submission and Index-Status Automation

- **Status:** ATTENTION
- **Checked:** 2026-10-02T16:51:41.646417+00:00
- **Mode:** authenticated control-plane, zero public Daily Yield requests
- **Synthetic Daily Yield views:** 0

## Current run

- Blogger inventory: **237**
- Submission candidates: **237**
- URLs submitted: **0**
- Quota deferred: **237**
- URL-info checks: **10**
- Known/crawled by Bing: **10**
- Pending monitoring: **20**
- Removed inventory alerts: **0**

## Guardrails

- API key remains only in the GitHub secret and is never written to evidence.
- No public Daily Yield URL, Bing Live URL fetch or synthetic pageview is created.
- Unchanged URLs are not resubmitted.
- Submission does not guarantee crawling, indexing, ranking or traffic.

## Errors

- Bing URL info API error 400: provider returned a JSON error
