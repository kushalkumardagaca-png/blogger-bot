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

## What "CONTRACT" means for your daily numbers

Nothing is blocked or deleted. The automation still writes. The gate says: while Google indexes
one page at a time, publish **2 master articles and 1 news wire per day** instead of the current
volume, and let those be the pages Google is told about first. Publishing five articles a day
into a blog with one indexed page does not add five pages of traffic; it adds five more pages
that tell Google this site produces bulk, near-identical content. When the indexed count rises,
the gate raises the cap on its own - it is arithmetic on Google's numbers, not a mood.
