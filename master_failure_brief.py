#!/usr/bin/env python3
"""Write the one-line reason a Master run stopped, into a file the morning check can read.

Nothing here repairs or retries anything. It exists because a failed preparation run used to lose its
own explanation: the run wrote `MASTER_AUTOMATION_STATUS.json` in its workspace, but the step that
commits files is skipped whenever the run fails, so by the next morning the only evidence left was a
list of red runs and no reason. The owner asked what failed and why; that question should not need a
GitHub token to answer.

Only this one file is written, it is overwritten by the next failure and cleared by the next success,
and it never holds a credential - the status file it reads holds a message and a stage name.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

STATUS = pathlib.Path("MASTER_AUTOMATION_STATUS.json")
BRIEF = pathlib.Path("MASTER_FAILURE_BRIEF.json")


def read_status(path: pathlib.Path = STATUS) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def brief_for(status: dict, workflow: str, kind: str, slot: str, run_id: str) -> dict:
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workflow": workflow,
        "kind": kind,
        "slot": slot,
        "run": run_id,
        "stage": str(status.get("stage") or status.get("step") or "preparation"),
        "status": str(status.get("status") or "FAIL"),
        "error_type": str(status.get("error_type") or ""),
        "error": " ".join(str(status.get("error") or "no persisted reason").split())[:900],
        "minutes_used": status.get("minutes_used", status.get("elapsed_minutes", "")),
        "published_after_this": False,
        "note": "the run published nothing; the day's slot stays open for the recovery cycle",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", default="master")
    ap.add_argument("--kind", default="")
    ap.add_argument("--slot", default="")
    ap.add_argument("--run", default="")
    ap.add_argument("--status-file", default=str(STATUS))
    ap.add_argument("--out", default=str(BRIEF))
    a = ap.parse_args()
    row = brief_for(read_status(pathlib.Path(a.status_file)), a.workflow, a.kind or "master", a.slot, a.run)
    pathlib.Path(a.out).write_text(json.dumps(row, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(row, ensure_ascii=False)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
