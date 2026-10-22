#!/usr/bin/env python3
"""Decide whether a pending Master recovery request still needs a writer run, and say so in one line.

Why this file exists. `.github/master-recovery-request` is the route this repository uses to recover a
Master slot that the day's schedule did not deliver, and it is triggered by a push to that path. On 22
October two requests were pushed inside an hour and honoured by nobody, because the commits that wrote
them carried a skip marker in their messages and GitHub therefore ignored the push outright: a route that
depends on the *absence* of a string in a commit message is not a route. The fix is not to forbid the
marker - the rest of the repository relies on it - but to ask the same question on a timer as well, from
the site's own records rather than from the event that woke it.

Which is also why the timer cannot simply dispatch unconditionally. A request that has already been
honoured, or is being honoured right now, must not start a second writer for the same slot: that is how a
recovery turns into a duplicate article. So the answer is "dispatch" only when the slot has no confirmed
live article for today, the plan belongs to today, no writer run is already active, and the request is
still young enough to be worth honouring. Where the records cannot be read the answer is still "dispatch",
because the writer re-checks for a live keeper before it publishes anything and an extra attempt is
cheap, while a slot that no one tries again is lost.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re, sys, urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
IST = ZoneInfo("Asia/Kolkata")
REQUEST = ROOT / ".github" / "master-recovery-request"
PLAN = ROOT / "MASTER_DAILY_PLAN.json"
TRACKER = ROOT / "MASTER_AUTOMATION_TRACKER.json"
WRITERS = {"evergreen": "master_evergreen_writer.yml", "trending": "master_trending_writer.yml"}
SUPPORTED = re.compile(r"^(evergreen|trending):([0-4])$")
DEFAULT_TTL_MINUTES = 90


def read_request(path: Path = REQUEST) -> tuple:
    """Return (kind, slot) from the request file, or (None, reason) when there is nothing to honour."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None, "no request file"
    value = re.sub(r"\s+", "", raw)
    match = SUPPORTED.match(value)
    if not match:
        return None, f"unusable request {value[:40]!r}: write evergreen:0-4 or trending:0-4"
    return match.group(1), int(match.group(2))


def json_file(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def slot_is_live(kind: str, slot: int, plan: dict, tracker: dict, today: dt.date) -> bool:
    """True when the day already has a confirmed live article in that slot.

    The plan date is checked first: an old plan cannot vouch for today, and a request left over from
    yesterday must not wake a writer for a day the pipeline refuses to publish anyway.
    """
    if str(plan.get("date") or "") != str(today):
        return False
    try:
        from master_slot_state import keeper_for_slot
    except ImportError:
        return False
    return bool(keeper_for_slot(plan, (tracker or {}).get("published", []), kind, slot))


def active_writer_run(runs_url: str, workflow_file: str, token: str = "") -> bool:
    """True when a writer run for this slot's workflow is queued or running right now."""
    url = f"{runs_url}?per_page=20&status=in_progress"
    request = urllib.request.Request(url, headers={"User-Agent": "master-recovery-request",
                                                   "Accept": "application/vnd.github+json"})
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            rows = (json.loads(answer.read().decode("utf-8")) or {}).get("workflow_runs", [])
        request = urllib.request.Request(f"{runs_url}?per_page=20&status=queued", headers=request.headers)
        with urllib.request.urlopen(request, timeout=30) as answer:
            rows += (json.loads(answer.read().decode("utf-8")) or {}).get("workflow_runs", [])
    except Exception:
        return False
    names = (workflow_file.replace(".yml", ""), workflow_file.replace(".yml", "").replace("_", " "))
    for run in rows:
        path = str(run.get("path") or "")
        name = str(run.get("name") or "").casefold()
        if path.endswith(workflow_file) or any(part.casefold() in name for part in names if len(part) > 8):
            return True
    return False


def decide(kind, slot, plan, tracker, *, today, requested_min_ago, writer_active,
           ttl_minutes: int = DEFAULT_TTL_MINUTES) -> dict:
    """The whole rule, in one place, so it can be tested without a repository or a network."""
    if kind is None:
        return {"dispatch": False, "note": slot or "nothing requested"}
    if requested_min_ago is not None and requested_min_ago > ttl_minutes:
        return {"dispatch": False, "note": f"request is {int(requested_min_ago)} minutes old and expired "
                                           "after {0}; the day's own guarantee job is the route from here".format(ttl_minutes)}
    if slot_is_live(kind, slot, plan, tracker, today):
        return {"dispatch": False, "note": "the slot already has a confirmed live article"}
    if writer_active:
        return {"dispatch": False, "note": "a writer run is already working on this kind"}
    return {"dispatch": True, "kind": kind, "slot": slot, "file": WRITERS[kind],
            "note": "no live article for the requested slot today"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-url", default="")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--requested-at", type=int, default=0, help="unix seconds of the last commit to the request file")
    parser.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)
    args = parser.parse_args()
    kind, slot = read_request()
    minutes = None
    if args.requested_at:
        minutes = max(0.0, (dt.datetime.now(dt.timezone.utc).timestamp() - args.requested_at) / 60.0)
    plan = json_file(PLAN, {})
    tracker = json_file(TRACKER, {})
    writer_file = WRITERS.get(kind or "", "")
    active = bool(args.runs_url and writer_file and active_writer_run(args.runs_url, writer_file, args.token))
    verdict = decide(kind, slot if isinstance(slot, int) else None, plan, tracker,
                     today=dt.datetime.now(IST).date(), requested_min_ago=minutes,
                     writer_active=active, ttl_minutes=args.ttl_minutes)
    out = os.environ.get("GITHUB_OUTPUT")
    lines = [f"dispatch={'true' if verdict['dispatch'] else 'false'}",
             f"note={verdict['note']}",
             f"kind={verdict.get('kind', '')}", f"slot={verdict.get('slot', '')}",
             f"file={verdict.get('file', '')}"]
    for line in lines:
        if out:
            Path(out).open("a", encoding="utf-8").write(line + "\n")
        print(line)
    if not verdict["dispatch"]:
        print(f"nothing to recover: {verdict['note']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    main()
