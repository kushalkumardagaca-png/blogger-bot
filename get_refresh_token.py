"""
Helper Script to generate BLOGGER_REFRESH_TOKEN
Run this script on any computer with Python:
    pip install google-auth-oauthlib
    python get_refresh_token.py
"""

import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/blogger']

def main():
    print("=" * 65)
    print("  DAILY YIELD - 1-TIME GOOGLE BLOGGER AUTH SETUP")
    print("=" * 65)
    client_id = input("Enter your OAuth Client ID: ").strip()
    client_secret = input("Enter your OAuth Client Secret: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"]
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8080, prompt='consent', access_type='offline')

    print("\n" + "=" * 65)
    print("SUCCESS! COPY THESE EXACT VALUES INTO GITHUB SECRETS:")
    print("=" * 65)
    print(f"BLOGGER_BLOG_ID:       8911514070006792465")
    print(f"BLOGGER_CLIENT_ID:     {client_id}")
    print(f"BLOGGER_CLIENT_SECRET: {client_secret}")
    print(f"BLOGGER_REFRESH_TOKEN: {creds.refresh_token}")
    print("=" * 65)

if __name__ == "__main__":
    main()
