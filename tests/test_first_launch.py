"""First-launch onboarding (North Star §4): persistence, the gate flag, the
app-mode POST endpoint, and the static markers the flow's shell depends on.

These are unit/console tests — no network. The console tests spin the real
loopback server exactly like ``test_admission_and_console`` so the token, Host,
app-mode and allowlist guards are exercised as refusals rather than described.
"""
from __future__ import annotations

import json
import subprocess
import threading
import urllib.error
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest

from crossaudit import workspace
from crossaudit.console.page import PAGE


# --------------------------------------------------------------- persistence
def test_onboarding_reads_default_false_then_round_trips(tmp_path: Path):
    support = tmp_path / "support"
    assert workspace.read_onboarding(support) == {"completed": False}

    assert workspace.set_onboarding(support, completed=True) == {"completed": True}
    assert workspace.read_onboarding(support) == {"completed": True}

    settings = json.loads((support / "app-settings.json").read_text())
    assert settings["onboarding"] == {"completed": True}
    # No wall-clock timestamp is persisted, so the written file stays deterministic.
    assert set(settings["onboarding"]) == {"completed"}


def test_onboarding_merges_and_never_drops_workspace_keys(tmp_path: Path, monkeypatch):
    support = tmp_path / "support"
    ws = tmp_path / "Chosen"
    ws.mkdir()
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(ws))
    workspace.select_workspace(support, str(ws))
    before = json.loads((support / "app-settings.json").read_text())
    assert before["workspace"] == str(ws.resolve())
    assert before["workspaces"] == [str(ws.resolve())]

    workspace.set_onboarding(support, completed=True)
    after = json.loads((support / "app-settings.json").read_text())
    assert after["workspace"] == before["workspace"], "workspace was dropped"
    assert after["workspaces"] == before["workspaces"], "workspaces was dropped"
    assert after["onboarding"] == {"completed": True}

    # Re-selecting a workspace after onboarding must not resurrect the flow.
    workspace.select_workspace(support, str(ws))
    final = json.loads((support / "app-settings.json").read_text())
    assert final["onboarding"] == {"completed": True}


def test_onboarding_settings_file_stays_owner_only(tmp_path: Path):
    support = tmp_path / "support"
    workspace.set_onboarding(support, completed=True)
    mode = (support / "app-settings.json").stat().st_mode & 0o777
    assert mode == 0o600


# ----------------------------------------------------------- app_settings flag
def test_app_settings_exposes_onboarding_flag(tmp_path: Path, monkeypatch):
    from crossaudit.console import server

    support = tmp_path / "support"
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(support))
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)

    settings = server.app_settings()
    assert settings["onboarding"] == {"completed": False}

    workspace.set_onboarding(support, completed=True)
    assert server.app_settings()["onboarding"] == {"completed": True}


def test_app_settings_onboarding_defaults_false_without_support(monkeypatch):
    from crossaudit.console import server

    monkeypatch.delenv("CROSSAUDIT_APP_SUPPORT", raising=False)
    assert server.app_settings()["onboarding"] == {"completed": False}


# ------------------------------------------------------------------- console
@pytest.fixture()
def console(tmp_path: Path):
    from crossaudit.config import load
    from crossaudit.console import serve

    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
        "checks: [parseable]\n")
    cfg = load(root / "crossaudit.yml")
    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def post_json_to(console: str, path: str, payload: dict):
    url = console.replace("/?t=", f"{path}?t=")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status, json.loads(response.read()), dict(response.headers)


def rejected(call):
    try:
        call()
    except urllib.error.HTTPError as error:
        try:
            return error.code, error.read(), dict(error.headers)
        finally:
            error.close()
    raise AssertionError("HTTP request unexpectedly succeeded")


def test_onboarding_endpoint_persists_and_is_app_mode_gated(
        console, tmp_path, monkeypatch):
    support = tmp_path / "support"
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(support))

    # Without app mode the write surface exists on the allowlist but refuses.
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)
    code, body, _headers = rejected(
        lambda: post_json_to(console, "/api/onboarding", {"action": "complete"}))
    assert code == 400
    assert b"macOS app" in body
    assert workspace.read_onboarding(support) == {"completed": False}

    # In app mode the flag is persisted and the fresh settings echo it back.
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    status, result, _headers = post_json_to(
        console, "/api/onboarding", {"action": "complete"})
    assert status == 200
    assert result["onboarding"] == {"completed": True}
    assert workspace.read_onboarding(support) == {"completed": True}


def test_onboarding_skip_also_completes_and_bad_action_refuses(
        console, tmp_path, monkeypatch):
    support = tmp_path / "support"
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(support))
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")

    status, result, _headers = post_json_to(
        console, "/api/onboarding", {"action": "skip"})
    assert status == 200 and result["onboarding"] == {"completed": True}
    assert workspace.read_onboarding(support) == {"completed": True}

    code, _body, _headers = rejected(
        lambda: post_json_to(console, "/api/onboarding", {"action": "sneak"}))
    assert code == 400


def test_onboarding_endpoint_needs_the_token_and_stays_on_the_allowlist(console):
    # A bare, untokened request is refused before any handler runs.
    bare = console.split("?", 1)[0] + "api/onboarding"
    req = urllib.request.Request(
        bare, data=b'{"action":"complete"}', method="POST",
        headers={"content-type": "application/json"})
    code, body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 403

    # An off-allowlist neighbour path has no route at all.
    tokened_but_unknown = console.replace("/?t=", "/api/onboardings?t=")
    req = urllib.request.Request(
        tokened_but_unknown, data=b"{}", method="POST",
        headers={"content-type": "application/json"})
    code, _body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 404


# --------------------------------------------------------------- static markers
class _PageContract(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.dialogs: list[dict] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if values.get("role") == "dialog":
            self.dialogs.append(values)


def test_first_run_markers_present_and_page_stays_valid():
    for marker in (
        'class="first-run" id="first-run"',
        'aria-label="First launch setup"',
        'data-fr-step="1"', 'data-fr-step="2"',
        'data-fr-indicator="1"', 'data-fr-indicator="2"',
        'id="fr-create"', 'id="fr-open"', 'id="fr-import"', 'id="fr-demo"',
        'id="fr-skip"', 'id="fr-continue"', 'id="fr-back"',
        'id="fr-recheck"', 'id="fr-groups"', 'id="fr-rollup"', 'id="fr-rail"',
        'id="hub-note"',
        "function setFirstRunStep(", "function showFirstRun(",
        "function hideFirstRun(", "function renderFirstRunReadiness(",
        "async function bootRoute(", "function completeOnboarding(",
        "/api/onboarding",
        "Build with ", "System readiness", "Everything required is ready",
        "Fix automatically", "Skip for now", "Preflight — probing environment",
    ):
        assert marker in PAGE, marker

    # The gate must key off the persisted flag, and must not resurrect the old
    # auto-open-Settings behaviour for a brand-new user.
    assert "s.onboarding&&s.onboarding.completed" in PAGE

    parser = _PageContract()
    parser.feed(PAGE)
    assert [value for value, count in Counter(parser.ids).items() if count > 1] == []
    known = set(parser.ids)
    for dialog in parser.dialogs:
        assert dialog.get("aria-modal") == "true"
        label = dialog.get("aria-labelledby")
        assert label and label in known


def test_every_new_first_run_string_has_chinese_parity():
    # Exact ZH map entries for the visible first-run strings (§24 parity).
    for pair in (
        '"Create your first project":"创建你的第一个项目"',
        '"Open an existing project":"打开已有项目"',
        '"Import a folder":"导入文件夹"',
        '"Explore a local demo":"体验本地演示"',
        '"System readiness":"系统就绪检查"',
        '"Everything required is ready":"所有必需项都已就绪"',
        '"Needs attention":"需要处理"',
        '"Optional enhancement":"可选增强"',
        '"Fix automatically":"自动修复"',
        '"Re-check":"重新检查"',
        '"Skip for now":"暂时跳过"',
        '"Technical detail":"技术细节"',
        '"Preflight — probing environment":"预检——正在探测环境"',
    ):
        assert pair in PAGE, pair

    # Count-bearing strings are covered by ZH_PATTERNS, not the exact map.
    for zh in ("个必需项需要处理", "项检查排队中"):
        assert zh in PAGE, zh
