#!/usr/bin/env python3
"""Why the blog published nothing on Tumblr for two days, and what keeps it from recurring.

Tumblr rotates the refresh token at every exchange, so the bundle on disk is only correct once the
new one has been committed back to this repository. The publisher used to exchange it on *every*
run, and any run that refreshed and then failed - or was interrupted before its persist step - left
the repository holding a token Tumblr had already consumed. From that moment every attempt answered
"invalid_grant", and the automation kept presenting the dead token. These tests pin the repair:
reuse the access token while it is valid, exchange it only when it must be exchanged, never retry a
refused grant, and say what the one repair is.
"""
import json
import tempfile
import unittest

import yaml
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import tumblr_publisher as tp

ROOT = Path(__file__).resolve().parent


def bundle(**over):
    row = {"access_token": "stored-access", "refresh_token": "stored-refresh",
           "expires_in": 1576800, "scope": "basic write offline_access",
           "obtained_at": datetime.now(tp.IST).isoformat()}
    row.update(over)
    return row


class Reuse(unittest.TestCase):
    def test_a_live_access_token_is_used_rather_than_exchanged(self):
        with mock.patch.object(tp, "decrypt_bundle", return_value=bundle()), \
             mock.patch.object(tp, "request", side_effect=AssertionError("must not touch Tumblr")):
            self.assertEqual(tp.access_token_or_refresh(), "stored-access")

    def test_an_expired_access_token_is_exchanged_once_and_stamped(self):
        stale = bundle(obtained_at=(datetime.now(tp.IST) - timedelta(days=30)).isoformat())
        saved = {}
        response = mock.Mock()
        response.json.return_value = {"access_token": "new-access", "refresh_token": "new-refresh",
                                     "expires_in": 1576800, "scope": "basic write offline_access"}
        env = {"TUMBLR_CONSUMER_KEY": "ck", "TUMBLR_CONSUMER_SECRET": "cs"}
        with mock.patch.object(tp, "decrypt_bundle", return_value=stale), \
             mock.patch.dict(tp.os.environ, env, clear=False), \
             mock.patch.object(tp, "request", return_value=response) as called, \
             mock.patch.object(tp, "encrypt_bundle", side_effect=lambda b: saved.update(b)):
            self.assertEqual(tp.access_token_or_refresh(), "new-access")
            self.assertEqual(called.call_count, 1, "one exchange per run, never a retry storm")
        self.assertEqual(saved["refresh_token"], "new-refresh")
        self.assertIn("obtained_at", saved, "the next run must know how old this token is")
        self.assertEqual(saved["scope"], "basic write offline_access")

    def test_a_legacy_bundle_without_a_date_exchanges_instead_of_guessing(self):
        legacy = bundle()
        legacy.pop("obtained_at")
        response = mock.Mock()
        response.json.return_value = {"access_token": "new-access", "refresh_token": "new-refresh",
                                     "expires_in": 1576800, "scope": "basic write offline_access"}
        with mock.patch.object(tp, "decrypt_bundle", return_value=legacy), \
             mock.patch.dict(tp.os.environ, {"TUMBLR_CONSUMER_KEY": "ck", "TUMBLR_CONSUMER_SECRET": "cs"}), \
             mock.patch.object(tp, "request", return_value=response), \
             mock.patch.object(tp, "encrypt_bundle"):
            self.assertEqual(tp.access_token_or_refresh(), "new-access")

    def test_age_of_a_bundle_is_measured_or_reported_unknown(self):
        self.assertIsNone(tp.token_age_seconds({"access_token": "a"}))
        age = tp.token_age_seconds(bundle(obtained_at=(datetime.now(tp.IST) - timedelta(minutes=5)).isoformat()))
        self.assertTrue(240 < age < 400, age)


class HonestFailure(unittest.TestCase):
    def test_a_refused_grant_names_the_repair_and_is_not_retried(self):
        message = ('request failed: https://api.tumblr.com/v2/oauth2/token: 400 Client Error: '
                   'Bad Request for url: {"error":"invalid_grant",'
                   '"error_description":"Invalid refresh token"}')

        def refuse(*a, **k):
            raise RuntimeError(message)

        with mock.patch.object(tp, "decrypt_bundle", return_value=bundle(obtained_at="not-a-date")), \
             mock.patch.dict(tp.os.environ, {"TUMBLR_CONSUMER_KEY": "ck", "TUMBLR_CONSUMER_SECRET": "cs"}), \
             mock.patch.object(tp, "request", side_effect=refuse) as called:
            with self.assertRaises(RuntimeError) as caught:
                tp.refresh_access()
        reason = str(caught.exception)
        self.assertEqual(called.call_count, 1, "a consumed token must not be presented twice")
        self.assertIn("invalid_grant", reason)
        self.assertIn("tumblr_oauth_bootstrap.py", reason, "the reason must carry the one action that fixes it")
        self.assertIn("re-authoris", reason)

    def test_a_transient_failure_is_still_passed_through_unchanged(self):
        with mock.patch.object(tp, "decrypt_bundle", return_value=bundle(obtained_at="x")), \
             mock.patch.dict(tp.os.environ, {"TUMBLR_CONSUMER_KEY": "ck", "TUMBLR_CONSUMER_SECRET": "cs"}), \
             mock.patch.object(tp, "request", side_effect=RuntimeError("request failed: 503 upstream")):
            with self.assertRaises(RuntimeError) as caught:
                tp.refresh_access()
        self.assertIn("503", str(caught.exception))
        self.assertNotIn("tumblr_oauth_bootstrap.py", str(caught.exception))


class WorkflowShape(unittest.TestCase):
    def test_every_channel_commits_its_state_even_after_a_refusal(self):
        text = (ROOT / ".github" / "workflows" / "coordinated_social_publish.yml").read_text(encoding="utf-8")
        blocks = json.dumps([line for line in text.splitlines() if "Persist" in line or "!cancelled()" in line])
        self.assertEqual(4, text.count("if: ${{ !cancelled() }}"), "one per network: " + blocks)
        self.assertEqual(4, text.count("files+=(SOCIAL_CREDENTIAL_HEALTH.json)"))

    def test_the_publisher_asks_the_clock_before_the_network(self):
        source = (ROOT / "tumblr_publisher.py").read_text(encoding="utf-8")
        self.assertIn("def access_token_or_refresh", source)
        self.assertIn("token=access_token_or_refresh()", source)
        self.assertNotIn("token=refresh_access();user=verify_account(token)", source)


class ReAuthorisationRoute(unittest.TestCase):
    """The owner can only re-authorise where the encryption key lives - in GitHub Actions.

    Running the bootstrap on a laptop cannot work, because TUMBLR_TOKEN_ENCRYPTION_KEY exists only
    as a repository secret, so the workflow must take the one-time code from a secret (never from a
    visible dispatch input, which would be readable in a public repository's run page), record the
    result, and tolerate being run twice.
    """

    TEXT = (ROOT / ".github" / "workflows" / "tumblr_oauth_bootstrap.yml").read_text(encoding="utf-8")

    def test_the_code_arrives_as_a_secret_not_a_public_input(self):
        self.assertIn("TUMBLR_AUTHORIZATION_CODE: ${{ secrets.TUMBLR_AUTHORIZATION_CODE }}", self.TEXT)
        self.assertNotIn("inputs.authorization", self.TEXT)

    def test_the_result_is_recorded_and_a_repeat_run_is_harmless(self):
        self.assertIn("social_credential_health.py --platform tumblr", self.TEXT)
        self.assertIn("git diff --staged --quiet", self.TEXT)
        self.assertIn("Tumblr authorisation could not be completed", self.TEXT)

    def test_the_refusal_reason_and_the_repair_reach_the_run_page(self):
        # The 21 October failure was readable only in a screenshot: the step that was supposed to
        # explain it could not itself be parsed, and the token file it should have kept was
        # committed only on the success path.
        self.assertIn("--extract", self.TEXT)
        self.assertIn("TUMBLR_AUTHORIZATION_CODE secret", self.TEXT)
        steps = [step for step in yaml.safe_load(self.TEXT)["jobs"]["authorize"]["steps"]]
        commit = [step for step in steps if "Commit encrypted token bundle" in str(step.get("name"))]
        self.assertEqual(len(commit), 1)
        self.assertEqual(commit[0].get("if"), "${{ !cancelled() }}")

    def test_the_bundles_obtain_their_timestamp_through_the_publisher(self):
        boot = (ROOT / "tumblr_oauth_bootstrap.py").read_text(encoding="utf-8")
        self.assertIn('"obtained_at"', boot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
