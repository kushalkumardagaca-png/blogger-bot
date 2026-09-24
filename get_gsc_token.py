#!/usr/bin/env python3
"""
ONE-TIME HELPER — Connect Google Search Console to the blog's cloud automation
==============================================================================
Kushal: run this once on any computer with Python 3, when you are able:

    pip install google-auth-oauthlib
    python get_gsc_token.py

What happens:
  1. A browser window opens.
  2. Sign in with the Google account that owns the blog
     (kushalkumadaga.ca@gmail.com).
  3. You may see "Google hasn't verified this app" — that is YOUR OWN app
     (the one created in your Google Cloud Console). Click
     "Advanced" -> "Go to (app)" -> tick the Search Console permission
     -> click Allow.
  4. This screen then shows a long code (refresh token).

Then paste that code into GitHub as a secret (2 more minutes):
  1. Go to: https://github.com/kushalkumardagaca-png/blogger-bot/settings/secrets/actions
  2. Click "New repository secret"
  3. Name:  GSC_REFRESH_TOKEN
  4. Secret: paste the code
  5. Click "Add secret"

DONE. Within a few hours the health watchdog notices it automatically and
starts: sitemap management, Google index tracking, and search metrics in
every health report. No other action ever needed.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/webmasters']


def main():
    print("=" * 65)
    print("  DAILY YIELD - 1-TIME SEARCH CONSOLE LINK SETUP")
    print("=" * 65)
    client_id = input("Enter your OAuth Client ID: ").strip()
    client_secret = input("Enter your OAuth Client Secret: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8081/"]
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8081, prompt='consent',
                                  access_type='offline')

    print()
    print("=" * 65)
    print("SUCCESS! Now add this to GitHub as secret 'GSC_REFRESH_TOKEN':")
    print("=" * 65)
    print(creds.refresh_token)
    print("=" * 65)
    print("GitHub -> blogger-bot repo -> Settings -> Secrets and variables ->")
    print("Actions -> New repository secret -> Name: GSC_REFRESH_TOKEN")
    print("The cloud watchdog will pick it up automatically within hours.")


if __name__ == "__main__":
    main()
