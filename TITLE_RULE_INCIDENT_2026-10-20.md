# Title-rule incident — 20 October 2026

Written so this can be read without opening GitHub, because Actions job output is not visible
from outside the repository.

## What happened

Commit `93c9141d` reached `main` at 11:14 UTC (16:44 IST) on 20 October 2026. From then until at
least 14:41 UTC, the master-article publishers (`master_trending_writer.yml`,
`master_evergreen_writer.yml`) failed on every attempt - failing runs at 12:23, 13:01, 13:45, 14:08
and 14:19 UTC - and the master slots at 19:45, 20:45 and 22:15 IST produced nothing. 18 of the
day's 21 slots were live as of the 20:11 IST slot check, which records `live: 18, onTime: 17,
late: 1, pending: 1, upcoming: 2` and `status: ATTENTION`. The wire and edition desks were
unaffected, and every master published before 11:14 UTC is still live.

## Why

A change pushed earlier the same day (commit `93c9141d`) replaced a raw 46-character slice of every
generated master title with a helper that allowed 72 characters, on the reasoning that a longer
headline reads better in a Google result. The reasoning was wrong for this repository: the quality
gate in `master_article_v2.py` refuses any master title outside 12–46 characters

```python
if not 12<=len(title)<=46: errors.append("title must be short and 12–46 characters")
```

so every generated candidate was rejected before publishing, and the publish/notify/route steps of
those runs were skipped. The change looked healthy locally because the generator's own tests only
checked the generator.

Two things are recorded here so the lesson is not lost:

1. a formatting fix in a generator must be checked against every downstream gate, not only its own
   tests;
2. the underlying defect was a headline cut **inside a word** (`"…in Cross-B"`), not the length of
   the cut. Raising the limit was never the fix.

## What was changed (not the gate)

The 12–46 rule still stands. `seo_hygiene.py` was deliberately left untouched — a push that touches
it triggers `bing_seo_repair.yml`, which would rewrite every live title on the blog.

* `master_v3_generator.head_clip(value, limit=46)` now builds a title from whole words only: words
  are added while they fit inside 46 characters, a character slice is never taken, no ellipsis is
  used to hide a truncation, and a headline is not left standing on a preposition or an article
  (`"…is Scaling in"`). A candidate that cannot be clipped inside the rule returns `""` and is
  rejected by the caller, which is what the validator would do anyway.
* `headline_repair.py` (the 01:50 IST nightly job) keeps the same ceiling — `MAX_REPAIRED` is now
  `MAX_TITLE_CHARS = 46`, not 72. A repaired line is taken from the article's own heading and then
  trimmed, word by word, until it fits inside 46 and ends on a complete word. A heading that carries
  a date can never become a master title, so dated headings are excluded. A title with no
  corroborating heading in its own article is left alone, even if it ends mid-word.
* Tests: `test_headline_repair.py` now asserts the 12–46 range explicitly, that a clipped title is
  always a whole-word prefix of the source, and that no title ends on a hanging word.
* `audit_publishing_automation.py` gained a permanent guard: *no generator or repair job may write
  a master title outside the validator's own 12–46 rule*. It also fails if `limit=72` or
  `MAX_REPAIRED = 72` ever returns to either file.

## Proof run in this workspace

* `python -m pytest -q` → **531 passed, 42 subtests passed**
* `python audit_publishing_automation.py` → `{"pass": 196, "fail": 0}`
* `python audit_zero_view_policy.py` → `{"pass": 12, "fail": 0}`
* Read-only drill against the live Blogger feed (19 newest posts, nothing written): 11 titles match
  the old cut signature, **1** has an article heading that corroborates a repair, and that proposal
  is `Payoneer: How Stablecoin is Scaling in Cross-B` (46, mid-word) → `Payoneer: How Stablecoin is
  Scaling` (35). No proposal was outside 12–46. The other 10 were left alone because their own
  articles show no matching heading — that restraint is deliberate: it is the same rule that kept
  this job from manufacturing duplicates.
* Every generated-title sample now passes `master_article_v2.validate()`'s title rule.

## Not caused by this, and not "fixed"

* `content policy: unsupported first-person product or investment experience` — a policy gate
  refusing to publish claims a reader cannot verify. It worked as designed; the gate was not relaxed.
* `Publish exact assigned destination to Tumblr` exited 1 at 13:27 UTC. The coordinated social runs
  at 13:24 UTC and 14:04 UTC both succeeded, so the channel recovered on its own.
* One trending run at 13:13 UTC was cancelled by GitHub's concurrency rule, not by an error.

## The second cause, found after the first fix went live

The title rule was repaired and pushed at 20:22 IST. The next evergreen attempt (20:34 IST) still
failed, on a different line of the same contract, and the run annotation said it plainly:

```
FAIL master-v3 deterministic evidence section failed: 504 words; required 400-490
```

That is the fallback section builder, which runs when the model's own prose cannot be accepted.
It trimmed a section down to 480 words, and *then* attached the source citation to every
paragraph, so the text the validator finally measured was 504 words and the whole article was
rejected for a difference nobody had looked at. Two changes, both pushed at 22:47 IST:

1. the citations are attached **before** the length is measured, so what is counted is what is
   published;
2. the trimmer no longer gives up when a paragraph gets short: it removes sentences from the end
   of the longest paragraph until the window is met, and drops a whole paragraph only while at
   least four remain, which is the minimum the same validator demands.

A paragraph is never half-cut, and a section is never handed over without its citation - both are
asserted in `test_master_v3_excerpt_policy.py`.

## The social side of the same day

`SOCIAL_GUARANTEE_STATUS.json` for 20 October, generated 21:02 IST: 18 articles, **36 posts
expected, 9 articles with both posts, 9 missing**. Per platform: Mastodon 12, Bluesky 9,
Facebook 6, **Tumblr 0**. Tumblr's own tracker shows its last published post was on **18 October
at 15:19 IST**, so the network has been refusing posts for two days and nothing in the repository
said why, because the reason lived in a job log that cannot be read from outside. Twenty-two social
runs failed today with only "Process completed with exit code 1" to show for it.

Fixed in the same push: every channel (Facebook, Bluesky, Tumblr, Mastodon) now retries three
times with back-off, writes the network's own words into `SOCIAL_CREDENTIAL_HEALTH.json` with
anything token-shaped redacted, and persists that file. `social_guard.py` had been refusing to
dispatch to a network recorded as unusable since it was written - it simply could never see the
record. From the next run onward a broken network is stated in the repository and in the run
annotation, and the posts that the 9 missing routes still owe are re-tried by recovery.

What code cannot do: a dead social login has to be re-authorised by the owner. For Tumblr that
means signing in at www.tumblr.com as **dailyyield-official**, then re-running
`python tumblr_oauth_bootstrap.py` and committing the new `tumblr_token.enc`. No password, code or
token should ever be pasted into a chat.

## The 40-minute clock (owner's rule, 20 October 2026 evening)

Preparation was planned at 10-50 minutes and must never run past 40. It had no internal limit at
all: the evergreen job allowed 120 minutes and the trending job 150, so one stalled Commons
download or one hung model call could sit on a slot for most of the day while the slot stayed empty.

Now:

* `time_budget.py` sets one deadline for the whole attempt - research, writing, validation and
  photo selection share it: **30 minutes** (`MASTER_PREPARATION_BUDGET_MINUTES`).
* Every network read in that path asks the clock how long it may wait, so a request can no longer
  block for a minute when the run has ten seconds left. `requests` calls in the writing path that
  carried a fixed 30-90 second wait are now bounded; only the two Google authorisation exchanges
  keep a fixed 30 seconds, because those must succeed for anything else to be possible.
* Section writing runs on 5 workers instead of 3, which is the speed the shorter clock needs:
  ten sections in two waves rather than four.
* The prepare step is capped at **34 minutes** and the job at **40 minutes**.
* An attempt that fails after more than 10 minutes is **not** repeated inside the same run - that
  would only double the wait. The run exits, says why, and the ten-minute recovery cycle starts a
  fresh attempt with a full clock. Attempts that fail quickly (a model that would not start, a git
  race) still get their in-run retry.
* Every outcome records `budgetMinutes`, `elapsedMinutes` and `remainingMinutes` in
  `MASTER_AUTOMATION_STATUS.json`, so "how long did the last attempt take" is answerable from the
  repository without job-log access, and the run prints "Preparation used X of 30 budgeted
  minutes".

The clock never lowers a quality gate: if the article cannot be written, sourced, validated and
illustrated with three licensed photographs inside 30 minutes, the slot is reported as missing and
tried again - it is not filled with something thinner.

