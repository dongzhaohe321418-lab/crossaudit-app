from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import _selfid, app, app_keys
from crossaudit.config import load
from crossaudit.console import projects
from crossaudit.constitution import Draft, Rule
from crossaudit.errors import ConfigDenial


def app_payload(**changes):
    value = {
        "name": "desktop-demo",
        "description": "Create exactly one readable project review with no unsupported claims.",
        "project_type": "general",
        "max_rounds": 3,
        "auditor_vendor": "openai",
        "auditor_model": "gpt-5.6-sol",
        "generator_vendor": "anthropic",
        "generator_model": "claude-sonnet-4-6",
        "github": False,
    }
    value.update(changes)
    return value


def test_keychain_write_never_places_secret_in_process_arguments(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(app_keys.subprocess, "run", run)
    monkeypatch.setattr(app_keys, "_security", lambda: "/usr/bin/security")
    monkeypatch.setattr(app_keys, "_account", lambda: "tester")
    app_keys.write("openai", "test-only-secret")

    args, kwargs = calls[0]
    assert "test-only-secret" not in args
    assert kwargs["input"] == "test-only-secret\ntest-only-secret\n"
    assert os.environ["CROSSAUDIT_OPENAI_KEY"] == "test-only-secret"


def test_settings_response_reports_presence_but_never_secret(monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "private-openai")
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "private-anthropic")

    result = app_keys.apply({})

    encoded = json.dumps(result)
    assert result["providers"]["openai"]["configured"]
    assert result["providers"]["anthropic"]["configured"]
    assert "private-openai" not in encoded and "private-anthropic" not in encoded


def test_app_bootstrap_creates_a_clean_hidden_controller(tmp_path):
    workspace = tmp_path / "CrossAudit Projects"
    workspace.mkdir()

    root = app._controller_project(workspace)
    cfg = load(root / "crossaudit.yml")

    assert root.name == ".crossaudit-home"
    assert cfg.auditor.key_env == "CROSSAUDIT_OPENAI_KEY"
    assert cfg.generator_key_env == "CROSSAUDIT_ANTHROPIC_KEY"
    assert cfg.scope_dirs == ["work"]
    assert not (root / "work").exists()
    assert subprocess.run(["git", "status", "--porcelain"], cwd=root,
                          capture_output=True, text=True, check=True).stdout == ""


def test_app_workspace_override_is_trusted_process_state(tmp_path, monkeypatch, cfg):
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(tmp_path))
    assert projects.workspace_base(cfg) == tmp_path.resolve()


def test_app_project_creation_requires_both_selected_provider_keys(
        tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.delenv("CROSSAUDIT_OPENAI_KEY", raising=False)
    monkeypatch.delenv("CROSSAUDIT_ANTHROPIC_KEY", raising=False)

    with pytest.raises(ConfigDenial, match="Openai API key in Settings"):
        projects.create_project(tmp_path, app_payload(), lambda *_: None)


def test_app_project_config_binds_keys_to_vendor_not_role(tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "openai-test")
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "anthropic-test")
    draft = Draft("A product review", "review", [
        Rule("CA-OUT-001", "BLOCKER", "One file", "Exactly one file exists.")])
    monkeypatch.setattr(projects.wizard, "_distil", lambda *a, **kw: draft)

    result = projects.create_project(tmp_path, app_payload(), lambda *_: None)
    cfg = load(Path(result["root"]) / "crossaudit.yml")

    assert cfg.auditor.key_env == "CROSSAUDIT_OPENAI_KEY"
    assert cfg.generator_key_env == "CROSSAUDIT_ANTHROPIC_KEY"
    assert "CA-TASK-001" in (cfg.root / cfg.constitution).read_text()


def test_frozen_app_identity_uses_embedded_build_digest(tmp_path, monkeypatch):
    digest = "a" * 64
    (tmp_path / "crossaudit-build.json").write_text(json.dumps({
        "code_digest_sha256": digest, "version": "4.0.0"}))
    monkeypatch.setattr(_selfid.sys, "frozen", True, raising=False)
    monkeypatch.setattr(_selfid.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert _selfid.install_mode() == "frozen-app"
    assert _selfid.code_digest() == digest
    assert "frozen-app" in _selfid.ADMISSIBLE_MODES


def test_project_console_anchors_process_cwd_to_the_requested_project(
        tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    observed = {}
    # Register the variable with monkeypatch so project_console's direct
    # os.environ assignment is undone after this test.
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "")
    monkeypatch.setattr(app, "load_into_environment", lambda: None)

    def stop_at_load(_path):
        observed["cwd"] = Path.cwd()
        raise RuntimeError("stop after cwd assertion")

    monkeypatch.setattr(app, "load", stop_at_load)
    before = Path.cwd()
    try:
        with pytest.raises(RuntimeError, match="cwd assertion"):
            app.project_console(project, 0)
    finally:
        os.chdir(before)
    assert observed["cwd"] == project.resolve()
