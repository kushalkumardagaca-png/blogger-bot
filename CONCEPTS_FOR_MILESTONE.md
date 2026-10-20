# The five things you asked me to explain, in plain words

Written 20 October 2026. Every number below is measured, and the file that measures it is named,
so you can check it tomorrow without asking me again.

---

## 1. Google News and Discover

**What they are.** Two free places inside Google where articles are *handed to people* instead of
being found by them. Google News is the "News" tab and the News app: a column of headlines for a
topic. Discover is the stream you see on the Google app's home screen and on an Android phone's
empty search page, before anyone types anything.

**What they are used for.** Both are recommendation feeds. They do not wait for a search query;
they decide which publications a reader should see. Getting into them means your article can be
read by someone who has never heard of Daily Yield.

**Why it matters for 50,000 readers a day.** Our search channel is not working yet for a specific,
measured reason: Google has indexed **1 of 551** submitted pages, so 550 pages are invisible to a
search that nobody can run against them. News and Discover treat you differently: Google reviews
*the source* once, and once accepted, it fetches your feed on its own schedule. That is the only
free route left that changes how Google behaves towards the blog rather than asking Google to crawl
more of it.

**Where we stand.** `google_news_readiness.py` now reads the public feed the way their reviewers do,
every night at 02:05 IST. Measured today: **19 feed entries, 12 with a cut-off headline**; of 6
pages inspected, **none has an `og:image`** and **none has a head `meta description`**. Cut
headlines are being repaired nightly by `headline_repair.py` (40 a day, from each article's own
text). The missing `og:image` is a theme-head fact, listed in `ROADMAP_UPCOMING.md`.

**What you have to do.** Nothing for the measurement - it runs by itself. The submission is
item 5 below.

---

## 2. Citable data pages

**What they are.** A small page built around a number people need and quote: today's best fixed
deposit rates, the current small-savings rate table, the latest gold price by city. Same shape every
day, updated, with the source and the date on it.

**What they are used for.** Two things no essay can do. First, other websites link to them -
"according to Daily Yield's rate table" - and links from other sites are the strongest signal Google
has that a site should be trusted. Second, readers come back for the number, which is what turns a
one-time visitor into the "daily audience" you defined.

**Why it matters for 50,000 readers a day.** Your milestone is counted in *people who return*.
Return visits are produced by pages that change and that a reader can bookmark. Articles are read
once.

**Where we stand - and why it is parked.** The material already exists: the site already maintains
`/p/markets-today.html` and `/p/global-snapshot.html`. Building more pages *now* would work against
the decision you made today - index the 13 front doors first. So the build is sequenced right after
those pages are indexed; the pipeline (extract the numbers we already publish, one dated table, one
chart from the article's own licensed photo, no invented figures) is written down in
`ROADMAP_UPCOMING.md`.

**What you have to do.** Nothing yet.

---

## 3. GA4 read permission

**What it is.** GA4 is Google Analytics 4, Google's free visitor counter. **The counter is already
fitted to your blog**: the live homepage carries `gtag('config', 'G-WLEEYTKV12')`, verified from the
site today. Nothing needs installing, and nothing needs touching during the AdSense review.

**What "read permission" is for.** The counter collects numbers, but the robots cannot *read* them.
The Google token saved in this project was authorised for Search Console only, so every attempt
answered `ACCESS_TOKEN_SCOPE_INSUFFICIENT`. Read permission is a small, limited, read-only approval
that lets the automation ask Google "how many people read the site yesterday".

**Why it matters for 50,000 readers a day.** It is the difference between a target and a guess.
Your definition - 50,000 people a day, each opening one or two articles - is a count of *people*,
and the only instrument that measures it is GA4's `engagedSessions`. Until it is readable, the
growth ladder prints `UNMEASURABLE_UNTIL_GA4_IS_READABLE` rather than inventing a figure.

**Where we stand.** `ga4_measurement.py` runs nightly, writes `GA4_MEASUREMENT.md`, and today says
`CREDENTIALS_MISSING` with the remedy inside it. The growth ladder already switches itself to real
pageviews and real readers the moment the token exists - that wiring is built and tested.

**What you have to do (about 4 minutes, once).** Follow `GA4_CONNECT.md`: run
`python get_analytics_token.py`, sign in as the blog's Google account, tick both permissions, and
paste the code it prints into the GitHub secret named `GA4_REFRESH_TOKEN`. Never paste a token into
a chat.

---

## 4. Bing quota

**What it is.** Bing Webmaster Tools is Microsoft's version of Search Console. It gives every
verified site a *daily quota* - a number of addresses it is willing to look at. Our measured number
is `DailyQuota 0`, in `INDEXING_HEALTH.json`. Quota zero means Bing will not accept our submissions.

**What it is used for.** IndexNow is the mechanism that tells Bing (and, through it, Yandex,
Seznam, Naver and others) "this page changed, come now". With a zero quota and an IndexNow key the
blogspot domain cannot host at its root, that channel is shut: measured today, IndexNow has
**queued 400 URLs and had 0 ever accepted**.

**Why it matters - and how much.** Bing is a genuine second opinion on indexing and in India carries
a modest share of finance searches; it is free capacity, not the road to 50,000. The honest weight:
useful, second-tier, and it does not need money - it needs a verification tag in the page head,
which is a theme change and therefore waits for the review to finish.

**Where we stand.** Nothing is being faked: the nightly report already prints
`indexnowLooksBlocked` as a visible warning whenever the queue grows and nothing is accepted. The
verification snippet is written in `ROADMAP_UPCOMING.md` for after ~17 November.

**What you have to do.** Nothing today. After the review: sign in at Bing Webmaster Tools with the
blog's Google account, add the site, paste the verification `<meta>` tag into Blogger → Theme →
Edit HTML, just above `</head>`.

---

## 5. Publisher Center clicks

**What it is.** `publishercenter.google.com` is where a website registers itself with Google as a
news *publication*. You give it a name and logo, you point it at your feed, you map your feed
labels to sections (Markets, Economy, Banking, Companies and IPOs, country desks), and then you
press "request a review".

**What it is used for.** It is the door for item 1. Google News and Discover do not accept a site by
waiting for crawlers to notice it; they accept a *publication* that a human has registered and
reviewed.

**Why it matters for 50,000 readers a day.** It is the only free action that changes Google's
posture from "we will sample 551 unknown pages slowly" to "this is a source; here is its section".
Every other lever we have built decides *what* Google is told about; this decides *who we are* to
Google.

**What to click, exactly (10 minutes, free).**
1. Open `https://publishercenter.google.com` and sign in as `kushalkumardagaca.ca@gmail.com` (the
   account that owns the blog; the one that owns the blog's Search Console property).
2. **Add publication → from a website or feed.**
3. Publication name: **Daily Yield**. Add the logo you already use, and set the site homepage to
   `https://dailyyield.blogspot.com`.
4. When it asks for the feed, use: `https://dailyyield.blogspot.com/feeds/posts/default` - that is
   the same feed the readiness checker reads, and it carries the labels, the byline
   (`Kushal K. Daga`) and the publish date for every edition.
5. Create sections from the labels you already publish: *Markets, Crypto & Commodities*,
   *Economy, Trade & Jobs*, *Banking, Fintech & Personal Money*, *Companies, IPOs & Deals*, and the
   country desks. In each section choose "add page" → **publication feed** → filter by that label.
6. Home page layout: put `Economy, Trade & Jobs` and `Markets, Crypto & Commodities` first - those
   are the two editions that publish every single day, so the front page is never empty.
7. In **Settings → Publisher information**, fill the postal address, phone and the "about" text;
   Google rejects publications that cannot be contacted.
8. Press **Request review**. Then re-check `GOOGLE_NEWS_READINESS.md` a day later - the number of
   listing defects is the only proof that matters.

**One warning so you are not surprised.** Reviewers reject publications whose headlines are cut off
or whose pages carry no image or description. The cut headlines are being repaired nightly already;
the `og:image` and head-description gaps are theme-head items waiting for the review to end. If a
first submission is rejected, that is normal, and it is fixed by the same files, not by a new
account.
