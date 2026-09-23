import os
import sys
from datetime import datetime, timedelta
import pytz
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
client_id = os.environ.get("BLOGGER_CLIENT_ID")
client_secret = os.environ.get("BLOGGER_CLIENT_SECRET")
refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN")

creds = Credentials(
    None,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret
)
service = build("blogger", "v3", credentials=creds)

# List posts to see current status
res = service.posts().list(blogId=BLOG_ID, maxResults=5).execute()
print(f"Blogger API Connection: SUCCESS! Retrieved {len(res.get('items', []))} recent posts.")
for p in res.get('items', []):
    print(" -", p.get('title'), "| Status:", p.get('status'), "| Published:", p.get('published'))
