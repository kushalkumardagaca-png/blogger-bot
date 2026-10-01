#!/usr/bin/env python3
"""Submit newly published Blogger destinations to the coordinated social router."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

EVENTS = Path("social_events.json")
WORKFLOW = "coordinated_social_publish.yml"


def main() -> int:
    if not EVENTS.exists():
        print("No social event file; nothing dispatched.")
        return 0
    events = json.loads(EVENTS.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise RuntimeError("social event file is not a list")
    seen = set()
    for event in events:
        key = str(event.get("item_key", ""))
        url = str(event.get("target_url", ""))
        mode = str(event.get("content_mode", "post"))
        published = str(event.get("published_at", ""))
        if not key or not url.startswith("https://dailyyield.blogspot.com/") or mode != "post":
            raise RuntimeError(f"invalid social event: {event}")
        fingerprint = (key, url)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        subprocess.run([
            "gh", "workflow", "run", WORKFLOW,
            "-f", f"item_key={key}",
            "-f", f"target_url={url}",
            "-f", f"content_mode={mode}",
            "-f", f"published_at={published}",
        ], check=True)
        print(f"Dispatched {key}: {url}")
    print(f"Dispatched {len(seen)} coordinated social event(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
