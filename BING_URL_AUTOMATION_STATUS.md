# Bing URL Submission and Index-Status Automation

- **Status:** ATTENTION
- **Checked:** 2026-10-23T23:57:40.740023+00:00
- **Mode:** authenticated control-plane, zero public Daily Yield requests
- **Synthetic Daily Yield views:** 0

## Current run

- Blogger inventory: **636**
- Submission candidates: **225**
- URLs submitted: **0**
- Quota deferred: **225**
- Performance-monitor records checked: **0**
- Known/crawled by Bing: **0**
- Pending monitoring: **411**
- Removed inventory alerts: **20**

## Guardrails

- API key remains only in the GitHub secret and is never written to evidence.
- No public Daily Yield URL, Bing Live URL fetch or synthetic pageview is created.
- Unchanged URLs are not resubmitted.
- Submission does not guarantee crawling, indexing, ranking or traffic.

## Errors

- Bing quota API error 400: provider returned a JSON error
