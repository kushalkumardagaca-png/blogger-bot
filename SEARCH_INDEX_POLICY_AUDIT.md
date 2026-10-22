# Search index policy conformance

**14 PASS · 13 FAIL** across 597 URLs (583 posts, 14 pages) · checked 2026-10-22T03:37:18+00:00

Judged against Bing's Webmaster Guidelines and Google's URL Inspection criteria; the sources are named in the JSON. Nothing in this file edits the site.

| check | verdict | what we found | who can change it |
|---|---|---|---|
| `sitemap-readable:sitemap.xml` | ✅ Bing §2 §3 | HTTP 200 with 583 <loc> entries | platform |
| `sitemap-lists-only-live-urls:sitemap.xml` | ✅ Bing §3 §9 | 0 listed URL(s) not in Blogger's published feed | blogger |
| `sitemap-readable:sitemap-pages.xml` | ✅ Bing §2 §3 | HTTP 200 with 14 <loc> entries | platform |
| `sitemap-lists-only-live-urls:sitemap-pages.xml` | ✅ Bing §3 §9 | 0 listed URL(s) not in Blogger's published feed | blogger |
| `sitemap-freshness-signals` | ✅ Bing §3 (lastmod) | sitemap.xml=yes sitemap-pages.xml=yes - Blogger decides this, not us | platform |
| `no-utility-pages-in-sitemaps` | ❌ Bing §3 §21 §11 (low-value URLs) | 4 machine page, redirect notice or template artifact(s) offered for indexing: context-httpsschema_0119702296.html, context-httpsschema.html, indexnow-key.html, share-market_0718113516.html | blogger |
| `homepage-duplicate-urls-consolidate` | ✅ Bing §6 (canonical consolidation) | 1 of 4 homepage variant(s) answer 200, and all of them declare the same root canonical - the variants that answer 404 are not duplicates, they are the absence of one | platform |
| `titles-descriptive-and-complete` | ❌ Bing §13 §17; Google indexing criteria | 6 under 12 chars, 40 over 70, 0 empty, 6 cut mid-phrase (our own title clip does this) | repo |
| `titles-not-shouted-in-caps` | ❌ Bing §13 (titles written for users) | 14 page or post title(s) are entirely upper case | blogger |
| `no-duplicate-titles-across-urls` | ❌ Bing §6 §13 | 4 title(s) shared by more than one URL; worst cluster is 6 URLs on one title | repo |
| `opening-delivers-the-headline` | ✅ Bing §17 §18 (one topic per URL, key information early); Google: does the page serve the query | 0 of 588 URL(s) open without the headline's own subject words (measured on the first 2 paragraphs of every post with a usable body; 9 were too short to judge and are not counted) | repo |
| `content-not-thin` | ❌ Bing §11 §15 | 1 of 597 URLs under 300 words of real text | repo |
| `no-near-duplicate-pages` | ❌ Bing §6; abuse: duplicate content across URLs | 40 pair(s) of URLs at or above 0.42 Jaccard shingle overlap (capped scan) | repo |
| `no-keyword-stuffing` | ❌ Bing abuse: artificially engineered language | 1 URL(s) where one content word exceeds 5% of the page | repo |
| `images-described-not-decorated` | ❌ Bing §5 §12 (alt text, captions) | 1 URL(s) contain an <img> with no usable alt text | repo |
| `image-file-names-are-descriptive` | ❌ Bing §12 (unique, relevant file names) | 3 of 31 committed image file name(s) repeats across the site (photo-1.jpg on 473 URLs, photo-2.jpg on 149 URLs) - the slug in the path carries the meaning and the file name carries none, so a new article's photos should be named after its subject instead of photo-1 | repo |
| `image-names-not-hidden-by-the-host` | ✅ Bing §12 | 0 URL(s) reach a crawler as an opaque id because Blogger's image proxy renames the upload - measured, not ours to change, and the alt text checked above carries the description instead | platform |
| `no-double-published-urls` | ❌ Bing §6 §9 (duplicate or redirected URLs) | 8 article(s) were published twice; Blogger numbered the copy's slug, so both copies sit in the sitemap as separate URLs with the same text | repo |
| `rendered-head-completeness` | ✅ Bing §13; Google indexability | 5 URL(s) rendered: 0 without a title, 0 without a meta description, 1 did not answer 200 and were not judged | platform |
| `no-blocking-robots-meta` | ✅ Bing §10; Google: indexing allowed? | 0 sampled URL(s) carry noindex/nocache/noarchive/nosnippet, 1 did not answer 200 and were not judged | blogger |
| `exactly-one-h1` | ❌ Bing §13 (heading hierarchy) | 1 sampled URL(s) without exactly one <h1>, 1 did not answer 200 and were not judged | platform |
| `content-present-without-scripts` | ✅ Bing §8 (no client-side-only content) | 0 sampled URL(s) whose body text is not in the served HTML, 1 did not answer 200 and were not judged | platform |
| `structured-data-matches-the-page` | ✅ Bing §14; Google: enhancement issues | 5 URL(s) sampled, 0 markup problem(s), 1 did not answer 200 and were not judged | repo |
| `robots-allows-both-crawlers` | ❌ Bing §8 §10; Google: crawl allowed? | HTTP 404; neither bot is blocked; declares no sitemap | blogger |
| `sitemaps-declared-in-robots` | ❌ Bing §2; Google: referring sitemap | robots.txt does not name both sitemaps, so a crawler that finds robots.txt may never reach the pages sitemap (Google reports 'no referring sitemap') | blogger |
| `updated-pages-are-still-substantial` | ✅ Bing §19 | 0 URL(s) were revised and are still below the thin line | repo |
| `every-url-carries-a-date` | ✅ Bing §3 §19; Google structured data | 597/597 URLs publish a machine-readable date | repo |

## URLs that must change

**no-utility-pages-in-sitemaps** (4 total)
- `https://dailyyield.blogspot.com/2026/09/context-httpsschema_0119702296.html`
- `https://dailyyield.blogspot.com/2026/09/context-httpsschema.html`
- `https://dailyyield.blogspot.com/p/indexnow-key.html`
- `https://dailyyield.blogspot.com/p/share-market_0718113516.html`

**titles-descriptive-and-complete** (52 total)
- `https://dailyyield.blogspot.com/2026/10/student-loan-interest-rates-federal.html`
- `https://dailyyield.blogspot.com/2026/10/billionaire-mukesh-ambani-launches.html`
- `https://dailyyield.blogspot.com/2026/10/cost-of-living-protests-hit-belgium.html`
- `https://dailyyield.blogspot.com/2026/10/proposals-to-close-minneapolis-schools.html`
- `https://dailyyield.blogspot.com/2026/10/inside-india-newsletter-billionaire.html`
- `https://dailyyield.blogspot.com/2026/10/how-to-evaluate-healthcare-ai.html`
- `https://dailyyield.blogspot.com/p/daily-news.html`
- `https://dailyyield.blogspot.com/p/money-atlas_01486068069.html`
- `https://dailyyield.blogspot.com/p/disclaimer.html`
- `https://dailyyield.blogspot.com/p/contact-us_01883938366.html`
- `https://dailyyield.blogspot.com/p/calculator_0908148622.html`
- `https://dailyyield.blogspot.com/p/about-us_02080501126.html`

**titles-not-shouted-in-caps** (14 total)
- `https://dailyyield.blogspot.com/2026/10/eurusd-11253-eurgbp-08438-eurjpy-177.html`
- `https://dailyyield.blogspot.com/p/terms-and-conditions.html`
- `https://dailyyield.blogspot.com/p/global-snapshot.html`
- `https://dailyyield.blogspot.com/p/markets-today.html`
- `https://dailyyield.blogspot.com/p/share-market_0718113516.html`
- `https://dailyyield.blogspot.com/p/privacy-policy.html`
- `https://dailyyield.blogspot.com/p/daily-news.html`
- `https://dailyyield.blogspot.com/p/money-atlas_01486068069.html`
- `https://dailyyield.blogspot.com/p/for-corporate_01804417406.html`
- `https://dailyyield.blogspot.com/p/disclaimer.html`
- `https://dailyyield.blogspot.com/p/contact-us_01883938366.html`
- `https://dailyyield.blogspot.com/p/calculator_0908148622.html`

**no-duplicate-titles-across-urls** (4 total)
- `banking  personal money news (6 urls)`
- `corporate finance and industry news (6 urls)`
- `asiapacific finance news  18 october 2026 (2 urls)`
- `americas finance news  11 october 2026 (2 urls)`

**content-not-thin** (1 total)
- `https://dailyyield.blogspot.com/p/indexnow-key.html (257w)`

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

**no-keyword-stuffing** (1 total)
- `https://dailyyield.blogspot.com/p/article.html (article 220/3619)`

**images-described-not-decorated** (1 total)
- `https://dailyyield.blogspot.com/2026/09/category-market-and-trading-2026-10-01.html (1 of 9 image(s) undescribed)`

**image-file-names-are-descriptive** (3 total)
- `photo-1.jpg`
- `photo-2.jpg`
- `photo-3.jpg`

**no-double-published-urls** (8 total)
- `americas-finance-news-2026-10-12: https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-12.html, https://dailyyield.blogspot.com/2026/10/americas-finance-news-2026-10-12_01065225874.html`
- `asia-pacific-finance-news-2026-10-18: https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18.html, https://dailyyield.blogspot.com/2026/10/asia-pacific-finance-news-2026-10-18_01443792159.html`
- `banking-fintech-personal-money-2026-10: https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01140619784.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01450325346.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01559215980.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_01893468813.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_02014784419.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0271866575.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0512615699.html, https://dailyyield.blogspot.com/2026/10/banking-fintech-personal-money-2026-10_0558819666.html`
- `canada-2026-10-01: https://dailyyield.blogspot.com/2026/10/canada-2026-10-01.html, https://dailyyield.blogspot.com/2026/10/canada-2026-10-01_0922194937.html`
- `category-corporate-finance-and-industry: https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_01348401010.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_01395999271.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_01446121781.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_061642693.html, https://dailyyield.blogspot.com/2026/09/category-corporate-finance-and-industry_0629962340.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01660061060.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01760479359.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_01971481127.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_02023327578.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_02075404004.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0259378603.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0777916234.html, https://dailyyield.blogspot.com/2026/10/category-corporate-finance-and-industry_0978730797.html`
- `category-economy-and-macro-policy-2026: https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_01001893817.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_017346688.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_01743986716.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_01962741990.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_0527246697.html, https://dailyyield.blogspot.com/2026/09/category-economy-and-macro-policy-2026_0624211380.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_01679841755.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_01862474054.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_01900447569.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0496477750.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0526097754.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0623923357.html, https://dailyyield.blogspot.com/2026/10/category-economy-and-macro-policy-2026_0694295104.html`
- `context-httpsschema: https://dailyyield.blogspot.com/2026/09/context-httpsschema.html, https://dailyyield.blogspot.com/2026/09/context-httpsschema_0119702296.html`
- `us-2026-10-01: https://dailyyield.blogspot.com/2026/10/us-2026-10-01.html, https://dailyyield.blogspot.com/2026/10/us-2026-10-01_01887906195.html`

**exactly-one-h1** (1 total)
- `https://dailyyield.blogspot.com/p/indexnow-key.html`

## What a feed cannot answer

- Cloaking (Bing abuse): needs a comparison of Bingbot-served and user-served HTML, which this repository's no-public-navigation rule forbids automating.
- Page speed and Core Web Vitals: not measurable from a feed; Blogger owns the delivery.
- Originality against the rest of the web: needs the source articles, which our publishing gates already check paragraph by paragraph before a post is allowed out.
- Ad density: AdSense has not placed ads, so the 'made for advertising' test is not yet applicable; it must be re-audited the day ads are approved.

PASS here means the measured condition holds for every URL we can read. It is not a promise of indexing, ranking or grounding eligibility.
