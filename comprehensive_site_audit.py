#!/usr/bin/env python3
"""Compatibility step: verify the zero-view audit already produced its evidence."""
from pathlib import Path
import json

required = [
    "HEALTH_STATUS.json",
    "HEALTH_REPORT.md",
    "COMPREHENSIVE_SITE_AUDIT.json",
    "COMPREHENSIVE_SITE_AUDIT.md",
]
missing = [path for path in required if not Path(path).exists()]
if missing:
    raise SystemExit("Zero-view audit evidence missing: " + ", ".join(missing))
status = json.loads(Path("HEALTH_STATUS.json").read_text())
if not status.get("zero_view") or status.get("synthetic_views") != 0:
    raise SystemExit("Zero-view policy evidence is absent or invalid")
print(json.dumps({"zero_view": True, "synthetic_views": 0, "evidence": "verified"}))
