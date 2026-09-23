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

# Future time: 10 days from now
future_time = (datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=10)).strftime("%Y-%m-%dT11:30:00+05:30")
print(f"Testing scheduling a post for future time: {future_time}")

body = {
    "kind": "blogger#post",
    "blog": {"id": BLOG_ID},
    "title": "TEST SCHEDULE POST - Automated Future Verification",
    "content": "<p>This is a test scheduled post to verify automated scheduling.</p>",
    "published": future_time
}

try:
    res = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
    print("SUCCESS! Post created!")
    print("Post ID:", res.get("id"))
    print("Status:", res.get("status"))
    print("Published date on post:", res.get("published"))
    
    # Clean up test post immediately so blog stays clean
    service.posts().delete(blogId=BLOG_ID, postId=res.get("id")).execute()
    print("Cleaned up test post successfully!")
except Exception as e:
    print("Error during insert:", e)
