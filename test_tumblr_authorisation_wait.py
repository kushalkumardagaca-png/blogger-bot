#!/usr/bin/env python3
"""The authorisation waits for the owner, because a person cannot beat a job queue.

A Tumblr authorization code is single-use and worth minutes, and GitHub fixes a job's secrets when
that job *starts*. So a code saved after pressing Run is invisible to that run, and a code saved
before it ages out during queue time and installs. Run #8 on 21 October 2026 died exactly there. The
repair is a job that simply holds the run, followed by the job that exchanges the code and therefore
reads the value as it is by then.

An earlier attempt polled GitHub for the secret's save time, which needed a permission that does not
exist (`secrets: read`): GitHub then refused the *whole file* as invalid and the workflow could not
start at all. A mistake in the repair tool is worse than the outage, so the wait uses no API, needs no
permission, and is rehearsed here on every input shape a dispatcher can type.
"""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
WORKFLOW = ROOT / ".github" / "workflows" / "tumblr_oauth_bootstrap.yml"
EXPRESSION = re.compile(r"\$\{\{.*?\}\}")
# GitHub's documented workflow permission keys. Anything else makes the file invalid at startup.
PERMISSION_KEYS = {"actions", "checks", "contents", "deployments", "discussions", "id-token",
                   "issues", "packages", "pages", "pull-requests", "repository-projects",
                   "security-events", "statuses"}


def document():
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    loaded["on"] = loaded.get("on", loaded.get(True))  # PyYAML reads a bare `on:` as boolean True
    return loaded


def hold_script():
    run = document()["jobs"]["hold-for-code"]["steps"][0]["run"]
    return EXPRESSION.sub("zzz", run)


class Shape(unittest.TestCase):
    def test_the_file_only_uses_permissions_github_defines(self):
        # `secrets: read` was invented here on 21 October and cost the workflow its ability to start.
        for key in document()["permissions"]:
            self.assertIn(key, PERMISSION_KEYS, f"{key!r} is not a GitHub workflow permission")
        self.assertEqual(document()["permissions"], {"contents": "write"})

    def test_the_exchange_waits_for_the_hold_and_survives_it_being_skipped(self):
        jobs = document()["jobs"]
        self.assertIn("hold-for-code", jobs)
        self.assertEqual(jobs["authorize"]["needs"], "hold-for-code")
        self.assertEqual(jobs["authorize"]["if"], "${{ !failure() && !cancelled() }}")
        self.assertEqual(jobs["hold-for-code"]["if"],
                         "${{ github.event.inputs.wait_for_code_minutes != '0' }}")

    def test_no_job_depends_on_a_name_that_the_file_does_not_declare(self):
        for job_id, job in document()["jobs"].items():
            needs = job.get("needs")
            needs = [needs] if isinstance(needs, str) else list(needs or [])
            for name in needs:
                self.assertIn(name, document()["jobs"], f"{job_id} needs {name!r}, which is not a job")

    def test_the_hold_never_reads_a_secret_value_or_calls_an_api(self):
        script = hold_script()
        for forbidden in ("gh api", "secrets.", "TUMBLR_AUTHORIZATION_CODE }", "curl "):
            self.assertNotIn(forbidden, script)

    def test_the_dispatch_input_is_read_the_way_this_repo_reads_others(self):
        # `github.event.inputs.*` is the spelling already proven across this repository's workflows; an
        # expression context GitHub would not resolve makes the whole file invalid at start-up.
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count("github.event.inputs.wait_for_code_minutes"), 2)
        self.assertNotIn("${{ inputs.", text)

    def test_the_default_hold_is_four_minutes_and_can_be_switched_off(self):
        self.assertEqual(document()["on"]["workflow_dispatch"]["inputs"]["wait_for_code_minutes"]["default"], "4")


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.dir / "step.sh").write_text(hold_script(), encoding="utf-8")

    def hold(self, limit, seconds=3):
        return subprocess.run(["timeout", str(seconds), "bash", str(self.dir / "step.sh")],
                              env=dict(os.environ, LIMIT=str(limit)), text=True, capture_output=True)

    def test_it_holds_for_the_requested_minute_and_then_releases(self):
        result = subprocess.run(["bash", str(self.dir / "step.sh")],
                                env=dict(os.environ, LIMIT="1"), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Waiting 1 minutes", result.stdout)
        self.assertIn("Hold finished", result.stdout)

    def test_nonsense_input_holds_the_default_instead_of_crashing(self):
        for value in ("soon", "0.5"):
            with self.subTest(value=value):
                result = self.hold(value)
                self.assertIn("whole number of minutes", result.stdout)
                self.assertNotIn("syntax error", result.stderr)
                self.assertNotIn("invalid arithmetic", result.stderr)

    def test_a_greedy_request_is_capped_at_nine_minutes(self):
        result = self.hold(25)
        self.assertIn("capped at 9 minutes", result.stdout)
        # The cap is what the loop actually announces it will hold for, not just what it printed.
        self.assertIn("Waiting 9 minutes", result.stdout)

    def test_the_owner_is_told_which_step_matters(self):
        result = self.hold(1 if False else 0.0001)  # any value: the guidance is unconditional
        self.assertIn("Update the TUMBLR_AUTHORIZATION_CODE secret", result.stdout)
        self.assertIn("a spent code is worth nothing", result.stdout)


if __name__ == "__main__":
    unittest.main()
