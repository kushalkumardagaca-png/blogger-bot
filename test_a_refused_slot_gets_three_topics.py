#!/usr/bin/env python3
"""A slot a gate refused gets three substitute topics inside one run, not one.

The 23 October Evergreen failure was not a broken writer. It was a slot that spent the whole day in
red because every attempt was allowed exactly two topics: the plan's own, and one substitute. Both were
thin on sources - the eight-source gate found 0, then 5 - so the run raised, the guard dispatched
another attempt twenty minutes later, and the same two topics were measured again. Fifteen red runs and
fifteen emails, and no article.

Nothing here lowers a gate. Every candidate still answers the same eight topic-specific sources, the
same three licensed photographs and the same originality rule. What changed is that a run now works
through three substitutes, blocking each refusal so the next candidate is a genuinely different subject,
and it stops immediately when the failure is not a gate's refusal at all - a 503, an embargo, an
edition identity are not a topic's fault and must not be laundered into a topic swap.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import master_v3_pipeline as pipeline  # noqa: E402

GATE_ERROR = "V3 source gate found 5 topic-specific sources; eight required"


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.saved = {}
        for name in ("ROOT", "PLAN", "STATUS", "selected", "reuse_completed_slot", "build_candidate",
                     "replace_blocked_topic", "block_topic", "trending_candidates"):
            self.saved[name] = getattr(pipeline, name)
        pipeline.ROOT = self.tmp
        pipeline.PLAN = self.tmp / "MASTER_DAILY_PLAN.json"
        pipeline.STATUS = self.tmp / "MASTER_AUTOMATION_STATUS.json"
        self.plan = {"date": "2026-10-23", "status": "READY",
                     "evergreen": [{"id": "orig", "title": "Original topic", "category": "Banking"}],
                     "trending": [{"id": "orig", "title": "Original topic", "category": "Banking"}]}
        self.blocked = []
        pipeline.selected = lambda kind, slot: (self.plan, dict(self.plan[kind][slot]))
        pipeline.reuse_completed_slot = lambda *a, **k: False
        def block(plan, kind, slot, item, error):
            self.blocked.append(str(item.get("id")))
            plan.setdefault("blockedTopics", {})[str(item.get("id"))] = {"kind": kind, "slot": slot}
        pipeline.block_topic = block
        pipeline.trending_candidates = lambda plan, item: [item]

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(pipeline, name, value)

    def counting_builder(self, succeed_on=None, error=GATE_ERROR):
        """Records which topics were asked for; raises the gate's refusal for the others."""
        seen = []

        def build(kind, slot, candidate):
            seen.append(candidate["id"])
            if succeed_on is None or len(seen) < succeed_on:
                raise RuntimeError(f"{error} (topic {candidate['id']})")
            target = self.tmp / f"package-{candidate['id']}.json"
            target.write_text("{}", encoding="utf-8")
            return candidate, target, f"Title {candidate['id']}", f"slug-{candidate['id']}", "meta", ["News"], "<p>body</p>"
        return build, seen

    def substituter(self):
        """Hands out a different topic each time, the way the blocked-topic ledger does."""
        counter = {"n": 0}

        def replace(plan, kind, slot, item):
            counter["n"] += 1
            return {"id": f"sub{counter['n']}", "title": f"Substitute {counter['n']}", "category": "Banking"}
        return replace


class ThreeSubstitutes(unittest.TestCase):
    def setUp(self):
        self.h = Harness(); self.h.setUp()

    def tearDown(self):
        self.h.tearDown()

    def test_a_slot_keeps_trying_until_a_topic_answers_the_gate(self):
        build, seen = self.h.counting_builder(succeed_on=4)
        pipeline.build_candidate = build
        pipeline.replace_blocked_topic = self.h.substituter()
        pipeline.prepare("evergreen", 0)
        self.assertEqual(seen, ["orig", "sub1", "sub2", "sub3"],
                         "the plan's topic first, then three substitutes, in one run")
        self.assertEqual(self.h.plan["evergreen"][0]["id"], "sub3", "the day's plan records what the slot now holds")
        self.assertIn("blockedTopics", self.h.plan)

    def test_a_refused_slot_says_what_was_tried(self):
        build, seen = self.h.counting_builder(succeed_on=None)
        pipeline.build_candidate = build
        pipeline.replace_blocked_topic = self.h.substituter()
        with self.assertRaises(RuntimeError) as caught:
            pipeline.prepare("evergreen", 0)
        message = str(caught.exception)
        self.assertIn("3 substitute topic(s) tried", message)
        self.assertIn("source gate", message, "the reason still has to be the gate's own words")
        self.assertEqual(seen, ["orig", "sub1", "sub2", "sub3"])

    def test_every_refusal_blocks_its_topic(self):
        build, _ = self.h.counting_builder(succeed_on=None)
        pipeline.build_candidate = build
        pipeline.replace_blocked_topic = self.h.substituter()
        with self.assertRaises(RuntimeError):
            pipeline.prepare("evergreen", 0)
        self.assertEqual(self.h.blocked, ["orig", "sub1", "sub2", "sub3"],
                         "a topic refused once is not offered again by the next run")

    def test_a_failure_that_is_not_a_gate_does_not_go_looking_for_another_topic(self):
        build, seen = self.h.counting_builder(succeed_on=None, error="publication embargo has not lifted")
        pipeline.build_candidate = build
        pipeline.replace_blocked_topic = self.h.substituter()
        with self.assertRaises(RuntimeError) as caught:
            pipeline.prepare("evergreen", 0)
        self.assertIn("embargo", str(caught.exception))
        self.assertEqual(seen, ["orig"], "only a gate's refusal about a topic may change the topic")
        self.assertEqual(self.h.blocked, [], "an infrastructure failure must not burn a day's topic list")

    def test_no_substitute_is_invented_when_the_search_itself_finds_nothing(self):
        def replace(plan, kind, slot, item):
            raise RuntimeError("no unused evergreen topic remains for slot 0")
        build, seen = self.h.counting_builder(succeed_on=None)
        pipeline.build_candidate = build
        pipeline.replace_blocked_topic = replace
        with self.assertRaises(RuntimeError) as caught:
            pipeline.prepare("evergreen", 0)
        self.assertIn("no unused evergreen topic remains", str(caught.exception))
        self.assertEqual(seen, ["orig"])


    def test_a_substitute_already_refused_this_run_is_not_tried_twice(self):
        build, seen = self.h.counting_builder(succeed_on=None)
        pipeline.build_candidate = build
        pipeline.replace_blocked_topic = lambda plan, kind, slot, item: {"id": "same", "title": "Same", "category": "Banking"}
        with self.assertRaises(RuntimeError) as caught:
            pipeline.prepare("evergreen", 0)
        self.assertIn("refusing to spend another attempt on it", str(caught.exception))
        self.assertEqual(seen, ["orig", "same"], "the repeat is refused before it costs a third build")


class SubstitutesAreRankedByEvidence(unittest.TestCase):
    def test_the_substitute_search_prefers_the_deepest_source_pool(self):
        source = (ROOT / "master_v3_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("found = sorted(found, key=lambda row: (min(len(row.get('sources') or []), 8)", source,
                      "an Evergreen substitute is chosen for how much evidence it can answer with")


if __name__ == "__main__":
    unittest.main()
