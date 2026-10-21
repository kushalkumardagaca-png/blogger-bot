# What is shortlisted, what is parked, and what each one needs

Written 20 October 2026, from your own words in this session. Nothing here is decided for you; this
is the list, with the honest blocker beside each entry.

## You shortlisted these for the upcoming phase

### 1. YouTube Shorts
- **What it would be:** a 45-60 second vertical video per article - the article's own licensed
  photograph, three or four measured numbers as on-screen text, and a spoken narration - published
  to a YouTube channel you own, automatically, alongside the blog post.
- **Why it is the only real road to 50,000 a day inside 2026:** Shorts are handed to strangers by a
  recommendation engine that does not care about your crawl budget. Every other channel we have
  needs Google to index us first.
- **What it needs from you:** a YouTube channel on the blog's Google account, and your yes to
  machine narration (I will not put an AI face or AI visuals on the brand; the picture stays the
  article's own licensed photo).
- **What I build when you say go:** an asset generator (caption, on-screen figures from the
  measured data already in the repo, a 1080×1920 render), a quota-aware uploader, a
  publication-verification guard so a green run is never read as a live video, and a nightly report
  with views and subscribers - the same discipline as the rest of this repository.
- **Honest caution:** Shorts reach is high-variance. It can produce 100 views or 100,000 on the same
  day's work, and no one can promise which.

### 2. Instagram automation
- **Status in the code today:** deliberately absent. The route was removed on your instruction and
  a guard in `audit_publishing_automation.py` fails the build if it comes back.
- **The real blocker, unchanged:** not the blog, not the caption, not the image. The last
  diagnostic read `Error validating access token: The user has not authorized application
  1086897220785233` - the app you were logged into on the Meta side (personal profile) is not the
  app configured for @daily_yield (`162905014900462`). Content publishing only works when the
  Instagram professional account has authorised the *same* app, from the *same* login.
- **What it needs from you, before any code:** in Instagram on the brand account: Settings → Apps
  and websites → Invites (accept the pending app invite), or add the account to the business
  portfolio that owns the app and generate a long-lived token from that app. Nothing in the repo
  can do this, and asking for your password or a 6-digit code is not how this project works.
- **What I would rebuild once that is true:** the publisher, the container/publish flow
  (`media` → poll `FINISHED` → `media_publish`), the single-image rule (the article's own JPEG,
  4:5, under 8 MB, no substituted images), the caption limit of 2200 characters with the alt text,
  and the quota guard that refuses to post when `content_publishing_limit` is exhausted.

## Parked, with the reason written down

### Newsletter / owned audience
You chose **not now**. The mechanism (a weekly digest assembled from the day's editions, plus the
exact 5-minute signup on either Buttondown or follow.it) is understood and would not take long, but
it needs an account that only you can create. Left open on purpose.

### Citable data pages
Built on top of `markets-today` and `global-snapshot`, and deliberately sequenced *after* the front
doors get indexed - adding new pages now spends the resource you asked to concentrate. Plan: one
dated table per topic, a chart made from measured numbers only, the source line and the date on the
page, so other sites can quote it.

### Custom domain (dailyyield.in / .com)
You said no money. Everything the blog lacks - crawl trust, News acceptance, a root file for
IndexNow - would be easier on a domain we control, and none of it is possible on `blogspot.com`
without the free-but-registered domain. Parked, and named in the reports where it blocks us.

### Theme head metadata: `og:image`, `canonical`, `meta description`
Measured on the live pages today: the `<head>` carries **no** `og:` tags, **no** `twitter:` tags,
**no** canonical link and **no** description, while the article body contains 35 images. That is why
Google News and Discover have no picture to show and write their own snippets. The fix is a handful
of lines above `</head>` in Blogger → Theme → Edit HTML, and it is the one thing I am *not* doing
without your explicit go-ahead, because the AdSense review (~3-17 November) is open. Ready when the
review closes:

```
<b:if cond='data:view.isPost'>
  <meta expr:content='data:view.title.escaped' property='og:title'/>
  <meta expr:content='data:view.url.canonical' property='og:url'/>
  <meta expr:content='data:view.url.canonical' name='twitter:url'/>
  <b:if cond='data:view.featuredImage'>
    <meta expr:content='data:view.featuredImage' property='og:image'/>
    <meta expr:content='data:view.featuredImage' name='twitter:image'/>
  </b:if>
</b:if>
```
Backup the current theme before pasting, and check one article page afterwards: the `og:image` line
should appear in the head.

### IndexNow / Bing verification file
`blogspot.com` cannot host `/{key}.txt` at the root, so IndexNow stays half-broken here; Bing
verification by `<meta>` tag works, but that is also a theme edit → same queue as above.

### Publishing cadence
The 21 a day stands, exactly as you decided. The capacity gate now only decides **what is announced
to Google** and **how duplicates are handled** - it no longer proposes cutting output.

## Held by rule, permanently, in this project

- No AI or substituted images (the article's own licensed photograph only).
- No scraping, no private/undocumented APIs, no bulk follow/unfollow, no buying audience.
- No relaxing an index or quality gate to make a number look better.
- Never paste a password, 6-digit code, token or app secret into a chat; secrets go into GitHub
  repository secrets.
- **No social media automation for Tumblr.** It was removed on 21 October 2026 (see
  `TUMBLR_REMOVAL_2026-10-21.md`): no publisher, no authorisation flow, no scheduled job, no route.
  Bringing it back, or adding any network, is the owner's decision, not something to reintroduce.
- **No procedure that depends on a human remembering steps.** If a fix needs someone to paste a value
  into a secret, do it in a specific order, or press Run inside a short window, the fix is wrong and
  must be rebuilt from the repository side. (This is what killed the 20-21 October Tumblr attempt:
  an authorisation code lives 30-60 seconds, while a queued run needs two minutes to arrive.)
- The 42-post rule survives that removal unchanged in weight: 21 articles a day, **two different**
  destinations each, now spread over Facebook, Bluesky and Mastodon at 14 slots per network.
