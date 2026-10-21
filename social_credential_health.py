#!/usr/bin/env python3
"""Record, in the repository itself, whether each social network can actually publish.

Every social failure in this project used to arrive as one line in a GitHub run - "Process
completed with exit code 1" - and then vanished, because Actions job output cannot be read from
outside the repository. Twenty-two social runs failed that way on 20 October 2026 with no stated
reason, and nine of the day's thirty-six posts were never delivered.

This module fixes the invisibility, not the quality gate. A channel job calls it after the
publisher runs; the platform's own words are stripped of anything token-shaped and written to
``SOCIAL_CREDENTIAL_HEALTH.json``. ``social_guard.blocked_platforms()`` already reads that file and
stops dispatching to a network recorded as broken, so a dead credential stops burning forty
retries a day and the day's report says why a post is missing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HEALTH = ROOT / "SOCIAL_CREDENTIAL_HEALTH.json"
IST = timezone(timedelta(hours=5, minutes=30), name="IST")
# Tumblr left social automation on 21 October 2026, so a record for it is never written and never
# read: a platform outside this tuple is refused rather than silently tracked as healthy.
PLATFORMS = ("facebook", "bluesky", "mastodon")

# The words that tell a human what broke, in the order they are worth reading.
USEFUL = re.compile(
    r"(?i)\b(?:error|failed|failure|denied|invalid|expired|unauthori[sz]ed|forbidden|"
    r"too many requests|rate limit|timeout|timed out|unreachable|not found|revoked|"
    r"insufficient|quota|conflict|unable|cannot|expected|missing|does not control)\b")
# Anything that could be a bearer token, refresh token or client secret is replaced before the
# line leaves the runner. The point is to make the reason readable, not to archive a credential.
SECRET_LIKE = re.compile(r"(?i)(bearer\s+[a-z0-9._\-]+|[a-z0-9+/_\-]{28,}=*)")


def scrub(value: str, limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = SECRET_LIKE.sub("[redacted]", text)
    return text[:limit]


def reason_from(path: Path) -> str:
    """The most useful line the publisher printed, or an empty string if it printed nothing."""
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return ""
    for line in reversed(lines):
        if line and USEFUL.search(line):
            return scrub(line)
    return ""


def record(platform: str, ok: bool, reason: str = "", path: Path = HEALTH) -> dict:
    """Merge one platform's state into the health file and return the row that was written."""
    if platform not in PLATFORMS:
        raise ValueError(f"unknown social platform {platform!r}")
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rows = {}
    if not isinstance(rows, dict):
        rows = {}
    row = {"ok": bool(ok), "checkedAtIST": datetime.now(IST).isoformat(timespec="seconds"),
           "reason": scrub(reason)}
    if ok:
        row["action"] = "none; the network is publishing"
    else:
        row["action"] = ("the owner must re-authorise this network's connection; the social guard "
                         "will hold its posts back and keep counting them as missing until then")
    rows[platform] = row
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument("--code", type=int, default=0, help="the publisher's exit code")
    parser.add_argument("--output", default="", help="captured publisher output, for the reason line")
    parser.add_argument("--extract", action="store_true", help="print the reason line and change nothing")
    parser.add_argument("--file", default=str(HEALTH))
    arguments = parser.parse_args()

    path = Path(arguments.file)
    reason = reason_from(Path(arguments.output)) if arguments.output else ""
    if arguments.extract:
        print(reason)
        return 0
    row = record(arguments.platform, arguments.code == 0, reason, path)
    print(json.dumps({"platform": arguments.platform, **row}, ensure_ascii=False))
    # Never fail a social job over its own bookkeeping.
    return 0


if __name__ == "__main__":
    sys.exit(main())
