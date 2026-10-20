#!/usr/bin/env python3
"""Turn a one-time Instagram authorisation code into a stored, encrypted token.

The owner pastes the code into the repository's secrets, never into a chat, runs this
workflow once, and the repository keeps the resulting long-lived token encrypted. The
publisher refreshes it before the 60-day expiry, so the connection does not silently
die. Nothing here stores a password, and no Daily Yield page is ever requested.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / "instagram_token.enc"
STATE = ROOT / "instagram_token_state.json"
TIMEOUT = (15, 60)


def required(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for this one-time bootstrap")
    return value


def main() -> int:
    mode = "verify" if "--verify" in sys.argv else "exchange"
    if mode == "verify":
        key = required("INSTAGRAM_TOKEN_ENCRYPTION_KEY")
        token = Fernet(key.encode()).decrypt(TOKEN_FILE.read_bytes()).decode().strip()
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        host = "graph.instagram.com" if (state.get("apiMode") or "instagram_login") != "facebook_login" \
            else "graph.facebook.com"
        user = state.get("ig_user_id") or ""
        response = requests.get(f"https://{host}/v26.0/{user}", params={"fields": "id,username,account_type",
                                                                        "access_token": token}, timeout=TIMEOUT)
        print(json.dumps({"ok": response.ok, "account": response.json() if response.ok else
                          str(response.text)[:220]}, ensure_ascii=False))
        return 0 if response.ok else 1

    client_id = required("INSTAGRAM_APP_ID")
    client_secret = required("INSTAGRAM_APP_SECRET")
    redirect = required("INSTAGRAM_REDIRECT_URI")
    code = required("INSTAGRAM_AUTHORIZATION_CODE")
    key = required("INSTAGRAM_TOKEN_ENCRYPTION_KEY")

    exchanged = requests.post("https://api.instagram.com/oauth/access_token",
                             data={"client_id": client_id, "client_secret": client_secret,
                                   "grant_type": "authorization_code", "redirect_uri": redirect, "code": code},
                             timeout=TIMEOUT)
    if not exchanged.ok:
        raise RuntimeError(f"Instagram refused the authorisation code: {exchanged.text[:280]}")
    short = exchanged.json()
    user_id = str(short.get("user_id") or "")
    short_token = short.get("access_token") or ""
    if not (user_id and short_token):
        raise RuntimeError("Instagram returned no user id or token")

    long_lived = requests.get("https://graph.instagram.com/v26.0/access_token",
                              params={"grant_type": "ig_exchange_token", "client_secret": client_secret,
                                      "access_token": short_token}, timeout=TIMEOUT)
    if not long_lived.ok:
        raise RuntimeError(f"long-lived exchange failed: {long_lived.text[:280]}")
    payload = long_lived.json()
    token = payload.get("access_token") or ""
    expires_in = int(payload.get("expires_in") or 5184000)

    debug = requests.get("https://graph.instagram.com/v26.0/debug_token",
                         params={"input_token": token},
                         headers={"Authorization": f"Bearer {client_id}|{client_secret}"}, timeout=TIMEOUT)
    scopes = []
    if debug.ok:
        data = debug.json().get("data") or {}
        scopes = sorted(data.get("scopes") or [])
        if not data.get("is_valid"):
            raise RuntimeError("Instagram returned a token that its own debugger calls invalid")
    if "instagram_business_content_publish" not in " ".join(scopes):
        raise RuntimeError("the approved token does not carry instagram_business_content_publish, so it "
                           "cannot publish; re-authorise with that permission and run this again")

    TOKEN_FILE.write_bytes(Fernet(key.encode()).encrypt(token.encode()))
    STATE.write_text(json.dumps({"version": 1, "ig_user_id": user_id, "apiMode": "instagram_login",
                                 "scopes": scopes,
                                 "expires_at": (dt.datetime.now(dt.timezone.utc)
                                                + dt.timedelta(seconds=expires_in)).isoformat(),
                                 "token_fingerprint": "sha256:"
                                 + __import__("hashlib").sha256(token.encode()).hexdigest()[:12],
                                 "bootstrap_at": dt.datetime.now(dt.timezone.utc).isoformat()},
                                indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "ig_user_id": user_id, "scopes": scopes,
                      "expires_at": json.loads(STATE.read_text())["expires_at"],
                      "tokenStoredEncrypted": str(TOKEN_FILE.name)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
