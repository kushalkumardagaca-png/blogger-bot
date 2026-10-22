"""The owner's rule of 23 October 2026: not one published article may go offline because of a workflow.

Nothing here grades writing. These tests hold the machinery to two promises that were made in plain
words and are worth more than the promise:

1. a take-down (deleting a post, or pushing a live post back to draft) may not run unattended at all,
   because a frozen site that cannot say "the owner asked for this" should leave the article up;
2. a nightly gate may not turn red for a reason that is not a defect in the site, because a flood of
   unactionable failures is how a real one gets missed - which is exactly how Growth Control Tower lost
   three nights to a missing PyYAML.

Both are checked by running the shipped files as the scheduler runs them, not by reading them.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(args, env=None):
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}, timeout=300)


class TakeDownPaths(unittest.TestCase):
    def test_every_script_that_can_delete_a_post_consults_the_freeze(self):
        """A file that can remove a live URL must ask the owner's policy before it tries.

        This is the tripwire for the next person who adds a cleanup script: the day a file learns to
        call Blogger's DELETE or /unpublish endpoint, it has to pass through site_change_control, or
        this test and the capability audit both go red on the same commit that added it.
        """
        offenders = []
        for path in sorted(ROOT.glob("*.py")):
            if path.name.startswith("test_") or path.name == "site_change_control.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not re.search(r"""method\s*=\s*["']DELETE["']|/unpublish\b""", text):
                continue
            if "stop_if_frozen" not in text:
                offenders.append(path.name)
        self.assertEqual([], offenders,
                         "these files can take a published article down without the owner's freeze: "
                         + ", ".join(offenders))

    def test_the_duplicate_purge_refuses_to_delete_while_the_site_is_frozen(self):
        """`--apply` alone must never be able to empty the blog: the freeze answers and the run ends 0.

        Exit 0 is deliberate. A held action is not a failure, and a nightly job that ends red because
        the owner froze the site is the noise the owner asked to have stopped.
        """
        proc = run(["blogger_duplicate_purge.py", "--apply"])
        self.assertEqual(0, proc.returncode, proc.stdout[-600:] + proc.stderr[-600:])
        self.assertIn("HELD_BY_OWNER_FREEZE", proc.stdout)

    def test_the_duplicate_purge_still_refuses_without_the_typed_word(self):
        """Even with the freeze released, deletion needs a word no cron can type."""
        here = ROOT / "blogger_duplicate_purge.py"
        source = here.read_text(encoding="utf-8")
        self.assertIn("CONFIRM_PHRASE", source)
        self.assertIn("--confirm", source)
        self.assertIn('_dy_stop_if_frozen("blogger_duplicate_purge")', source)
        self.assertIn("if __name__ == \"__main__\":", source)
        # and the refusal sits before any network call, so an unattended dispatch cannot reach Blogger
        apply_at = source.index("if arguments.apply and arguments.confirm != CONFIRM_PHRASE:")
        delete_at = source.index('method="DELETE"')
        self.assertLess(apply_at, delete_at,
                        "the typed confirmation must be checked before the delete call is reachable")

    def test_the_wrong_master_cleanup_is_held_by_the_freeze_too(self):
        proc = run(["cleanup_wrong_master_post.py", "--post-id", "1234567890"])
        self.assertEqual(0, proc.returncode, proc.stdout[-600:] + proc.stderr[-600:])
        self.assertIn("HELD_BY_OWNER_FREEZE", proc.stdout)


class GatesDoNotCryWolf(unittest.TestCase):
    def test_a_missing_library_is_reported_as_not_measured_and_never_as_a_defect(self):
        """Run the capability audit where `import yaml` fails: it must exit clean and say "not measured".

        Before 23 October this branch answered `False`, so Growth Control Tower - whose runner installs
        requests and Pillow only - failed every night for a reason that had nothing to do with the site.
        """
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yaml.py").write_text('raise ImportError("simulated: no PyYAML on this runner")\n',
                                            encoding="utf-8")
            proc = run(["audit_publishing_automation.py", "--check-only"], env={"PYTHONPATH": tmp})
        self.assertEqual(0, proc.returncode, proc.stdout[-800:] + proc.stderr[-800:])
        summary = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(0, summary["fail"], "a missing library must not be counted as a failure")
        self.assertGreaterEqual(summary.get("notMeasured", 0), 1,
                                "the unreadable check must be recorded as not measured, not dropped")

    def test_the_growth_control_tower_installs_the_library_its_gate_reads(self):
        """And the gate itself is still given PyYAML, so "not measured" stays the rare case."""
        text = (ROOT / ".github/workflows" / "growth_control_tower.yml").read_text(encoding="utf-8")
        self.assertRegex(text, r"pip install[^\n]*pyyaml")


if __name__ == "__main__":
    unittest.main(verbosity=2)
