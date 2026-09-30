# Daily Yield Editorial Outreach

This subsystem prepares a small, source-verified editorial pilot. It never sends email.

## Safety rules

- Only addresses explicitly published on an official page are stored.
- Every contact is classified by the purpose stated on that page.
- `eligible + auto_approved` can be sent automatically under the locked daily policy.
- `eligible + review_required` can produce a draft but cannot be automatically reserved.
- `human_only` and `excluded` records cannot produce drafts.
- Existing suppressions, prior sent records and duplicate addresses block drafting.
- One initial approach per recipient; at most one follow-up, never sooner than 10 days.
- Sponsorship, advertising, paid placement and bulk promotion are outside scope.
- Open pixels are prohibited. Click measurement uses ordinary tagged destination links and aggregated server-side analytics, never synthetic traffic.
- Messages use a multipart plain-text and branded HTML presentation. A small inline animated GIF provides progressive enhancement; its complete first frame is the fallback for clients without animation.
- Gmail uses the least-privilege `gmail.send` scope and cannot read or delete inbox content.

## Generate the review packet

```bash
python outreach/editorial_outreach.py validate
python outreach/editorial_outreach.py draft --limit 10
```

Drafts appear under `outreach/review_queue/`; `pilot_manifest.json` records why each prospect was included or blocked. Generated messages are administrative proposals, not publishable articles. Any publication that prohibits AI-generated material remains `human_only` and receives no generated draft.
