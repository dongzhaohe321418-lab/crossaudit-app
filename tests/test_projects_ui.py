from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from crossaudit.cli import pair
from crossaudit.config import load
from crossaudit import workspace
from crossaudit.console import daemon, projects
from crossaudit.errors import ConfigDenial


def payload(**changes):
    row = {
        "name": "demo",
        "description": "Every number must have a unit and a declared source.",
        "max_rounds": 3,
        "auditor_vendor": "openai",
        "auditor_model": "gpt-5.6-sol",
        "generator_vendor": "anthropic",
        "generator_model": "claude-sonnet-4-6",
        "github": False,
    }
    row.update(changes)
    return row


def test_browser_creation_makes_a_complete_local_project(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    seen = []
    result = projects.create_project(tmp_path, payload(),
                                     lambda stage, detail: seen.append((stage, detail)))
    root = Path(result["root"])
    cfg = load(root / "crossaudit.yml")

    assert cfg.auditor.vendor == "openai"
    assert cfg.auditor.model == "gpt-5.6-sol"
    assert cfg.generator_vendor == "anthropic"
    assert cfg.generator_model == "claude-sonnet-4-6"
    assert cfg.audit_repo is None
    assert cfg.scope_dirs == ["work"]
    assert cfg.checks == ["parseable", "declared", "internal", "complete"]
    assert result["project_type"] == "general"
    assert (root / "AUDIT_RULES.md").is_file()
    assert (root / "DETERMINISTIC_CHECKS.md").is_file()
    assert not (root / "work").exists()
    assert not (root / "experiments").exists()
    assert subprocess.run(["git", "status", "--porcelain"], cwd=root,
                          capture_output=True, text=True, check=True).stdout == ""
    assert any(stage == "local" for stage, _ in seen)


def test_browser_creation_can_explicitly_choose_the_science_contract(tmp_path,
                                                                     monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    result = projects.create_project(
        tmp_path, payload(name="lab", project_type="science"), lambda *_: None)
    root = Path(result["root"])
    cfg = load(root / "crossaudit.yml")

    assert cfg.scope_dirs == ["experiments"]
    assert cfg.checks == ["schema", "units", "convergence", "provenance"]
    assert (root / "experiments" / "TEMPLATE" / "results.json").is_file()
    assert "metadata.yml" in (root / "AUDIT_RULES.md").read_text()


@pytest.mark.parametrize("changes,why", [
    ({"name": "../escape"}, "project name"),
    ({"auditor_vendor": "openai", "generator_vendor": "openai"},
     "different vendors"),
    ({"max_rounds": 0}, "between 1 and 10"),
])
def test_browser_creation_refuses_unsafe_or_impossible_settings(tmp_path, changes, why):
    with pytest.raises(ConfigDenial, match=why):
        projects.create_project(tmp_path, payload(**changes), lambda *_: None)


def test_background_validation_never_writes_setup_state_outside_workspace(
        tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    projects.create_project(tmp_path, payload(name="control"), lambda *_: None)
    current = load(tmp_path / "control" / "crossaudit.yml")
    outside = tmp_path.parent / "outside-crossaudit-target"
    marker = outside / ".crossaudit" / projects.SETUP_FILE
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"status":"belongs-to-someone-else"}')
    jobs = projects.ProjectJobs()
    jobs.start(current, payload(name="../outside-crossaudit-target"), lambda: None)
    deadline = time.monotonic() + 2
    while jobs.snapshot()[0]["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert marker.read_text() == '{"status":"belongs-to-someone-else"}'


def test_pairing_never_overwrites_an_unrelated_origin(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "remote", "add", "origin",
                    "https://github.com/someone/other.git"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** exact\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: owner/project\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m, "
        "key_env: CROSSAUDIT_AUDITOR_KEY}\n"
        "generator: {vendor: anthropic, provider: anthropic, model: n, "
        "key_env: CROSSAUDIT_GENERATOR_KEY}\n")
    cfg = load(root / "crossaudit.yml")
    monkeypatch.setattr(pair, "gh", lambda: "/usr/bin/false")
    monkeypatch.setattr(pair, "_exists", lambda _repo: True)

    with pytest.raises(ConfigDenial, match="refusing to replace"):
        pair.apply_pair(cfg, "owner/project", "owner/project-audit", private=True)


def test_pairing_refuses_a_dirty_config_before_any_remote_mutation(
        tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** exact\n")
    config = root / "crossaudit.yml"
    config.write_text(
        "version: 1\nscience_repo: owner/project\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m, "
        "key_env: CROSSAUDIT_AUDITOR_KEY}\n"
        "generator: {vendor: anthropic, provider: anthropic, model: n, "
        "key_env: CROSSAUDIT_GENERATOR_KEY}\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=t@example.com",
                    "commit", "-q", "-m", "setup"], cwd=root, check=True)
    config.write_text(config.read_text() + "# user edit\n")
    called = False

    def remote_auth():
        nonlocal called
        called = True
        return "/usr/bin/false"

    monkeypatch.setattr(pair, "gh", remote_auth)
    with pytest.raises(ConfigDenial, match="has changes"):
        pair.apply_pair(load(config), "owner/project", "owner/project-audit",
                        private=True)
    assert called is False


@pytest.mark.parametrize("stderr,hint", [
    ("organization has SAML SSO enforcement", "organisation's SSO"),
    ("HTTP 403: Resource not accessible", "lacks repository"),
    ("API rate limit exceeded", "rate-limited"),
    ("repository already exists", "may not be visible"),
])
def test_github_failures_explain_the_user_action(stderr, hint, monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
    Result.stderr = stderr
    monkeypatch.setattr(pair, "gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pair.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(ConfigDenial, match=hint):
        pair._gh("repo", "create", "owner/project")


def test_repository_availability_does_not_hide_network_failures(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "connection reset by peer"

    monkeypatch.setattr(pair, "gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pair.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(ConfigDenial) as caught:
        pair._exists("owner/project")
    assert caught.value.detail == {"issue": "github_check", "action": "retry"}


def test_project_page_contains_the_control_plane_contract():
    from crossaudit.console.page import PAGE

    for text in ("Projects", "Create a supervised project", "auditor_vendor",
                 "generator_vendor", "/api/projects/create",
                 "/api/projects/stream", "Create and connect two repositories",
                 'role="progressbar"', "project-live-copy",
                 'aria-label="Back to projects"',
                 "document.getElementById('back-projects').onclick=showProjects",
                 "Connect GitHub", "/api/github/connect", "Open GitHub",
                 "Local workspace folder", "Choose folder…",
                 "/api/workspace/select", "/api/github/check",
                 "Check names", "Edit repository names", "recovery-modal"):
        assert text in PAGE
    for text in ("Models & reasoning", "/api/runtime/options", "/api/runtime",
                 "Save for next call", "Reasoning effort", "Atomic between calls"):
        assert text in PAGE
    assert "data-copy-recovery-github" in PAGE
    assert "This dialog updates automatically after approval." in PAGE


def test_repository_check_preserves_editable_names_and_requires_explicit_adoption(
        monkeypatch):
    monkeypatch.setattr(projects, "github_status", lambda force=False: {
        "connected": True, "owner": "owner", "detail": "Connected as owner"})
    monkeypatch.setattr(pair, "_exists", lambda repo: repo.endswith("/audit-ledger"))
    selected = payload(name="local-folder", github=True,
                       science_repo="owner/customer-work",
                       audit_repo="owner/audit-ledger")

    checked = projects.check_repositories(selected)
    assert checked["science"] == "owner/customer-work"
    assert checked["audit"] == "owner/audit-ledger"
    assert checked["ready"] is False
    with pytest.raises(ConfigDenial) as caught:
        projects.check_repositories(selected, enforce=True)
    assert caught.value.detail["issue"] == "repo_exists"
    selected["adopt_existing"] = True
    assert projects.check_repositories(selected, enforce=True)["ready"] is True


def test_workspace_selection_is_app_only_and_immediately_changes_project_base(
        tmp_path, monkeypatch, cfg):
    selected = tmp_path / "Chosen Workspace"
    selected.mkdir()
    support = tmp_path / "support"
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(tmp_path / "original"))
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)
    with pytest.raises(ConfigDenial, match="macOS app"):
        projects.select_workspace(cfg, str(selected))

    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(support))
    result = projects.select_workspace(cfg, str(selected))
    assert result == {"workspace": str(selected.resolve()), "selected": True}
    assert projects.workspace_base(cfg) == selected.resolve()


def test_projects_in_every_native_selected_workspace_remain_visible(
        tmp_path, monkeypatch, cfg):
    support = tmp_path / "support"
    first = tmp_path / "First"
    second = tmp_path / "Second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(support))
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(first))
    workspace.select_workspace(support, str(first))
    workspace.select_workspace(support, str(second))
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)
    projects.create_project(first, payload(name="first-project"), lambda *_: None)
    projects.create_project(second, payload(name="second-project"), lambda *_: None)
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")

    names = {item["name"] for item in projects.snapshot(cfg)["items"]}
    assert {"first-project", "second-project"} <= names


def test_default_conversation_exposes_only_audited_deliverables():
    from crossaudit.console.page import PAGE

    assert "['passed','consumed'].includes(auditStatus(d,m.sha))" in PAGE
    assert "Only final files that passed independent review." in PAGE
    assert "No audited deliverables yet." in PAGE


def test_github_connection_job_surfaces_device_code_then_account(monkeypatch):
    states = iter([
        {"connected": False, "owner": None, "detail": "not authenticated"},
        {"connected": True, "owner": "release-user",
         "detail": "Connected as release-user"},
    ])
    monkeypatch.setattr(projects, "github_status", lambda force=False: next(states))
    monkeypatch.setattr(projects.shutil, "which", lambda name: "/usr/bin/gh")
    command = []
    popen_options = {}

    class FakeProcess:
        stdout = iter(["First copy your one-time code: TEST-CODE\n"])

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    def popen(args, **kwargs):
        command.extend(args)
        popen_options.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(projects.subprocess, "Popen", popen)
    auth = projects.GithubAuthJobs()
    notified = []
    result = auth.start(lambda: notified.append(True))
    deadline = time.monotonic() + 1
    while auth.snapshot()["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)

    row = auth.snapshot()
    assert result["job"] == row["id"]
    assert row["code"] == "TEST-CODE"
    assert row["status"] == "complete" and row["owner"] == "release-user"
    assert command[:3] == ["/usr/bin/gh", "auth", "login"]
    assert "--web" in command and "--git-protocol" in command
    assert popen_options["env"]["GH_PROMPT_DISABLED"] == "1"
    assert popen_options["env"]["BROWSER"] == "/usr/bin/false"
    assert notified


def test_project_menu_projects_a_sibling_daemons_live_progress(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    projects.create_project(tmp_path, payload(name="one"), lambda *_: None)
    projects.create_project(tmp_path, payload(name="two"), lambda *_: None)
    current = load(tmp_path / "one" / "crossaudit.yml")
    sibling = (tmp_path / "two").resolve()
    monkeypatch.setattr(projects, "github_status", lambda: {
        "connected": False, "owner": None, "detail": "not connected"})
    monkeypatch.setattr(daemon, "read_run", lambda cfg: (
        {"pid": 42, "port": 32123, "token": "local", "started": 1}
        if cfg.root == sibling else None))
    monkeypatch.setattr(daemon, "fetch_state", lambda _info: {
        "progress": {"task": "prepare acceptance data", "elapsed": 7,
                     "finished": False,
                     "steps": [{"actor": "auditor", "text": "reviewing the commit"}]}})
    projects._RUNTIME_CACHE.clear()

    row = next(item for item in projects.snapshot(current)["items"]
               if item["root"] == str(sibling))
    assert row["status"] == "running"
    assert row["progress"] == {
        "task": "prepare acceptance data", "elapsed": 7,
        "actor": "auditor", "step": "reviewing the commit"}


def test_failed_github_setup_is_visible_and_resumes_idempotently(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    projects.create_project(tmp_path, payload(name="control"), lambda *_: None)
    current = load(tmp_path / "control" / "crossaudit.yml")
    monkeypatch.setattr(projects, "github_status", lambda force=False: {
        "connected": True, "owner": "owner", "detail": "Connected as owner"})
    monkeypatch.setattr(pair, "_exists", lambda _repo: False)

    attempts = []
    def fail_once(cfg, science, audit, *, private, progress, allow_existing=True):
        attempts.append((science, audit))
        progress("github", f"Created {science}")
        raise ConfigDenial("simulated failure after the first repository")

    monkeypatch.setattr(pair, "apply_pair", fail_once)
    jobs = projects.ProjectJobs()
    started = jobs.start(current, payload(name="recover", github=True), lambda: None)
    deadline = time.monotonic() + 3
    while jobs.snapshot()[0]["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert jobs.snapshot()[0]["status"] == "failed"
    setup = projects._read_setup(tmp_path / "recover")
    assert setup["status"] == "failed" and setup["github"] is True
    row = next(p for p in projects.snapshot(current)["items"] if p["name"] == "recover")
    assert row["status"] == "setup_failed" and row["setup"]["recoverable"] is True

    def succeed(cfg, science, audit, *, private, progress, allow_existing=True):
        attempts.append((science, audit))
        progress("github", f"Adopting existing {science}")
        progress("audit", f"Seeded {audit}")
        return {"science": science, "audit": audit, "created": []}

    monkeypatch.setattr(pair, "apply_pair", succeed)
    resumed = projects.resume_project(tmp_path, tmp_path / "recover", lambda *_: None)
    assert resumed["resumed"] is True
    assert projects._read_setup(tmp_path / "recover")["status"] == "complete"
    assert attempts == [("owner/recover", "owner/recover-audit")] * 2


def test_live_model_refresh_uses_the_selected_role_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    projects.create_project(tmp_path, payload(name="control"), lambda *_: None)
    current = load(tmp_path / "control" / "crossaudit.yml")
    seen = []
    monkeypatch.setattr(projects, "list_models",
                        lambda vendor, key_env, **kwargs: seen.append((vendor, key_env)) or
                        ["future-model-2", "future-model-1"])
    result = projects.refresh_models(current, "anthropic", "generator")
    assert result["models"] == ["future-model-2", "future-model-1"]
    assert seen == [("anthropic", "CROSSAUDIT_GENERATOR_KEY")]


def test_runtime_model_and_effort_switch_is_committed_atomically(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    projects.create_project(tmp_path, payload(name="control"), lambda *_: None)
    root = tmp_path / "control"
    current = load(root / "crossaudit.yml")

    options = projects.runtime_options(current)
    assert options["applies"] == "next_provider_call"
    assert {row["id"] for row in options["roles"]["auditor"]["efforts"]} >= {
        "low", "medium", "high", "max"}
    result = projects.update_runtime(current, {
        "generator_model": "claude-opus-4-8",
        "generator_reasoning_effort": "xhigh",
        "auditor_model": "gpt-5.6-terra",
        "auditor_reasoning_effort": "max",
    })

    updated = load(root / "crossaudit.yml")
    assert result["changed"] is True and len(result["commit"]) == 40
    assert updated.generator_model == "claude-opus-4-8"
    assert updated.generator_reasoning_effort == "xhigh"
    assert updated.auditor.model == "gpt-5.6-terra"
    assert updated.auditor.reasoning_effort == "max"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=root,
                          capture_output=True, text=True, check=True).stdout == ""
    assert subprocess.run(["git", "show", "--format=%s", "--no-patch", "HEAD"],
                          cwd=root, capture_output=True, text=True,
                          check=True).stdout.startswith("config:")


def test_runtime_switch_refuses_unsupported_effort_and_preserves_config(
        tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    projects.create_project(tmp_path, payload(name="control"), lambda *_: None)
    config = tmp_path / "control" / "crossaudit.yml"
    current = load(config)
    before = config.read_bytes()

    with pytest.raises(ConfigDenial, match="does not expose an adjustable effort"):
        projects.update_runtime(current, {
            "generator_model": "claude-haiku-4-5-20251001",
            "generator_reasoning_effort": "max",
            "auditor_model": "gpt-5.6-sol",
            "auditor_reasoning_effort": "high",
        })
    assert config.read_bytes() == before


def test_runtime_switch_never_overwrites_an_external_config_edit(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    projects.create_project(tmp_path, payload(name="control"), lambda *_: None)
    config = tmp_path / "control" / "crossaudit.yml"
    config.write_text(config.read_text() + "# owner's pending edit\n")
    before = config.read_bytes()

    with pytest.raises(ConfigDenial, match="uncommitted changes"):
        projects.update_runtime(load(config), {
            "generator_model": "claude-sonnet-4-6",
            "generator_reasoning_effort": "medium",
            "auditor_model": "gpt-5.6-terra",
            "auditor_reasoning_effort": "medium",
        })
    assert config.read_bytes() == before
