"""The Analytics connection must be usable, not merely documented.

On 21 October 2026 the nightly gate ran the Analytics reader with no `env:` block, so it answered
`CREDENTIALS_MISSING` every night for weeks while the instructions to fix it sat in the same
repository. These tests pin the three things that make the difference between an instruction and a
working measurement: every job that runs the reader is handed the credentials, the advice script can
explain every status the reader can produce, and no token value can be echoed into a public log.
"""
import ast
import json
import re
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"


def steps_named(workflow):
    document = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8")) or {}
    for job_id, job in (document.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            yield job_id, step


class ReaderReceivesCredentials(unittest.TestCase):
    def test_every_ga4_reader_step_is_handed_its_credentials(self):
        starved = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for job_id, step in steps_named(path.name):
                if "ga4_measurement.py" not in str(step.get("run") or ""):
                    continue
                env = step.get("env") or {}
                for needed in ("GA4_CLIENT_ID", "GA4_CLIENT_SECRET", "GA4_REFRESH_TOKEN"):
                    if needed not in env:
                        starved.append(f"{path.name}:{job_id} missing {needed}")
        self.assertEqual(starved, [], "\n".join(starved))


class AdviceCoversEveryStatus(unittest.TestCase):
    """The reader's status words and the advice script's sentences may not drift apart.

    A status with no sentence is a red run whose log says nothing, which is the failure the owner
    has told me to design out; a sentence for a status nobody writes is a false remedy.
    """

    def reader_statuses(self):
        tree = ast.parse((ROOT / "ga4_measurement.py").read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "status" for t in node.targets):
                for word in ast.walk(node.value):
                    if isinstance(word, ast.Constant) and isinstance(word.value, str) \
                            and re.fullmatch(r"[A-Z][A-Z_]{3,}", word.value):
                        found.add(word.value)
        return found

    def reader_remedies(self):
        tree = ast.parse((ROOT / "ga4_measurement.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "REMEDIES":
                return {key.value for key in node.value.keys}
        self.fail("REMEDIES is no longer a literal in ga4_measurement.py")

    def advice(self):
        tree = ast.parse((ROOT / "ga4_connection_advice.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "ADVICE":
                return {key.value: ast.literal_eval(value) for key, value
                        in zip(node.value.keys, node.value.values)}
        self.fail("ADVICE is no longer a literal in ga4_connection_advice.py")

    def test_the_advice_script_speaks_to_every_status_the_reader_can_write(self):
        statuses, advice = self.reader_statuses(), self.advice()
        self.assertEqual(advice.keys(), statuses,
                         f"silent about {sorted(statuses - set(advice))}, "
                         f"invents {sorted(set(advice) - statuses)}")
        self.assertTrue(self.reader_remedies() <= statuses,
                        "a remedy is written for a status the reader never produces")

    def test_every_status_tells_a_person_what_to_do_next(self):
        for status, (level, sentence) in self.advice().items():
            self.assertIn(level, ("error", "warning", "notice"), status)
            self.assertGreaterEqual(len(sentence), 40, f"{status} is too thin to act on")
            self.assertTrue(sentence.endswith("."), f"{status} is not a sentence")
            if status in ("CREDENTIALS_MISSING", "SCOPE_INSUFFICIENT", "TOKEN_REFUSED",
                          "PROPERTY_NOT_FOUND", "TAG_NOT_OBSERVED"):
                self.assertEqual(level, "error", f"{status} is an owner-only fix and must be red")

    def test_the_two_easily_confused_repairs_name_different_files(self):
        advice = self.advice()
        # "authorise again" and "authorise with Analytics added" must not read the same.
        self.assertIn("GA4_CONNECT.md", advice["CREDENTIALS_MISSING"][1])
        self.assertIn("GA4_REFRESH_TOKEN", advice["SCOPE_INSUFFICIENT"][1])
        self.assertIn("GA4_REFRESH_TOKEN", advice["TOKEN_REFUSED"][1])
        self.assertIn("GA4_PROPERTY_ID", advice["PROPERTY_NOT_FOUND"][1])

    def test_a_refused_token_is_named_as_its_own_repair(self):
        text = (ROOT / "ga4_measurement.py").read_text(encoding="utf-8")
        self.assertIn('"TOKEN_REFUSED"', text)
        self.assertIn("400, 401", text)
        self.assertIn("GA4_CONNECT.md", text)


class NoSecretsInLogs(unittest.TestCase):
    def test_the_connection_check_never_echoes_a_credential(self):
        text = (WORKFLOWS / "ga4_connection_check.yml").read_text(encoding="utf-8")
        for job_id, step in steps_named("ga4_connection_check.yml"):
            run = str(step.get("run") or "")
            for match in re.finditer(r'\$\{?(\w*(TOKEN|SECRET|CLIENT_ID|KEY)\w*)\}?', run):
                used = match.group(1)
                self.assertNotRegex(run, rf'echo[^\n]*\$\{{{used}\}}',
                                   f"{used} would be printed in full into a public log")
        self.assertIn('${#2}', text)          # lengths, which is the only disclosure allowed
        self.assertNotIn('echo "$GA4_REFRESH_TOKEN"', text)
        self.assertNotIn('echo $GA4_CLIENT_SECRET', text)


class WorkflowIsValidGithubSchema(unittest.TestCase):
    VALID = {"actions", "checks", "contents", "deployments", "discussions", "id-token", "issues",
             "packages", "pages", "pull-requests", "repository-projects", "security-events", "statuses"}

    def test_permissions_keys_and_job_needs_resolve(self):
        document = yaml.safe_load((WORKFLOWS / "ga4_connection_check.yml").read_text(encoding="utf-8"))
        self.assertTrue(set(document["permissions"]) <= self.VALID,
                        f"invalid permissions keys: {set(document['permissions']) - self.VALID}")
        jobs = document["jobs"]
        self.assertIn("check", jobs)
        for job_id, job in jobs.items():
            self.assertIn("runs-on", job)
            for ref in ([job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs") or []):
                self.assertIn(ref, jobs, f"{job_id} needs {ref}, which is not declared")
        runs = [step.get("run") for step in jobs["check"]["steps"] if step.get("run")]
        self.assertTrue(runs, "the job has no shell steps at all")
        for script in runs:
            stripped = re.sub(r"\$\{\{.*?\}\}", "zzz", script, flags=re.S)
            parsed = subprocess.run(["bash", "-n"], input=stripped, text=True, capture_output=True)
            self.assertEqual(parsed.returncode, 0, f"bash cannot parse: {parsed.stderr}")
            self.assertNotIn("python3 - <<", script, "inline heredocs do not survive a run: block")


if __name__ == "__main__":
    unittest.main()
