#!/usr/bin/env python3
"""Decide whether a pending News recovery request still needs a run, and say so in one line.

`.github/news-recovery-request` is the route this repository uses when a desk's edition did not appear:
write the desk slugs in the file, push, and the wires job is asked for those desks immediately. It is
triggered by a push to that path, which means *every* push that touches it re-honours whatever the file
happens to say - including a request from nine hours ago for two editions that have been live since
09:00. Before 23 October that meant a news run was dispatched, found nothing due, and its bookkeeping
was reported as a red run the owner had to read an email about.

So the answer is "dispatch" only when at least one requested desk has no live edition on the day's own
board. Where the board cannot be read, or is too old to be trusted, the answer stays "dispatch": a desk
nobody re-asked for is a missing edition, and an extra run that finds nothing due costs nothing the
reader sees. The desk list is filtered to what is actually missing, so a request for three desks whose
two are already live asks for one.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re, sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
IST = ZoneInfo("Asia/Kolkata")
REQUEST = ROOT / ".github" / "news-recovery-request"
BOARD = ROOT / "SLOT_GUARANTEE_STATUS.json"
DESKS = ("asia-pacific", "china", "india", "russia", "markets", "europe", "economy",
         "americas", "companies", "global", "banking")
STALE_MINUTES = 90


def read_request(path: Path = REQUEST) -> tuple[list[str], str]:
    """The desks asked for, in file order. Anything outside the eleven desks is dropped, not guessed."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return [], "no request file"
    wanted = [part.strip().casefold() for part in re.split(r"[,\s]+", raw) if part.strip()]
    unknown = [w for w in wanted if w not in DESKS]
    desks = [w for w in wanted if w in DESKS]
    if not desks:
        return [], ("no desk named" if not unknown else f"unrecognised desk(s): {', '.join(unknown[:4])}")
    return desks, (f"ignored {', '.join(unknown[:4])}" if unknown else "")


def board_state(path: Path = BOARD) -> tuple[dict[str, bool], str]:
    """{desk: live?} from the guarantee board, plus a note when the board cannot be trusted."""
    try:
        board = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"board unreadable ({type(exc).__name__})"
    note = ""
    stamp = str(board.get("generatedAt") or "")
    if stamp:
        try:
            when = dt.datetime.fromisoformat(stamp)
            if when.tzinfo is None:
                when = when.replace(tzinfo=IST)
            age = (dt.datetime.now(IST) - when).total_seconds() / 60
            if age > STALE_MINUTES:
                return {}, f"board is {int(age)} min old, past the {STALE_MINUTES}-minute trust window"
        except ValueError:
            note = "board timestamp unreadable"
    rows = {str(row.get("key") or ""): bool(row.get("live")) for row in board.get("rows") or []}
    if not rows:
        return {}, "board carries no slot rows"
    return rows, note


def decide(request_path: Path = REQUEST, board_path: Path = BOARD) -> dict:
    desks, ask_note = read_request(request_path)
    out = {"dispatch": False, "desks": "", "note": ""}
    if not desks:
        out["note"] = ask_note or "nothing requested"
        return out
    rows, board_note = board_state(board_path)
    if not rows:
        out.update(dispatch=True, desks=",".join(desks),
                   note=f"asking anyway; {board_note or 'no board'}" + (f"; {ask_note}" if ask_note else ""))
        return out
    missing = [d for d in desks if not rows.get(f"news-{d}")]
    live = [d for d in desks if rows.get(f"news-{d}")]
    if not missing:
        out["note"] = f"already live today: {', '.join(live)}"
        return out
    out.update(dispatch=True, desks=",".join(missing),
               note=f"missing: {', '.join(missing)}"
                    + (f"; already live: {', '.join(live)}" if live else "")
                    + (f"; {ask_note}" if ask_note else ""))
    return out


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--request", type=Path, default=REQUEST)
    parser.add_argument("--board", type=Path, default=BOARD)
    args = parser.parse_args(argv[1:])
    answer = decide(args.request, args.board)
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as out:
            out.write(f"dispatch={'true' if answer['dispatch'] else 'false'}\n")
            out.write(f"desks={answer['desks']}\n")
            out.write(f"note={answer['note']}\n")
    print(f"{'DISPATCH' if answer['dispatch'] else 'HOLD'} desks={answer['desks'] or '-'} :: {answer['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
