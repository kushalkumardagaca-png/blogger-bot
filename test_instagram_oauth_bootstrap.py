#!/usr/bin/env python3
"""The one-time Instagram connection is where a mistake becomes permanent, so it is tested.

Storing a token that cannot publish, or storing a plaintext token, are both worse than
not connecting yet. These cases pin what the bootstrap must do with the code the owner
pastes once and never sees again.
"""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import instagram_oauth_bootstrap as boot
from cryptography.fernet import Fernet


class TempFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._paths = (boot.TOKEN_FILE, boot.STATE)
        boot.TOKEN_FILE = self.tmp / "instagram_token.enc"
        boot.STATE = self.tmp / "instagram_token_state.json"
        self.key = Fernet.generate_key().decode()

    def tearDown(self):
        boot.TOKEN_FILE, boot.STATE = self._paths


class Graph:
    """Answers the four calls the bootstrap is allowed to make."""

    def __init__(self, *, code_ok=True, debug_ok=True, is_valid=True, scopes=("instagram_business_basic",
                                                                               "instagram_business_content_publish"),
                 probe_ok=True):
        self.calls = []
        self.code_ok, self.debug_ok, self.is_valid = code_ok, debug_ok, is_valid
        self.scopes, self.probe_ok = list(scopes), probe_ok

    def _response(self, ok, payload):
        response = mock.Mock()
        response.ok = ok
        response.status_code = 200 if ok else 400
        response.text = json.dumps(payload)
        response.json = lambda: payload
        return response

    def post(self, url, data=None, timeout=None, **kwargs):
        self.calls.append(("POST", url))
        if not self.code_ok:
            return self._response(False, {"error_type": "OAuthRequestException",
                                          "error_message": "Invalid code"})
        return self._response(True, {"access_token": "short-lived-token", "user_id": "1784149834884056"})

    def get(self, url, params=None, timeout=None, **kwargs):
        self.calls.append(("GET", url.rsplit("/", 1)[-1]))
        if url.endswith("access_token"):
            return self._response(True, {"access_token": "long-lived-token-value", "expires_in": 5184000})
        if "debug_token" in url:
            if not self.debug_ok:
                return self._response(False, {"error": {"message": "unsupported"}})
            return self._response(True, {"data": {"is_valid": self.is_valid, "scopes": self.scopes}})
        if "content_publishing_limit" in url:
            if not self.probe_ok:
                return self._response(False, {"error": {"message": "(#10) This page requires additional "
                                                                    "permission to be used by your app"}})
            return self._response(True, {"data": [{"quota_usage_total": {"quota_usage": 0, "quota_total": 50}}]})
        return self._response(True, {"id": "1784149834884056", "username": "daily_yield",
                                    "account_type": "BUSINESS"})


class Bootstrap(TempFiles):
    def env(self, **overrides):
        base = {"INSTAGRAM_APP_ID": "app-id", "INSTAGRAM_APP_SECRET": "app-secret",
                "INSTAGRAM_REDIRECT_URI": "https://localhost:8410/callback",
                "INSTAGRAM_AUTHORIZATION_CODE": "one-time-code",
                "INSTAGRAM_TOKEN_ENCRYPTION_KEY": self.key}
        base.update(overrides)
        return base

    def _exchange(self, graph, **overrides):
        with mock.patch.dict(boot.os.environ, self.env(**overrides), clear=True), \
             mock.patch.object(boot, "requests", graph):
            return boot.main()

    def test_a_missing_value_is_named_instead_of_traced(self):
        with mock.patch.dict(boot.os.environ, self.env(INSTAGRAM_AUTHORIZATION_CODE=""), clear=True), \
             mock.patch.object(boot, "requests", Graph()):
            self.assertRaisesRegex(RuntimeError, "INSTAGRAM_AUTHORIZATION_CODE is required", boot.main)

    def test_a_refused_code_is_reported_not_swallowed(self):
        with self.assertRaisesRegex(RuntimeError, "refused the authorisation code"):
            self._exchange(Graph(code_ok=False))

    def test_a_used_code_is_explained_as_needing_a_fresh_one(self):
        with self.assertRaisesRegex(RuntimeError, "request a fresh one"):
            self._exchange(Graph(is_valid=False))

    def test_the_token_is_stored_encrypted_and_never_as_plain_text(self):
        self.assertEqual(self._exchange(Graph()), 0)
        blob = boot.TOKEN_FILE.read_bytes()
        self.assertNotIn(b"long-lived-token-value", blob, "the secret file must not hold readable text")
        key = Fernet(self.key.encode())
        self.assertEqual(Fernet.decrypt(key, blob).decode(), "long-lived-token-value")
        state = json.loads(boot.STATE.read_text())
        self.assertEqual(state["ig_user_id"], "1784149834884056")
        self.assertEqual(state["scopesVerifiedBy"], "debugger")
        self.assertTrue(state["expires_at"] > "2026")
        self.assertTrue(state["token_fingerprint"].startswith("sha256:"))

    def test_an_unreachable_debugger_is_survived_when_the_publish_probe_works(self):
        self.assertEqual(self._exchange(Graph(debug_ok=False)), 0)
        state = json.loads(boot.STATE.read_text())
        self.assertEqual(state["scopesVerifiedBy"], "capability probe")

    def test_a_token_that_cannot_publish_is_refused_and_nothing_is_stored(self):
        with self.assertRaisesRegex(RuntimeError, "cannot publish"):
            self._exchange(Graph(debug_ok=False, probe_ok=False, scopes=[]))
        self.assertFalse(boot.TOKEN_FILE.exists())
        self.assertFalse(boot.STATE.exists())

    def test_only_the_debugger_knows_the_publish_scope_is_absent(self):
        with self.assertRaisesRegex(RuntimeError, "cannot publish"):
            self._exchange(Graph(scopes=["instagram_business_basic"], probe_ok=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
