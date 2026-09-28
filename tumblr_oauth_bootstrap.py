#!/usr/bin/env python3
"""One-time Tumblr OAuth2 authorization-code exchange.

Plaintext credentials and tokens are never printed or committed. The resulting
refresh-token bundle is encrypted with a Fernet key held only in GitHub Actions.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import requests
from cryptography.fernet import Fernet

TOKEN_URL = "https://api.tumblr.com/v2/oauth2/token"
USER_URL = "https://api.tumblr.com/v2/user/info"
REDIRECT_URI = "https://github.com/kushalkumardagaca-png/blogger-bot"
TOKEN_FILE = Path("tumblr_token.enc")
EXPECTED_BLOG = "dailyyield-official"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required encrypted setup value: {name}")
    return value


def main() -> int:
    response = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": required("TUMBLR_AUTHORIZATION_CODE"),
        "client_id": required("TUMBLR_CONSUMER_KEY"),
        "client_secret": required("TUMBLR_CONSUMER_SECRET"),
        "redirect_uri": REDIRECT_URI,
    }, timeout=(15, 60))
    if not response.ok:
        raise RuntimeError(f"Tumblr authorization exchange failed: HTTP {response.status_code}; create a fresh authorization code")
    token = response.json()
    if not token.get("access_token") or not token.get("refresh_token"):
        raise RuntimeError("Tumblr did not return both access and offline refresh tokens")
    scopes = set(str(token.get("scope", "")).split())
    if not {"basic", "write", "offline_access"}.issubset(scopes):
        raise RuntimeError(f"Tumblr granted incomplete scopes: {sorted(scopes)}")
    info_response = requests.get(USER_URL, headers={"Authorization": "Bearer " + token["access_token"]}, timeout=(15, 60))
    info_response.raise_for_status()
    blogs = info_response.json().get("response", {}).get("user", {}).get("blogs", [])
    names = {str(x.get("name", "")).lower() for x in blogs}
    urls = {str(x.get("url", "")).lower() for x in blogs}
    if EXPECTED_BLOG not in names and not any(EXPECTED_BLOG in url for url in urls):
        raise RuntimeError("Authorized Tumblr account does not control dailyyield-official")
    safe_bundle = {
        "access_token": token["access_token"], "refresh_token": token["refresh_token"],
        "expires_in": token.get("expires_in"), "scope": token.get("scope"),
        "token_type": token.get("token_type", "bearer"),
    }
    encrypted = Fernet(required("TUMBLR_TOKEN_ENCRYPTION_KEY").encode()).encrypt(json.dumps(safe_bundle).encode())
    TOKEN_FILE.write_bytes(encrypted + b"\n")
    print(f"Tumblr OAuth verified for {EXPECTED_BLOG}; encrypted offline token bundle created.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"TUMBLR_OAUTH_BOOTSTRAP_ERROR: {exc}", file=sys.stderr)
        raise
