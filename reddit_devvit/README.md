# Daily Yield Reddit Publisher

Official Devvit application for `r/DailyYield`.

## Behavior

- Runs at 04:30 UTC (10:00 IST) once daily.
- Reads the public Blogger JSON feed rather than requesting rendered Post pages.
- Selects the newest master article and excludes entries labelled `News` or `Daily News`.
- Stores the last published URL in installation-scoped Redis and skips duplicates.
- Creates a substantive self post with a summary, original link, discussion question and disclosure.
- Runs as Reddit's labelled app account, never votes, sends private messages or posts outside the installation subreddit.
- Provides a moderator-only manual publish action for controlled testing.

## Fetch domain

- `dailyyield.blogspot.com` — official Daily Yield Blogger feed only.

## Installation

`install.sh` is deliberately self-contained so deployment does not depend on public repository access. Download the reviewed installer, upload it to the Cloud Shell home directory, and run:

```bash
cd ~/dailyyield-feed
bash ~/install.sh
npx devvit upload
npx devvit publish
```

Publishing submits an unlisted version for Reddit review, including the declared `dailyyield.blogspot.com` fetch domain. Do not install the reviewed version until Reddit approves it.

After approval:

```bash
cd ~/dailyyield-feed
npx devvit install DailyYield
```

Then use the moderator-only **Daily Yield: publish latest article** subreddit action once for the controlled live test. Redis prevents that same URL from being posted again by the daily scheduler.
