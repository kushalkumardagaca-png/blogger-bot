# Search index policy conformance

**23 PASS · 4 FAIL** across 599 URLs (585 posts, 14 pages) · checked 2026-10-22T05:40:12+00:00

Judged against Bing's Webmaster Guidelines and Google's URL Inspection criteria; the sources are named in the JSON. Nothing in this file edits the site.

| check | verdict | what we found | who can change it |
|---|---|---|---|
| `sitemap-readable:sitemap.xml` | ✅ Bing §2 §3 | HTTP 200 with 585 <loc> entries | platform |
| `sitemap-lists-only-live-urls:sitemap.xml` | ✅ Bing §3 §9 | 0 listed URL(s) not in Blogger's published feed | blogger |
| `sitemap-readable:sitemap-pages.xml` | ✅ Bing §2 §3 | HTTP 200 with 14 <loc> entries | platform |
| `sitemap-lists-only-live-urls:sitemap-pages.xml` | ✅ Bing §3 §9 | 0 listed URL(s) not in Blogger's published feed | blogger |
| `sitemap-freshness-signals` | ✅ Bing §3 (lastmod) | sitemap.xml=yes sitemap-pages.xml=yes - Blogger decides this, not us | platform |
| `no-utility-pages-in-sitemaps` | ❌ Bing §3 §21 §11 (low-value URLs) | 3 machine page, redirect notice or template artifact(s) offered for indexing: context-httpsschema_0119702296.html, context-httpsschema.html, share-market_0718113516.html - 1 exempt because IndexNow reads its key there | blogger |
| `homepage-duplicate-urls-consolidate` | ✅ Bing §6 (canonical consolidation) | 4 of 4 homepage variant(s) answer 200, and all of them declare the same root canonical - the variants that answer 404 are not duplicates, they are the absence of one | platform |
| `titles-descriptive-and-complete` | ✅ Bing §13 §17; Google indexing criteria | 0 under its floor (12 for an article, 4 for a page), 0 over 70, 0 empty, 0 cut mid-phrase (our own title clip does this) | repo |
| `titles-not-shouted-in-caps` | ✅ Bing §13 (titles written for users) | 0 page or post title(s) are entirely upper case | blogger |
| `no-duplicate-titles-across-urls` | ✅ Bing §6 §13 | 0 title(s) shared by more than one URL; worst cluster is none | repo |
| `opening-delivers-the-headline` | ✅ Bing §17 §18 (one topic per URL, key information early); Google: does the page serve the query | 0 of 590 URL(s) open without the headline's own subject words (measured on the first 2 paragraphs of every post with a usable body; 8 were too short to judge and are not counted) | repo |
| `content-not-thin` | ✅ Bing §11 §15 | 0 of 598 content URLs under 300 words of real text (1 machine URL(s) are not judged on writing) | repo |
| `no-near-duplicate-pages` | ❌ Bing §6; abuse: duplicate content across URLs | 40 pair(s) of URLs at or above 0.42 Jaccard shingle overlap (capped scan) | repo |
| `no-keyword-stuffing` | ✅ Bing abuse: keyword stuffing | 0 URL(s) push one word through paragraph after paragraph (4+ times in at least 45% of them), which is the abuse Bing names. A page that mentions its own subject once per paragraph is not flagged: that is what an article about a thing looks like. | repo |
| `images-described-not-decorated` | ❌ Bing §5 §12 (alt text, captions) | 1 URL(s) contain an <img> with no usable alt text | repo |
| `image-file-names-are-descriptive` | ✅ Bing §12 (unique, relevant file names) | 0 of 0 committed image file name(s) repeats across the site () - the slug in the path carries the meaning and the file name carries none, so a new article's photos should be named after its subject instead of photo-1; 598 URL(s) published before 2026-10-22 keep the file names they shipped with, because renaming them would break a live image | repo |
| `image-names-not-hidden-by-the-host` | ✅ Bing §12 | 0 URL(s) reach a crawler as an opaque id because Blogger's image proxy renames the upload - measured, not ours to change, and the alt text checked above carries the description instead | platform |
| `no-double-published-urls` | ❌ Bing §6 §9 (duplicate or redirected URLs) | 8 article(s) were published twice; Blogger numbered the copy's slug, so both copies sit in the sitemap as separate URLs with the same text | repo |
| `rendered-head-completeness` | ✅ Bing §13; Google indexability | 6 URL(s) rendered: 0 without a title, 0 without a meta description | platform |
| `no-blocking-robots-meta` | ✅ Bing §10; Google: indexing allowed? | 0 sampled URL(s) carry noindex/nocache/noarchive/nosnippet | blogger |
| `exactly-one-h1` | ✅ Bing §13 (heading hierarchy) | 0 sampled URL(s) without exactly one <h1>; machine endpoints are exempt, as they are from every other writing rule | platform |
| `content-present-without-scripts` | ✅ Bing §8 (no client-side-only content) | 0 sampled URL(s) whose body text is not in the served HTML | platform |
| `structured-data-matches-the-page` | ✅ Bing §14; Google: enhancement issues | 6 URL(s) sampled, 0 markup problem(s) | repo |
| `robots-allows-both-crawlers` | ✅ Bing §8 §10; Google: crawl allowed? | HTTP 200; neither bot is blocked; declares sitemap | blogger |
| `sitemaps-declared-in-robots` | ✅ Bing §2; Google: referring sitemap | both Blogger sitemaps are named in robots.txt | blogger |
| `updated-pages-are-still-substantial` | ✅ Bing §19 | 0 URL(s) were revised and are still below the thin line | repo |
| `every-url-carries-a-date` | ✅ Bing §3 §19; Google structured data | 599/599 URLs publish a machine-readable date | repo |

## URLs that must change

**no-utility-pages-in-sitemaps** (3 total)
- `https://dailyyield.blogspot.com/2026/09/context-httpsschema_0119702296.html`
- `https://dailyyield.blogspot.com/2026/09/context-httpsschema.html`
- `https://dailyyield.blogspot.com/p/share-market_0718113516.html`

**no-near-duplicate-pages** (40 total)
- `https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18_01443792159.html ≈ https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18.html (0.84)`
- `https://dailyyield.blogspot.com/2026/10/india-finance-news-2026-10-11.html ≈ https://dailyyield.blogspot.com/2026/10/india-finance-news-2026-10-10.html (0.54)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/italy-2026-10-09.html (0.43)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/china-2026-10-09.html (0.42)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/japan-2026-10-09.html (0.44)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/germany-2026-10-09.html (0.43)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/south-korea-2026-10-09.html (0.45)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/australia-2026-10-09.html (0.43)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/brazil-2026-10-08.html (0.45)`
- `https://dailyyield.blogspot.com/2026/10/brazil-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/mexico-2026-10-04.html (0.45)`
- `https://dailyyield.blogspot.com/2026/10/italy-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/spain-2026-10-09.html (0.44)`
- `https://dailyyield.blogspot.com/2026/10/italy-2026-10-09.html ≈ https://dailyyield.blogspot.com/2026/10/china-2026-10-09.html (0.44)`

**images-described-not-decorated** (1 total)
- `https://dailyyield.blogspot.com/2026/09/category-market-and-trading-2026-10-01.html (1 of 9 image(s) undescribed)`

**no-double-published-urls** (8 total)
- `americas-finance-news-2026-10-12: https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-12.html, https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-12_01065225874.html`
- `asia-pacific-finance-news-2026-10-18: https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18.html, https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18_01443792159.html`
- `banking-fintech-personal-money-2026-10: https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01140619784.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01450325346.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01559215980.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01893468813.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_02014784419.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0271866575.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0512615699.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0558819666.html`
- `canada-2026-10-01: https://dailyyield.blogspot.com/2026/10/canada-2026-10-01.html, https://dailyyield.blogspot.com/2026/10/canada-2026-10-01_0922194937.html`
- `category-corporate-finance-and-industry: https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_01348401010.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_01395999271.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_01446121781.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_061642693.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_0629962340.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01660061060.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01760479359.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01971481127.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_02023327578.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_02075404004.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0259378603.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0777916234.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0978730797.html`
- `category-economy-and-macro-policy-2026: https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_01001893817.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_017346688.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_01743986716.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_01962741990.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_0527246697.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_0624211380.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_01679841755.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_01862474054.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_01900447569.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0496477750.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0526097754.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0623923357.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0694295104.html`
- `context-httpsschema: https://dailyyield.blogspot.com/2026/09/context-httpsschema.html, https://dailyyield.blogspot.com/2026/09/context-httpsschema_0119702296.html`
- `us-2026-10-01: https://dailyyield.blogspot.com/2026/10/us-2026-10-01.html, https://dailyyield.blogspot.com/2026/10/us-2026-10-01_01887906195.html`

## What a feed cannot answer

- Cloaking (Bing abuse): needs a comparison of Bingbot-served and user-served HTML, which this repository's no-public-navigation rule forbids automating.
- Page speed and Core Web Vitals: not measurable from a feed; Blogger owns the delivery.
- Originality against the rest of the web: needs the source articles, which our publishing gates already check paragraph by paragraph before a post is allowed out.
- Ad density: AdSense has not placed ads, so the 'made for advertising' test is not yet applicable; it must be re-audited the day ads are approved.

PASS here means the measured condition holds for every URL we can read. It is not a promise of indexing, ranking or grounding eligibility.
