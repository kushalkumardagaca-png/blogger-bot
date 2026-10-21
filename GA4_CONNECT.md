# Analytics read access, one step at a time — about 4 minutes, nothing to install

Written 21 October 2026. This replaces the older "run the script" version of this file, because
that version assumed you had Python on a computer and were willing to hunt for a value you had
stored four months ago. You are not, and you shouldn't have to be.

**What this is for.** The blog already counts visitors: every page carries
`gtag('config', 'G-WLEEYTKV12')`, verified from the live site. What is missing is permission for
the robots to *read* that count, so the nightly report still says `CREDENTIALS_MISSING` and the
growth ladder prints `UNMEASURABLE_UNTIL_GA4_IS_READABLE` instead of a real number. Your milestone
is 50,000 *people* a day, and `engagedSessions` in GA4 is the only instrument that measures people.

**What this does not do.** It does not touch the blog, the theme, the robots.txt, or anything an
AdSense reviewer looks at. It only adds a read-only approval on Google's side plus three values in
this repository. The AdSense review (~3–17 November) is unaffected.

**Why this one is safe to do at your own pace.** A Google refresh token does not expire in a
minute. Unlike the Tumblr code that ruined 20–21 October, there is no race: save the values, then
check the answer whenever you like.

---

## Step 1 — let the project speak Analytics (2 minutes, 3 clicks)

Open <https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com> and press
**Enable**. Then the same for the second API the robots use to find the property:
<https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com> → **Enable**.

Use the project picker at the top of the page to select the project that holds the blog's existing
Google keys — the one you used for Search Console in July. If you are not sure, the first project
the console opens on is normally it; Step 2 will tell you if it was the wrong one.

## Step 2 — get an OAuth client, or reuse the one you have

Open <https://console.cloud.google.com/apis/credentials>. In the new interface the same list is at
<https://console.cloud.google.com/auth/clients>.

**If an "OAuth 2.0 Client IDs" row already exists** (the Search Console one), click it and look for
the **Client secret** line with its copy icon:

* If the secret is visible — copy both values and go straight to Step 3A. Nothing else to create,
  and GitHub already knows this pair, so you paste **one** value in total.
* If you cannot reveal it, **do not press "Reset secret"**: that would silently break the nightly
  Search Console readings, which use that same pair. Create a client of your own instead:
  **Create credentials → OAuth client ID → Application type: Web application**, name
  `Daily Yield robots`, and under **Authorized redirect URIs** add exactly
  `https://developers.google.com/oauthplayground`. Press Create and copy the Client ID and the
  Client secret. This new pair is used only for Analytics, so the Search Console channel keeps its
  own credentials and stays as it is.

Then, whichever kind of client you are using, check the consent screen once:
<https://console.cloud.google.com/auth/audience>. If **Publishing status** says `Testing`, make sure
`kushalkumardagaca.ca@gmail.com` is listed under **Test users** (that is the account that owns the
blog and its Search Console property). In Testing mode Google throws refresh tokens away after
**7 days**, so if you prefer not to publish the app, that is fine — the nightly job detects a dead
token on its own and the morning report says `TOKEN_REFUSED`, which means "do Step 3 again", not
"something is broken on the site".

## Step 3A — get the token in your browser, no terminal (2 minutes)

<https://developers.google.com/oauthplayground/> is Google's own page for exactly this.

1. Click the **gear icon** (top right) to open **OAuth 2.0 configuration**. Tick **Use your own
   OAuth credentials**, paste the **OAuth Client ID** and **OAuth Client secret** from Step 2, and
   set **Access type: Offline** — that one choice is the whole reason a long-lived token comes out
   at the end instead of a one-hour access token. Leave **OAuth flow: Server-side** and **OAuth
   endpoints: Google** as they are. The page tells you plainly that the redirect URI
   `https://developers.google.com/oauthplayground` has to be listed on the client, which is why Step
   2 asks for a **Web application** client.
   *(If you reused the existing Search Console client and it is a "Desktop app" client, it has no
   redirect list, so this page cannot be used — go to Step 3B instead.)*
   One disclosure, because it is your secret: the Playground proxies the exchange, so Google's own
   playground server sees the client ID and secret (it states they are not logged). If you would
   rather not, use Step 3B, which keeps everything between your machine and Google.
2. In **Step 1: Select & authorize APIs**, ignore the long list and use the box under it — *"input
   your own OAuth scopes"* — and paste these two lines, one per line:
   ```
   https://www.googleapis.com/auth/analytics.readonly
   https://www.googleapis.com/auth/webmasters.readonly
   ```
   Search Console's read scope is included on purpose: the robots then keep using one authorisation
   for both jobs instead of two.
   Press **Authorize APIs** → sign in as `kushalkumardagaca.ca@gmail.com` → when Google says
   *"Google has not verified this app"*, that is your own app: **Advanced → Go to ... (unsafe) →
   Allow both permissions**.
3. That opens **Step 2: Exchange authorization code for tokens**. Press **Exchange authorization code
   for tokens**. The box fills with JSON; copy the value after `"refresh_token":` — one long word
   beginning `1//`. (The **Get access token** button under it is optional: it shows a live count in
   the next box, which is a nice way to see it working before you save anything.)

## Step 3B — or run the helper, if you have Python on a computer (2 minutes)

In this repository's folder: `pip install google-auth-oauthlib` then `python get_analytics_token.py`.
It asks for the same two values from Step 2, opens a browser on `http://localhost:8082/` to collect
your Allow, and prints the refresh token in the terminal. It needs a **Desktop app** client.

## Step 4 — hand the values to the robots (30 seconds, and no order to remember)

Add secrets here: <https://github.com/kushalkumardagaca-png/blogger-bot/settings/secrets/actions> →
**New repository secret**. Name on the left, value on the right, **Add secret** — one after the
other; the sequence does not matter and nothing runs while you type.

| Name | Value |
| --- | --- |
| `GA4_REFRESH_TOKEN` | the refresh token from Step 3 — always |
| `GA4_CLIENT_ID` | only if you created a new client in Step 2 |
| `GA4_CLIENT_SECRET` | only if you created a new client in Step 2 |

Optional, and you can skip it safely: <https://github.com/kushalkumardagaca-png/blogger-bot/settings/variables/actions>
→ **New repository variable** → `GA4_PROPERTY_ID` = the number under Analytics → Admin → *Property
settings* (<https://analytics.google.com/analytics/web/>). Without it the nightly job finds the
property itself from `G-WLEEYTKV12`.

**Never** paste a token, a password or a 6-digit code into a chat with me, and never into the
article editor. These four boxes are the only place they go.

## Step 5 — press Run once, read one sentence (30 seconds)

<https://github.com/kushalkumardagaca-png/blogger-bot/actions/workflows/ga4_connection_check.yml> →
**Run workflow** → **Run workflow** again. About 25 seconds later the log's last line is a plain
sentence, and the run goes green only if Google really returned numbers:

| The line says | What it means | What changes |
| --- | --- | --- |
| `MEASURED — … pageviews and … engaged readers` | connected | nothing further, ever |
| `CREDENTIALS_MISSING` | a box in Step 4 is empty or mis-named | re-check the three names |
| `SCOPE_INSUFFICIENT` | the token exists but predates Analytics | repeat Step 3, replace only `GA4_REFRESH_TOKEN` |
| `TOKEN_REFUSED` | Google expired the token (7-day Testing rule) | repeat Step 3, replace only `GA4_REFRESH_TOKEN` |
| `PROPERTY_NOT_FOUND` | the token works, the property is unnamed | add the `GA4_PROPERTY_ID` variable |
| `NO_DATA_YET` | connected, but the property has no rows in that window | nothing: it is a real answer, not a failure |

If the account you signed into shows no Analytics property at all, the tag belongs to the other
Google account — sign in as `dailyyield.official@gmail.com` and repeat Step 3. The blog is unchanged
either way.

## What happens by itself afterwards

The nightly **Indexing Capacity Gate** (02:05 IST) already runs `ga4_measurement.py` →
`GA4_MEASUREMENT.md`, and `growth_ladder.py` switches its own basis the moment a number exists:
`Views are counted as GA4_PAGEVIEWS_7_DAY_AVERAGE` instead of `SEARCH_CONSOLE_CLICKS_DIVIDED_BY_28`.
As of this writing that job ran **without being handed its credentials** — the fix for that is in
this same commit, and a standing audit check now fails loudly if a job ever runs the reader with no
secrets again, because a documented instruction is not a working measurement.
