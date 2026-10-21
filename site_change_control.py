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


def release_for(action: str) -> dict:
    """The owner's recorded release for one named action, or nothing at all.

    A release counts only when the versioned policy carries the owner's own instruction beside the
    action name, because the difference between a granted edit and an accident is the sentence that
    says which one it is.
    """
    for entry in policy().get('releasedCorrections') or []:
        if isinstance(entry, dict) and entry.get('action') == action and entry.get('ownerInstruction'):
            return entry
    return {}


def allowed(action: str) -> bool:
    return not is_frozen() or (action not in (policy().get('heldCliActions') or {}) and bool(release_for(action)))


def stop_if_frozen(action: str) -> None:
    # Fail shut in both directions: an action stays held while it is listed, and dropping a name from
    # the list unlocks nothing unless the same file records the owner's release for that action.
    if is_frozen() and not allowed(action):
        print(json.dumps({'status': 'HELD_BY_OWNER_FREEZE', 'action': action,
                          'siteWrites': 0, 'reason': 'AdSense review and early-earnings freeze; a new explicit owner-approved release is required.'}))
        raise SystemExit(0)
    if is_frozen():
        entry = release_for(action)
        print(json.dumps({'status': 'OWNER_RELEASED_CORRECTION', 'action': action,
                          'scope': entry.get('scope'), 'releasedAt': entry.get('releasedAt'),
                          'siteWrites': 'permitted for this scope only',
                          'note': 'every other action in heldCliActions and heldWorkflows stays held'}))


def main(argv: list) -> int:
    if len(argv) >= 3 and argv[1] == '--allowed':
        print('true' if allowed(argv[2]) else 'false')
        return 0
    print(json.dumps({'frozen': is_frozen(), 'heldActions': sorted((policy().get('heldCliActions') or {})),
                      'released': sorted(release for release in ((policy().get('releasedCorrections') or [{}])
                                                                  [0].get('action'),) if release)}))
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv))
