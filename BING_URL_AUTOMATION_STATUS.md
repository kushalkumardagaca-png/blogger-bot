# Bing URL Submission and Index-Status Automation

- **Status:** ATTENTION
- **Checked:** 2026-10-24T04:53:45.785538+00:00
- **Mode:** authenticated control-plane, zero public Daily Yield requests
- **Synthetic Daily Yield views:** 0

## Current run

- Blogger inventory: **641**
- Submission candidates: **230**
- URLs submitted: **0**
- Quota deferred: **230**
- Performance-monitor records checked: **10**
- Known/crawled by Bing: **0**
- Pending monitoring: **416**
- Removed inventory alerts: **20**

## Guardrails

- API key remains only in the GitHub secret and is never written to evidence.
- No public Daily Yield URL, Bing Live URL fetch or synthetic pageview is created.
- Unchanged URLs are not resubmitted.
- Submission does not guarantee crawling, indexing, ranking or traffic.

## Errors

- Bing quota API error 400: provider returned a JSON error

## Provider warnings

- Bing page stats API error 400: provider returned a JSON error
