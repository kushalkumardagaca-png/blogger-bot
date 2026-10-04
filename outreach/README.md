# Daily Yield Editorial Outreach

This subsystem continuously discovers and verifies editorial opportunities, then sends source-matched proposals through Gmail's send-only API. The daily target is **at least 10 and never more than 20** initial messages, subject to strict recipient eligibility.

## Continuous discovery

- Runs hourly around the clock.
- Uses public search-result RSS only to locate candidate official pages; search snippets are never accepted as evidence.
- Obeys `robots.txt`, uses a declared Daily Yield user agent and limits page requests.
- Accepts a candidate only when the official HTTPS page itself contains Daily Yield-relevant finance topics, an explicit invitation for pitches/contributions/tips/guest proposals, and an organizational email belonging to the same domain.
- Rejects paid placement, editorial fees, backlink schemes, sponsored-post routes and unrelated categories.
- Adds no more than one automatically discovered recipient per organization page.
- Records the official source, verification date, country and IANA time zone.
- Classifies an explicit prohibition on automated/AI material as `human_only`, which blocks automated delivery.

## Delivery safeguards

- Sends only during approximately 08:00–12:59 in the recipient's recorded local time zone.
- Maximum 20 initial messages per IST calendar day; target minimum 10.
- A shortage is reported at the end of the day instead of filling the quota with doubtful contacts.
- Existing suppressions, prior interactions, duplicate addresses and duplicate organizations are blocked.
- One initial approach per recipient; no automatic repeat after Gmail accepts a message.
- Sponsorship, paid placement, link exchanges and bulk promotion are outside scope.
- Open pixels and synthetic pageviews are prohibited.
- Gmail authorization is limited to `gmail.send`; it cannot read or delete inbox content.
- Every message is committed as a reservation before Gmail is contacted, preventing duplicate retries.

## Local validation

```bash
python outreach/editorial_outreach.py validate
python outreach/prospect_discovery.py
python outreach/editorial_outreach.py draft --limit 20
python -m unittest outreach/test_editorial_outreach.py
```

Generated messages are administrative proposals, not completed submissions. Restricted, excluded and `human_only` recipients never receive automated messages.
