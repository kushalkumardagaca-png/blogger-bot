# Analytics read access, one step at a time — about 4 minutes, nothing to install

Written 21 October 2026. This replaces the older "run the script" version of this file, because
that version assumed you had Python on a computer and were willing to hunt for a value you had
stored four months ago. You are not, and you shouldn't have to be.

> **If you are here because a run just failed with `ACCESS_TOKEN_SCOPE_INSUFFICIENT`, start at
> "Do this now: regenerate the whole set inside the Blogger Bot project" below.** The general route
> after it is the same, written for a first-time setup.

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
   Google says a settings change like that can take **5 minutes to a few hours** to take effect, so if
   the next page answers `redirect_uri_mismatch`, wait ten minutes and press it again instead of
   changing anything else.
2. Copy the **Client ID**.
3. The **Client secret is not readable anywhere on that page, and that is not a mistake you made**:
   after Google's April 2025 change (applied to all clients from November 2025) secrets are hashed in
   the console, and once the creation dialog closes only the **last four characters** are shown, for
   identification. It is never displayed again.
4. So ask Google for a *second* secret on the same client. That is Google's documented way to recover a
   lost secret, and it is safe here because **adding** a secret does not switch the old one off: on the
   client details page press **Add secret** on the right, and copy the value **immediately**, because it
   is shown once. A client may hold up to two enabled secrets, so the value this repository already holds
   keeps working for the nightly Search Console readings while Analytics uses the new one.
5. **Never press "Disable", "Delete" or "Reset" on the older secret.** Any of those would break every job
   that refreshes with the stored value, and they would all start failing with `invalid_client`.

*If that page offers no **Add secret** button* (some accounts are read-only there): leave this client
alone and create a second one — **Create client → Web application**, name `Daily Yield robots`,
authorized redirect URI `https://developers.google.com/oauthplayground` — and copy **both** values from
the popup that appears the instant it is created, since they are never shown again. Step 4 then wants
three values instead of one, and nothing that currently works is touched.

You do **not** need to store this pair in GitHub: the repository already holds it under
`GSC_CLIENT_ID` and `GSC_CLIENT_SECRET`, and every job that reads Analytics resolves the three values
one at a time (`google_credentials.py`) — so the new `GA4_REFRESH_TOKEN` is used with the existing
client pair. That is why Step 4 costs you one paste instead of three, and it is true for the nightly
measurement, the control tower and the Table 3 audit alike: they were fixed on 21 October 2026 after
two of them picked a whole set of names by prefix and would have ignored a correct single paste.

*One more thing worth knowing:* the authorisation is tied to the **client**, not to which of its two
enabled secrets was used, so the repository can go on refreshing with the secret it already holds. If
Google ever answers `invalid_client` after you rotate, paste the new secret as `GA4_CLIENT_SECRET` too —
that is the whole repair, and `GA4_CONNECT.md` step 4 has the box for it.

**Already checked, so skip it:** <https://console.cloud.google.com/auth/audience> showed
**Publishing status: In production**, **User type: External**. That is the good state — a token minted
now is not thrown away after 7 days, and no test-user list applies. The `TOKEN_REFUSED` warning below
exists only for the day someone changes that page.

## Do this now: regenerate the whole set inside the Blogger Bot project

Measured from the owner's run at 13:25 IST on 21 October 2026 — `GA4_MEASUREMENT.json`:

> `HTTP 403 Request had insufficient authentication scopes. reasons: ACCESS_TOKEN_SCOPE_INSUFFICIENT`

That is one specific diagnosis, and it is not a project or API problem: both Analytics APIs are enabled
in **Blogger Bot** (`blogger-bot-509403`), every OAuth client lives in that project, and Google accepted
the stored refresh token. What it refused is the **permission list inside that token** — it was
authorised with one scope line instead of two. The project is fine; the token is too narrow.

So rebuild the set from a clean client in that project. Fifteen minutes, and every value is shown to you
exactly once, so read this whole section before pressing anything.

### 1. New OAuth client, in Blogger Bot
<https://console.cloud.google.com/apis/credentials?project=blogger-bot-509403> → **Create credentials →
OAuth client ID** (in the newer screen: <https://console.cloud.google.com/auth/clients> → **Create
client**, with Blogger Bot chosen in the picker at the top):

- **Application type: Web application**
- **Name:** `Daily Yield robots`
- **Authorized redirect URIs → Add URI:** `https://developers.google.com/oauthplayground`
- **Create** → a popup shows **Client ID** and **Client secret** together. Copy **both** into a note now.
  That popup is the only time either screen ever shows the secret; there is no "reveal" afterwards.

Leave `Daily Yield Search Console Automation` and `Blogger Web App` exactly as they are, and do not
press Disable, Delete or Reset on any secret of theirs: the nightly Search Console readings and the blog's
own posting refresh through those clients.

### 2. Authorise BOTH scopes, in Google's Playground
<https://developers.google.com/oauthplayground/>

1. **Gear icon** → tick **Use your own OAuth credentials** → paste the new **Client ID** and new
   **Client secret** → set **Access type: Offline** (without this there is no refresh token to copy) →
   close the gear.
2. Ask for **one permission: Analytics, read-only.** Do not paste anything: under
   **Step 1: Select & authorize APIs** type `analytics` in the search box above the API list, and tap
   the line **"View and download your Google Analytics data"** under **Google Analytics Admin API
   v1beta** (or under **Google Analytics Data API v1beta** — same permission, either one).
   Full detail, including where the entries sit if the search box is hidden on a phone, is in
   **"Which permission to tick, and where it is in the list"** above.
   The Search Console line is deliberately left out this time: it was never required, because the
   repository keeps its own Search Console token, and asking for two permissions in one box is what
   the phone could not do.
3. **Authorize APIs** → sign in as `kushalkumardagaca.ca@gmail.com` → **Advanced → Go to … (unsafe)**.
   The consent screen shows **one** line to tick — *"See and download your Google Analytics data"* — so
   tick it → **Allow / Continue**.
4. **Exchange authorization code for tokens** → the result box fills with JSON. Before copying, check
   the JSON contains the key `"refresh_token"` — if it has only `"access_token"`, the Offline setting
   did not stick; set it again and repeat from step 1. Copy the `refresh_token` value (starts `1//`).

### 3. **Update** the three values already in the repository — do not add new ones
<https://github.com/kushalkumardagaca-png/blogger-bot/settings/secrets/actions>

For each of these three: click its **name** in the list → **Update** (the pencil), replace the value,
save. Names stay exactly as they are; a second copy of a name is not needed and would confuse later
debugging.

| Name | New value |
| --- | --- |
| `GA4_CLIENT_ID` | the **new** client ID from step 1 |
| `GA4_CLIENT_SECRET` | the **new** client secret from step 1 |
| `GA4_REFRESH_TOKEN` | the **new** `refresh_token` from step 2 |

All three must come from the **same** client: a token minted by one client cannot be refreshed with
another's secret, which is why the pair is replaced along with it. `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`
and `GSC_REFRESH_TOKEN` are **not** part of this and must keep the old values — that is what the blog's
Search Console evidence runs on.

### 4. Run the check, and read three lines
<https://github.com/kushalkumardagaca-png/blogger-bot/actions/workflows/ga4_connection_check.yml> →
**Run workflow**. The log now shows, in order: which of the six credential names hold a value (counts
only, never the values), the line `in force: GA4_CLIENT_ID + GA4_CLIENT_SECRET + GA4_REFRESH_TOKEN` —
which is how you confirm the new trio is what the job used — and then either
`MEASURED — … pageviews and … engaged readers`, or Google's own sentence.

If it still says `ACCESS_TOKEN_SCOPE_INSUFFICIENT` after this, the answer is in that `in force:` line:
it means the token being refreshed did not come from the new trio, so one of the three boxes holds an
older value. Re-check those three and run again — no new client, no new token.

*Shorter route, for next time:* the client ID and secret are innocent in a scope failure, so if the
consent screen is simply re-done with both scopes, only `GA4_REFRESH_TOKEN` needs replacing. The full
three-value rebuild above is the right call when the client itself was half-configured, which is why
this one is written out in full.

---

## Which permission to tick, and where it is in the list

You need **one** permission: **Analytics, read-only**
(`https://www.googleapis.com/auth/analytics.readonly`).

The Search Console line I asked for too is not needed: the blog's Search Console reading already has its
own working token in this repository (`GSC_REFRESH_TOKEN`), and nothing on the Analytics side uses the
other. Asking for both was tidiness, not a requirement — and it is exactly what the phone could not do,
because the paste box swallows two lines into one. One permission means one tap and one tick.

**Route A — pick it from the list. Nothing to paste.**
On <https://developers.google.com/oauthplayground/> , under **Step 1: Select & authorize APIs**, there is
a search box above the list (labelled *Select the scope*). Type **`analytics`**. Two entries appear:

| Listed as | The line to tap |
| --- | --- |
| **Google Analytics Admin API v1beta** | *View and download your Google Analytics data* — `https://www.googleapis.com/auth/analytics.readonly` |
| **Google Analytics Data API v1beta** | the same line and the same URL |

Tap that line once; a check or highlight appears on the row. Ticking it under both entries is harmless —
it is one permission, not two. If the search box is not showing on your phone, the list is alphabetical:
scroll to the **G** block, just below *Google Ads API*, and the two Analytics rows are there; Search
Console sits far below under **S**, which is why typing in the box is quicker.

**Route B — the paste box, with ONE line only.** The box at the bottom of Step 1, under the long list,
takes what you type as a scope. Paste this single line and nothing else — no second line, no Enter key:

```
https://www.googleapis.com/auth/analytics.readonly
```

Then in both routes: **Authorize APIs** → sign in as `kushalkumardagaca.ca@gmail.com` → **Advanced → Go to
… (unsafe)** → the consent screen now shows **one** line to tick ("See and download your Google Analytics
data") → **Allow / Continue** → **Exchange authorization code for tokens** → the JSON must contain
`"refresh_token"` → copy that value.

## What the report proves now, instead of guessing

From 21 October 2026 the reader asks Google what the token it just obtained is permitted to do, and puts
that answer in the evidence:

```
what the stored token is permitted to do: `analytics.readonly`
token permits: analytics.readonly
```

If Analytics is absent from that line, the run **stops before touching the Analytics API** and says
`the stored token carries only: …` with the list. So the next time anything is refused you read a
permission list, not a 403 code, and no one has to work out which of three repairs a status implied.
Nothing is printed about the tokens themselves: the short-lived access token is never written to the
report or the log, and this repository is public.

---

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
2. In **Step 1: Select & authorize APIs**, type `analytics` in the search box above the list and tick
   **"View and download your Google Analytics data"** — that single line is all this needs:
   ```
   https://www.googleapis.com/auth/analytics.readonly
   ```
   *(On a keyboard you may also add `https://www.googleapis.com/auth/webmasters.readonly` so one
   authorisation covers both jobs; it is a convenience, not a requirement, and the repository's
   Search Console token already works on its own.)*
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
