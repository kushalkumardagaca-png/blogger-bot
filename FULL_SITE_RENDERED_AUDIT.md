# Daily Yield — Full Rendered Website Audit

Audit date: 25 September 2026 (IST)

## Scope

- Homepage: 1
- Blogger Pages: 12
- Posts and News articles: 36
- Total public URLs rendered: 49
- Viewports per URL: mobile 360×800, tablet 768×1024, desktop 1440×1000
- Total rendered-browser checks: 147

## Final result

**147 PASS · 0 FAIL**

Every URL was loaded in Chromium with JavaScript enabled and evaluated after dynamic components had time to render.

## Checks performed

- Body-level horizontal overflow
- Responsive card dimensions and text wrapping
- Article, news and related-reading carousels
- Mobile touch layout, mouse/trackpad controller presence and continuous motion
- Broken visible images and failed first-party resources
- Duplicate HTML IDs
- Four unique related-reading destinations per post
- Visible Kushal K. Daga branding/byline on Posts
- Empty or script-only links
- Uncaught JavaScript, ReferenceError, TypeError and page-level exceptions
- Canonical BlogPosting and NewsArticle identity
- Internal navigation and image-resource availability

## Defects found and repaired

1. Related-reading groups were allowed to flex-shrink, compressing 235–290 px cards into 29 px columns on mobile. Groups and cards now have explicit non-shrinking widths.
2. “The Payday Waterfall” contained two full copies of its schema/style/article package, creating duplicate IDs and duplicated content. The second package was removed.
3. Older regular articles had stale predicted canonical addresses. Every regular BlogPosting schema was normalized to its actual live URL, `@id`, `url` and `mainEntityOfPage`.
4. Four articles and Money Atlas contained copied Cloudflare challenge-injection scripts that attempted to load a nonexistent `/cdn-cgi/` asset from Blogspot. All five scripts were removed.
5. Money Atlas depended only on Frankfurter for FX data. Frankfurter currently returns HTTP 403, so a lawful sequential `open.er-api.com` fallback was added. The rendered page was verified showing live fallback rates and its update date.
6. The carousel controller was retained in its layout-safe native `scrollLeft` implementation; no transform is applied to card tracks.

## Resource results

- Unique content images tested directly: 90
- Broken image URLs: 0
- Duplicate IDs after remediation: 0
- Posts with malformed related shelf: 0
- Body-level horizontal overflow failures: 0
- Uncaught first-party JavaScript failures: 0

Expected third-party primary-source failures are tolerated only where an operating fallback or nonessential third-party support request exists. They are not treated as real data and never overwrite a valid earlier result.

## Automation protection

The same fixes are retained in the publishing and maintenance code:

- Future related shelves use non-shrinking responsive cards.
- Master articles and News posts receive the shared native-motion controller.
- Maintenance repairs canonical BlogPosting identity and removes copied challenge scripts.
- Money Atlas retains sequential FX fallback behavior.
- Publishing automation audit remains **44 PASS · 0 FAIL**.
