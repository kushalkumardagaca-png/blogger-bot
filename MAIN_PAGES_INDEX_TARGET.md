# Main pages — indexing scoreboard

**NOT_STARTED** · checked 2026-10-22T08:35:31+00:00

- Targets: **13** main pages (homepage first)
- In Google's index: **0**
- Reported by Bing: **0**
- Still missing from at least one platform: **13**
- Days to 30 November 2026: **39** · pace needed: **3 page(s) a week**

## Every page

| page | Google | coverage | Bing |
|---|---|---|---|
| `/` | NEUTRAL | Redirect error | unreported |
| `/p/terms-and-conditions.html` | NEUTRAL | Discovered - currently not indexed | unreported |
| `/p/global-snapshot.html` | NEUTRAL | Redirect error | unreported |
| `/p/markets-today.html` | NEUTRAL | Redirect error | unreported |
| `/p/privacy-policy.html` | NEUTRAL | Discovered - currently not indexed | unreported |
| `/p/daily-news.html` | NEUTRAL | Redirect error | unreported |
| `/p/money-atlas_01486068069.html` | NEUTRAL | Redirect error | unreported |
| `/p/for-corporate_01804417406.html` | NEUTRAL | Redirect error | unreported |
| `/p/disclaimer.html` | NEUTRAL | Discovered - currently not indexed | unreported |
| `/p/contact-us_01883938366.html` | NEUTRAL | Redirect error | unreported |
| `/p/calculator_0908148622.html` | NEUTRAL | Redirect error | unreported |
| `/p/article.html` | NEUTRAL | Redirect error | unreported |
| `/p/about-us_02080501126.html` | NEUTRAL | Redirect error | unreported |

## Sitemaps registered on the URL-prefix property

- what the automation may do: `https://dailyyield.blogspot.com/` → **siteOwner**, `sc-domain:dailyyield.blogspot.com` → **siteOwner**
- `sitemap-pages.xml` — submitted 2026-09-25, **last read by Google: 2026-10-20**, errors 0, warnings 0
- `sitemap.xml` — submitted 2026-09-25, **last read by Google: 2026-10-21**, errors 0, warnings 0

## What a phone is told today

Asked as a mobile client - which is how Google fetches and renders now - these URLs do not serve the document; they bounce to Blogger's mobile template, and that template names the URL the crawler came from as its canonical. Every one of these is why 'Redirect error' appears in Search Console, and it is one theme setting, not 453 pages of content work.

- `/p/global-snapshot.html` — a mobile fetch answers **302** and points at `/p/global-snapshot.html?m=1`
- `/p/markets-today.html` — a mobile fetch answers **302** and points at `/p/markets-today.html?m=1`
- `/p/daily-news.html` — a mobile fetch answers **302** and points at `/p/daily-news.html?m=1`
- `/p/for-corporate_01804417406.html` — a mobile fetch answers **302** and points at `/p/for-corporate_01804417406.html?m=1`
- `/p/contact-us_01883938366.html` — a mobile fetch answers **302** and points at `/p/contact-us_01883938366.html?m=1`

## Verdicts the live page does not reproduce

the live page answers 200 with no redirect today, asked as a desktop client and as a mobile one, so the platform's complaint describes an older crawl and what is missing is a fresh one

- `/p/calculator_0908148622.html` — Google said “Redirect error” on 2026-09-25; today it answers None with 0 redirect(s)
- `/p/article.html` — Google said “Redirect error” on 2026-10-02; today it answers None with 0 redirect(s)
- `/p/about-us_02080501126.html` — Google said “Redirect error” on 2026-10-20; today it answers None with 0 redirect(s)

## Only you can do these

1. Bing's URL-submission quota for this property is reported as 0. In Bing Webmaster Tools open Configuration → Basic settings and confirm the site is verified, then check Crawl → IndexNow and the sitemap entry under Configuration → Sitemaps.
1. 5 of the redirect complaints are real right now, and they are all the same thing: Blogger answers Google's smartphone fetch with '302 -> the same URL + ?m=1', and that target declares the parameterless URL as its canonical, which is what Google files as Redirect error. One setting removes all of them: Blogger → Theme → the ⋮ beside Customize → **Mobile devices** → choose the desktop theme (do not serve a separate mobile template). The pages themselves need no change - measured today, the ?m=1 response is byte-identical to the desktop one, so a reader on a phone already receives this theme and only pays an extra hop for it. After the setting is saved, this watch re-probes both identities nightly and the complaint should clear on Google's next crawl of each URL.
1. 3 of those verdicts cannot be reproduced on the live page today, checked as a desktop fetch and as Google's smartphone fetch. Do not delete, rebuild or rename those pages: the redirect that produced the verdict is already gone, and the only thing missing is a crawl. Request indexing is what asks for it.
1. Tap Request indexing for 13 main pages in the Search Console interface. There is no API for it; this is the one step only you can do.

## Request indexing queue (no API exists for this)

1. `https://dailyyield.blogspot.com/` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/terms-and-conditions.html` — NEUTRAL; Discovered - currently not indexed
1. `https://dailyyield.blogspot.com/p/global-snapshot.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/markets-today.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/privacy-policy.html` — NEUTRAL; Discovered - currently not indexed
1. `https://dailyyield.blogspot.com/p/daily-news.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/money-atlas_01486068069.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/for-corporate_01804417406.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/disclaimer.html` — NEUTRAL; Discovered - currently not indexed
1. `https://dailyyield.blogspot.com/p/contact-us_01883938366.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/calculator_0908148622.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/article.html` — NEUTRAL; Redirect error
1. `https://dailyyield.blogspot.com/p/about-us_02080501126.html` — NEUTRAL; Redirect error

Google's indexed-version verdict is the only indexing signal this job trusts. Bing's GetPageStats reports the pages it chose to surface, so an absent page is unreported and never counted as proof of non-indexing. No figure in this file is a promise about ranking, traffic or review.
