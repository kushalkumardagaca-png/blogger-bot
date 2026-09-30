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

From the generated `dailyyield-feed` Devvit project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/reddit_devvit/install.sh | bash
npx devvit upload
npx devvit publish
```

After Reddit approves the version and fetch domain:

```bash
npx devvit install DailyYield
```
