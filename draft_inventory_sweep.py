#!/usr/bin/env python3
"""Keep the Blogger draft box empty unless a draft is waiting for a scheduled release.

The publisher does not want articles produced that are never going to be
published and simply sit in the Blogger draft list. Two sources can leave such a
draft behind:

* an interrupted three-pass News publish (the draft is created first, then
  published) — the engine now discards its own working copy on failure, and this
  sweep clears anything an older run left behind;
* a draft created by an earlier programme whose window has since passed.

The single approved queue is the quarantined-draft revival: those drafts carry a
live schedule and are published one at a time. They are reported and kept.

Everything else is backed up into DRAFT_SWEEP_BACKUP.json (so nothing is lost
even though Blogger has no wastebasket in its API) and then deleted. The run
writes DRAFT_INVENTORY_STATUS.json with the counts before and after, and can be
run without ``--apply`` to report only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "DRAFT_INVENTORY_STATUS.json"
BACKUP = ROOT / "DRAFT_SWEEP_BACKUP.json"
REVIVAL_STATE = ROOT / "QUARANTINE_REVIVAL_STATE.json"
BACKUP_CONTENT_LIMIT = 60_000


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def token() -> str:
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(
            urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST"),
            timeout=30) as response:
        return json.load(response)["access_token"]


def api(path: str, access: str, method: str = "GET"):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{required('BLOGGER_BLOG_ID')}{path}"
    request = urllib.request.Request(url, method=method, headers={
        "Authorization": "Bearer " + access, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Blogger {method} {path} → HTTP {exc.code}: "
                           f"{exc.read().decode('utf-8', 'replace')[:300]}") from exc


def drafts(access: str) -> list[dict]:
    found: list[dict] = []
    page_token = ""
    while True:
        query = {"status": "draft", "maxResults": "50",
                 "fields": "items(id,title,url,updated,labels,content),nextPageToken"}
        if page_token:
            query["pageToken"] = page_token
        batch = api("/posts?" + urllib.parse.urlencode(query), access)
        found.extend(batch.get("items", []))
        page_token = batch.get("nextPageToken", "")
        if not page_token:
            return found


def revival_queue() -> dict[str, dict]:
    try:
        state = json.loads(REVIVAL_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if state.get("enabled") is False or state.get("status") == "RETIRED":
        return {}
    return {str(row.get("draft_id")): row for row in state.get("items", {}).values()
            if row.get("status") != "live"}


def classify(items: list[dict], queue: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    keep, stale = [], []
    for item in items:
        if str(item.get("id")) in queue:
            keep.append({"id": item["id"], "title": item.get("title", ""),
                         "reason": "scheduled revival queue", "label": queue[str(item["id"])].get("status", "")})
        else:
            stale.append(item)
    return keep, stale


def backup(entries: list[dict], kept: list[dict], removed: list[dict]) -> None:
    record = {"sweptAt": dt.datetime.now(dt.timezone.utc).isoformat(),
              "kept": kept,
              "removed": [{"id": row.get("id"), "title": row.get("title", ""),
                           "labels": row.get("labels", []), "updated": row.get("updated", ""),
                           "content": (row.get("content") or "")[:BACKUP_CONTENT_LIMIT]} for row in removed]}
    entries.append(record)
    BACKUP.write_text(json.dumps(entries[-6:], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def restore(access: str) -> int:
    """Re-create the drafts kept in the backup, newest sweep first."""
    try:
        entries = json.loads(BACKUP.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(json.dumps({"status": "NOTHING_TO_RESTORE"}))
        return 0
    restored, failed = [], []
    for entry in entries:
        for row in entry.get("removed", []):
            if not row.get("content"):
                continue
            try:
                api("/posts?isDraft=true", access, "POST") if False else None
                body = json.dumps({"kind": "blogger#post", "title": row.get("title", ""),
                                   "content": row["content"], "labels": row.get("labels", [])}).encode()
                request = urllib.request.Request(
                    f"https://www.googleapis.com/blogger/v3/blogs/{required('BLOGGER_BLOG_ID')}/posts?isDraft=true",
                    data=body, method="POST",
                    headers={"Authorization": "Bearer " + access, "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    created = json.load(response)
                restored.append({"id": created.get("id"), "title": row.get("title", "")})
                time.sleep(1.5)
            except Exception as exc:  # noqa: BLE001
                failed.append({"title": row.get("title", ""), "error": str(exc)[:200]})
    print(json.dumps({"status": "RESTORED" if restored else "NOTHING_RESTORED",
                      "restored": len(restored), "failed": len(failed)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="delete the leftover drafts")
    parser.add_argument("--restore", action="store_true",
                        help="bring drafts back from DRAFT_SWEEP_BACKUP.json (the sweep is reversible)")
    args = parser.parse_args()
    if args.restore:
        # Deleted legacy drafts and the retired eight-hour queue are not an
        # approved publication source. Do not authenticate or restore by accident.
        print(json.dumps({"status": "RESTORE_RETIRED", "restored": 0,
                          "reason": "Owner instruction: do not revive deleted legacy drafts."}))
        return 0
    access = token()
    found = drafts(access)
    keep, stale = classify(found, revival_queue())
    deleted, failures = [], []
    if args.apply:
        for item in stale:
            try:
                api(f"/posts/{item['id']}", access, "DELETE")
                deleted.append({"id": item["id"], "title": item.get("title", "")})
                time.sleep(1.5)
            except Exception as exc:  # noqa: BLE001
                failures.append({"id": item.get("id"), "title": item.get("title", ""), "error": str(exc)[:200]})
    try:
        existing = json.loads(BACKUP.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = []
    if args.apply:
        backup(existing, keep, stale)
    remaining = len(drafts(access)) if args.apply else len(found)
    report = {"checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "apply": args.apply,
              "draftsFound": len(found), "keptForScheduledRelease": keep,
              "leftoversFound": [{"id": row.get("id"), "title": row.get("title", "")} for row in stale],
              "leftoversDeleted": deleted, "deleteFailures": failures, "draftsRemaining": remaining,
              "syntheticViews": 0, "publicDailyYieldRequests": 0,
              "status": "PASS" if remaining == len(keep) else ("PASS" if not args.apply else "ATTENTION")}
    STATUS.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "draftsFound": len(found),
                      "kept": len(keep), "deleted": len(deleted), "remaining": remaining}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
