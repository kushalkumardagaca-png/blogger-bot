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

Both must be enabled **in the project that holds the blog's Google keys**. On 21 October 2026 the
owner's screens showed that project, and it is the only one: its service accounts all end in
`@572287903723.iam.gserviceaccount.com`, and it contains the OAuth client
`Daily Yield Search Console Automation` (created 26 Sept 2026). Select it in the project picker at the
top left before enabling anything. To check the enabling worked, open either link again: a button
reading **Manage** means the API is on for that project; a button reading **Enable** means it was
turned on somewhere else and has to be done again with the right project chosen.

## Step 2 — reuse the client you already have (nothing to create)

Open <https://console.cloud.google.com/apis/credentials>, or the same list in the newer screen:
<https://console.cloud.google.com/auth/clients>. As seen on 21 October 2026 it holds two rows:

| Client | Type | Use it? |
| --- | --- | --- |
| **Daily Yield Search Console Automation** (26 Sept 2026) | Web application | **yes — this one** |
| ⚠ Blogger Web App (22 Sept 2026) | Web application | no, leave it alone; the blog's own posting key lives behind it |

Being a *Web application* client is exactly what the browser route needs, because it has an editable
redirect list. Click **Daily Yield Search Console Automation** and:

1. Find **Authorized redirect URIs** → **Add URI** → paste `https://developers.google.com/oauthplayground`
   → **Save**. Adding a URI never disturbs a working authorisation: nothing that runs today stops.
2. On the same page copy the **Client ID**, and reveal/copy the **Client secret** (web clients show it
   with a copy icon).
3. **Do not press "Reset secret"** or delete anything. A reset would silently break the nightly Search
   Console readings, which use this same pair, and every job would start failing with `invalid_client`.

You do **not** need to store this pair in GitHub: the repository already holds it under
`GSC_CLIENT_ID` and `GSC_CLIENT_SECRET`, and every job that reads Analytics resolves the three values
one at a time (`google_credentials.py`) — so the new `GA4_REFRESH_TOKEN` is used with the existing
client pair. That is why Step 4 costs you one paste instead of three, and it is true for the nightly
measurement, the control tower and the Table 3 audit alike: they were fixed on 21 October 2026 after
two of them picked a whole set of names by prefix and would have ignored a correct single paste.

*Only if* the secret cannot be revealed on that page: leave it as it is and create a second client —
**Create credentials → OAuth client ID → Application type: Web application**, name
`Daily Yield robots`, authorized redirect URI `https://developers.google.com/oauthplayground` — and
then Step 4 needs its `GA4_CLIENT_ID` and `GA4_CLIENT_SECRET` added as well. The Search Console
channel keeps its own credentials untouched either way.

**Already checked, so skip it:** <https://console.cloud.google.com/auth/audience> showed
**Publishing status: In production**, **User type: External**. That is the good state — a token minted
now is not thrown away after 7 days, and no test-user list applies. The `TOKEN_REFUSED` warning below
exists only for the day someone changes that page.

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
| `GA4_REFRESH_TOKEN` | the refresh token from Step 3 — **this is the only paste, if you reused the
existing client as Step 2 says** |
| `GA4_CLIENT_ID` | only if you created a second client instead |
| `GA4_CLIENT_SECRET` | only if you created a second client instead |

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
