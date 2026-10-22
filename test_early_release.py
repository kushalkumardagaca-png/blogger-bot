"""Tests for the one exception to the release window: a named, owner-approved early release.

The window in `publication_timing` is what the site promises its readers - articles arrive at the hour the
audience is there - and no automation, tolerance, retry or failed run may cross it. The single exception
exists because on 21 October 2026 an outstanding article was prepared in seventeen minutes and then waited
two hours for its window while the desk had asked for it immediately. The exception is deliberately awkward
to use: someone has to push a file that names the exact article and carries the owner's token.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import tempfile
import unittest
from unittest import mock

import publication_timing as timing


def frozen_clock(iso):
    """Pin the clock for a release-window test.

    `wait_for_release` decides whether to sleep by comparing the window with the IST time right now, so the
    same test took the other branch after 20:45 than before it: the suite passed by day and failed by
    night, which was a fault in the test rather than in the code. Pinned on 22 October 2026, when the daily
    run reported it after the window had gone by.
    """
    moment = dt.datetime.fromisoformat(iso)

    class Frozen:
        @staticmethod
        def now(tz=None):
            return moment.astimezone(tz) if tz else moment

    return mock.patch.object(timing.dt, "datetime", Frozen())


class Marker:
    """Writes a throwaway authorisation file and points the module at it."""

    def __init__(self, text):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.path = self.tmp / "master-early-release"
        if text is not None:
            self.path.write_text(text, encoding="utf-8")

    def __enter__(self):
        return mock.patch.object(timing, "EARLY_FILE", self.path)

    def __exit__(self, *exc):
        return False


class OnlyWhatTheFileNames(unittest.TestCase):
    def test_no_file_means_no_early_release_for_anybody(self):
        with Marker(None) as patched:
            patched.start()
            self.assertEqual(timing.early_release("trending", 4), "")

    def test_the_token_has_to_be_present(self):
        with Marker("trending:4 the run wanted to finish early\n") as patched:
            patched.start()
            self.assertEqual(timing.early_release("trending", 4), "")

    def test_a_named_slot_does_not_authorise_a_different_one(self):
        with Marker("trending:4 owner-approved - now\n") as patched:
            patched.start()
            self.assertEqual(timing.early_release("trending", 3), "")
            self.assertEqual(timing.early_release("evergreen", 4), "")
            self.assertIn("now", timing.early_release("trending", 4))

    def test_a_stale_line_about_another_slot_cannot_be_read_as_this_one(self):
        with Marker("trending:0 owner-approved - retired after use\n") as patched:
            patched.start()
            self.assertEqual(timing.early_release("trending", 4), "")


class TheWindowIsSkippedOnce(unittest.TestCase):
    def test_an_authorised_article_is_released_without_sleeping(self):
        with Marker("trending:4 owner-approved - the desk asked for it now\n") as patched, \
             mock.patch.object(timing.time, "sleep") as slept, frozen_clock("2026-10-22T20:00:00+05:30"):
            patched.start()
            lateness = timing.wait_for_release("20:45", allow_early=("trending", 4))
        slept.assert_not_called()
        self.assertLessEqual(abs(lateness), 0.0001)

    def test_an_unauthorised_article_still_waits_for_its_window(self):
        with Marker("trending:4 owner-approved - the desk asked for it now\n") as patched, \
             mock.patch.object(timing.time, "sleep") as slept, frozen_clock("2026-10-22T20:00:00+05:30"):
            patched.start()
            timing.wait_for_release("20:45", allow_early=("trending", 0))
        slept.assert_called_once()
        self.assertGreater(slept.call_args[0][0], 0)
        self.assertEqual(round(slept.call_args[0][0]), 45 * 60,
                         "the whole window is what it waits for, not a token amount")

    def test_a_window_that_has_already_passed_is_not_waited_for(self):
        """The other side of the same rule, and the side that used to depend on what time it was."""
        with Marker("unrelated:9 owner-approved\n") as patched, \
             mock.patch.object(timing.time, "sleep") as slept, frozen_clock("2026-10-22T21:30:00+05:30"):
            patched.start()
            timing.wait_for_release("20:45", allow_early=("trending", 0))
        slept.assert_not_called()

    def test_dry_runs_never_sleep_whether_authorised_or_not(self):
        with Marker(None) as patched, mock.patch.object(timing.time, "sleep") as slept:
            patched.start()
            self.assertEqual(timing.wait_for_release("20:45", dry=True, allow_early=("trending", 4)), 0)
        slept.assert_not_called()


class TheCodeStaysHonest(unittest.TestCase):
    def test_the_release_path_is_the_only_one_consulting_the_marker(self):
        pipeline = pathlib.Path(timing.__file__).with_name("master_v3_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("wait_for_release(MASTER_LIVE[(kind,slot)],allow_early=(kind,slot))", pipeline)
        self.assertEqual(pipeline.count("wait_for_release("), 1)

    def test_the_writer_listens_for_the_marker(self):
        text = (pathlib.Path(timing.__file__).with_name(".github") / "workflows" / "master_trending_writer.yml").read_text(encoding="utf-8")
        self.assertIn("- '.github/master-early-release'", text)


if __name__ == "__main__":
    unittest.main()
