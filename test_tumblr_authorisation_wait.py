#!/usr/bin/env python3
"""The authorisation waits for the owner instead of asking the owner to race the queue.

Tumblr hands out an authorization code that is single-use and worth minutes. GitHub fixes a job's
secrets when the job starts, so any wait inside the same job is pointless: the value read is the one
that was already there. The repair is structural - a short job that waits for the secret's
`updated_at` to move, then a second job that does the exchange and therefore reads the fresh value.
Run #8 on 21 October 2026 died on exactly this race, and its log showed a code that was already
retired being offered again.

These tests run the real wait loop with a stubbed `gh`, so the behaviour - notice a save within about
five seconds, tolerate nonsense input, never crash on it - is proven rather than assumed.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
WORKFLOW = ROOT / ".github" / "workflows" / "tumblr_oauth_bootstrap.yml"
EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)


def workflow():
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML reads the bare `on:` key of a workflow as the boolean True, so both spellings are asked.
    document["on"] = document.get("on", document.get(True))
    return document


def wait_script():
    """The wait step's shell, with GitHub expressions replaced by one safe word."""
    run = workflow()["jobs"]["wait-for-code"]["steps"][0]["run"]
    return EXPRESSION.sub("zzz", run)


class Shape(unittest.TestCase):
    def test_the_exchange_runs_after_the_wait_and_survives_a_skipped_wait(self):
        document = workflow()
        jobs = document["jobs"]
        self.assertIn("wait-for-code", jobs)
        self.assertEqual(jobs["authorize"].get("needs"), "wait-for-code")
        # needs + !failure() is what lets the exchange run when the owner asked for no wait at all.
        self.assertEqual(jobs["authorize"].get("if"), "${{ !failure() && !cancelled() }}")
        self.assertEqual(jobs["wait-for-code"].get("if"), "${{ inputs.wait_for_code_minutes != '0' }}")

    def test_the_token_job_can_ask_github_when_the_secret_was_last_saved(self):
        document = workflow()
        self.assertEqual(document["permissions"].get("secrets"), "read")
        self.assertEqual(document["permissions"].get("actions"), "read")

    def test_a_waiting_run_defaults_to_four_minutes(self):
        inputs = workflow()["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["wait_for_code_minutes"]["default"], "4")

    def test_the_wait_never_tries_to_read_the_secret_value_itself(self):
        script = wait_script()
        self.assertIn("--jq .updated_at", script)
        for forbidden in ("--jq .value", "secrets.TUMBLR_AUTHORIZATION_CODE", "echo $TUMBLR_AUTH"):
            self.assertNotIn(forbidden, script)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.dir / "step.sh").write_text(wait_script(), encoding="utf-8")
        self.gh = self.dir / "gh"

    def run_wait(self, limit, gh_output, seconds=6):
        self.gh.write_text(gh_output, encoding="utf-8")
        self.gh.chmod(0o755)
        env = dict(os.environ, REPO="o/r", SECRET="TUMBLR_AUTHORIZATION_CODE", LIMIT=str(limit),
                   STARTED="2026-10-21T04:40:00Z", PATH=f"{self.dir}:{os.environ['PATH']}")
        return subprocess.run(["timeout", str(seconds), "bash", str(self.dir / "step.sh")],
                              env=env, text=True, capture_output=True)

    def test_a_freshly_saved_secret_ends_the_wait_at_once(self):
        output = self.run_wait(4, '#!/bin/bash\necho "2099-01-01T00:00:00Z"\n', seconds=20)
        self.assertEqual(output.returncode, 0, output.stdout + output.stderr)
        self.assertIn("Exchanging it now.", output.stdout)

    def test_a_stale_secret_keeps_polling_rather_than_giving_up_early(self):
        output = self.run_wait(4, "#!/bin/bash\necho null\n", seconds=8)
        self.assertEqual(output.returncode, 124, "a timeout is the correct outcome while no save lands")
        self.assertIn("still waiting for a newer code", output.stdout)

    def test_nonsense_input_waits_four_minutes_instead_of_crashing(self):
        for value in ("soon", "0.5", ""):
            with self.subTest(value=value):
                output = self.run_wait(value, "#!/bin/bash\necho null\n", seconds=4)
                self.assertNotIn("syntax error", output.stderr)
                self.assertNotIn("invalid arithmetic", output.stderr)
                if value:
                    self.assertIn("whole number of minutes", output.stdout)
                else:
                    # An empty input means the default was never overridden, so nothing to explain.
                    self.assertIn("If you have not pressed Approve", output.stdout)

    def test_a_greedy_wait_is_capped_so_a_queued_run_cannot_sit_on_a_dead_code(self):
        output = self.run_wait(25, "#!/bin/bash\necho null\n", seconds=8)
        self.assertIn("capped at 9 minutes", output.stdout)
        self.assertIn("of 540 seconds", output.stdout)


if __name__ == "__main__":
    unittest.main()
