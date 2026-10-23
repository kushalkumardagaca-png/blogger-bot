#!/usr/bin/env python3
"""The guard that chases empty slots has to notice when the reason is a gate it can open.

On 23 October 2026 the day began with three overdue slots and no article published, and the reason was a
field in a status file: three posts whose photographs carried a source link with no credit line under it.
Every writer, every desk and every recovery job was refusing correctly, and every ten minutes the guard
re-dispatched them to refuse again. Nothing in the repository asked for the one repair that would clear
it, because the workflow that can make that repair had its apply switch pinned to 'false'. Chasing a slot
a gate will refuse is noise, not delivery. These cases pin the behaviour that turns noise into a fix:
notice the cause, ask for the narrow repair, and keep the request off the writers' backs in between.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import slot_guard

STATUS = {
    "status": "WARNING", "apply": False, "remaining_live_policy_flags": [], "unsafe_active_links": [],
    "image_rights_gap_posts": 3, "checked_at": "2026-10-22T19:26:23+00:00",
}
LEDGER = {"posts_with_figure_rights_gaps": 3, "gaps": [{"url": "u"}]}


def corpus(root, status=None, ledger=None):
    (root / "BLOGGER_CORPUS_POLICY_STATUS.json").write_text(json.dumps(status or {}))
    (root / "BLOGGER_IMAGE_RIGHTS_LEDGER.json").write_text(json.dumps(ledger or {}))


class TheGuardNamesTheReason(unittest.TestCase):
    def test_a_caption_gap_that_holds_the_corpus_is_recognised(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            corpus(root, STATUS, LEDGER)
            reason = slot_guard.gate_blocked_by_figure_credits(root)
            self.assertIn("3 post(s)", reason)
            self.assertIn("no readable credit", reason)

    def test_a_healthy_ledger_is_not_a_repair_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            corpus(root, dict(STATUS, status="PASS"), {"posts_with_figure_rights_gaps": 0})
            self.assertEqual(slot_guard.gate_blocked_by_figure_credits(root), "")

    def test_a_gap_the_corpus_job_has_already_cleared_is_not_re_opened_as_a_request(self):
        # The ledger can lag a status file: the repair is owed when the corpus still reads the gap, and
        # a PASS with a stale ledger line must not wake an authenticated walk over 598 posts.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            corpus(root, dict(STATUS, status="PASS"), LEDGER)
            self.assertEqual(slot_guard.gate_blocked_by_figure_credits(root), "")

    def test_heavier_policy_flags_are_left_to_their_own_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            corpus(root, dict(STATUS, remaining_live_policy_flags=[{"post_id": "9"}]), LEDGER)
            self.assertEqual(slot_guard.gate_blocked_by_figure_credits(root), "")
            corpus(root, dict(STATUS, unsafe_active_links=[{"post_id": "9"}]), LEDGER)
            self.assertEqual(slot_guard.gate_blocked_by_figure_credits(root), "")

    def test_an_unreadable_status_file_raises_nothing_and_requests_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(slot_guard.gate_blocked_by_figure_credits(pathlib.Path(tmp)), "")


class TheRepairRequestIsNarrowAndSpaced(unittest.TestCase):
    def test_the_repair_is_asked_through_the_workflow_that_owns_it(self):
        calls = []
        with mock.patch.object(slot_guard.subprocess, "run",
                               side_effect=lambda cmd, **k: calls.append(cmd)) as run:
            self.assertIn("requested", slot_guard.dispatch_rights_repair(True))
        self.assertEqual(calls[0][:4], ["gh", "workflow", "run", "blogger_corpus_hardening.yml"])
        self.assertIn("apply=true", calls[0])
        self.assertIn("scope=rights", calls[0])

    def test_the_guard_never_writes_the_site_itself(self):
        source = (ROOT / "slot_guard.py").read_text(encoding="utf-8")
        self.assertNotIn("www.googleapis.com/blogger", source)
        self.assertIn('REPAIR_WORKFLOW = "blogger_corpus_hardening.yml"', source)

    def test_a_dispatch_failure_is_reported_not_raised(self):
        # Losing the request must not lose the rest of the day's board.
        with mock.patch.object(slot_guard.subprocess, "run", side_effect=OSError("gh unavailable")):
            self.assertIn("failed", slot_guard.dispatch_rights_repair(True))

    def test_the_repair_cannot_be_requested_on_every_pass(self):
        self.assertGreaterEqual(slot_guard.REPAIR_SPACING, slot_guard.DISPATCH_SPACING)

    def test_a_dry_run_reports_without_dispatching(self):
        with mock.patch.object(slot_guard.subprocess, "run") as run:
            self.assertIn("would request", slot_guard.dispatch_rights_repair(False))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
