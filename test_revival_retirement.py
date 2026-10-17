#!/usr/bin/env python3
"""The owner's 17 October removal must never silently reactivate the old queue."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import draft_inventory_sweep as sweep
import revive_quarantine as revival

ROOT = Path(__file__).parent


class RevivalRetirementTests(unittest.TestCase):
    def test_plan_and_state_are_retired_without_erasing_history(self):
        plan = json.loads((ROOT / 'QUARANTINE_REVIVAL_PLAN.json').read_text())
        state = json.loads((ROOT / 'QUARANTINE_REVIVAL_STATE.json').read_text())
        for document in (plan, state):
            self.assertIs(document['enabled'], False)
            self.assertEqual(document['status'], 'RETIRED')
            self.assertTrue(document['retired_reason'])
        self.assertEqual(state['next_due_at'], '')
        self.assertEqual(len(plan['items']), 18)
        self.assertTrue(state['items'])

    def test_no_active_workflow_can_start_the_revival_publisher(self):
        self.assertFalse((ROOT / '.github/workflows/quarantine_revival.yml').exists())
        for path in (ROOT / '.github/workflows').glob('*.y*ml'):
            self.assertNotIn('revive_quarantine.py', path.read_text(), str(path))

    def test_even_forced_apply_has_no_publication_or_social_side_effects(self):
        operations = ('state', 'save', 'token', 'fetch_public_posts', 'publish_one', 'announce')
        with contextlib.ExitStack() as stack:
            mocks = {name: stack.enter_context(patch.object(revival, name)) for name in operations}
            for apply in (False, True):
                for force in (False, True):
                    with self.subTest(apply=apply, force=force):
                        result = revival.run(apply=apply, force=force)
                        self.assertEqual(result['status'], 'RETIRED')
                        self.assertEqual(result['articlesPublished'], 0)
                        self.assertEqual(result['socialPostsDispatched'], 0)
            for mock in mocks.values():
                mock.assert_not_called()

    def test_a_missing_or_unreadable_plan_cannot_enable_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            with patch.object(revival, 'PLAN', path), patch.object(revival, 'token') as token:
                self.assertEqual(revival.run(True, True)['status'], 'RETIRED')
                path.write_text('{invalid json')
                self.assertEqual(revival.run(True, True)['status'], 'RETIRED')
                path.write_text('{}')
                self.assertEqual(revival.run(True, True)['status'], 'RETIRED')
                token.assert_not_called()

    def test_forced_command_reports_retirement_without_credentials(self):
        with patch('sys.argv', ['revive_quarantine.py', '--apply', '--force']), \
             patch.object(revival, 'token') as token, \
             patch.dict('os.environ', {'GITHUB_STEP_SUMMARY': ''}), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(revival.main(), 0)
            self.assertEqual(json.loads(output.getvalue())['status'], 'RETIRED')
            token.assert_not_called()

    def test_retired_queue_is_not_treated_as_a_pending_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text(json.dumps({'status': 'RETIRED', 'enabled': False,
                                        'items': {'123': {'draft_id': '123', 'status': 'repair_failed'}}}))
            with patch.object(sweep, 'REVIVAL_STATE', path):
                self.assertEqual(sweep.revival_queue(), {})


if __name__ == '__main__':
    unittest.main()
