# Daily Yield Editorial Outreach

This subsystem sends a small, source-verified editorial outreach batch through Gmail's send-only API. The daily target is ten initial messages, but a message is permitted only when the recipient's own official page explicitly invites that kind of editorial contact.

## Safety and delivery rules

- Only addresses explicitly published on an official page are stored.
- Every contact records the permitted purpose and source-check date.
- `eligible + auto_approved` may be reserved and sent under the locked policy.
- `eligible + review_required` can produce a draft but cannot be sent automatically.
- `human_only` and `excluded` records cannot produce drafts.
- Existing suppressions, prior interactions and duplicate addresses block repeat initial messages.
- One initial approach per recipient; at most one follow-up, never sooner than ten days.
- Sponsorship, paid placement, link exchanges and bulk promotion are outside scope.
- Open pixels and synthetic pageviews are prohibited.
- Gmail authorization is limited to `gmail.send`; it cannot read or delete inbox content.
- Every message is committed as a reservation before Gmail is contacted, preventing duplicate retries.
- The workflow fails visibly when fewer than ten messages are recorded as sent for the day; a successful no-op can no longer hide an empty eligible queue.

## Local validation

```bash
python outreach/editorial_outreach.py validate
python outreach/editorial_outreach.py draft --limit 10
python -m unittest outreach/test_editorial_outreach.py
```

Generated drafts are administrative proposals, not publishable articles. A recipient that prohibits automated or AI-generated material remains `human_only` and receives no generated message.
