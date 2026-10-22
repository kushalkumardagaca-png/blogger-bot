"""Tests for the resilience added after 21 October 2026, when ten Master slots lost hours of the day.

Five articles landed late, one landed eight hours late, and the writers logged fifteen failed runs - every
one of them dying inside the same preparation step. The causes were not exotic: one request per model
provider, so a rate limit ended the section; a quota-independent fallback that raised an exception whenever
a source was too short to quote, which threw away the slot it was supposed to save; a validator that
treated the digits inside a publication's own name as an unsupported claim; and photo pools built from
yesterday's plan because the nightly build ran five minutes before today's plan was written.

Each test here pins one of those failure shapes. None of them lowers a standard: the window, the citation
rule, the number rule and the three-photograph rule are all still enforced, and one is asserted to still
reject bad prose. The window is now *derived* from the section rule it was contradicting (see
TheDocumentWindowMatchesItsSections below), which is a consistency repair, not a concession: the per-section
floor of 400 words, the four-paragraph rule and the three-photograph rule are unchanged, and the assembly
check became harder to satisfy for short articles, not easier.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import master_failure_brief
import master_v3_generator as gen
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parent


class EnoughTime:
    """Stand-in for the run's clock: never short of time, so retries are allowed to be tried."""

    def out(self):
        return False

    def remaining(self):
        return 3600.0

    def seconds(self, ceiling=60, floor=5):
        return ceiling

    def note(self):
        return {"minutes_used": 1}

    def stop(self, doing):
        return RuntimeError(f"out of time while {doing}")


def long_text(count=160):
    return " ".join(f"sentence number {index} carries plain wording only" for index in range(count))


class BusyProviderIsRetried(unittest.TestCase):
    def setUp(self):
        self.saved = gen.BUDGET
        gen.BUDGET = EnoughTime()
        self.addCleanup(lambda: setattr(gen, "BUDGET", self.saved))

    def test_a_rate_limited_primary_is_asked_again_and_its_answer_is_used(self):
        calls = {"n": 0}

        def flaky(prompt, max_tokens=1400):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("models.github.ai HTTP 429: rate limit exceeded")
            return long_text()

        with mock.patch.object(gen, "github_text", flaky), \
             mock.patch.object(gen, "sleep_within_budget", lambda *_: True):
            self.assertEqual(len(gen.text_call("write it").split()), len(long_text().split()))
        self.assertEqual(calls["n"], 3)

    def test_a_provider_that_is_not_authorised_is_not_asked_again(self):
        with mock.patch.object(gen, "github_text", side_effect=RuntimeError("HTTP 401: bad credentials")) as primary, \
             mock.patch.object(gen, "ollama_text", side_effect=RuntimeError("model not loaded")) as local:
            with self.assertRaises(RuntimeError) as caught:
                gen.text_call("write it")
        self.assertEqual(primary.call_count, 1)
        self.assertEqual(local.call_count, 1)
        self.assertIn("401", str(caught.exception))

    def test_only_transient_statuses_count_as_busy(self):
        for detail in ("HTTP 429", "HTTP 503: unavailable", "408 request timeout", "502 Bad Gateway"):
            self.assertTrue(gen.provider_looks_busy(detail), detail)
        for detail in ("HTTP 401", "HTTP 403 forbidden", "HTTP 404 not found", ""):
            self.assertFalse(gen.provider_looks_busy(detail), detail)

    def test_a_wait_is_never_taken_when_the_run_cannot_afford_it(self):
        class AlmostOut(EnoughTime):
            def remaining(self):
                return 200.0

        gen.BUDGET = AlmostOut()
        with mock.patch.object(gen.time, "sleep") as slept:
            self.assertFalse(gen.sleep_within_budget(25, "github_text"))
        slept.assert_not_called()


class TheQuotaFallbackNeverLosesASlot(unittest.TestCase):
    """The fallback exists for the hour the models are down, so it must not raise on thin material."""

    def test_sources_too_short_to_quote_still_make_a_valid_section(self):
        sources = [(1, {"name": "Reuters", "title": "Nikkei falls as tech sells off", "text": "Two words."}),
                   (2, {"name": "Bloomberg", "title": "Oil rises on supply concern", "text": "Brief."}),
                   (3, {"name": "ET Markets", "title": "Bank stocks slide", "text": "x" * 40}),
                   (4, {"name": "Mint", "title": "Rupee steady", "text": "y" * 30})]
        paragraphs = gen.deterministic_section("Markets in motion", sources)
        self.assertGreaterEqual(len(paragraphs), 4)
        ok, why = gen.validate_section(paragraphs, gen.evidence_text(sources))
        self.assertTrue(ok, why)
        self.assertTrue(all("[[S" in paragraph for paragraph in paragraphs))

    def test_two_unquotable_records_are_enough_to_say_something_true(self):
        sources = [(1, {"name": "CNBC-TV18", "title": "Market record number 0 on policy", "text": "z" * 400}),
                   (2, {"name": "IRS", "title": "Publication 590-B", "text": "brief note"})]
        paragraphs = gen.deterministic_section("Evidence angle", sources)
        ok, why = gen.validate_section(paragraphs, gen.evidence_text(sources))
        self.assertTrue(ok, why)

    def test_a_figure_inside_a_providers_own_name_is_not_an_invented_claim(self):
        supported = gen.evidence_text([(1, {"name": "CNBC-TV18", "title": "Markets", "text": "text"})])
        self.assertIn("18", " ".join(supported.values()))

    def test_a_number_the_models_invented_is_still_rejected(self):
        sources = [(1, {"name": "Reuters", "title": "Bank lending and market conditions",
                        "text": "Banks reported slower growth in the quarter. " * 40})]
        section = gen.deterministic_section("Bank lending", sources)
        ok, why = gen.validate_section(section, gen.evidence_text(sources))
        self.assertTrue(ok, why)
        section[1] = "The sector lost Rs 4123 crore in the quarter. " + section[1]
        ok, why = gen.validate_section(section, gen.evidence_text(sources))
        self.assertFalse(ok)
        self.assertIn("unsupported number", why)

    def test_the_evidence_basis_names_what_a_citation_may_carry(self):
        rows = [(7, {"name": "Name", "title": "Title", "text": "Body"})]
        self.assertEqual(gen.evidence_text(rows), {7: "Body Title Name"})


class PhotosArePooledBeforeTheyAreHunted(unittest.TestCase):
    def test_a_topic_without_a_pool_builds_one_before_the_live_search(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        fake_library = mock.Mock(MASTER_DIR=tmp, slugify=lambda value: value, ensure_master_pool=mock.Mock())
        built = {}

        def ensure(topic_key, title, briefs, target):
            built["args"] = (topic_key, title, target)

        fake_library.ensure_master_pool.side_effect = ensure
        with mock.patch.dict(sys.modules, {"photo_library": fake_library}), \
             mock.patch.object(gen, "BUDGET", EnoughTime()), \
             mock.patch.object(gen, "choose_photos", return_value=[{"placement": 1}] * 3) as chosen:
            gen.photo_set("Nikkei falls as tech sells off", "Markets", "nikkei-falls", "f042d1602df6951f")
        self.assertEqual(built["args"], ("f042d1602df6951f", "Nikkei falls as tech sells off", 4))
        chosen.assert_called_once()

    def test_a_full_pool_is_left_alone_and_a_failing_build_cannot_stop_an_article(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / "topic.json"
        tmp.write_text(json.dumps({"entries": [{"source_id": str(n)} for n in range(6)]}), encoding="utf-8")
        fake_library = mock.Mock(MASTER_DIR=tmp.parent, slugify=lambda value: value,
                                 ensure_master_pool=mock.Mock(side_effect=RuntimeError("commons unreachable")))
        with mock.patch.dict(sys.modules, {"photo_library": fake_library}), \
             mock.patch.object(gen, "BUDGET", EnoughTime()), \
             mock.patch.object(gen, "choose_photos", return_value=["a", "b", "c"]):
            self.assertEqual(gen.photo_set("Oil rises", "Markets", "oil-rises", "topic"), ["a", "b", "c"])
        fake_library.ensure_master_pool.assert_not_called()


class TheRunLeavesItsReason(unittest.TestCase):
    def test_a_failed_run_writes_one_small_brief_and_nothing_else(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        status = tmp / "MASTER_AUTOMATION_STATUS.json"
        status.write_text(json.dumps({"status": "FAIL", "stage": "prepare", "kind": "trending", "slot": 1,
                                      "error_type": "RuntimeError",
                                      "error": "V3 photo search exhausted " + ("every broadened search " * 90)}),
                                 encoding="utf-8")
        out = tmp / "MASTER_FAILURE_BRIEF.json"
        with mock.patch.object(sys, "argv", ["master_failure_brief.py", "--workflow", "master_trending_writer.yml",
                                             "--kind", "trending", "--slot", "1", "--run", "493",
                                             "--status-file", str(status), "--out", str(out)]):
            self.assertEqual(master_failure_brief.main(), 0)
        row = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(row["workflow"], "master_trending_writer.yml")
        self.assertEqual(row["run"], "493")
        self.assertTrue(row["error"].startswith("V3 photo search exhausted"))
        self.assertLessEqual(len(row["error"]), 900)
        self.assertFalse(row["published_after_this"])

    def test_a_missing_or_unreadable_status_file_still_leaves_a_readable_brief(self):
        row = master_failure_brief.brief_for({}, "master_evergreen_writer.yml", "evergreen", "3", "519")
        self.assertEqual(row["error"], "no persisted reason")
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(row["stage"], "preparation")


class TheWorkflowsCarryTheFix(unittest.TestCase):
    def setUp(self):
        self.writers = {name: (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                        for name in ("master_trending_writer.yml", "master_evergreen_writer.yml")}

    def test_both_writers_publish_the_reason_when_they_fail(self):
        for name, text in self.writers.items():
            self.assertIn("- name: Leave the failure reason where the morning check reads it", text, name)
            block = text.split("- name: Leave the failure reason where the morning check reads it", 1)[1]
            block = block.split("- name:", 1)[0]
            self.assertIn("- name: Leave the failure reason where the morning check reads it\n        if: failure()",
                        text, f"{name}: the brief must be written only when the run failed")
            self.assertIn("master_failure_brief.py", block, name)
            # -f, and see the test below for why: the file is untracked by design, and the run's own
            # dirty files blocked the rebase, so the reason never reached git at all.
            self.assertIn("git add -f MASTER_FAILURE_BRIEF.json", block, name)
            self.assertIn("git diff --cached --quiet", block, name)
            self.assertTrue(block.rstrip().endswith("exit 0"), f"{name}: reporting must never fail the run")
            self.assertNotIn("master_packages", block, f"{name}: only the brief is committed on failure")

    def test_photo_pools_are_now_built_after_the_days_plan_exists(self):
        text = (ROOT / ".github/workflows/photo_library_refresh.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '45 19 * * *'", text)
        self.assertNotIn("cron: '45 18 * * *'", text)
        self.assertIn("Master Topic Discovery", text)

    def test_a_failed_run_actually_lands_its_reason_in_git(self):
        # The brief was written and never committed, because the pull that follows it ran against a
        # tree the run itself had dirtied: `git pull --rebase` refuses that, all three attempts
        # failed, and the step ended quietly. That is why 21 October left fifteen red runs and no
        # explanation. -f matters for the same reason: the file is untracked by design.
        for name in ("master_trending_writer.yml", "master_evergreen_writer.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn("--autostash", text, name + " must rebase over its own dirty files")
            self.assertIn("git add -f MASTER_FAILURE_BRIEF.json", text, name + " must force the brief in")

    def test_the_preparation_budget_rule_is_untouched(self):
        for text in self.writers.values():
            self.assertIn("MASTER_PREPARATION_BUDGET_MINUTES: '30'", text)
            self.assertIn("1800-second budget", text)


class TheDocumentWindowMatchesItsSections(unittest.TestCase):
    """The 4340-word article that was thrown away on 21 October 2026.

    Ten sections of 400-490 words assemble to 4000-4900 words; the assembler demanded 4000-4200, so an
    article whose sections averaged 434 was perfect by the section rule and fatal by the document rule, and
    Trending, Evergreen and the Prewarmer all failed at the same step for the same arithmetic. The window is
    now computed from the section bounds, which also makes a 7-section article possible for the first time.

    The fixtures are written in sentences on purpose: `sentence_trim` moves whole sentences, so a block of
    text with no full stops would prove nothing about whether trimming can actually converge.
    """

    @staticmethod
    def sentences(count):
        """Exactly `count` words, in sentences of ten, so a trim has something to remove."""
        out, made = [], 0
        while made < count:
            size = min(10, count - made)
            out.append(" ".join(f"alpha{index + made}" for index in range(size)) + ".")
            made += size
        return " ".join(out)

    @classmethod
    def block(cls, sections, words_each):
        rows = []
        for index in range(sections):
            parts, left = [], words_each
            for part in range(4):
                share = (left + 3 - part) // (4 - part)
                parts.append(cls.sentences(share))
                left -= share
            rows.append({"heading": f"Section {index + 1} evidence", "paragraphs": parts})
        return rows

    def test_fixture_words_are_counted_the_way_the_generator_counts_them(self):
        for total in (400, 434, 490):
            rows = self.block(1, total)
            self.assertEqual(gen.words(" ".join(rows[0]["paragraphs"])), total,
                             f"a {total}-word section must measure {total} words here")

    def test_a_full_length_assembly_is_left_alone(self):
        sections = self.block(10, 434)
        fitted, core = gen.fit_core_to_contract(sections)
        self.assertEqual(core, 4340, "4340 words is inside the contract and must not be trimmed at all")
        self.assertEqual(fitted[0]["paragraphs"], sections[0]["paragraphs"])

    def test_an_over_long_assembly_is_trimmed_inside_the_ceiling(self):
        sections = self.block(10, 560)
        fitted, core = gen.fit_core_to_contract(sections)
        self.assertLessEqual(core, 4900, f"a 10-section document must be brought under 4900, got {core}")
        floor, _ = gen.core_window(len(fitted))
        self.assertGreaterEqual(core, floor, "trimming may not rescue the ceiling by breaking the floor")
        for row in fitted:
            self.assertGreaterEqual(gen.words(" ".join(row["paragraphs"])), 400,
                                    "no section may be trimmed below its own 400-word floor")

    def test_the_window_is_derived_from_the_number_of_sections(self):
        self.assertEqual(gen.core_window(10), (4000, 4900))
        self.assertEqual(gen.core_window(7), (2800, 3430),
                         "a 7-section article used to be impossible: it could never reach 4000")
        self.assertEqual(gen.core_window(14), (5600, 6860))

    def test_the_validator_applies_the_same_derived_rule(self):
        import master_article_v2 as v2
        good = self.block(10, 434)
        with self.assertRaises(ValueError) as refused:
            v2.validate({"policy_version": v2.POLICY_VERSION, "title": "Gold rate evidence guide",
                         "sections": good})
        self.assertNotIn("main article is", str(refused.exception),
                         "the document rule must not reject an assembly the section rule allows")
        thin = self.block(10, 380)
        with self.assertRaises(ValueError) as refused:
            v2.validate({"policy_version": v2.POLICY_VERSION, "title": "Gold rate evidence guide",
                         "sections": thin})
        message = str(refused.exception)
        self.assertIn("main article is 3800 words across 10 sections", message,
                      "a thin assembly is still refused, and the reason names the sections: " + message)
        self.assertIn("400\u2013490 words per section allows 4000\u20134900", message.replace("–", "\u2013"))

    def test_the_old_impossible_pair_cannot_come_back(self):
        import master_article_v2 as v2
        source = Path(v2.__file__).read_text(encoding="utf-8")
        self.assertNotIn("CORE_MIN,CORE_MAX=4000,4200", source,
                         "a document window has to be a multiple of the section window it is built from")
        generator_source = Path(gen.__file__).read_text(encoding="utf-8")
        self.assertNotIn("4200", generator_source, "the assembler must not hard-code a second ceiling")
        self.assertNotIn("4000<=", generator_source)


if __name__ == "__main__":
    unittest.main()
