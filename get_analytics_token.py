#!/usr/bin/env python3
"""
ONE-TIME HELPER - let the automation read the visitor counts the blog already collects
=======================================================================================
Kushal: the analytics tag is ALREADY on the site (it says
`gtag('config', 'G-WLEEYTKV12')` on every page), so there is nothing to install on
Daily Yield and nothing to change during the AdSense review. The only thing missing is
permission for the robots to read the numbers, because the saved Google token was
created for Search Console alone.

Run this once on any computer with Python 3:

    pip install google-auth-oauthlib
    python get_analytics_token.py

What happens:
  1. A browser window opens.
  2. Sign in with the Google account that owns the blog
     (kushalkumardagaca.ca@gmail.com).
  3. You may see "Google hasn't verified this app" - that is YOUR OWN app. Click
     "Advanced" -> "Go to (app)" -> tick BOTH permissions (Search Console and Google
     Analytics) -> Allow.
  4. The screen then shows a long code (a new refresh token).

Put that code in GitHub - never in a chat:
  1. https://github.com/kushalkumardagaca-png/blogger-bot/settings/secrets/actions
  2. "New repository secret"
  3. Name:  GA4_REFRESH_TOKEN
  4. Secret: paste the code, then "Add secret"

Optional but helpful: in the same screen, under "Secrets and variables" -> "Variables"
-> "New repository variable", add GA4_PROPERTY_ID with the numeric Property ID you see
in Analytics -> Admin -> Property settings. If you skip it, the job finds it itself
using the measurement id G-WLEEYTKV12.

Use the SAME OAuth Client ID and Client Secret as the Search Console setup
(GSC_CLIENT_ID / GSC_CLIENT_SECRET in the repo). After that the nightly job
(02:05 IST, "Indexing Capacity Gate") starts reporting real pageviews, and the growth
ladder switches from "search clicks / 28" to measured views on its own.
"""
import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:  # the one-line remedy, printed instead of a traceback
    sys.stderr.write(
        "This helper needs one small library:  python -m pip install google-auth-oauthlib\n"
        "If you would rather not install anything, use the browser steps in GA4_CONNECT.md instead:\n"
        "they do the same authorisation on Google's own page and print the same code.\n")
    raise SystemExit(1)

# Search Console is kept in the same authorisation so the existing index reporting keeps
# working with one token instead of two.
SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def main():
    print("=" * 65)
    print("  DAILY YIELD - 1-TIME ANALYTICS READ SETUP")
    print("=" * 65)
    # already-known values are used without typing; both names are accepted because the repository
    # keeps the Search Console pair under GSC_* and the Analytics pair under GA4_*
    client_id = (os.environ.get("GA4_OAUTH_CLIENT_ID") or os.environ.get("GA4_CLIENT_ID")
                 or input("Enter your OAuth Client ID: ").strip())
    client_secret = (os.environ.get("GA4_OAUTH_CLIENT_SECRET") or os.environ.get("GA4_CLIENT_SECRET")
                     or input("Enter your OAuth Client Secret: ").strip())

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8082/"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8082, prompt="consent", access_type="offline")

    print()
    print("=" * 65)
    print("SUCCESS! Now add this to GitHub as secret 'GA4_REFRESH_TOKEN':")
    print("=" * 65)
    print(creds.refresh_token)
    if not creds.refresh_token:
        sys.stderr.write("Google returned no refresh token: the consent did not include offline access. "
                         "Run it again and choose Allow on the screen that lists both permissions.\n")
        raise SystemExit(1)
    print("=" * 65)
    print("GitHub -> blogger-bot repo -> Settings -> Secrets and variables ->")
    print("Actions -> New repository secret -> Name: GA4_REFRESH_TOKEN")
    print("The nightly job will then report measured pageviews instead of search clicks.")


if __name__ == "__main__":
    main()
