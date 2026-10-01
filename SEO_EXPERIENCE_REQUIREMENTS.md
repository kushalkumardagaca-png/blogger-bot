# Daily Yield SEO and Reader Experience Standard

This is the permanent implementation standard derived from the three website checklists supplied on 2026-10-01.

## Implemented in Theme v4

- Responsive mobile navigation, site search, sticky masthead, skip link and back-to-top control.
- Reading-progress indicator, print stylesheet, restrained loading indicator, reduced-motion support, hover and keyboard focus states.
- Share/copy behavior, light/dark reader preference and prominent floating Contact access.
- Honest privacy choices: essential storage works without consent; optional analytics remains denied until allowed.
- Visible form validation/success feedback and automatic password visibility controls only if a genuine password field is ever introduced.
- Visible homepage FAQ paired exactly with FAQPage JSON-LD.
- Visible single-item breadcrumbs paired with BreadcrumbList JSON-LD.
- WebSite/SearchAction structured data, canonical URL and responsible crawler/index directives.
- UTM campaign attribution stored only for the browser session; no personal data and no URL mutation.
- Responsive image loading/decoding safeguards; first editorial image receives high fetch priority and later images lazy-load.
- Author identity, contact route, privacy, terms, disclaimer, related suggestions and Page-family directory remain preserved.

## Search and reach

- Google Search Console inventory, sitemap submission and URL inspection remain automated.
- Bing Webmaster sitemap submission is implemented through `search_reach.py` and activates only after the repository owner configures the official `BING_WEBMASTER_API_KEY` secret.
- Blogger HTTPS and server-rendered HTML remain the delivery foundation.
- Public content is index/follow; private, duplicate, administrative and internal-result URLs must not be forced into the index.
- ChatGPT-User and OAI-SearchBot discovery are permitted through page-level directives. Blogger robots.txt remains controlled in Blogger Search preferences.

## Integrity boundaries

- No synthetic Daily Yield pageviews.
- No fabricated backlinks, reviews, traffic, engagement or real-time claims.
- No sitewide FAQ schema without matching visible questions and answers.
- No unnecessary password flow.
- No analytics loader or identifier is invented; the consent layer governs analytics only when a legitimate measurement configuration exists.
- A sub-two-second load is a performance target, never a universal guarantee.
- Forbes or any other authority link must be editorially earned through legitimate outreach.
- AI assistance is governed by usefulness, sourcing, originality and named accountability—not hidden or mass-generated filler.
