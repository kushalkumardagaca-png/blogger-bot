# Daily Yield Editorial Outreach — Reviewed Pilot

**Prepared:** 30 September 2026  
**State:** Review only — nothing sent  
**Sender identity:** Kushal K. Daga, Daily Yield (`dailyyield.official@gmail.com`)

## Pilot result

- 9 official-source prospects classified
- 2 purpose-matched messages drafted for review
- 7 contacts blocked from automated drafting because their stated purpose is restricted, human-only, paid, stale or inapplicable
- 0 messages sent
- Gmail OAuth is not configured
- Sending is hard-locked in `send_lock.json`
- Tracking pixels and synthetic pageviews are prohibited

## Review queue

| Recipient | Why contact is permitted | Matched Daily Yield work | State |
|---|---|---|---|
| Financial Times Opinion Desk | Its official page invites original, unpublished opinion proposals | *Emergency Fund Size by Job Type* as portfolio context; proposal offers a new exclusive article | Review required; not sent |
| Money Newsroom | Its official contact page invites topics readers would like covered | *Emergency Fund Size by Job Type* | Review required; not sent |

The drafts are saved as:

- `review_queue/01-ft-opinion.eml`
- `review_queue/02-money-newsroom.eml`

## Contacts intentionally blocked

- **Business Standard:** official editorial address exists, but the page does not expressly invite general unsolicited promotion; human-only.
- **Financial Planning:** accepts guest pitches but prohibits AI-generated copy and requires adviser-focused original work; human-only.
- **Strategic Finance:** accepts queries but requires human-written, experience-based original manuscripts; human-only.
- **FDIC Money Smart:** contact is limited to Money Smart implementation success stories; Daily Yield does not currently have a qualifying case.
- **Outlook India:** the published address is specifically for letters responding to editorial coverage; not a generic outreach route.
- **Finance India:** formal original-research route with a non-refundable submission fee; outside the unpaid editorial scope.
- **The Financial Diet:** its formerly indexed pitch page now returns a 404; the historical email is excluded unless a current invitation is published.

## Controls implemented

1. Official-source URL and verification date for every contact.
2. Purpose classification: `eligible`, `restricted` or `excluded`.
3. Automation classification: `review_required`, `human_only` or `excluded`.
4. Exact article-to-recipient matching and relevance scoring.
5. Duplicate-recipient blocking.
6. Suppression list and prior-interaction blocking.
7. One-follow-up maximum with a minimum 10-day interval reserved for any future sender.
8. Message fingerprints for audit and duplicate prevention.
9. Ordinary UTM-tagged links for genuine aggregate click measurement; no open pixels.
10. No SMTP, Gmail API, network request or send function in the drafting subsystem.

## Activation gate

Before any message can be sent, Daily Yield still needs:

1. Human approval of each draft and its factual claims.
2. A one-time Gmail OAuth consent for the sender account.
3. A separate fail-closed sender implementation with daily limits, reply/suppression updates and bounce handling.
4. A two-message pilot, followed by review of replies and genuine clicks before adding more recipients.

No password, OTP, app password or raw access token should ever be provided.
