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

## Tumblr: the two-day outage, and the cause found the same evening

Delivered per network on 20 October (each article is expected on two of the four networks, and the
count below is the same one the guarantee report uses):

| network | expected | delivered | state |
| --- | --- | --- | --- |
| Mastodon | 12 | 12 | working |
| Bluesky | 9 | 9 | working |
| Facebook | 7 | 7 | working |
| **Tumblr** | **10** | **0** | **broken since 18 October, 15:19 IST** |

So the 10 posts the day owes are *all* Tumblr, and the other three networks are at 100 per cent.
The reason is now written in the run annotation of the failing job:

```
RuntimeError: request failed: https://api.tumblr.com/v2/oauth2/token: 400 Bad Request
{"error":"invalid_grant","error_description":"Invalid refresh token"}
```

**Why a working connection died.** Tumblr rotates the refresh token at every exchange: each time
the publisher swapped it for an access token, Tumblr handed back a *new* refresh token, and the old
one stopped working. The publisher wrote the new bundle to the runner's disk and the commit of that
file was a *later* step - so the first run that refreshed and then failed, or was interrupted before
its persist step ran, left the repository holding a token Tumblr had already consumed. Every attempt
since then presented that dead token, and each attempt failed with `invalid_grant`. The automation
could not heal this by trying harder: retrying a consumed token is exactly what cannot work.

**What was changed (all pushed).**

1. `tumblr_publisher.py` no longer exchanges the refresh token on every run. It reuses the stored
   access token while Tumblr still honours it and exchanges only when that token is close to
   expiry - from roughly twenty exchanges a month to about one every eighteen days, so there is
   almost nothing left to lose.
2. A refused grant is named for what it is and is **never retried**; the message states the only
   repair, and the failure is recorded in `SOCIAL_CREDENTIAL_HEALTH.json`.
3. Every channel now persists its state with `if: !cancelled()`, so a refusal is committed instead
   of evaporating with the job log. This is the same defect that made 22 social failures today
   unreadable, in a second place.
4. `Tumblr OAuth Bootstrap` (the workflow) now records the outcome, prints Tumblr's own words on
   failure, and tolerates being run when nothing changed. The one-time code is read from a
   repository secret - never from a dispatch input, because a public repository shows dispatched
   inputs on the run page.
5. `social_guard.py` had been written to stop sending work to a network recorded as unusable, but
   it could never see the record because of (3); that now functions, so a dead Tumblr stops costing
   runner minutes and each missing post stays counted as missing.
6. Tests: `test_tumblr_token_reuse.py` (reuse, expiry, no-retry-on-invalid-grant, legacy bundle,
   and the shape of the authorisation workflow) and one new publishing-audit check, so the reuse
   rule cannot be quietly undone. `569 passed, 76 subtests`; audits 201/0 and 12/0.

**What only the owner can do to bring Tumblr back (about 3 minutes, no code to write):**

1. In a browser, sign in to Tumblr as **dailyyield-official** and open the app's authorise address
   for the app whose client id is in the repository variable `TUMBLR_CONSUMER_KEY`.
2. After approving, the browser is sent to `https://github.com/kushalkumardagaca-png/blogger-bot?code=...`
   - that page is a GitHub 404 on purpose; copy the whole address from the address bar.
3. Repository → Settings → Secrets and variables → Actions → **New repository secret**, name
   `TUMBLR_AUTHORIZATION_CODE`, paste the copied address as the value, save.
4. Actions → **Tumblr OAuth Bootstrap** → Run workflow. It exchanges the code, checks the account
   really controls `dailyyield-official`, encrypts the new bundle with the key that exists only
   inside Actions, commits `tumblr_token.enc`, and marks the network healthy.
5. Delete that secret's value afterwards (Settings → Secrets → `TUMBLR_AUTHORIZATION_CODE` → update
   to empty or remove), since it is single-use.

Nothing should ever be pasted into chat: not a password, not a code, not a token. Once step 4 has
run, the 10 withheld Tumblr posts are re-tried by the same recovery that runs every ten minutes,
and the guard resumes the route as soon as the health record says the network works.

### 21 October, morning: the repair step itself was broken

The owner followed the re-authorisation steps and the job failed with `invalid_grant` / *"The
authorization code has expired"* - the code had been generated a while before it was saved, and a
Tumblr code is single-use and dies within minutes. Two things came out of that run:

- it proved the new health record works, because `social_credential_health.py` printed
  `{"platform":"tumblr","ok":false,...,"action":"the owner must re-authorise ..."}` on the run page,
  which was invisible before; and
- it exposed a bug in the step I had written the previous evening. Its bash could not be parsed
  (`line 10: unexpected EOF while looking for matching '`) because a human apostrophe sat inside the
  expansion `${reason:-see Tumblr's message above}`, where bash reads quotes as syntax. A step that
  fails to parse never reaches its `::error` annotation, its repair hint or its `exit "$code"`, and
  the commit of the token file was then skipped because it ran only on success.

Fixed: the message is now phrased without quotes and the commit step carries `if: ${{ !cancelled() }}`
so a refused authorisation is recorded too. `test_workflow_shell_syntax.py` hands **every** `run:`
block of **every** workflow to `bash -n` (with `${{ ... }}` replaced by one safe word) and rejects an
apostrophe or quote inside an expansion default; `audit_publishing_automation.py` gained the same
check, so no workflow can again be unable to explain its own failure. That test found the bug in the
repository immediately and reported nothing else wrong across all workflows. `573 passed, 76 subtests`;
audits 202/0 and 12/0.

Remaining step is the owner's alone, and it has a time limit: get a fresh code and re-run
*Tumblr OAuth Bootstrap* in the same sitting, pressing **Update** on the `TUMBLR_AUTHORIZATION_CODE`
secret rather than creating a second one.

### 21 October, 09:47 IST: the second failure, and why a re-run can never fix an expired code

The owner pressed *Tumblr OAuth Bootstrap* again and Tumblr again answered `invalid_grant` / *"The
authorization code has expired"*. The run history proves the cause: attempts #6 and #7 were 2h22m
apart (07:25 and 09:47 IST) and nothing was re-saved between them, so the job was handed the same
spent code twice. An expired code is not a state to wait out; the only way forward is a new approval.

Three changes came out of it, so the situation cannot repeat silently:

- `tumblr_attempt_record.py` keeps a SHA-256 **fingerprint** of the value the job was given, never the
  value itself, and the run page now says *"This is the SAME code as the previous attempt, which
  Tumblr already retired"* instead of repeating a message the owner cannot act on. A reason line that
  is nothing but a code is dropped rather than stored, so no credential can reach the history of a
  public repository.
- the record and the token file are committed even when the exchange fails (`if: !cancelled()`), which
  step 6 of run #7 proved in anger: the refusal reached `SOCIAL_CREDENTIAL_HEALTH.json` at 09:47:56
  with Tumblr's own words in it.
- the job installs its two Python modules only when they are missing, taking about twenty seconds of
  queue time off every attempt, because each second is a chance for the code to age out.

`test_tumblr_attempt_record.py` pins all of it (nine tests, including the privacy of the record). The
suite stands at **582 passed, 76 subtests**, with the publishing audit at 202/0 and the zero-view
policy audit at 12/0.

### 21 October, 10:00 IST: run #8, and the race that no person should have to win

Run #8 (on `bfda7ae`, 23s, failed) showed the new machinery working end to end: Tumblr's own words on
the run page, the attempt recorded (`authorisation attempt recorded: fingerprint only`), the refusal
written to `SOCIAL_CREDENTIAL_HEALTH.json` at 10:00:05, and **Commit encrypted token bundle ✅ success**
so the next attempt can compare. It also showed the honest limit of that design: GitHub fixes a job's
secrets when the job *starts*, so anyone who saves the code after pressing Run is handed the *previous*
value, and a code saved before pressing Run ages out during queue time and the install. Tumblr's
window is minutes; the round trip was not reliably shorter than that.

The repair is structural rather than instructional - **the workflow now waits for the owner instead of
the owner racing the workflow**. `tumblr_oauth_bootstrap.yml` has two jobs: `wait-for-code` polls
GitHub for the moment `TUMBLR_AUTHORIZATION_CODE` is *newer than this run* (default four minutes,
0 skips it), and `authorize` - which starts only after the wait and therefore snapshots the *fresh*
value - does the exchange. Order of operations for the owner is now: press Run, approve on Tumblr,
Update the secret; the wait ends about five seconds later and the exchange follows at once.

`test_tumblr_authorisation_wait.py` runs the real loop against a stubbed `gh`: a fresh save ends the
wait immediately, a stale one keeps polling, a non-numeric or empty input waits the default four
minutes instead of dying on bash arithmetic (run #8 proved how loudly that fails), and a request for 25
minutes is capped at 9 so a queued run can never sit on a dead code. The loop reads only
`updated_at`, never the value, and `if: ${{ !failure() && !cancelled() }}` keeps the exchange alive
when the wait is skipped. Suite: **590 passed, 79 subtests**; audits 202/0 and 12/0.

