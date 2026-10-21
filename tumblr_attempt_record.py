#!/usr/bin/env python3
"""Remember that a Tumblr authorisation was attempted, without remembering the code.

The owner's second attempt on 21 October 2026 failed with "The authorization code has expired" for a
mundane reason: the workflow was pressed again while the secret still held the code from the first
attempt, and a Tumblr code is single-use and retired within minutes. No amount of re-running can
revive it, so the useful thing the run page can do is name that exact situation instead of repeating
the same four words.

This records a short SHA-256 fingerprint of the value that was used - never the value itself, which
would put a live credential into the history of a public repository - so a repeated attempt can be
called out as "the same code as last time".
"""
from __future__ import annotations

import argparse
import hashlib
import re
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
RECORD = Path(__file__).resolve().parent / "TUMBLR_OAUTH_ATTEMPT.json"


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def previous_fingerprint() -> str:
    try:
        return str(json.loads(RECORD.read_text(encoding="utf-8")).get("fingerprint", ""))
    except Exception:
        return ""


CODE_SHAPED = re.compile(r"^[0-9a-f]{24,}$")


def read_reason(path: str) -> str:
    """The last line of the captured error, unless that line *is* a credential.

    A reason is kept so the run page and the repository agree about what Tumblr objected to. A bare
    one-time code or token must never be stored, so anything shaped like one is dropped rather than
    committed into a public repository's history.
    """
    if not path:
        return ""
    try:
        lines = [line.strip() for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()]
    except Exception:
        return ""
    line = lines[-1] if lines else ""
    return "" if CODE_SHAPED.match(line) else line[:400]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("previous", "record"))
    parser.add_argument("--fingerprint", default="", help="12 hex characters, never the code itself")
    parser.add_argument("--code", type=int, default=0, help="the exchange step's exit code")
    parser.add_argument("--reason-file", default="", help="file holding the message to keep")
    args = parser.parse_args()

    if args.action == "previous":
        print(previous_fingerprint())
        return 0

    record = {
        "fingerprint": args.fingerprint,
        "attemptedAtIST": datetime.now(IST).isoformat(timespec="seconds"),
        "outcome": "exchanged" if args.code == 0 else "refused by Tumblr",
        "reason": read_reason(args.reason_file),
    }
    RECORD.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("authorisation attempt recorded: fingerprint only, never the code or a token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
