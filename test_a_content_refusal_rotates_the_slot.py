#!/usr/bin/env python3
"""A content refusal changes the topic, and an unwinnable headline never reaches a build.

Two defects emptied three slots on the evening of 23 October, and neither was a gate being too strict.

The strict compiler refuses a draft by raising `ValueError("MASTER V2 REJECTED — content policy: ...")`.
The slot's rotation caught only `RuntimeError` and only recognised six other gate names, so a refusal
about the *draft* stopped the run at its first topic: nothing blocked, nothing rotated, and the next run
measured the same refusal. Fifteen red emails later the slot was exactly where it started.

The second defect is a headline shape the pipeline can never publish: a superlative ranking of a product
or institution ("best banks for fixed deposits") is only acceptable with a stated selection method and a
disclosure of commercial relationship, which an automated explainer does not have. Such topics were being
handed to the slot as substitutes, so a run could spend its whole budget on refusals it was certain to
receive. The search is now told the same rule the compiler applies; the rule itself has not moved, and an
article that did state a method still passes it.

Both fixes report themselves. `policy_evidence` puts the tripped phrase into the failure, with long digit
runs masked, so a genuine exposed number is never copied into a public status file.
"""
from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import master_v3_pipeline as pipeline  # noqa: E402
from content_policy_guard import audit_text, title_needs_ranking_methodology  # noqa: E402
from master_article_v2 import policy_evidence  # noqa: E402

RANKED = "Best banks for fixed deposits in 2026"
PLAIN = "How a fixed deposit rate is set each quarter"


class WhichRefusalsRotate(unittest.TestCase):
    def test_the_strict_compilers_refusal_is_a_gate_refusal(self):
        error = ValueError("MASTER V2 REJECTED — content policy: deceptive financial or commercial promise")
        self.assertTrue(pipeline.gate_refusal(error), "a refusal about this draft must change the topic")

    def test_a_ranking_refusal_is_recognised_too(self):
        self.assertTrue(pipeline.gate_refusal(ValueError(
            "MASTER V2 REJECTED — content policy: unsupported financial ranking or fake-review risk")))

    def test_infrastructure_and_embargo_still_stop_the_run(self):
        for text in ("publication embargo has not lifted", "Blogger API returned 503",
                     "daily dynamic Master plan is not READY", "GITHUB_TOKEN is required"):
            with self.subTest(text):
                self.assertFalse(pipeline.gate_refusal(RuntimeError(text)),
                                 "a broken pipeline must never be laundered into a topic swap")

    def test_the_compiler_still_raises_the_same_value_error(self):
        source = (ROOT / "master_article_v2.py").read_text(encoding="utf-8")
        self.assertIn('raise ValueError("MASTER V2 REJECTED — "', source)
        self.assertIn("except (RuntimeError,ValueError) as exc:", (ROOT / "master_v3_pipeline.py").read_text(encoding="utf-8"))


class HeadlineShape(unittest.TestCase):
    def test_a_superlative_product_headline_needs_a_method(self):
        self.assertTrue(title_needs_ranking_methodology(RANKED))

    def test_an_explainer_headline_does_not(self):
        self.assertFalse(title_needs_ranking_methodology(PLAIN))
        self.assertFalse(title_needs_ranking_methodology(""))

    def test_the_gate_itself_is_unchanged(self):
        refused = audit_text(RANKED, "Banks pay different rates and readers should compare them.", "master-package", False)
        self.assertIn("unsupported financial ranking or fake-review risk", refused)
        stated = audit_text(RANKED,
                            "Our selection methodology is published below; there is no paid placement and no "
                            "commercial relationship with any bank named. Banks pay different rates.",
                            "master-package", False)
        self.assertNotIn("unsupported financial ranking or fake-review risk", stated,
                         "an article that states its method still passes - nothing was made harder")

    def test_the_unwinnable_topics_leave_the_candidate_pools(self):
        rows = [{"id": "a", "title": RANKED}, {"id": "b", "title": PLAIN}]
        self.assertEqual([r["id"] for r in pipeline.publishable_candidates(rows)], ["b"])


class SlotBehaviour(unittest.TestCase):
    """prepare() driven with the generator, the pool and the plan replaced."""

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
                     "evergreen": [{"id": "rank", "title": RANKED, "category": "Banking"}],
                     "trending": [{"id": "rank", "title": RANKED, "category": "Banking"}]}
        self.blocked = []
        pipeline.selected = lambda kind, slot: (self.plan, dict(self.plan[kind][slot]))
        pipeline.reuse_completed_slot = lambda *a, **k: False
        pipeline.trending_candidates = lambda plan, item: [item]

        def block(plan, kind, slot, item, error):
            self.blocked.append((str(item.get("id")), str(error)[:60]))
            plan.setdefault("blockedTopics", {})[str(item.get("id"))] = {"kind": kind, "slot": slot}
        pipeline.block_topic = block

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(pipeline, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build_ok(self, kind, slot, candidate):
        target = self.tmp / f"{candidate['id']}.json"
        target.write_text("{}", encoding="utf-8")
        return candidate, target, f"Title {candidate['id']}", f"slug-{candidate['id']}", "m", ["News"], "<p>b</p>"

    def test_an_unwinnable_headline_is_set_aside_before_any_build(self):
        built = []
        pipeline.build_candidate = lambda k, s, c: (built.append(c["id"]), self.build_ok(k, s, c))[1]
        pipeline.replace_blocked_topic = lambda plan, kind, slot, item: {"id": "good", "title": PLAIN,
                                                                         "category": "Banking"}
        pipeline.prepare("evergreen", 0)
        self.assertEqual(built, ["good"], "the ranking topic never costs a build, a photo search and a run")
        self.assertEqual(self.blocked[0][0], "rank")
        self.assertIn("ranks a product or institution", self.blocked[0][1])

    def test_a_value_error_from_the_compiler_rotates_to_the_next_topic(self):
        seen = []

        def build(kind, slot, candidate):
            seen.append(candidate["id"])
            if candidate["id"] == "bad":
                raise ValueError("MASTER V2 REJECTED — content policy: possible exposed payment-card-like number")
            return self.build_ok(kind, slot, candidate)
        pipeline.build_candidate = build
        self.plan["evergreen"][0] = {"id": "bad", "title": PLAIN, "category": "Banking"}
        pipeline.replace_blocked_topic = lambda plan, kind, slot, item: {"id": "next", "title": "Another explainer",
                                                                          "category": "Banking"}
        pipeline.prepare("evergreen", 0)
        self.assertEqual(seen, ["bad", "next"], "the refusal is a reason to change topic, not to stop the day")
        self.assertIn("bad", self.plan.get("blockedTopics", {}))

    def test_no_substitute_is_invented_when_the_pool_is_empty(self):
        def build(kind, slot, candidate):
            raise ValueError("MASTER V2 REJECTED — content policy: deceptive financial or commercial promise")
        pipeline.build_candidate = build

        def none(plan, kind, slot, item):
            raise RuntimeError("no unused evergreen topic remains for slot 0")
        pipeline.replace_blocked_topic = none
        with self.assertRaises(RuntimeError) as caught:
            pipeline.prepare("evergreen", 0)
        self.assertIn("no unused evergreen topic remains", str(caught.exception))
        self.assertNotIn("None", str(caught.exception))


class TheReasonTravelsWithTheFailure(unittest.TestCase):
    def test_the_tripped_phrase_is_quoted_back(self):
        text = ("PPF investors are promised guaranteed returns every year, and the small savings scheme "
                "is opened at any post office in India with a minimum deposit of five hundred rupees.")
        issues = audit_text("PPF and small savings", text, "master-package", False)
        self.assertIn("deceptive financial or commercial promise", issues)
        snippet = policy_evidence("PPF and small savings", text, issues)
        self.assertIn("guaranteed returns", snippet)

    def test_a_long_number_is_masked_on_the_way_out(self):
        text = ("The payment switch logged the transaction against the identifier 4111111111111111 for the "
                "settlement window that closed at the end of the quarter in India this year for readers.")
        issues = audit_text("Payments", text, "master-package", False)
        self.assertIn("possible exposed payment-card-like number", issues)
        snippet = policy_evidence("Payments", text, issues)
        self.assertTrue(snippet, "the failure must say what it caught")
        self.assertNotIn("4111111111111111", snippet, "a real number must not be copied into a public file")
        self.assertIn("41", snippet)

    def test_nothing_about_the_gate_can_be_bargained_with(self):
        source = (ROOT / "content_policy_guard.py").read_text(encoding="utf-8")
        self.assertIn('if title_needs_ranking_methodology(title):', source)
        self.assertNotIn("RANKING_TITLE = None", source)


if __name__ == "__main__":
    unittest.main()
