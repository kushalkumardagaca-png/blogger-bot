#!/usr/bin/env python3
"""Owner's AdSense/early-earnings change freeze. No time/env/force bypass."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY = ROOT / 'SITE_CHANGE_POLICY.json'


def policy() -> dict:
    try:
        data = json.loads(POLICY.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {'frozen': True}
    except (OSError, ValueError):
        return {'frozen': True}


def is_frozen() -> bool:
    # Explicit version-controlled owner release only; missing/malformed fails shut.
    return policy().get('frozen') is not False


def stop_if_frozen(action: str) -> None:
    if is_frozen():
        print(json.dumps({'status': 'HELD_BY_OWNER_FREEZE', 'action': action,
                          'siteWrites': 0, 'reason': 'AdSense review and early-earnings freeze; a new explicit owner-approved release is required.'}))
        raise SystemExit(0)
