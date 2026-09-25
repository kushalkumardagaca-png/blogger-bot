# Daily Yield — Google Search Console From-Scratch Plan

Baseline date: 25 September 2026 (IST)

## What can and cannot be reset

Daily Yield remains at `https://dailyyield.blogspot.com/`. Search Console properties are attached to URLs/domains, not to the publication name. Changing the website name therefore does not make the verified property obsolete.

Google does not provide a control or API to erase historical Search Console performance/indexing data from an unchanged property. The safe reset is:

1. Keep the verified URL-prefix property.
2. Remove obsolete sitemap submissions.
3. Submit the two current Blogger sitemaps.
4. Start a new local monitoring baseline dated 25 September 2026.
5. Inspect every current indexable URL.
6. Manually run Test Live URL and Request Indexing only where inspection indicates follow-up.

## Current authorization status

The repository currently has no `GSC_REFRESH_TOKEN`. Search Console automation has therefore never run; watchdog reports correctly show `SKIP`.

One owner action is required:

1. Authorize the existing Google Cloud OAuth client for `https://www.googleapis.com/auth/webmasters` using `get_gsc_token.py`.
2. Add the resulting refresh token to GitHub Actions secrets as `GSC_REFRESH_TOKEN`.
3. Confirm that the authorizing Google account is an owner/full user of `https://dailyyield.blogspot.com/` in Search Console.

Never send the refresh token in chat or commit it to the repository.

## First authorized rebuild

Run the GitHub Actions workflow **Rebuild Google Search Console baseline** with `reset_old_sitemaps=true`.

It will:

- Confirm the exact verified URL-prefix property and permission level.
- Inventory the homepage, every current Page and every current Post/News URL.
- Exclude the intentional legacy redirect `/p/share-market_0718113516.html` as an indexing target.
- Delete obsolete submitted sitemap entries only; it does not delete Google history.
- Submit:
  - `https://dailyyield.blogspot.com/sitemap.xml`
  - `https://dailyyield.blogspot.com/sitemap-pages.xml`
- Use the official URL Inspection API on every indexable URL.
- Record verdict, coverage state, crawl/fetch state, robots state, Google canonical, user canonical and last crawl time.
- Create `GSC_REBUILD_REPORT.md`, `GSC_REBUILD_REPORT.json` and a manual Live Test queue.

## Manual Search Console work

Google provides no public API for **Test Live URL** or **Request Indexing**. For each URL in the generated queue:

1. Open Search Console → URL Inspection.
2. Paste the exact URL.
3. Click **Test Live URL**.
4. Confirm that Google reports the URL can be indexed.
5. Click **Request Indexing** when appropriate.

A successful live test is not proof of indexing; it only confirms that Google’s inspection crawler can presently access the page.

## Continuing automation

After authorization, the six-times-daily health watchdog will:

- Maintain both Blogger sitemaps.
- Inventory the homepage plus every current Page and Post.
- Inspect each URL at most once per day.
- Persist coverage, crawl, fetch, robots and canonical states.
- Track newly indexed URLs and slow-indexing URLs.
- Report Search Analytics impressions, clicks and average position after Google’s normal reporting delay.

The automation will never falsely report a live test, indexing request or successful indexing when Google has not returned that status.
