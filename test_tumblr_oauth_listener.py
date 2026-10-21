#!/usr/bin/env python3
"""The listener that ends the sixty-second race, driven against a fake GitHub and a fake Tumblr.

Every earlier route for re-authorising Tumblr asked a person to save a code and then start a run, and
a Tumblr code is single-use and worth roughly thirty to sixty seconds. The queue alone is longer than
the code's life, so the attempts failed in a row and each failure looked like a mistake by whoever
pressed the buttons. The listener reverses who waits: the job is already running, and a code is
exchanged seconds after the commit that carries it.

These tests drive that loop with the network replaced. They assert the four promises that matter: a
new code is exchanged once, the same spent code is never offered twice, a refusal keeps the watch
alive, and the code itself never appears in a log line, a record or a commit.
"""
import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

import tumblr_oauth_listener as tl

ROOT = Path(__file__).resolve().parent
CODE = "206d18fac7f75653c62087e2f48813cc06765f04"


def drive(reads, exchange_result, scrub=True, minutes=2, chat_every=1):
    """Run main() with the outside world replaced; the last read repeats until the clock runs out."""
    state = {"clock": 0, "poll": 0}

    def read():
        item = reads[min(state["poll"], len(reads) - 1)]
        state["poll"] += 1
        return item

    with mock.patch.object(tl, "read_code_file", side_effect=read), \
         mock.patch.object(tl, "exchange", return_value=exchange_result) as exchange, \
         mock.patch.object(tl, "record_outcome", return_value="refused by Tumblr"), \
         mock.patch.object(tl, "commit_local", return_value=True), \
         mock.patch.object(tl, "scrub_and_push", return_value=scrub) as scrubber, \
         mock.patch.object(tl, "CHAT_EVERY", chat_every), \
         mock.patch.object(tl.time, "sleep", lambda seconds: state.__setitem__("clock", state["clock"] + seconds)), \
         mock.patch.object(tl.time, "time", lambda: state["clock"]), \
         mock.patch.dict(tl.os.environ, {"LISTENER_MINUTES": str(minutes)}), \
         contextlib.redirect_stdout(io.StringIO()) as out:
        code = tl.main()
    return code, out.getvalue(), exchange, scrubber


class PicksTheCode(unittest.TestCase):
    def test_accepts_the_bare_code_the_whole_address_and_a_mangled_one(self):
        for value in (CODE,
                      f"https://github.com/o/r?code={CODE}&state=x#=_",
                      f"https://github.com/o/r?code={CODE}&amp;state=x"):
            with self.subTest(value=value[:24]):
                self.assertEqual(tl.pick_code(value), CODE)

    def test_an_untouched_template_is_not_a_code(self):
        template = (ROOT / ".github" / "tumblr-oauth-code").read_text(encoding="utf-8")
        self.assertEqual(tl.pick_code(template), "",
                         "the file as committed must never look like a live credential")
        self.assertEqual(tl.pick_code("# comment\n\n"), "")
        self.assertEqual(tl.pick_code(""), "")


class NeverLeavesTheCodeBehind(unittest.TestCase):
    def test_redaction_covers_the_value_and_its_prefix(self):
        self.assertNotIn(CODE, tl.redact(f"failed with {CODE}", CODE))
        self.assertNotIn(CODE[:12], tl.redact(f"failed with {CODE[:20]}", CODE))
        self.assertEqual(tl.redact("nothing to hide", ""), "nothing to hide")

    def test_the_recorded_reason_is_the_last_line_without_the_code(self):
        with mock.patch.object(tl.subprocess, "run") as run:
            reason = tl.record_outcome(CODE, 2, "noise\nRuntimeError: " + CODE + " refused\n")
        self.assertEqual(reason, "RuntimeError: [one-time code] refused")
        scripts = [" ".join(map(str, call.args[0])) for call in run.call_args_list]
        self.assertTrue(any("social_credential_health.py" in line for line in scripts), scripts)
        self.assertTrue(any("tumblr_attempt_record.py" in line for line in scripts), scripts)
        # The reason handed to the recorders must not be JSON noise or the code itself.
        written = Path("/tmp/tumblr-listener.err").read_text(encoding="utf-8")
        self.assertNotIn(CODE, written)
        self.assertIn("refused", written)

    def test_no_log_line_ever_contains_the_code(self):
        _, printed, _, _ = drive([("", "sha-0", "ok"), (CODE, "sha-1", "ok"), ("", "sha-2", "ok")],
                                 (2, f"exchanging {CODE} now", f"RuntimeError: {CODE} refused"),
                                 minutes=1)
        self.assertNotIn(CODE, printed)


class LoopBehaviour(unittest.TestCase):
    def test_it_waits_and_exchanges_the_first_new_code_it_sees(self):
        result, printed, exchange, scrubber = drive(
            [("", "sha-0", "ok"), ("", "sha-0", "ok"), (CODE, "sha-1", "ok"), ("", "sha-2", "ok")],
            (0, "verified", ""))
        self.assertEqual(result, 0)
        exchange.assert_called_once_with(CODE)
        scrubber.assert_called_once_with(CODE)
        self.assertIn("nothing pasted yet", printed)
        self.assertIn("Tumblr is authorised", printed)

    def test_a_refusal_keeps_watching_and_never_offers_the_spent_code_twice(self):
        result, printed, exchange, _ = drive(
            [("", "sha-0", "ok"), (CODE, "sha-1", "ok"), ("", "sha-2", "ok")], (2, "", "refused"))
        self.assertEqual(result, 0)
        self.assertEqual(exchange.call_count, 1, "a refused code must not be offered again")
        self.assertIn("paste a fresh one", printed)

    def test_a_code_left_in_the_file_after_a_failure_is_not_retried_forever(self):
        # The scrub may be refused; then the same blob sha must not be acted on twice.
        result, printed, exchange, _ = drive([("", "sha-0", "ok"), (CODE, "sha-1", "ok")], (2, "", "refused"),
                                            scrub=False, minutes=1)
        self.assertEqual(exchange.call_count, 1, "one attempt per blob, however long the watch runs")

    def test_a_scrub_failure_is_reported_as_a_chore_not_a_lie(self):
        _, printed, _, _ = drive([("", "sha-0", "ok"), (CODE, "sha-1", "ok")], (0, "verified", ""), scrub=False)
        self.assertIn("could not be scrubbed", printed)

    def test_a_read_failure_retries_rather_than_crashing(self):
        # The refused read must come after the startup read, which deliberately ignores what is
        # already in the file so an old code is never tried.
        _, printed, _, _ = drive([("", "sha-0", "ok"), ("", "", "read refused (403)"), ("", "sha-0", "ok")],
                                 (0, "", ""), minutes=1)
        self.assertIn("read refused (403); will retry", printed)

    def test_the_window_closes_as_no_code_rather_than_a_failure(self):
        result, printed, exchange, _ = drive([("", "sha-0", "ok")], (0, "", ""), minutes=1)
        self.assertEqual(result, 0)
        self.assertEqual(exchange.call_count, 0)
        self.assertIn("window closed without a code", printed)


class WindowSizing(unittest.TestCase):
    """A push run has no dispatch input, and an empty one must not kill the watch."""

    def window(self, value):
        with mock.patch.dict(tl.os.environ, {"LISTENER_MINUTES": value}):
            return tl.window_minutes()

    def test_unusable_values_become_the_full_window(self):
        for value in ("", "soon", "0.5", None):
            with self.subTest(value=value):
                if value is None:
                    with mock.patch.dict(tl.os.environ, {}, clear=True):
                        self.assertEqual(tl.window_minutes(), 170)
                else:
                    self.assertEqual(self.window(value), 170)

    def test_a_requested_window_is_honoured_but_stays_inside_the_job_limit(self):
        self.assertEqual(self.window("5"), 5)
        self.assertEqual(self.window("170"), 170)
        self.assertEqual(self.window("99999"), 178)
        self.assertEqual(self.window("0"), 1)


class Wiring(unittest.TestCase):
    TEXT = (ROOT / ".github" / "workflows" / "tumblr_oauth_listener.yml").read_text(encoding="utf-8")

    def test_a_commit_starting_the_watch_needs_no_one_to_press_run(self):
        self.assertIn("- .github/tumblr-oauth-listener", self.TEXT)
        self.assertRegex(self.TEXT, r"concurrency:\n\s+group: daily-yield-tumblr-oauth-listener")
        self.assertIn("cancel-in-progress: true", self.TEXT)

    def test_only_the_permission_it_uses_is_requested(self):
        self.assertIn("permissions:\n  contents: write\n", self.TEXT)
        for forbidden in ("secrets: read", "actions: read"):
            self.assertNotIn(forbidden, self.TEXT, f"{forbidden} is not a GitHub permission key")

    def test_the_final_advice_survives_a_failed_exchange(self):
        self.assertIn("if: ${{ !cancelled() }}", self.TEXT)
        self.assertIn("/edit/main/.github/tumblr-oauth-code", self.TEXT)

    def test_the_encryption_key_reaches_only_the_listener_process(self):
        self.assertIn("TUMBLR_TOKEN_ENCRYPTION_KEY: ${{ secrets.TUMBLR_TOKEN_ENCRYPTION_KEY }}", self.TEXT)
        self.assertNotIn("echo $TUMBLR", self.TEXT)

    def test_a_push_started_run_still_gets_a_window(self):
        self.assertIn("github.event.inputs.listen_minutes || '170'", self.TEXT)

    def test_the_listener_reports_its_own_crash_instead_of_silence(self):
        source = (ROOT / "tumblr_oauth_listener.py").read_text(encoding="utf-8")
        self.assertIn("TUMBLR_LISTENER_ERROR", source)
        self.assertIn("def window_minutes", source)

    def test_the_code_file_is_empty_of_credentials_at_rest(self):
        body = (ROOT / ".github" / "tumblr-oauth-code").read_text(encoding="utf-8")
        self.assertTrue(all(line.startswith("#") or not line.strip() for line in body.splitlines()),
                        "the committed template must hold comments only")


if __name__ == "__main__":
    unittest.main()
