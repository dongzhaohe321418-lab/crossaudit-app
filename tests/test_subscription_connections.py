from __future__ import annotations

import json
from pathlib import Path
import pytest

from crossaudit import connections
from crossaudit.config import load
from crossaudit.console import projects
from crossaudit.constitution import Draft, Rule
from crossaudit.errors import ConfigDenial, ProviderDenial
from crossaudit.providers import codex_subscription


def _payload(**updates):
    row = {
        "name": "subscription-project",
        "description": "Create one accurate review.",
        "project_type": "general",
        "max_rounds": 3,
        "auditor_vendor": "openai",
        "auditor_connection": "chatgpt",
        "auditor_model": "gpt-5.6-sol",
        "generator_vendor": "anthropic",
        "generator_connection": "api",
        "generator_model": "claude-sonnet-4-6",
        "github": False,
    }
    row.update(updates)
    return row


def test_account_state_is_allowlisted_and_never_exposes_tokens(monkeypatch):
    server = codex_subscription.CodexAppServer("/fake/codex")
    monkeypatch.setattr(server, "call", lambda *args, **kwargs: {
        "account": {"type": "chatgpt", "email": "person@example.test",
                    "planType": "plus", "accessToken": "must-not-leak",
                    "refreshToken": "must-not-leak-either"}})

    state = server.account()

    assert state == {"available": True, "connected": True, "type": "chatgpt",
                     "email": "person@example.test", "plan": "plus"}
    assert "must-not-leak" not in json.dumps(state)


def test_api_key_codex_session_is_not_mislabelled_as_chatgpt(monkeypatch):
    server = codex_subscription.CodexAppServer("/fake/codex")
    monkeypatch.setattr(server, "call", lambda *args, **kwargs: {
        "account": {"type": "apiKey", "email": "person@example.test"}})
    state = server.account()
    assert not state["connected"]
    assert "API-key login" in state["detail"]


def test_login_rejects_an_unexpected_browser_origin(monkeypatch):
    server = codex_subscription.CodexAppServer("/fake/codex")
    monkeypatch.setattr(server, "call", lambda *args, **kwargs: {
        "loginId": "provider-id", "authUrl": "https://lookalike.example/login"})
    with pytest.raises(ProviderDenial, match="unexpected login origin"):
        server.start_login()


def test_collector_fails_closed_when_subscription_agent_attempts_a_tool():
    collector = codex_subscription._Collector("thread-1")
    collector.accept({"method": "item/completed", "params": {
        "threadId": "thread-1", "item": {"type": "commandExecution"}}})
    collector.accept({"method": "turn/completed", "params": {
        "threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed"}}})

    assert collector.forbidden == ["commandExecution"]
    assert collector.done.is_set()


def test_subscription_completion_rejects_redirected_endpoints():
    with pytest.raises(ConfigDenial, match="cannot be redirected"):
        codex_subscription.complete(
            model="gpt-5.6-sol", system="auditor", prompt="review",
            base_url="https://example.test/v1")


def test_login_job_exposes_url_and_status_but_not_login_identifier(monkeypatch):
    jobs = connections.LoginJobs()
    notices = []
    monkeypatch.setattr(codex_subscription, "account_status",
                        lambda: {"available": True, "connected": False})
    monkeypatch.setattr(codex_subscription.SERVER, "start_login", lambda: {
        "loginId": "provider-secret-correlation", "authUrl": "https://chatgpt.com/login"})
    # Keep this test at the start boundary; completion has a separate runtime
    # integration test and no provider credential should enter this object.
    monkeypatch.setattr(codex_subscription.SERVER, "wait_login",
                        lambda *_: {"success": False, "error": "cancelled"})

    started = jobs.start("openai", "chatgpt", lambda: notices.append(True))
    snapshot = jobs.snapshot()

    assert started["url"].startswith("https://chatgpt.com/")
    assert snapshot and snapshot["provider"] == "openai"
    assert "login_id" not in snapshot
    assert "provider-secret-correlation" not in json.dumps(snapshot)


def test_anthropic_subscription_binding_is_refused_without_scraping():
    with pytest.raises(ConfigDenial, match="does not permit"):
        connections.LoginJobs().start("anthropic", "subscription", lambda: None)


def test_api_readiness_observes_new_environment_value_without_cache(monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_OPENAI_KEY", raising=False)
    connections.invalidate()
    connections.status()
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "new-test-key")
    assert connections.ready("openai", "api")


def test_ui_project_can_bind_official_subscription_provider(
        tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "anthropic-test")
    monkeypatch.setattr(connections, "ready", lambda vendor, method: True)
    monkeypatch.setattr(projects.wizard, "_distil", lambda *args, **kwargs: Draft(
        "Review", "general", [Rule("CA-OUT-001", "BLOCKER", "One file",
                                     "Exactly one final file exists.")]))

    result = projects.create_project(tmp_path, _payload(), lambda *_: None)
    cfg = load(Path(result["root"]) / "crossaudit.yml")

    assert cfg.auditor.provider == "openai_codex"
    assert cfg.auditor.vendor == "openai"
    assert cfg.generator_provider == "anthropic"


def test_list_models_requires_connected_chatgpt(monkeypatch):
    monkeypatch.setattr(codex_subscription.SERVER, "account", lambda: {
        "available": True, "connected": False})
    with pytest.raises(ConfigDenial, match="Sign in with ChatGPT"):
        codex_subscription.list_models()


def test_ui_model_refresh_uses_subscription_account_not_api_key(cfg, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_OPENAI_KEY", raising=False)
    monkeypatch.setattr(codex_subscription, "list_models",
                        lambda: ["gpt-account-visible"])
    result = projects.refresh_models(cfg, "openai", "auditor", "chatgpt")
    assert result["models"] == ["gpt-account-visible"]
    assert result["method"] == "chatgpt"
