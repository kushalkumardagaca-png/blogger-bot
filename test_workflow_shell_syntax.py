"""Every shell step in every workflow must parse before it can report anything.

A `run:` block that bash cannot parse does not fail gracefully: bash aborts the whole block at
parse time, so the publish attempt, its health record, the repair hint and the exit code all vanish
and the job dies with `unexpected EOF while looking for matching`, exit 2. On 21 October 2026 that
killed the Tumblr authorisation step - the one step the owner relies on when a connection has to be
repaired - because a human apostrophe sat inside a `${reason:-see Tumblr's message}` expansion,
which bash parses as shell syntax rather than as text.

So the shape is checked, not trusted: `${{ ... }}` expressions become one safe word, and each
remaining script is handed to `bash -n`. This costs a fraction of a second per workflow and covers
every quoting mistake of that family, in steps written by anyone.
"""
import re
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent

EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)
SAFE_WORD = "zzz"


def run_blocks():
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_id, job in (document.get("jobs") or {}).items():
            for step in (job.get("steps") or []):
                script = step.get("run")
                if isinstance(script, str):
                    yield path.name, job_id, str(step.get("name") or "unnamed step"), script


class WorkflowShellSyntax(unittest.TestCase):
    def test_there_are_workflows_to_check(self):
        self.assertGreater(sum(1 for _ in run_blocks()), 100)

    def test_every_run_block_is_valid_bash(self):
        broken = []
        for workflow, job, name, script in run_blocks():
            result = subprocess.run(
                ["bash", "-n"], input=EXPRESSION.sub(SAFE_WORD, script),
                text=True, capture_output=True)
            if result.returncode:
                broken.append(f"{workflow}/{job}/{name}: {result.stderr.strip()[:160]}")
        self.assertEqual(broken, [], "these workflow steps would die before reporting anything:\n"
                         + "\n".join(broken))

    def test_apostrophes_never_ride_inside_an_expansion_default(self):
        # The exact defect: bash reads the quote in ${var:-it's fine} as an opening quote.
        pattern = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-[^}\n]*['\"][^}\n]*\}")
        for workflow, job, name, script in run_blocks():
            for line in script.splitlines():
                match = pattern.search(line)
                self.assertIsNone(
                    match, f"{workflow}/{job}/{name} has an unquoted apostrophe in "
                           f"{match.group(0) if match else ''!r}; phrase it without one")


if __name__ == "__main__":
    unittest.main()
