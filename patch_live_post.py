import os
import sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
POST_ID = "6615350878444001009"

client_id = os.environ.get("BLOGGER_CLIENT_ID")
client_secret = os.environ.get("BLOGGER_CLIENT_SECRET")
refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN")

if not all([client_id, client_secret, refresh_token]):
    print("Error: Missing Blogger credentials!")
    sys.exit(1)

creds = Credentials(
    None,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret
)
service = build("blogger", "v3", credentials=creds)

with open("scheduled_ready/topic_321_the-first-couples-money-meeting-agenda.html", "r", encoding="utf-8") as f:
    master_html = f.read()

body = {"content": master_html}
updated = service.posts().patch(blogId=BLOG_ID, postId=POST_ID, body=body).execute()
print(f"SUCCESS: Post {POST_ID} patched with authentic editorial photo! URL: {updated.get('url')}")
