# Tumblr automation removed — 21 October 2026

## The instruction
"Remove the entire automation for Tumblr. We are not running any social media automation in that
application." Nothing was kept "in case". Every piece of code, secret use and scheduled job that
posted to Tumblr or asked for Tumblr authorisation is gone, including the authorisation listener
that was added the previous day, because a thing nobody may run is a thing that must not exist in
the repository.

## What was deleted
| Removed | What it had done |
|---|---|
| `tumblr_publisher.py` | turned one article link into one Tumblr post |
| `tumblr_oauth_bootstrap.py` | tried to swap an authorisation code for a token, four times an hour |
| `tumblr_attempt_record.py` | recorded each failed swap as evidence |
| `tumblr_oauth_listener.py` | the standing watcher that held the code open while it was swapped (21 hours old) |
| `tumblr_token.enc` | the encrypted token, which had been refused by Tumblr since 19 October |
| `.github/tumblr-oauth-code`, `.github/tumblr-oauth-listener` | the drop files a person had to write into |
| `tumblr_publisher.yml`, `tumblr_oauth_bootstrap.yml`, `tumblr_oauth_listener.yml` | the three scheduled runs |
| `cleanup_duplicate_tumblr.py` + `cleanup_duplicate_tumblr.yml` + its evidence file | the duplicate sweep for that network |
| four Tumblr test files | tests for code that no longer exists |

## Where the publishing weight went — the 42 posts are unchanged
Twenty-one articles a day, **two destinations each**, is the owner's rule and it was not reduced.
The 42 daily article posts are now spread evenly over three live networks:

| Network | article posts per day | share of the 12 daily resource promotions |
|---|---|---|
| Facebook | 14 | 4 |
| Bluesky | 14 | 4 |
| Mastodon | 14 | 4 |

Every article still gets **two different** networks, and across any three consecutive days all 21
pairs are different, so no network carries two posts of the same article. The twelve resource
promotions did not fall from 12 to 9: their times and cron lines are untouched, only the
destination of the three Tumblr windows moved — 10:45 IST to Mastodon, 17:00 IST to Bluesky and
23:15 IST to Facebook, giving every network four of the twelve.

`social_rotation.py` is the single source for that plan; the workflow `plan` job, the guard, the
health probe, the dedupe check and the pre-approval report all read the same three-network list.
The audit now verifies the **values** rather than the prose, so an explanatory comment naming the
retired network cannot accidentally satisfy a check.

## What still works, untouched
The Blogger blog, its articles, the Facebook, Bluesky and Mastodon publishers, the recovery loop,
the quality gates and the daily preparation cadence. On the blog itself the Tumblr profile link in
`social_identity.py` and the footer link in `subscription_experience.py` stay — they are a web
address a reader can visit, not automation; the owner can ask for them to be removed too.
`tumblr_tracker.json` is kept as the history of 151 posts (last one 18 October) and stays readable;
`merge_social_tracker.py` still understands its `tumblr_post_id` field for that reason.

## What changed in what gets reported
`SOCIAL_GUARANTEE_STATUS.json` counted every article as owing two posts, so before this removal it
carried **10 posts missing**, all of them Tumblr routes to a network that no longer accepts the
stored token. From now on the same report counts routes over three live networks, so that
long-standing red line cannot appear again. The guard counts how many posts an article already has
(2 satisfied it), so the re-pairing on the day of removal did not trigger extra posts: an article
that had its two posts was and stays complete.

## What the owner must do — nothing, and one optional tidying
No authorisation, no code, no paste, no Run button. Optionally, and only because they are now
unused, three entries can be deleted in the repository's Settings → Secrets and variables →
Actions: the `TUMBLR_CONSUMER_SECRET` and `TUMBLR_TOKEN_ENCRYPTION_KEY` secrets, the still-unused
`TUMBLR_AUTHORIZATION_CODE` secret from yesterday's attempt, and the `TUMBLR_CONSUMER_KEY` and
`TUMBLR_AUTOMATION_ENABLED` variables. Leaving them costs nothing; nothing reads them any more.

## Proof of this state, as of the commit that removed it
`python -m pytest -q` → **561 passed, 76 subtests passed**.
`python audit_publishing_automation.py` → **{"pass": 201, "fail": 0}**.
`python audit_zero_view_policy.py` → **{"pass": 12, "fail": 0}**.
`grep` over every workflow and module shows no Tumblr step, secret, job or platform value outside
comments that explain this document.
