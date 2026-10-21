#!/usr/bin/env python3
"""Watch for a pasted Tumblr authorisation code and exchange it within seconds.

Tumblr authorization codes are single-use and, by OAuth practice, valid for roughly thirty to sixty
seconds. Every failure of the "save it in a secret, then press Run" route came from that window: the
run queues, checks out, installs, and only then reads the value - by which time Tumblr has retired the
code. No amount of instruction improves a race that is lost by design, so this job is *already
running*: it polls the code file every five seconds and exchanges the instant something new appears,
which makes the gap seconds instead of minutes.

Three rules keep it safe:
- the code is never printed, and never written back anywhere - only a SHA-256 fingerprint is recorded;
- the code file is scrubbed in the same commit that lands the encrypted token, so a spent value is
  never offered twice;
- a refusal does not end the run. The listener keeps watching, so the next paste needs no restart,
  no dispatch box and no secret page.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parent
CODE_PATH = ".github/tumblr-oauth-code"
POLL_SECONDS = 5
CHAT_EVERY = 6  # a heartbeat line twice a minute, not one per poll
API = os.environ.get("GITHUB_API", "https://api.github.com")
REPO = os.environ.get("GITHUB_REPOSITORY", "kushalkumardagaca-png/blogger-bot")
FILES_TO_PUSH = [CODE_PATH, "tumblr_token.enc", "SOCIAL_CREDENTIAL_HEALTH.json",
                 "TUMBLR_OAUTH_ATTEMPT.json"]


def now() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def window_minutes() -> int:
    """How long to keep watching, whatever the trigger handed over.

    A push-started run has no dispatch input at all, so the variable arrives empty, and `int("")` is a
    ValueError that kills the watch before it begins - which is exactly what happened on 21 October at
    10:55 IST. Anything unusable becomes the full window, and the window is clamped inside the job's
    own three-hour limit so the run ends on its own terms rather than being cancelled mid-flight.
    """
    try:
        value = int(str(os.environ.get("LISTENER_MINUTES", "")).strip())
    except ValueError:
        value = 170
    return max(1, min(value, 178))


def redact(text: str, secret: str) -> str:
    """Remove the code from anything that will be printed or committed."""
    if not secret:
        return text
    return text.replace(secret, "[one-time code]").replace(secret[:12], "[one-time code]")


def pick_code(content: str) -> str:
    """The usable code inside the file: a bare value or the whole callback address.

    Mobile browsers hide long query strings, so the owner is told to paste whatever the address bar
    shows. Comments left in the template are ignored, and an empty file means "nothing pasted yet".
    """
    for line in reversed([item.strip() for item in content.splitlines() if item.strip()]):
        if line.startswith("#"):
            continue
        if "://" in line:
            found = parse_qs(urlparse(line).query).get("code", [""])[0]
            return found.strip()
        return line.strip().strip("/")
    return ""


def should_exchange(code: str, sha: str, seen_sha: str) -> bool:
    return bool(code) and bool(sha) and sha != seen_sha


def api(method: str, path: str, payload: dict | None = None) -> tuple[int, dict | str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    request = urllib.request.Request(
        API + path,
        data=None if payload is None else json.dumps(payload).encode(),
        method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "dailyyield-tumblr-oauth-listener",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]
    except Exception as exc:  # network trouble must never kill the watch
        return 0, f"{type(exc).__name__}: {exc}"[:300]
    try:
        return response.status, json.loads(body)
    except Exception:
        return response.status, body[:300]


def read_code_file() -> tuple[str, str, str]:
    """(code, blob sha, message) from the repository's current main branch."""
    status, body = api("GET", f"/repos/{REPO}/contents/{CODE_PATH}?ref=main")
    if status != 200 or not isinstance(body, dict):
        return "", "", f"read refused ({status})"
    content = base64.b64decode(body.get("content", "")).decode("utf-8", "replace")
    return pick_code(content), str(body.get("sha", "")), "ok"


def exchange(code: str) -> tuple[int, str, str]:
    """Run the existing bootstrap with this code, so nothing about the exchange is duplicated."""
    env = dict(os.environ, TUMBLR_AUTHORIZATION_CODE=code)
    result = subprocess.run([sys.executable, str(ROOT / "tumblr_oauth_bootstrap.py")],
                            cwd=ROOT, env=env, text=True, capture_output=True)
    return result.returncode, result.stdout, result.stderr


def record_outcome(code: str, returncode: int, stderr: str) -> str:
    """Hand the refusal to the two recorders the publisher already reads, with the code removed."""
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    reason = redact(lines[-1] if lines else "", code)[:400]
    Path("/tmp/tumblr-listener.err").write_text(reason + "\n", encoding="utf-8")
    for script, extra in (("social_credential_health.py", ["--platform", "tumblr", "--code",
                                                           str(returncode)]),
                          ("tumblr_attempt_record.py", ["record", "--fingerprint", fingerprint(code),
                                                         "--code", str(returncode)])):
        subprocess.run([sys.executable, str(ROOT / script), *extra, "--output" if script.startswith("social") else "--reason-file", "/tmp/tumblr-listener.err"],
                       cwd=ROOT, text=True, capture_output=True)
    return reason


def fingerprint(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def scrub_and_push(code: str) -> bool:
    """Land the new token, and empty the code file, in one commit. Returns whether it worked."""
    _, sha, _ = api("GET", f"/repos/{REPO}/contents/{CODE_PATH}?ref=main")
    payload = {"message": "Tumblr authorisation completed by the listener; code file scrubbed [skip ci]",
               "branch": "main", "content": base64.b64encode(b"").decode(), "sha": sha}
    status, body = api("PUT", f"/repos/{REPO}/contents/{CODE_PATH}", payload)
    return status in (200, 201)


def commit_local(message: str) -> bool:
    """Push with the repository's own git identity, retrying the way persist_social_state.sh does."""
    def git(*args: str) -> int:
        return subprocess.run(("git", "-c", "user.name=Daily Yield Tumblr Listener",
                               "-c", "user.email=bot@dailyyield.blogspot.com", *args),
                              cwd=ROOT, text=True, capture_output=True).returncode
    for path in FILES_TO_PUSH:
        if (ROOT / path).exists():
            git("add", "--", path)
    if git("diff", "--cached", "--quiet") == 0:
        return True
    for attempt in range(6):
        if git("commit", "-q", "-m", message) != 0:
            return False
        if git("fetch", "-q", "origin", "main") == 0 and git("rebase", "-q", "FETCH_HEAD") == 0 \
                and git("push", "-q", "origin", "HEAD:main") == 0:
            return True
        time.sleep(2 + attempt)
    return False


def main() -> int:
    minutes = window_minutes()
    deadline = time.time() + minutes * 60
    seen = ""
    _, seen, _ = read_code_file()  # start from the current state: an old code is not worth trying
    print(f"[{now()}] listening for a pasted Tumblr authorisation code in {CODE_PATH} "
          f"(up to {minutes} minutes, every {POLL_SECONDS}s)")
    quiet = 0
    while time.time() < deadline:
        code, sha, message = read_code_file()
        if message != "ok":
            print(f"[{now()}] {message}; will retry")
        elif should_exchange(code, sha, seen):
            print(f"[{now()}] a code has arrived; exchanging it now (fingerprint {fingerprint(code)})")
            returncode, stdout, stderr = exchange(code)
            reason = record_outcome(code, returncode, stderr)
            print(redact(stdout, code).strip() or "(no output)")
            if returncode == 0:
                if scrub_and_push(code):
                    print(f"[{now()}] token committed and the code file scrubbed. Tumblr is authorised.")
                else:
                    commit_local("Tumblr authorisation completed by the listener [skip ci]")
                    print(f"[{now()}] token committed, but the code file could not be scrubbed by the "
                          f"API; it is a spent value and harmless, though it should be emptied by hand.")
                return 0
            commit_local("Record the refused Tumblr authorisation attempt [skip ci]")
            scrub_and_push(code)
            seen = sha  # never offer the same spent code twice, even if the scrub is refused
            print(f"[{now()}] Tumblr refused this code: {reason or 'no detail returned'}. Still "
                  f"listening - paste a fresh one and it is exchanged within {POLL_SECONDS}s, with no "
                  f"other step and nothing to press.")
        elif code and sha == seen:
            pass
        else:
            seen = sha or seen
            quiet += 1
            if quiet % CHAT_EVERY == 0:
                left = int(deadline - time.time())
                print(f"[{now()}] nothing pasted yet ({left}s of listening left)")
        time.sleep(POLL_SECONDS)
    print(f"[{now()}] listener window closed without a code. Tumblr remains paused, not broken.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # a watch that dies silently is worse than no watch at all
        print(f"TUMBLR_LISTENER_ERROR: {type(exc).__name__}: {exc}")
        raise
