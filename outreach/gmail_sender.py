#!/usr/bin/env python3
"""Fail-closed Gmail API sender for source-verified Daily Yield outreach.

The workflow reserves every message in Git before calling Gmail. A reserved
message is never automatically reserved again, preventing repeats if a runner
fails after Gmail accepts a message but before result persistence.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from zoneinfo import ZoneInfo

import editorial_outreach as outreach

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
OUTBOX = outreach.OUTREACH / "outbox"
FIELDS = ["interaction_id", "prospect_id", "email", "message_fingerprint", "status", "created_at", "updated_at", "follow_up_count", "notes"]
IST = ZoneInfo("Asia/Kolkata")


def now() -> datetime:
    return datetime.now(IST)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required GitHub secret: {name}")
    return value


def lock() -> dict:
    return json.loads(outreach.SEND_LOCK.read_text(encoding="utf-8"))


def require_enabled() -> dict:
    settings = lock()
    if settings.get("sending_enabled") is not True or settings.get("gmail_oauth_configured") is not True:
        raise RuntimeError("send lock is closed")
    if settings.get("tracking_pixels_allowed") is not False or settings.get("synthetic_pageviews_allowed") is not False:
        raise RuntimeError("privacy or zero-view invariant violated")
    return settings


def access_token() -> str:
    form = urllib.parse.urlencode({
        "client_id": required("GMAIL_CLIENT_ID"),
        "client_secret": required("GMAIL_CLIENT_SECRET"),
        "refresh_token": required("GMAIL_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request(TOKEN_URL, data=form, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            raw = json.loads(exc.read().decode("utf-8", "replace"))
            safe = {k: raw.get(k) for k in ("error", "error_description") if raw.get(k)}
        except Exception:
            safe = {"response": "non-JSON OAuth error"}
        raise RuntimeError(f"Gmail OAuth refresh failed: HTTP {exc.code}; {safe}") from exc
    token = payload.get("access_token", "")
    if not token:
        raise RuntimeError("Google returned no Gmail access token")
    granted = set(str(payload.get("scope", GMAIL_SEND_SCOPE)).split())
    if GMAIL_SEND_SCOPE not in granted:
        raise RuntimeError("OAuth grant does not include gmail.send")
    return token


def auth_check() -> int:
    access_token()
    print("Gmail OAuth refresh succeeded; gmail.send is available; no message sent")
    return 0


def read_interactions() -> list[dict[str, str]]:
    return outreach.read_csv(outreach.INTERACTIONS)


def write_interactions(rows: list[dict[str, str]]) -> None:
    temporary = outreach.INTERACTIONS.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{key: row.get(key, "") for key in FIELDS} for row in rows])
    temporary.replace(outreach.INTERACTIONS)


def reserve() -> int:
    settings = require_enabled()
    errors = outreach.registry_errors()
    if errors:
        raise RuntimeError("outreach registry invalid: " + "; ".join(errors))
    rows = read_interactions()
    today = now().date().isoformat()
    already_today = sum(1 for row in rows if row.get("created_at", "").startswith(today) and row.get("status") in {"reserved", "sent"})
    remaining = max(0, int(settings["max_initial_messages_per_day"]) - already_today)
    if not remaining:
        print("Daily outreach limit already reached; reserved=0")
        return 0

    result = outreach.draft(remaining)
    if result:
        return result
    manifest = json.loads(outreach.MANIFEST.read_text(encoding="utf-8"))
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = now().isoformat(timespec="seconds")
    prospects = {row["prospect_id"]: row for row in outreach.read_csv(outreach.PROSPECTS)}
    reserved = 0
    for item in manifest.get("selected", []):
        if prospects.get(item["prospect_id"], {}).get("automation_mode") != "auto_approved":
            continue
        fingerprint = item["fingerprint"]
        if any(row.get("message_fingerprint") == fingerprint or row.get("email", "").lower() == item["email"].lower() for row in rows):
            continue
        source = outreach.ROOT / item["draft"]
        message = BytesParser(policy=policy.default).parsebytes(source.read_bytes())
        if message.get("X-Daily-Yield-State"):
            message.replace_header("X-Daily-Yield-State", "RESERVED-BEFORE-SEND")
        message["Reply-To"] = "dailyyield.official@gmail.com"
        message["Message-ID"] = f"<dailyyield-{fingerprint[:32]}@gmail.com>"
        destination = OUTBOX / f"{fingerprint}.eml"
        destination.write_bytes(message.as_bytes(policy=policy.SMTP))
        rows.append({
            "interaction_id": f"{now().strftime('%Y%m%d%H%M%S')}-{item['prospect_id']}",
            "prospect_id": item["prospect_id"], "email": item["email"],
            "message_fingerprint": fingerprint, "status": "reserved",
            "created_at": stamp, "updated_at": stamp, "follow_up_count": "0",
            "notes": "Reserved and persisted before Gmail API send",
        })
        reserved += 1
    write_interactions(rows)
    print(json.dumps({"reserved": reserved, "daily_remaining_before_reservation": remaining, "sent": 0}))
    return 0


def gmail_send(token: str, raw_message: bytes) -> dict:
    encoded = base64.urlsafe_b64encode(raw_message).decode().rstrip("=")
    request = urllib.request.Request(
        SEND_URL,
        data=json.dumps({"raw": encoded}).encode(),
        method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", "replace"))
            error = payload.get("error", {})
            safe = {"status": error.get("status"), "message": error.get("message")}
        except Exception:
            safe = {"response": "non-JSON Gmail API error"}
        raise RuntimeError(f"Gmail send failed: HTTP {exc.code}; {safe}") from exc


def send_reserved() -> int:
    require_enabled()
    token = access_token()
    prospects = {row["prospect_id"]: row for row in outreach.read_csv(outreach.PROSPECTS)}
    suppressions = {row["email"].lower() for row in outreach.read_csv(outreach.SUPPRESSIONS) if row.get("email")}
    rows = read_interactions()
    sent = 0
    for row in rows:
        if row.get("status") != "reserved":
            continue
        prospect = prospects.get(row["prospect_id"])
        if not prospect or prospect["eligibility"] != "eligible" or prospect["automation_mode"] != "auto_approved":
            row["status"] = "blocked_after_reservation"
            row["notes"] = "Eligibility changed before send"
            row["updated_at"] = now().isoformat(timespec="seconds")
            write_interactions(rows)
            continue
        if row["email"].lower() in suppressions:
            row["status"] = "suppressed"
            row["notes"] = "Suppression added before send"
            row["updated_at"] = now().isoformat(timespec="seconds")
            write_interactions(rows)
            continue
        path = OUTBOX / f"{row['message_fingerprint']}.eml"
        if not path.exists():
            row["status"] = "needs_review"
            row["notes"] = "Reserved outbox message missing; automatic retry prohibited"
            row["updated_at"] = now().isoformat(timespec="seconds")
            write_interactions(rows)
            continue
        try:
            result = gmail_send(token, path.read_bytes())
        except Exception as exc:
            row["status"] = "needs_review"
            row["notes"] = str(exc)[:500]
            row["updated_at"] = now().isoformat(timespec="seconds")
            write_interactions(rows)
            raise
        row["status"] = "sent"
        row["updated_at"] = now().isoformat(timespec="seconds")
        row["notes"] = json.dumps({"gmail_message_id": result.get("id", ""), "gmail_thread_id": result.get("threadId", "")})
        write_interactions(rows)
        sent += 1
    print(json.dumps({"sent": sent, "automatic_retries": 0}))
    return 0


def verify_daily() -> int:
    settings = require_enabled()
    today = now().date().isoformat()
    rows = read_interactions()
    sent = [row for row in rows if row.get("created_at", "").startswith(today) and row.get("status") == "sent"]
    target = int(settings["max_initial_messages_per_day"])
    result = {"date": today, "sent": len(sent), "target": target, "status": "PASS" if len(sent) == target else "SHORTFALL"}
    print(json.dumps(result))
    if len(sent) != target:
        raise RuntimeError(f"daily outreach shortfall: sent {len(sent)} of {target}; replenish verified eligible prospects")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("auth-check", "reserve", "send-reserved", "verify-daily"))
    args = parser.parse_args()
    if args.command == "auth-check":
        return auth_check()
    if args.command == "reserve":
        return reserve()
    if args.command == "verify-daily":
        return verify_daily()
    return send_reserved()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"EDITORIAL_OUTREACH_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
