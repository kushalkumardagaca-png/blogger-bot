#!/usr/bin/env python3
"""Rendered navigation is permanently disabled by the zero-view policy."""
from pathlib import Path
import json

report = {
    "mode": "DISABLED_ZERO_VIEW_POLICY",
    "failures": 0,
    "rendered_checks": 0,
    "synthetic_views": 0,
    "reason": "Opening public Daily Yield pages would create synthetic pageviews. Use authenticated API and static source audits instead.",
}
Path("RENDERED_SITE_AUDIT.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
