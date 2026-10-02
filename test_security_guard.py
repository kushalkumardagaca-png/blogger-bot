#!/usr/bin/env python3
"""Security approval boundaries: repository maintenance must not approve Blogger edits."""
import json
import sys

import security_guard as guard


def configure(monkeypatch, tmp_path, previous, current_repo, current_items):
    baseline = tmp_path / "baseline.json"
    status_json = tmp_path / "status.json"
    status_md = tmp_path / "status.md"
    backup = tmp_path / "backup.json.gz"
    baseline.write_text(json.dumps(previous))
    monkeypatch.setattr(guard, "BASELINE", baseline)
    monkeypatch.setattr(guard, "STATUS_JSON", status_json)
    monkeypatch.setattr(guard, "STATUS_MD", status_md)
    monkeypatch.setattr(guard, "BACKUP", backup)
    monkeypatch.setattr(guard, "repository_hashes", lambda: current_repo)
    monkeypatch.setattr(guard, "blogger_inventory", lambda: (current_items, {"items": []}))
    monkeypatch.setattr(guard, "secret_scan", lambda: [])
    monkeypatch.setattr(guard, "content_threats", lambda backup: [])
    return baseline, status_json


def test_main_branch_repository_maintenance_can_refresh_only_repo_hashes(monkeypatch, tmp_path):
    item = {"kind": "post", "id": "1", "content_sha256": "same"}
    previous = {"repository": {"app.py": "old"}, "blogger": {"post:1": item}}
    baseline, status = configure(monkeypatch, tmp_path, previous, {"app.py": "new"}, {"post:1": item})
    monkeypatch.setattr(sys, "argv", ["security_guard.py", "--approve-repository"])
    assert guard.main() == 0
    assert json.loads(status.read_text())["status"] == "PASS"
    approved = json.loads(baseline.read_text())
    assert approved["repository"] == {"app.py": "new"}
    assert approved["blogger"]["post:1"]["content_sha256"] == "same"


def test_repository_approval_never_approves_changed_blogger_content(monkeypatch, tmp_path):
    old = {"kind": "post", "id": "1", "content_sha256": "old"}
    new = {"kind": "post", "id": "1", "content_sha256": "changed"}
    previous = {"repository": {"app.py": "old"}, "blogger": {"post:1": old}}
    baseline, status = configure(monkeypatch, tmp_path, previous, {"app.py": "new"}, {"post:1": new})
    monkeypatch.setattr(sys, "argv", ["security_guard.py", "--approve-repository"])
    assert guard.main() == 1
    report = json.loads(status.read_text())
    assert report["status"] == "FAIL"
    assert any("existing Blogger content changed" in finding for finding in report["critical"])
    assert json.loads(baseline.read_text())["blogger"]["post:1"]["content_sha256"] == "old"
