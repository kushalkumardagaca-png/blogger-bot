# Daily Yield Editorial Outreach — Operational Status

**Verified date:** 4 October 2026 (IST)  
**Sender:** Kushal K. Daga, Daily Yield  
**Delivery:** Gmail API with send-only OAuth  
**Daily policy:** Target minimum 10, enforced maximum 20 source-verified initial messages; hourly discovery and recipient-local delivery windows

## Repair outcome

- Root cause: the workflow had only two automatically eligible recipients. Both were contacted on 30 September, so the next three successful workflow runs had an empty eligible queue and silently sent zero messages.
- The registry now contains additional purpose-matched contacts whose official pages expressly invite pitches, contributor inquiries, story ideas or finance submissions.
- The repair run reserved each message in Git before contacting Gmail and then recorded the immutable Gmail message and thread identifiers.
- Ten distinct messages were sent successfully on 4 October 2026: Forbes, Fortune, Business Insider, Investopedia, Inc., Best Finance Resource, Finance Care Online, FinanceBuzz Magazine, Investment Pedia and FinanceProper.
- Continuous discovery now runs hourly, accepts only official same-domain addresses attached to an explicit Daily Yield-relevant invitation, records country and time zone, and delivers during the recipient’s local morning business window.
- The workflow reports a final shortage if the day’s persisted sent count is below ten and blocks any count above twenty. A successful empty run can no longer conceal recipient exhaustion.

## Retained safeguards

- One initial message per address; duplicates and prior interactions are blocked.
- Suppression records are checked before reservation and again before sending.
- Restricted, human-only and excluded recipients cannot be sent automated messages.
- No paid-placement request, reciprocal-link request, tracking pixel or synthetic Daily Yield pageview.
- Gmail permission remains limited to `gmail.send`; inbox reading and deletion are unavailable.
- The 10–20 daily policy never authorizes unverified addresses or repeated daily spam. When verified eligible inventory is exhausted, the workflow reports a shortfall rather than contacting an unsafe recipient.
