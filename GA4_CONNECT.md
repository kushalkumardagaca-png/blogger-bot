# Turning "views a day" into a real number

Written 20 October 2026, after you chose "install the analytics tag now".

## The good news first: nothing has to be installed

I checked your live homepage while building this. Every page already carries the tag:

```
googletagmanager.com/gtag/js?id=G-WLEEYTKV12
gtag('config', 'G-WLEEYTKV12')
```

So the blog is already counting visitors into a Google Analytics 4 property. There is **no change
to make on the site**, which means the AdSense review (~3-17 November) is not affected at all.
What has been missing is permission for the robots to *read* those numbers. The Google token saved
in this project was created for Search Console only, which is why every previous attempt answered
`ACCESS_TOKEN_SCOPE_INSUFFICIENT`.

## What you do (about 4 minutes, once)

1. On any computer with Python 3, in this repository's folder, run:
   ```
   pip install google-auth-oauthlib
   python get_analytics_token.py
   ```
2. It asks for the same two values as the Search Console setup did (your OAuth Client ID and
   Client Secret). A browser window opens; sign in as the account that owns the blog
   (`kushalkumardagaca.ca@gmail.com`). If Google says "this app isn't verified", it is *your* app:
   **Advanced → Go to (app) → tick both permissions (Search Console and Google Analytics) → Allow.**
3. The screen prints a long code. Put it in GitHub as a **secret**, never in a chat:
   <https://github.com/kushalkumardagaca-png/blogger-bot/settings/secrets/actions> →
   *New repository secret* → name `GA4_REFRESH_TOKEN` → paste → *Add secret*.
4. Optional, saves one API call: on the same page switch to **Variables** → *New repository
   variable* → name `GA4_PROPERTY_ID`, value = the numeric **Property ID** you see in
   Analytics → Admin → *Property settings*. If you skip this, the nightly job finds the property
   itself from `G-WLEEYTKV12`.

## What happens by itself afterwards

At **02:05 IST every night** the Indexing Capacity Gate job now runs three measurements in order:

| Step | File it writes | What it answers |
| --- | --- | --- |
| `audience_channels.py` | `AUDIENCE_CHANNELS.md` | how many followers the networks can prove (today: 12) |
| `ga4_measurement.py` | `GA4_MEASUREMENT.md` | real pageviews, active users and sessions for the last 7 days |
| `growth_ladder.py` | `GROWTH_LADDER.md` | where you stand against the 31 December ladder, rung by rung |

The ladder already switches automatically: it prints `Views are counted as
GA4_PAGEVIEWS_7_DAY_AVERAGE` once the numbers are readable, and until then it says
`SEARCH_CONSOLE_CLICKS_DIVIDED_BY_28`, so you can always see which kind of number you are looking
at. Until step 3 above is done, the job reports `CREDENTIALS_MISSING` with these instructions in
the same file - it never writes a guess.

## Why this matters for the 50,000-a-day question

Two counts of "views" are not the same thing, and until today only one of them could be checked at
all. Your blog's whole measured search history is 1 click in 90 days, while the social networks
have produced 12 followers from 369 posts. With GA4 readable, the number you asked me to be sure
about is measured on every page of the site, from the first night - and the weekly ladder tells
you honestly whether we are on it.
