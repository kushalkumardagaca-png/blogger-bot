#!/usr/bin/env python3
"""A wide desk must fit the edition budget instead of failing the whole slot."""
from __future__ import annotations

import sys
import unittest

import news_pipeline as np


def article(sections, items_each, words_each=120):
    body = ['<article>']
    for name in sections:
        body.append(f'<h2 class="fbk-h2"><b>01</b> {name}</h2>')
        body.append('<p class="fbk-sub">Section.</p>')
        for index in range(items_each):
            filler = " ".join(["reported"] * words_each)
            body.append(
                '<div class="fbk-item"><span class="fbk-chip">Source</span>'
                f'<h3>{name} item {index}</h3><p>{filler}</p>'
                '<a class="fbk-src" href="https://example.com/x">Official source</a></div>')
    body.append("</article>")
    return "".join(body)


class QuietDeskIsSkippedNotFailed(unittest.TestCase):
    """A news hour with nothing new is a skip, not a red run and not an email.

    Seven of the failing runs on 21-22 October were recovery dispatches that landed between two wire
    bursts: the desk had only background context, `no current sourced items available` raised, and the
    whole workflow was marked failed for a site that correctly had nothing to report. The pipeline now
    records that desk as SKIPPED and leaves the run green - while a fit that genuinely cannot be found,
    a refused Blogger post or a wrong edition fingerprint still fails exactly as loudly as before.
    """

    def test_only_background_items_raise_the_quiet_condition(self):
        with self.assertRaises(np.NothingToReport) as seen:
            np.build_fitted_news_article(
                "markets", [{"background": True, "title": "Older context", "summary": "context",
                             "url": "https://wires.test/old", "agency": "reuters", "item_time": None}],
                [], __import__("datetime").date(2026, 10, 22), None, None, {}, [], [], None)
        self.assertIn("no current sourced item", str(seen.exception))

    def test_the_quiet_condition_is_still_a_value_error_for_older_callers(self):
        self.assertTrue(issubclass(np.NothingToReport, ValueError),
                        "anything that already handled a failed fit must keep handling it")

    def test_main_reports_a_quiet_desk_as_skipped_and_exits_zero(self):
        import json
        import os
        import pathlib
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as work:
            handle = open(pathlib.Path(work) / "NEWS_PIPELINE_STATUS.json", "w")
            previous = os.getcwd()
            os.chdir(work)
            try:
                def raise_quiet(desk, tracker, dry, token, **_):
                    raise np.NothingToReport(f"{desk}: no current sourced item in this window")

                argv = ["news_pipeline.py", "--desks", "markets", "--dry-run"]
                with mock.patch.object(np, "run_desk", raise_quiet), \
                        mock.patch.object(np, "load_tracker", lambda *a, **k: {"desks": {}}), \
                        mock.patch.object(np, "load_today_story_keys", lambda *a, **k: (set(), set())), \
                        mock.patch.object(np, "SOCIAL_EVENTS_FILE", str(pathlib.Path(work) / "social_events.json")), \
                        mock.patch.object(sys, "argv", argv):
                    np.main()
            finally:
                handle.close()
                os.chdir(previous)
            report = json.loads((pathlib.Path(work) / "NEWS_PIPELINE_STATUS.json").read_text())
            self.assertEqual(report["failed"], 0, report)
            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual(report["results"][0]["status"], "SKIPPED", report)
            self.assertIn("no current sourced item", report["results"][0]["reason"])

    def test_a_real_defect_still_fails_the_run(self):
        import os
        import pathlib
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as work:
            handle = open(pathlib.Path(work) / "NEWS_PIPELINE_STATUS.json", "w")
            previous = os.getcwd()
            os.chdir(work)
            try:
                def broken(desk, tracker, dry, token, **_):
                    raise RuntimeError("EDITION IDENTITY FAILED")

                argv = ["news_pipeline.py", "--desks", "markets", "--dry-run"]
                with mock.patch.object(np, "run_desk", broken), \
                        mock.patch.object(np, "load_tracker", lambda *a, **k: {"desks": {}}), \
                        mock.patch.object(np, "load_today_story_keys", lambda *a, **k: (set(), set())), \
                        mock.patch.object(np, "SOCIAL_EVENTS_FILE", str(pathlib.Path(work) / "social_events.json")), \
                        mock.patch.object(sys, "argv", argv):
                    with self.assertRaises(SystemExit) as exit_seen:
                        np.main()
                    self.assertEqual(exit_seen.exception.code, 1)
            finally:
                handle.close()
                os.chdir(previous)



class TrimNewsItemsTests(unittest.TestCase):
    def test_an_overlong_edition_is_fitted_without_emptying_a_section(self):
        document = article(["Global", "India", "China"], items_each=12, words_each=120)
        before = np.editorial_word_count(document)
        self.assertGreater(before, np.NEWS_MAX_WORDS)
        trimmed, count = np.trim_news_items(document)
        self.assertLessEqual(count, np.NEWS_MAX_WORDS)
        for name in ("Global", "India", "China"):
            section_start = trimmed.index(f"{name}</h2>")
            following = trimmed[section_start:]
            next_heading = following.find('<h2 class="fbk-h2">', 10)
            block = following if next_heading == -1 else following[:next_heading]
            self.assertIn('<div class="fbk-item">', block, f"{name} lost every item")

    def test_a_document_already_inside_the_budget_is_untouched(self):
        document = article(["Global"], items_each=2, words_each=100)
        self.assertEqual(np.trim_news_items(document)[0], document)

    def test_attribution_survives_every_removal(self):
        document = article(["Global", "India"], items_each=10, words_each=150)
        trimmed, _ = np.trim_news_items(document)
        items = trimmed.count('<div class="fbk-item">')
        self.assertEqual(trimmed.count('class="fbk-src"'), items)


if __name__ == "__main__":
    unittest.main()
