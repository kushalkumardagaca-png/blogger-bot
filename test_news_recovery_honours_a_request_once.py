#!/usr/bin/env python3
"""A recovery request is honoured once, for the editions that are actually missing.

`.github/news-recovery-request` asks the wires job for a desk. Two things were wrong with it on
23 October 2026: an empty file was reported as an error (a red email to say nothing had been asked
for), and the file kept being re-honoured on every later push - so a request written at 09:00 IST was
still dispatching runs for editions that had been live since the morning. A route that fires again after
it has been satisfied is not a safety net; it is a loop that eventually gets muted because people stop
reading it.

So the answer comes from the day's own board: dispatch only what is missing, and when nothing is
missing, say so as a notice. Where the board cannot be read, or is too old to trust, the answer is still
to ask - a desk nobody re-asked for is a missing edition, and that is the worse failure.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import news_recovery_request as request  # noqa: E402


def board(live: dict[str, bool], minutes_old: int = 5) -> str:
    when = dt.datetime.now(request.IST) - dt.timedelta(minutes=minutes_old)
    return json.dumps({"generatedAt": when.isoformat(),
                       "rows": [{"key": f"news-{desk}", "live": flag} for desk, flag in live.items()]})


class Decide(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def ask(self, text, board_json, name="case"):
        req = self.tmp / f"{name}.txt"; req.write_text(text, encoding="utf-8")
        bd = self.tmp / f"{name}.json"; bd.write_text(board_json, encoding="utf-8")
        return request.decide(req, bd)

    def test_only_the_missing_edition_is_asked_for(self):
        answer = self.ask("china, india", board({"china": True, "india": False}))
        self.assertTrue(answer["dispatch"])
        self.assertEqual(answer["desks"], "india", "china is already live; asking again publishes a second copy")
        self.assertIn("already live: china", answer["note"])

    def test_a_request_already_served_is_not_re_honoured(self):
        answer = self.ask("china, india", board({"china": True, "india": True}))
        self.assertFalse(answer["dispatch"])
        self.assertEqual(answer["desks"], "")
        self.assertIn("already live today", answer["note"])

    def test_an_empty_request_is_a_notice_and_not_a_failure(self):
        for text in ("", "   \n"):
            answer = self.ask(text, board({"china": True}))
            self.assertFalse(answer["dispatch"])
            self.assertEqual(answer["note"], "no desk named")

    def test_a_typo_in_the_request_is_reported_not_guessed(self):
        answer = self.ask("bankng, banking", board({"banking": False}))
        self.assertEqual(answer["desks"], "banking")
        self.assertIn("ignored bankng", answer["note"], "the misspelled desk is named back, never repaired silently")

    def test_a_missing_or_stale_board_asks_anyway(self):
        missing = request.decide(self.tmp / "none.txt", self.tmp / "no-board.json")
        self.assertFalse(missing["dispatch"], "no request file and no board means there is nothing to honour")
        (self.tmp / "req.txt").write_text("china", encoding="utf-8")
        stale = self.ask("china", board({"china": True}, minutes_old=240), name="stale")
        self.assertTrue(stale["dispatch"], "a board too old to trust must not be read as 'nothing is missing'")
        self.assertIn("min old", stale["note"])

    def test_a_board_without_rows_asks_anyway(self):
        answer = self.ask("china", json.dumps({"generatedAt": dt.datetime.now(request.IST).isoformat(), "rows": []}))
        self.assertTrue(answer["dispatch"])
        self.assertIn("no slot rows", answer["note"])


class WiredIntoTheWorkflow(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ".github" / "workflows" / "news_desk_recovery.yml").read_text(encoding="utf-8")

    def test_the_route_uses_the_decision_and_no_longer_errors_on_an_empty_file(self):
        self.assertIn("python3 news_recovery_request.py", self.text)
        self.assertIn("steps.want.outputs.dispatch == 'true'", self.text)
        self.assertIn("steps.want.outputs.desks", self.text)
        self.assertNotIn("Nothing requested", self.text, "an empty request must not be an error")
        self.assertIn("::notice title=No edition is missing::", self.text)

    def test_the_dispatch_is_still_serialised(self):
        self.assertIn("concurrency:", self.text)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_the_cli_exit_code_never_rides_on_a_hold(self):
        # A recovery that decides to do nothing must not leave a red run behind.
        source = (ROOT / "news_recovery_request.py").read_text(encoding="utf-8")
        self.assertIn("return 0", source)
        self.assertNotIn("raise SystemExit(1)", source)


if __name__ == "__main__":
    unittest.main()
