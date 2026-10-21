#!/usr/bin/env python3
"""Why re-running the authorisation does nothing, and how the run page now says so.

On 21 October 2026 the owner pressed *Tumblr OAuth Bootstrap* twice with the same saved code, 2h22m
apart, and Tumblr answered "The authorization code has expired" both times. The message is true but
useless: the code cannot be revived, so the only way forward is a brand-new approval. The workflow
now remembers a SHA-256 **fingerprint** of the value it was given - never the value, which would put
a live credential into a public repository's history - and says plainly when the same code is offered
again. These tests pin that behaviour and the privacy of it.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "tumblr_attempt_record.py"
WORKFLOW = ROOT / ".github" / "workflows" / "tumblr_oauth_bootstrap.yml"
DEAD_CODE = "9a98041b8cf58d01a677ab04f9d4ca414dfdc4fa"


def run(action, workdir, *args):
    # The copy inside the sandbox directory, not the repository script: the record path is derived
    # from where the script lives, so running the real one would write into the repository.
    return subprocess.run([sys.executable, str(Path(workdir) / "tumblr_attempt_record.py"), action,
                           *args], cwd=workdir, text=True, capture_output=True)


class FingerprintOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for name in ("tumblr_attempt_record.py",):
            (self.dir / name).write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
        self.addCleanup(self.tmp.cleanup)

    @property
    def record(self):
        return json.loads((self.dir / "TUMBLR_OAUTH_ATTEMPT.json").read_text(encoding="utf-8"))

    def test_nothing_is_claimed_before_the_first_attempt(self):
        result = run("previous", self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_a_refusal_is_written_down_with_its_reason(self):
        (self.dir / "reason.txt").write_text(
            "RuntimeError: Tumblr authorization exchange failed: HTTP 400; "
            "{'error': 'invalid_grant', 'error_description': 'The authorization code has expired'}\n",
            encoding="utf-8")
        result = run("record", self.dir, "--fingerprint", "147255888f67", "--code", "2",
                     "--reason-file", "reason.txt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record["outcome"], "refused by Tumblr")
        self.assertEqual(self.record["fingerprint"], "147255888f67")
        self.assertIn("authorization code has expired", self.record["reason"])

    def test_the_code_itself_never_reaches_the_repository(self):
        (self.dir / "reason.txt").write_text(DEAD_CODE, encoding="utf-8")
        run("record", self.dir, "--fingerprint", "147255888f67", "--code", "2",
            "--reason-file", "reason.txt")
        # A kept reason line would otherwise reprint the very code that is being guarded.
        text = (self.dir / "TUMBLR_OAUTH_ATTEMPT.json").read_text(encoding="utf-8")
        self.assertNotIn(DEAD_CODE, text)
        self.assertEqual(len(self.record["fingerprint"]), 12)

    def test_a_long_reason_is_clipped_rather_than_stored_whole(self):
        (self.dir / "reason.txt").write_text("x" * 5000, encoding="utf-8")
        run("record", self.dir, "--fingerprint", "abc", "--code", "2", "--reason-file", "reason.txt")
        self.assertLessEqual(len(self.record["reason"]), 400)

    def test_previous_fingerprint_is_what_a_repeat_run_needs(self):
        (self.dir / "reason.txt").write_text("expired", encoding="utf-8")
        run("record", self.dir, "--fingerprint", "147255888f67", "--code", "2",
            "--reason-file", "reason.txt")
        self.assertEqual(run("previous", self.dir).stdout.strip(), "147255888f67")

    def test_a_missing_reason_file_is_not_an_error(self):
        result = run("record", self.dir, "--fingerprint", "abc", "--code", "0",
                     "--reason-file", "nothing-here.txt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record["outcome"], "exchanged")
        self.assertEqual(self.record["reason"], "")


class WorkflowWiring(unittest.TestCase):
    TEXT = WORKFLOW.read_text(encoding="utf-8")

    def test_the_step_computes_a_fingerprint_before_it_exchanges_anything(self):
        self.assertIn('fingerprint="$(printf \'%s\' "${TUMBLR_AUTHORIZATION_CODE:-}"', self.TEXT)
        self.assertIn("python tumblr_attempt_record.py previous", self.TEXT)
        self.assertIn("python tumblr_attempt_record.py record", self.TEXT)

    def test_a_repeat_of_the_same_code_is_named_as_the_problem(self):
        self.assertIn('if [ "$previous" = "$fingerprint" ]; then', self.TEXT)
        self.assertIn("SAME code as the previous attempt", self.TEXT)
        self.assertIn("worth minutes, not hours", self.TEXT)

    def test_the_attempt_record_is_committed_so_the_next_run_can_see_it(self):
        self.assertIn("git add tumblr_token.enc TUMBLR_OAUTH_ATTEMPT.json", self.TEXT)


if __name__ == "__main__":
    unittest.main()
