#!/usr/bin/env python3
"""A workflow file is a program, and an inserted block must not eat its neighbour.

On 23 October 2026, minutes after the duplicate was reported, a `concurrency:` block added to two
recovery workflows was written where `permissions:` had been, so the file still parsed - and read as
`concurrency: {group, cancel-in-progress, actions: write, contents: read}`. The permissions key was
gone, the runs could no longer push or dispatch, and four red emails appeared in a minute for a
change whose only job was to prevent red. YAML's complaint-free parse is not a review; these are the
questions a reviewer should have asked.
"""
from __future__ import annotations

import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"
TOP_LEVEL = {"name", "on", "permissions", "concurrency", "env", "defaults",
             "jobs", "run-name", "timeout-minutes", "cancel-in-progress"}
CONCURRENCY_KEYS = {"group", "cancel-in-progress"}
PERMISSION_KEYS = {"contents", "actions", "checks", "deployments", "id-token",
                   "issues", "discussions", "packages", "pages", "pull-requests",
                   "repository-projects", "security-events", "statuses"}


class WorkflowShape(unittest.TestCase):
    def files(self):
        return sorted(p for p in WORKFLOWS.glob("*.yml"))

    def test_every_workflow_is_readable(self):
        self.assertGreater(len(self.files()), 20, "the scan must actually be looking at the workflows")

    def test_no_key_is_swallowed_by_its_neighbour(self):
        for path in self.files():
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            # YAML 1.1 reads the key `on:` as the boolean True; every workflow file in this
            # repository is written that way, so the check has to look past the parser's joke.
            keys = {("on" if key is True else key) for key in doc}
            self.assertFalse(keys - TOP_LEVEL, f"{path.name}: unexpected top-level keys {sorted(keys - TOP_LEVEL)}")
            concurrency = doc.get("concurrency")
            if isinstance(concurrency, dict):
                self.assertFalse(set(concurrency) - CONCURRENCY_KEYS,
                                 f"{path.name}: concurrency has absorbed {sorted(set(concurrency) - CONCURRENCY_KEYS)}")

    def test_the_scope_each_job_acts_with_is_still_declared(self):
        # Each of these five either commits to main or asks GitHub to start a run. Both are
        # permissions, and an omitted one does not fail loudly at edit time - it fails at 04:45.
        commits = ("daily_news_wires.yml", "blogger_corpus_hardening.yml")
        dispatches = ("news_desk_recovery.yml", "master_slot_recovery.yml", "slot_guarantee.yml")
        for name in commits:
            perms = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8")).get("permissions") or {}
            self.assertEqual(perms.get("contents"), "write", f"{name} commits evidence and must say so")
        for name in dispatches:
            perms = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8")).get("permissions") or {}
            self.assertIn(perms.get("actions"), ("write",), f"{name} dispatches other runs and must say so")

    def test_a_lock_block_is_a_lock_block(self):
        for name in ("daily_news_wires.yml", "news_desk_recovery.yml", "master_slot_recovery.yml",
                     "blogger_corpus_hardening.yml"):
            doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
            concurrency = doc.get("concurrency") or {}
            self.assertTrue(concurrency.get("group"), f"{name}: a concurrency block without a group")
            self.assertIs(concurrency.get("cancel-in-progress"), False,
                          f"{name}: a cancellable lock throws away the very run that was asked for")


if __name__ == "__main__":
    unittest.main()
