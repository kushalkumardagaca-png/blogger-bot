#!/usr/bin/env python3
"""Pick the Google authorisation a job should use, one value at a time.

The two jobs that read Analytics used to choose a whole *set* of variables by prefix: if all three
``GA4_*`` names were present they were used, otherwise all three ``GSC_*`` names were. That mis-read
the very setup the owner is told to do - one paste, ``GA4_REFRESH_TOKEN``, because the OAuth client
pair is already stored in the repository for Search Console. The reader then took the older Search
Console refresh token, which carries no Analytics scope, and reported "not connected" about a
connection that had just been made on Google's side.

So every value is resolved on its own, preferring the Analytics names, and the source of the token
is reported in the evidence file: "which credential did you actually use" must be answerable a month
later without asking anyone.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
CLIENT_ID = ("GA4_CLIENT_ID", "GSC_CLIENT_ID")
CLIENT_SECRET = ("GA4_CLIENT_SECRET", "GSC_CLIENT_SECRET")
REFRESH_TOKEN = ("GA4_REFRESH_TOKEN", "GSC_REFRESH_TOKEN")


def _pick(names):
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value, name
    return "", names[-1]


def analytics_credentials():
    """(client_id, client_secret, refresh_token, source, complete) - each looked up independently."""
    client_id, client_id_from = _pick(CLIENT_ID)
    client_secret, client_secret_from = _pick(CLIENT_SECRET)
    refresh_token, refresh_from = _pick(REFRESH_TOKEN)
    # the source line only names a different set when it really is a different set, so "I used the
    # Analytics token with the Search Console client pair" is readable and "GA4_REFRESH_TOKEN" alone
    # means nothing was borrowed
    borrowed_from = refresh_from.split("_", 1)[0]
    parts = [refresh_from] + [name for name in (client_id_from, client_secret_from)
                              if name.split("_", 1)[0] != borrowed_from]
    return (client_id, client_secret, refresh_token, " + ".join(parts),
            bool(client_id and client_secret and refresh_token))


def credential_source():
    return analytics_credentials()[3]


def access_token():
    """A short-lived bearer token for the Analytics and Search Console read scopes."""
    client_id, client_secret, refresh_token, _, complete = analytics_credentials()
    if not complete:
        raise RuntimeError("Analytics read credentials are not configured: store the value Google "
                           "printed in the repository secret GA4_REFRESH_TOKEN (GA4_CONNECT.md, step 4)")
    form = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret,
                                  "refresh_token": refresh_token,
                                  "grant_type": "refresh_token"}).encode()
    request = urllib.request.Request(TOKEN_URL, data=form, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("Google answered without an access token")
    return token
