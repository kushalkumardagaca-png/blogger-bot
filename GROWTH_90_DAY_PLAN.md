# The next 90 days, in the order I am running them

Written 20 October 2026. Everything here costs no money. Every number came from this
repository's own measurement files, dated 20 October, and every step below is either already
live in GitHub Actions or has a file in this repository that runs it.

## Where the blog actually stands

| What Google told us | Number |
| --- | --- |
| Pages submitted for indexing | 551 |
| Pages Google has actually indexed | **1** |
| "Discovered - currently not indexed" | 360 |
| Unknown to Google | 180 |
| Redirect errors | 10 |
| Clicks in the last 28 days | **1** |
| Impressions in the last 28 days | 2 |
| Bing daily quota | 0 |
| IndexNow URLs ever accepted | 0 (400 sitting in the queue) |

The blog does not have a traffic problem. It has a *visibility* problem: Google knows the
pages exist and has decided not to index them. So the plan below is not "publish more".

## What is honestly reachable by 31 December 2026

50,000 visits a day from search needs roughly 1.7-2.5 million impressions a day at a normal
2-3% click rate. That is not reachable in 72 days from 2 impressions. What is reachable:

- indexed pages: **1 -> 150-400**
- daily views: **150-1,500**
- 5,000-20,000 a day through 2027, and 50,000 a day realistically in late 2027.

The repository's own control tower already agrees: it sets `TARGET = 10_000_000` with
`DEADLINE = 2027-09-30`, about 14,700 a day on average.

## The steps, in order

1. **Cap publishing by what Google indexes - live now.** `indexing_capacity_gate.py` runs at
   20:35 UTC daily and writes `INDEXING_CAPACITY.md`. Today's verdict is **CONTRACT**: 2 master
   articles and 1 news wire a day. It also ranks which 40 URLs get announced to Google and holds
   back 89 that would only prove the pile is a template farm. `search_indexing.yml` now announces
   that ranked list instead of the whole sitemap, and shouts a visible warning whenever IndexNow
   accepts nothing, which is the failure that used to hide inside a green checkmark.
2. **Cut the duplicate pile - live now, audit every night.** `blogger_duplicate_purge.py` finds
   posts published twice under the same title (`...sold-property-eight-different-ways-to_0586614503.html`
   beside the original). It protects any URL the automation already points at, caps a run at 25,
   and archives every post before deleting it. The scheduled job only counts.
3. **Repair the headlines - live now.** A 46-character slice in the generator had cut every
   master article's title mid-word ("...is Scaling in Cross-B"). The generator is fixed for new
   posts, and `headline_repair.py` reads the full headline back out of each article's own body
   for the ones already live.
4. **Google News Publisher Center and Discover.** Free, and the biggest remaining step-change,
   because a news source gets indexed on trust rather than on a 551-page crawl budget. This one
   needs clicks in your Google accounts, not code.
5. **An owned audience.** The newsletter, then the four social networks already wired.

## What the owner decided on 20 October, and what changed because of it

Two decisions, both recorded here because they override what a measurement alone would do.

**1. The publishing robots keep running at full volume: 10 master articles and 11 news wires a
day.** They are not being cut to the 3 a day the gate suggests. Instead the plan is the hub
strategy: get Google to index the main daily page, and let that page hand out the articles.

That decision exposed a real defect, which is now fixed. Every one of the ~550 stories links to
`/p/daily-news.html` and `/p/article.html`, so a crawler standing on any article should be able
to walk to the hub and then onto today's work. Measured on the live hub: the hub's news data is
refreshed every day and is current, but the hub's HTML has **53 links and not one of them points
at a blog post** - every article link on it is built by JavaScript after the page loads. A robot
that does not run that script sees a dead end, which fits Search Console's 360
"discovered - currently not indexed" URLs exactly. `frozen_hub_refresh.py` now maintains a plain
HTML link index inside the hub (12 newest, real `<a href>`, no styles, no scripts, no new
headings, so the AdSense freeze rules still hold), refreshed by the Content Experience Repair job
at 07:55 IST daily.

**2. The two clean-ups apply themselves daily instead of waiting for a button.** The duplicate
pile removal (25 a day) and the headline repair (40 a day) now run `--apply` on their nightly
schedule; a manual run still defaults to a report. Both archive or back up everything they touch
into this repository before changing anything, and both hold back any URL the operation depends
on.

## What "CONTRACT" still means

The gate's verdict is a measurement, not an order: while Google indexes one page at a time, 21
submissions a day mostly add pages that tell Google this site produces bulk, similar content.
Publishing continues as the owner chose; what the gate controls is *what gets announced to Google
first* - 40 URLs a day in a ranked list, hubs and their stories ahead of the long tail - and it
raises the cap on its own when the indexed count rises.

