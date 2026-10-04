#!/usr/bin/env python3
"""Zero-view Daily Yield security and integrity monitor.

This is detection, evidence, backup and fail-closed alerting—not a claim that a
scheduled GitHub runner is a real-time WAF. Blogger content is read only through
the authenticated Blogger API; the public website is never requested.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")
BASELINE = ROOT / "SECURITY_BASELINE.json"
STATUS_JSON = ROOT / "SECURITY_STATUS.json"
STATUS_MD = ROOT / "SECURITY_STATUS.md"
BACKUP = ROOT / "SECURITY_BACKUP.json.gz"

CRITICAL_FILES = [
    "auto_blogger_publisher.py", "news_pipeline.py", "facebook_publisher.py",
    "social_creative.py", "zero_view_watchdog.py", "publication_preflight.py", "page_family.py",
    "brand_identity.py", "social_identity.py", "bluesky_publisher.py",
    "tumblr_publisher.py", "mastodon_publisher.py", "tumblr_oauth_bootstrap.py",
    "social_rotation.py", "dispatch_social_events.py", "persist_social_state.sh",
    "social_performance.py", ".github/workflows/social_performance.yml",
    ".github/workflows/coordinated_social_publish.yml",
    ".github/workflows/daily_blogger_poster.yml", ".github/workflows/daily_news_wires.yml",
    ".github/workflows/facebook_publisher.yml", ".github/workflows/bluesky_publisher.yml",
    ".github/workflows/tumblr_publisher.yml", ".github/workflows/mastodon_publisher.yml",
    "security_guard.py", "audit_site_enhancements.py", "search_reach.py",
    "bing_url_automation.py", "apply_site_enhancements.py", "update_page_family.py", "SEO_EXPERIENCE_REQUIREMENTS.md",
    "theme/Daily-Yield-Theme-Subscription.xml",
    "theme/Daily-Yield-Theme-v4-2026-10-01.xml",
    "outreach/editorial_outreach.py", "outreach/gmail_sender.py",
    "outreach/prospects.csv", "outreach/send_lock.json",
    "outreach/suppressions.csv",
]
MALICIOUS_PATTERNS = {
    "external script loader": re.compile(r"<script\b[^>]*\bsrc\s*=", re.I),
    "iframe/object/embed injection": re.compile(r"<(?:iframe|object|embed)\b", re.I),
    "javascript URL": re.compile(r"(?:href|src)\s*=\s*[\"']\s*javascript:", re.I),
    "cookie theft primitive": re.compile(r"document\.cookie", re.I),
    "dynamic-code primitive": re.compile(r"\b(?:eval|atob)\s*\(|fromCharCode\s*\(", re.I),
    "socket/miner primitive": re.compile(r"WebSocket\s*\(|coinhive|cryptonight|webmine", re.I),
    "event-handler injection": re.compile(r"\bonerror\s*=", re.I),
}
SECRET_PATTERNS = {
    "GitHub token": re.compile(r"\b(?:gh[oprsu]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "Google OAuth token": re.compile(r"\bya29\.[A-Za-z0-9._-]{20,}\b"),
    "Meta token": re.compile(r"\bEA[A-Za-z0-9]{60,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required secret: {name}")
    return value


def request_json(url: str, *, method: str = "GET", headers: dict | None = None, body=None) -> dict:
    if "dailyyield.blogspot.com" in url.lower():
        raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def oauth() -> str:
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)["access_token"]
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", "replace"))
            safe = {key: payload.get(key) for key in ("error", "error_description") if payload.get(key)}
        except Exception:
            safe = {"response": "non-JSON Google OAuth error"}
        raise RuntimeError(f"Google OAuth token refresh failed: HTTP {exc.code}; safe details: {safe}") from exc


def blogger_inventory() -> tuple[dict, dict]:
    token = oauth()
    headers = {"Authorization": "Bearer " + token}
    metadata = request_json(
        f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}?fields=id,name,url,updated,posts(totalItems),pages(totalItems)",
        headers=headers,
    )
    inventory = {}
    full_backup = {"capturedAt": datetime.now(timezone.utc).isoformat(), "blog": metadata, "items": []}
    for resource in ("pages", "posts"):
        page_token = ""
        while True:
            fields = "id,title,url,content,published,updated,status"
            params = {"status": "live", "fetchBodies": "true", "maxResults": "50", "fields": f"items({fields}),nextPageToken"}
            if page_token:
                params["pageToken"] = page_token
            data = request_json(
                f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/{resource}?{urllib.parse.urlencode(params)}",
                headers=headers,
            )
            for item in data.get("items", []):
                content = item.get("content", "")
                key = f"{resource[:-1]}:{item.get('id', '')}"
                inventory[key] = {
                    "kind": resource[:-1], "id": item.get("id", ""), "title": item.get("title", ""),
                    "url": item.get("url", ""), "updated": item.get("updated", ""),
                    "content_sha256": sha(content.encode("utf-8")),
                }
                full_backup["items"].append({**item, "kind": resource[:-1]})
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
    return inventory, full_backup


def repository_hashes() -> dict:
    paths = [ROOT / name for name in CRITICAL_FILES]
    paths.extend(sorted((ROOT / ".github" / "workflows").glob("*.yml")))
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths if path.exists()}


def secret_scan() -> list[str]:
    findings = []
    # Scan executable/configuration sources. Generated article HTML can contain
    # long embedded image/data strings that resemble provider tokens but cannot
    # grant repository or platform access.
    extensions = {".py", ".yml", ".yaml", ".js", ".sh"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in extensions:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label} detected in tracked file {path.relative_to(ROOT)}")
    return findings


def content_threats(backup: dict) -> list[str]:
    findings = []
    for item in backup["items"]:
        content = item.get("content", "")
        for label, pattern in MALICIOUS_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{label}: {item.get('kind')} {item.get('title')} [{item.get('id')}]")
    return findings


def write_report(status: str, critical: list[str], warnings: list[str], details: dict) -> None:
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(), "status": status,
        "mode": "BLOGGER_API_ZERO_PUBLIC_VIEWS", "syntheticViews": 0,
        "critical": critical, "warnings": warnings, "details": details,
    }
    STATUS_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Daily Yield Security Guard", "", f"- **Status:** {status}",
        f"- **Checked:** {report['checkedAt']}", "- **Public website requests:** 0", "",
        "## Critical findings",
    ]
    lines += [f"- {x}" for x in critical] or ["- None"]
    lines += ["", "## Warnings"] + ([f"- {x}" for x in warnings] or ["- None"])
    lines += ["", "## Scope", "- Authenticated Blogger API content integrity", "- Critical GitHub workflow/source hashes", "- Credential-pattern scanning", "- Malicious-injection pattern scanning", "- Deletion and unauthorized-edit detection", ""]
    STATUS_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--approve-current", action="store_true", help="Approve current repository and Blogger hashes after intentional content maintenance")
    parser.add_argument("--approve-repository", action="store_true", help="Approve the checked-out main-branch repository change only; Blogger mutations remain fail-closed")
    args = parser.parse_args()

    current_repo = repository_hashes()
    current_items, full_backup = blogger_inventory()
    previous = json.loads(BASELINE.read_text()) if BASELINE.exists() else {"repository": {}, "blogger": {}}
    critical, warnings = [], []

    previous_repo = previous.get("repository", {})
    if previous_repo and previous_repo != current_repo and not (args.approve_current or args.approve_repository):
        changed = sorted({*previous_repo, *current_repo} - {k for k in previous_repo.keys() & current_repo.keys() if previous_repo[k] == current_repo[k]})
        critical.append("critical repository files changed without baseline approval: " + ", ".join(changed[:20]))

    previous_items = previous.get("blogger", {})
    removed = sorted(set(previous_items) - set(current_items))
    changed_items = sorted(key for key in previous_items.keys() & current_items.keys() if previous_items[key].get("content_sha256") != current_items[key].get("content_sha256"))
    if previous_items and removed:
        critical.append("live Blogger items removed: " + ", ".join(removed[:20]))
    if previous_items and changed_items and not args.approve_current:
        critical.append("existing Blogger content changed without baseline approval: " + ", ".join(changed_items[:20]))

    critical.extend(secret_scan())
    critical.extend(content_threats(full_backup))
    new_items = sorted(set(current_items) - set(previous_items))
    if new_items:
        warnings.append(f"{len(new_items)} new live item(s) accepted after threat scan")

    status = "FAIL" if critical else "PASS"
    details = {
        "pages": sum(x["kind"] == "page" for x in current_items.values()),
        "posts": sum(x["kind"] == "post" for x in current_items.values()),
        "newItems": len(new_items), "changedItems": len(changed_items), "removedItems": len(removed),
        "repositoryFiles": len(current_repo), "backupCreated": bool(args.backup),
        "repositoryChangeApproved": bool(args.approve_repository or args.approve_current),
        "bloggerChangeApproved": bool(args.approve_current),
    }
    if args.backup:
        with gzip.open(BACKUP, "wt", encoding="utf-8") as archive:
            json.dump(full_backup, archive, ensure_ascii=False)
    if not critical or args.approve_current:
        BASELINE.write_text(json.dumps({
            "version": 1, "approvedAt": datetime.now(timezone.utc).isoformat(),
            "repository": current_repo, "blogger": current_items,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(status, critical, warnings, details)
    print(json.dumps({"status": status, **details}))
    return 1 if critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
