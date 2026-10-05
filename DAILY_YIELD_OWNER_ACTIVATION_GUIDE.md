# Daily Yield — Owner Activation Guide

This guide contains only the actions that cannot be performed by repository automation because they require the account owner’s logged-in Blogger, Google Analytics, Bing or Search Console interface.

Complete the sections in this order.

## 1. Upload Theme v4 in Blogger — required

1. Download `Daily-Yield-Theme-v4-2026-10-01.xml` from the Arena workspace.
2. Sign in to Blogger with Kushal’s owner account.
3. Select **Daily Yield**.
4. Open **Theme**.
5. Open the menu beside **Customize**.
6. Select **Back up** first and download the current Theme as a safety copy.
7. Return to the same menu and select **Restore** or **Upload**.
8. Choose `Daily-Yield-Theme-v4-2026-10-01.xml`.
9. Confirm the upload and wait for Blogger to finish.
10. Open Daily Yield normally on your own phone. This is a genuine owner visit, not an automated synthetic view.

Check these visible items:

- DAILY YIELD remains the dominant heading.
- Navigation is readable on two lines where designed.
- Search and mobile menu open correctly.
- The light/dark button changes the colour scheme.
- The reading-progress line moves while scrolling.
- The Contact button opens the Contact Page.
- The Privacy choices panel offers **Allow optional analytics** and **Essential only**.
- Homepage FAQ items expand and collapse.
- No article text, image or navigation section is missing.

If the Theme upload fails, restore the backup from step 6. Do not paste partial XML into Blogger.

## 2. Create and connect legitimate Google Analytics — optional but required to satisfy the GA checklist item

Theme v4 now sets Google Consent Mode to **denied by default before analytics loads**. Do not configure Analytics before Theme v4 is active.

### Create the GA4 property

1. Open `https://analytics.google.com/` while signed in to Kushal’s Google account.
2. Open **Admin**.
3. Select **Create property**.
4. Property name: `Daily Yield`.
5. Choose the correct India timezone and reporting currency.
6. Complete Google’s business-information screens truthfully.
7. Choose **Web** as the data platform.
8. Website URL: `https://dailyyield.blogspot.com/`.
9. Stream name: `Daily Yield website`.
10. Create the stream.
11. Copy the Measurement ID beginning with `G-`.

### Connect it in Blogger

1. Open **Blogger → Daily Yield → Settings**.
2. Find **Google Analytics Measurement ID**.
3. Paste only the `G-…` Measurement ID.
4. Save.
5. Do not paste the ID into this chat; it is not necessary for repository work.

Analytics must remain optional. A reader choosing **Essential only** must still be able to use the complete website.

## 3. Activate Bing Webmaster Tools — required for Bing submission

1. Open `https://www.bing.com/webmasters/`.
2. Sign in with the owner account.
3. Choose **Import from Google Search Console**. This is the simplest verified route because Daily Yield already has a functioning Search Console property.
4. Select `https://dailyyield.blogspot.com/` and finish the import.
5. In Bing Webmaster Tools, open **Settings** or **API Access**.
6. Create/copy the official API key.
7. Open GitHub repository settings: `https://github.com/kushalkumardagaca-png/blogger-bot/settings/secrets/actions`.
8. Select **New repository secret**.
9. Name it exactly: `BING_WEBMASTER_API_KEY`.
10. Paste the Bing key as the value and save.
11. Never paste the key into chat, a repository file, issue, commit or screenshot.

After the secret exists, the dedicated authenticated search-reach workflow can submit the two Blogger sitemaps through the implemented Bing integration, with duplicate daily submissions suppressed.

## 4. Request priority indexing in Google Search Console — only for important new/changed URLs

Google does not provide a general API for the **Request Indexing** button.

1. Open `https://search.google.com/search-console/`.
2. Select the Daily Yield property.
3. Use **URL inspection**.
4. Paste one important new or substantially changed Daily Yield URL.
5. Select **Test live URL**.
6. If Google reports that the URL can be indexed, select **Request indexing**.
7. Repeat only for priority Pages and newly important Posts; do not attempt to submit all 204 URLs manually. Sitemaps handle normal discovery.

Recommended priority after Theme v4 activation:

- Homepage
- Daily News Page
- Daily Article Page
- Calculator Page
- Markets Today Page
- Global Snapshot Page
- Money Atlas Page
- Terms & Conditions
- Privacy Policy

## 5. Real-user performance confirmation — required before claiming “under two seconds”

Do not use automated page-refresh tools or synthetic traffic.

1. After Theme v4 is live, use the site normally on your own phone for several days.
2. In Search Console, open **Core Web Vitals**.
3. Wait for Google’s real-user field data; it may take time to accumulate.
4. Review mobile and desktop results for LCP, INP and CLS.
5. Do not advertise a universal “under two seconds” result unless real-user data supports it.

## 6. Forbes and authority links — no account action can guarantee this

- Do not buy, exchange or fabricate a Forbes backlink.
- The official Forbes News Tips route is already registered as `review_required` in the outreach system.
- A message may be sent only when there is a specific, sourced and genuinely newsworthy idea.
- Any citation or backlink remains Forbes’ independent editorial decision.

## 7. Return the repository to private visibility — recommended

The permanent repository-scoped deploy key works with a private repository.

1. Open `https://github.com/kushalkumardagaca-png/blogger-bot/settings`.
2. Scroll to **Danger Zone**.
3. Select **Change repository visibility**.
4. Choose **Make private** and complete GitHub’s confirmation.
5. Do not remove the deploy key named `Arena Daily Yield permanent repository access` if you want future assistant-led repository maintenance.

## Items requiring no owner action

The following are already deployed and automated:

- Five master-article schedules.
- Twenty News desks.
- Exact Blogger URL recovery.
- Publication preflight and H1/alt enforcement.
- Search Console/sitemap monitoring.
- Security Guard integrity monitoring plus static zero-synthetic-view policy audits.
- Security Guard and integrity baseline.
- Facebook, Bluesky, Tumblr and Mastodon coordinated active-30 router.
- Fifteen-minute article social delay target.
- Daily platform rotation and Page rotation.
- External 404 confirmation and redirect-chain monitoring.
- Page-family accessibility repair.
- Legitimate editorial outreach safety controls.
- Reddit 0.0.2 protection while review remains pending.
