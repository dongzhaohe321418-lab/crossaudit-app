from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from crossaudit import app, app_doctor
from crossaudit.config import CONFIG_NAME, load
from crossaudit.errors import ConfigDenial


def test_software_check_distinguishes_missing_outdated_and_ready(monkeypatch):
    repair = {"action": "install_git_tools", "label": "Install Git tools"}

    missing = app_doctor._software(
        "git", "Git", None, ("--version",), (2, 30, 0),
        required=True, repair=repair)
    assert missing["status"] == "missing" and missing["blocking"]
    optional = app_doctor._software(
        "github_cli", "GitHub connection tool", None, ("--version",),
        (2, 45, 0), required=False, repair=repair)
    assert optional["status"] == "missing" and not optional["blocking"]

    monkeypatch.setattr(app_doctor, "_run",
                        lambda *_args, **_kwargs: (True, "git version 2.20.1"))
    outdated = app_doctor._software(
        "git", "Git", "/usr/bin/git", ("--version",), (2, 30, 0),
        required=True, repair=repair)
    assert outdated["status"] == "outdated"
    assert outdated["version"] == "2.20.1" and outdated["minimum"] == "2.30.0"

    monkeypatch.setattr(app_doctor, "_run",
                        lambda *_args, **_kwargs: (True, "git version 2.51.0"))
    ready = app_doctor._software(
        "git", "Git", "/usr/bin/git", ("--version",), (2, 30, 0),
        required=True, repair=repair)
    assert ready["status"] == "ready" and not ready["blocking"]
    assert "repair" not in ready


def test_doctor_reports_update_without_making_it_a_runtime_blocker(
        cfg, monkeypatch, tmp_path):
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(app_doctor, "_latest_release",
                        lambda: ("99.0.0", app_doctor.LATEST_RELEASE_URL))
    monkeypatch.setattr(app_doctor.shutil, "which",
                        lambda name: f"/test/{name}" if name in {"git", "gh", "codex"} else None)

    def command(path, *args, **_kwargs):
        if args[:3] == ("-C", str(cfg.root), "rev-parse"):
            return True, ".git"
        if args[-2:] == ("config", "user.name"):
            return True, "Test User"
        if args[-2:] == ("config", "user.email"):
            return True, "test@example.com"
        versions = {"/test/git": "git version 2.51.0",
                    "/test/gh": "gh version 2.96.0",
                    "/test/codex": "codex-cli 0.146.0"}
        return True, versions.get(path, "")

    monkeypatch.setattr(app_doctor, "_run", command)
    result = app_doctor.collect(cfg)
    update = next(row for row in result["checks"] if row["id"] == "crossaudit")

    assert update["status"] == "outdated"
    assert not update["blocking"]
    assert update["repair"]["action"] == "download_update"
    assert "CROSSAUDIT_" not in json.dumps(result)


def test_doctor_does_not_launch_apple_git_stub_when_tools_are_missing(
        cfg, monkeypatch, tmp_path):
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(app_doctor.sys, "platform", "darwin")
    monkeypatch.setattr(app_doctor.platform, "mac_ver", lambda: ("14.6.0", ("", "", ""), ""))
    monkeypatch.setattr(app_doctor.shutil, "which",
                        lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(app_doctor, "_latest_release",
                        lambda: (app_doctor.__version__, app_doctor.LATEST_RELEASE_URL))

    def command(path, *args, **_kwargs):
        if path == "/usr/bin/xcode-select" and args == ("-p",):
            return False, "Command Line Tools are absent"
        if path == "/usr/bin/git":
            raise AssertionError("the Apple Git stub would open an unsolicited installer")
        return False, "not found"

    monkeypatch.setattr(app_doctor, "_run", command)
    result = app_doctor.collect(cfg)
    git = next(row for row in result["checks"] if row["id"] == "git")
    ledger = next(row for row in result["checks"] if row["id"] == "project_repo")

    assert git["status"] == "missing" and git["blocking"]
    assert git["repair"]["action"] == "install_git_tools"
    assert ledger["status"] == "waiting" and not ledger["blocking"]


def test_doctor_identity_repair_is_project_local(cfg, monkeypatch):
    calls = []
    monkeypatch.setattr(app_doctor.shutil, "which", lambda name: "/test/git")

    def command(path, *args, **kwargs):
        calls.append((path, args, kwargs))
        return True, ""

    monkeypatch.setattr(app_doctor, "_run", command)
    result = app_doctor.repair(cfg, "set_git_identity", {
        "name": "Ada Lovelace", "email": "ada@example.com"})

    assert "saved for this project" in result["message"]
    assert any(args[-2:] == ("user.name", "Ada Lovelace") for _, args, _ in calls)
    assert any(args[-2:] == ("user.email", "ada@example.com") for _, args, _ in calls)
    assert all("--global" not in args for _, args, _ in calls)

    with pytest.raises(ConfigDenial, match="valid Git author email"):
        app_doctor.repair(cfg, "set_git_identity", {
            "name": "Ada", "email": "not-an-email"})


def test_unknown_doctor_repair_is_refused(cfg):
    with pytest.raises(ConfigDenial, match="not supported"):
        app_doctor.repair(cfg, "run_arbitrary_command", {})


def test_first_launch_still_builds_recovery_ui_when_git_cannot_run(
        tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(app.sys, "platform", "darwin")
    monkeypatch.setattr(app.shutil, "which", lambda name: "/usr/bin/git")

    calls = []

    def run(args, **_kwargs):
        calls.append(args)
        if args == ["/usr/bin/xcode-select", "-p"]:
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"missing tools")
        raise AssertionError("Git must not be invoked when Command Line Tools are absent")

    monkeypatch.setattr(app.subprocess, "run", run)
    root = app._controller_project(workspace)

    assert (root / CONFIG_NAME).is_file()
    assert (root / "AUDIT_RULES.md").is_file()
    assert not (root / ".git").exists()
    assert load(root / CONFIG_NAME).root == root
    assert calls == [["/usr/bin/xcode-select", "-p"]]


def test_settings_ui_exposes_doctor_and_only_allowlisted_actions():
    from crossaudit.console.page import PAGE

    assert 'id="doctor-checks"' in PAGE
    assert 'id="run-doctor"' in PAGE
    assert "'/api/doctor'" in PAGE
    assert "run_arbitrary_command" not in PAGE
