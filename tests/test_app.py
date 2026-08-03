from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import _selfid, app, app_keys, workspace
from crossaudit.config import load
from crossaudit.console import projects
from crossaudit.constitution import Draft, Rule
from crossaudit.errors import ConfigDenial
from crossaudit.providers.specs import SPECS


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


def test_settings_exposes_every_first_party_provider_without_a_secret(monkeypatch):
    for vendor, spec in SPECS.items():
        monkeypatch.setenv(spec.key_env, f"private-{vendor}")
    result = app_keys.apply({})
    encoded = json.dumps(result)
    assert set(result["providers"]) == set(SPECS)
    assert all(row["configured"] for row in result["providers"].values())
    assert "private-" not in encoded


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


def test_native_workspace_choice_persists_across_app_restarts(tmp_path, monkeypatch):
    support = tmp_path / "support"
    selected = tmp_path / "My Projects"
    another = tmp_path / "Client Projects"
    selected.mkdir()
    another.mkdir()
    # Track the process override before select_workspace changes it directly,
    # so pytest restores the caller's original environment after this test.
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(tmp_path / "original"))

    chosen = workspace.select_workspace(support, str(selected))
    workspace.select_workspace(support, str(another))
    assert chosen == selected.resolve()
    assert not list(selected.glob(".crossaudit-write-test-*"))
    if os.name != "nt":
        assert (support / workspace.SETTINGS_NAME).stat().st_mode & 0o777 == 0o600

    monkeypatch.delenv("CROSSAUDIT_WORKSPACE_ROOT", raising=False)
    assert app.workspace_root(support) == another.resolve()
    assert workspace.known_workspaces(support) == (
        selected.resolve(), another.resolve())


def test_workspace_choice_refuses_a_missing_path_with_ui_action(tmp_path):
    with pytest.raises(ConfigDenial) as caught:
        workspace.select_workspace(tmp_path / "support", str(tmp_path / "missing"))
    assert caught.value.detail == {
        "issue": "workspace_missing", "action": "choose_workspace"}


def test_native_shell_exposes_only_the_local_workspace_picker_bridge():
    source = (Path(__file__).parents[1] / "packaging" / "macos" /
              "CrossAuditApp.swift").read_text()
    assert "WKScriptMessageHandler" in source
    assert 'body["action"] as? String == "chooseWorkspace"' in source
    assert '["127.0.0.1", "localhost"]' in source
    assert "canChooseDirectories = true" in source
    assert "canChooseFiles = false" in source
    assert "DispatchSource.makeSignalSource" in source
    assert "[SIGINT, SIGTERM]" in source


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


def test_project_can_bind_gemini_and_deepseek_without_openai_routing(
        tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_GOOGLE_KEY", "google-test")
    monkeypatch.setenv("CROSSAUDIT_DEEPSEEK_KEY", "deepseek-test")
    monkeypatch.setattr(projects.wizard, "_distil", lambda *a, **kw: Draft(
        "A review", "review", [Rule("CA-OUT-001", "BLOCKER", "One output",
                                        "Exactly one output exists.")]))

    result = projects.create_project(tmp_path, app_payload(
        auditor_vendor="google", auditor_model="gemini-3.6-flash",
        generator_vendor="deepseek", generator_model="deepseek-v4-flash"),
        lambda *_: None)
    cfg = load(Path(result["root"]) / "crossaudit.yml")

    assert cfg.auditor.provider == "google"
    assert cfg.auditor.key_env == "CROSSAUDIT_GOOGLE_KEY"
    assert cfg.auditor.base_url is None
    assert cfg.generator_provider == "deepseek"
    assert cfg.generator_key_env == "CROSSAUDIT_DEEPSEEK_KEY"
    assert cfg.generator_base_url is None


def test_project_persists_each_roles_selected_api_region(tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_MINIMAX_KEY", "minimax-test")
    monkeypatch.setenv("CROSSAUDIT_QWEN_KEY", "qwen-test")
    monkeypatch.setattr(projects.wizard, "_distil", lambda *a, **kw: Draft(
        "A review", "review", [Rule("CA-OUT-001", "BLOCKER", "One output",
                                    "Exactly one output exists.")]))
    result = projects.create_project(tmp_path, app_payload(
        auditor_vendor="minimax", auditor_model="MiniMax-M2.7",
        auditor_endpoint="global", generator_vendor="qwen",
        generator_model="qwen3.7-plus", generator_endpoint="singapore"),
        lambda *_: None)
    cfg = load(Path(result["root"]) / "crossaudit.yml")
    assert cfg.auditor.base_url == "https://api.minimax.io/v1"
    assert cfg.generator_base_url == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")


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
