"""A gate that refuses a topic must cost that topic, not the slot.

On 22 October 2026 the same article was rebuilt again and again against the same refusal: the Evergreen
writer offered `master_failures/` 80 files for one slot, and the 20:45 Trending slot died on a sentence
the corpus already owned, because the rotation that exists for one kind of refusal did not cover the
others. The preparation step also wrote a substituted Evergreen topic into the *trending* row of the
day's plan.

Nothing here lowers a standard. Eight topic-specific sources, three subject-named photographs, the
originality rule and the word limits are all still enforced - what changed is that a refusal now spends
the topic instead of spending the slot, and the plan's own substitution machinery is allowed to run.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import master_v3_pipeline as pipe

TODAY = dt.date(2026, 10, 22)


def plan_book(**extra):
    plan = {"status": "READY", "date": str(TODAY), "blockedTopics": {},
            "trending": [{"id": f"t{n}", "title": f"Trend {n}", "category": "Markets",
                          "evergreen_category": "Budgeting"} for n in range(5)],
            "evergreen": [{"id": f"e{n}", "title": f"Ever {n}", "category": "Budgeting"} for n in range(5)]}
    plan.update(extra)
    return plan


class Harness:
    """Run the real `prepare()` against a temporary repository and fake generators."""

    def __init__(self, plan, *, build=None, candidates=None, substitute=None):
        self.plan = plan
        self.build = build
        self.candidates = candidates or []
        self.substitute = substitute
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        (self.tmp / "scheduled_ready").mkdir()
        (self.tmp / "master_packages" / "dynamic").mkdir(parents=True)
        self.statuses = []
        self.plans_written = []

    def __enter__(self):
        self._patches = [
            mock.patch.object(pipe, "ROOT", self.tmp),
            mock.patch.object(pipe, "PLAN", self.tmp / "MASTER_DAILY_PLAN.json"),
            mock.patch.object(pipe, "PACKAGES", self.tmp / "master_packages" / "dynamic"),
            mock.patch.object(pipe, "STATUS", self.tmp / "MASTER_AUTOMATION_STATUS.json"),
            mock.patch.object(pipe, "TRACKER", self.tmp / "MASTER_AUTOMATION_TRACKER.json"),
            mock.patch.object(pipe, "POOL", self.tmp / "MASTER_TREND_POOL.json"),
            mock.patch.object(pipe, "selected", lambda kind, slot: (self.plan, self.plan[kind][slot])),
            mock.patch.object(pipe, "reuse_completed_slot", lambda plan, kind, slot, emit_social=False: False),
            mock.patch.object(pipe, "trending_candidates", lambda plan, item: self.candidates or [item]),
            mock.patch.object(pipe, "build_candidate", self.build),
            mock.patch.object(pipe, "replace_blocked_topic", self._replace),
            mock.patch.object(pipe, "write", self._write),
        ]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in self._patches:
            patch.stop()

    def _replace(self, plan, kind, slot, item):
        if self.substitute is None:
            raise RuntimeError(f"no unused {kind} topic remains for slot {slot}")
        self.plan[kind][slot] = self.substitute
        return self.substitute

    def _write(self, path, value):
        if path.name == "MASTER_AUTOMATION_STATUS.json":
            self.statuses.append(dict(value))
        else:
            self.plans_written.append(json.loads(json.dumps(value, default=str)))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, default=str))


class GateRefusalSpendsTheTopic(unittest.TestCase):
    def test_a_refused_evergreen_topic_is_blocked_and_the_slot_still_gets_an_article(self):
        """The exact shape of tonight's loss: one refusal, and the slot was simply abandoned."""
        plan = plan_book()
        substitute = {"id": "e9", "title": "Ever 9", "category": "Budgeting"}

        with Harness(plan, build=None, substitute=substitute) as net:
            def build(kind, slot, candidate):
                if candidate["id"] == "e0":
                    raise RuntimeError("V3 source gate found 6 topic-specific sources; eight required")
                return (candidate, net.tmp / "master_packages" / "dynamic" / "e9.json",
                        candidate["title"], "ever-9", "m", ["Budgeting"], "<p>b</p>")

            with mock.patch.object(pipe, "build_candidate", build):
                pipe.prepare("evergreen", 0)
        blocked = net.plans_written[-1].get("blockedTopics") or {}
        self.assertIn("e0", blocked, "the refused topic must be marked for the day")
        self.assertIn("source gate", blocked["e0"]["error"])
        self.assertEqual(net.plans_written[-1]["evergreen"][0]["id"], "e9",
                         "the slot is filled by the substitute")
        self.assertEqual(net.plans_written[-1]["trending"][0]["id"], "t0",
                         "and the substitute must never be written into the trending row")
        self.assertEqual(net.statuses[-1]["status"], "PREPARED")

    def test_a_refusal_that_is_not_about_the_topic_fails_at_once_and_blocks_nothing(self):
        plan = plan_book()

        def build(kind, slot, candidate):
            raise RuntimeError("Blogger said 503 while the package was being checked")

        with Harness(plan, build=build) as net:
            with mock.patch.object(pipe, "build_candidate", build):
                with self.assertRaises(RuntimeError) as caught:
                    pipe.prepare("evergreen", 0)
        self.assertIn("503", str(caught.exception))
        self.assertEqual(plan["blockedTopics"], {},
                         "a transport failure is not evidence that the topic is unpublishable")

    def test_trending_now_rotates_on_the_originality_gate_and_not_only_on_sources(self):
        plan = plan_book()
        first = dict(plan["trending"][0], id="tA")
        second = dict(plan["trending"][0], id="tB")
        seen = []

        with Harness(plan, candidates=[first, second]) as net:
            def build(kind, slot, candidate):
                seen.append(candidate["id"])
                if candidate["id"] == "tA":
                    raise RuntimeError("CORPUS ORIGINALITY GATE FAILED - exact substantive sentence "
                                       "reused from 2026-10-15-trending-47323b65c210c6c4.json")
                return (candidate, net.tmp / "master_packages" / "dynamic" / "tB.json",
                        candidate["title"], "trend-b", "m", ["Markets"], "<p>b</p>")

            with mock.patch.object(pipe, "build_candidate", build):
                pipe.prepare("trending", 0)
        self.assertEqual(seen, ["tA", "tB"], "the second topic in the plan's own shortlist must be tried")
        self.assertEqual(plan["blockedTopics"], {}, "a rotation inside the day's list needs no block yet")

    def test_when_the_substitute_is_refused_too_the_run_says_so_twice(self):
        plan = plan_book()

        def build(kind, slot, candidate):
            raise RuntimeError("V3 photo search exhausted every broadened search")

        with Harness(plan, build=build, substitute={"id": "e9", "title": "Ever 9", "category": "Budgeting"}) as net:
            with mock.patch.object(pipe, "build_candidate", build):
                with self.assertRaises(RuntimeError) as caught:
                    pipe.prepare("evergreen", 0)
        message = str(caught.exception)
        self.assertIn("photo search exhausted", message)
        self.assertIn("substitute topic was refused too", message)


class TheRefusalVocabulary(unittest.TestCase):
    def test_the_four_gate_messages_that_mean_change_topic(self):
        for message in ("V3 source gate found 7 topic-specific sources; eight required",
                        "CORPUS ORIGINALITY GATE FAILED - exact substantive sentence reused",
                        "V3 photo search exhausted every broadened search",
                        "no evidence-ready trending candidate remained"):
            self.assertTrue(pipe.gate_refusal(RuntimeError(message)), message)

    def test_everything_else_keeps_failing_the_way_it_did(self):
        for message in ("daily dynamic Master plan is not READY",
                        "Master V3 publishes only the current IST date",
                        "EDITION IDENTITY FAILED",
                        "Recorded published slot could not be confirmed"):
            self.assertFalse(pipe.gate_refusal(RuntimeError(message)), message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
