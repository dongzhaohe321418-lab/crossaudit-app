"""Provider recovery, local guardrails, and UI-persisted policy."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from crossaudit import usage
from crossaudit.config import Budgets, Resilience, Role, heterogeneity, load
from crossaudit.console import projects
from crossaudit.errors import ConfigDenial, ProviderDenial
from crossaudit.providers import resilience
from crossaudit.providers.base import Reply
from crossaudit.providers.base import _http_denial


def _reply() -> Reply:
    return Reply("ok", "request", "a" * 64, "b" * 64,
                 {"usage": {"prompt_tokens": 2, "completion_tokens": 1}})


def test_retry_after_then_fallback_is_one_provider_turn(cfg, monkeypatch):
    primary = Role("primary", "model-a", "openai", "PRIMARY_KEY",
                   fallbacks=(Role("backup", "model-b", "google", "BACKUP_KEY"),))
    cfg = replace(cfg, resilience=Resilience(
        max_attempts=2, initial_backoff_seconds=1, max_backoff_seconds=4,
        retry_after_cap_seconds=9, circuit_breaker_failures=5,
        circuit_breaker_cooldown_seconds=30))
    monkeypatch.setenv("PRIMARY_KEY", "secret-a")
    monkeypatch.setenv("BACKUP_KEY", "secret-b")
    calls, waits, events = [], [], []

    def provider(name):
        def complete(**_kwargs):
            calls.append(name)
            if name == "primary":
                raise ProviderDenial("busy", status=429, category="rate_limit",
                                     retryable=True, retry_after_seconds=2)
            return _reply()
        return complete

    monkeypatch.setattr(resilience, "get_provider", provider)
    monkeypatch.setattr(resilience, "_sleep", waits.append)
    monkeypatch.setattr(resilience.random, "uniform", lambda *_: 1.0)
    reply = resilience.complete(
        cfg, "generator", primary, system="s", prompt="p",
        on_event=lambda *row: events.append(row))

    assert calls == ["primary", "primary", "backup"]
    assert waits == [2]
    assert resilience.route_from_reply(reply, primary)["fallback"] is True
    assert any(row[1] == "waiting to retry" for row in events)
    assert "secret-a" not in (cfg.root / cfg.state_dir /
                              resilience.STATE_NAME).read_text()


def test_open_circuit_skips_primary_on_the_next_call(cfg, monkeypatch):
    primary = Role("primary", "model-a", "openai", "PRIMARY_KEY",
                   fallbacks=(Role("backup", "model-b", "google", "BACKUP_KEY"),))
    cfg = replace(cfg, resilience=Resilience(
        max_attempts=1, initial_backoff_seconds=0, max_backoff_seconds=0,
        retry_after_cap_seconds=0, circuit_breaker_failures=1,
        circuit_breaker_cooldown_seconds=300))
    monkeypatch.setenv("PRIMARY_KEY", "a")
    monkeypatch.setenv("BACKUP_KEY", "b")
    calls = []

    def provider(name):
        def complete(**_kwargs):
            calls.append(name)
            if name == "primary":
                raise ProviderDenial("offline", category="transport", retryable=True)
            return _reply()
        return complete

    monkeypatch.setattr(resilience, "get_provider", provider)
    resilience.complete(cfg, "generator", primary, system="s", prompt="p")
    resilience.complete(cfg, "generator", primary, system="s", prompt="p")
    assert calls == ["primary", "backup", "backup"]
    route = next(row for row in resilience.snapshot(cfg)["routes"]
                 if row["provider"] == "primary")
    assert route["state"] == "open"


def test_hard_token_guardrail_refuses_before_network(cfg):
    cfg = replace(cfg, budgets=Budgets(daily_token_limit=1))
    usage.record_reply(
        root=cfg.root, state_dir=cfg.state_dir, role="generator", phase="generation",
        vendor="openai", provider="openai_compat", model="gpt-5.6-luna",
        reply=_reply(), system="s", prompt="p")
    with pytest.raises(ProviderDenial, match="Daily token limit reached") as caught:
        usage.enforce_budget(cfg)
    assert caught.value.detail["category"] == "budget"
    assert usage.summary(cfg)["budget"]["blocked"] is True


def test_recovery_pools_cannot_share_a_vendor(cfg):
    auditor = replace(cfg.auditor, fallbacks=(
        Role("google", "gemini", "google", "GOOGLE_API_KEY"),))
    cfg = replace(cfg, auditor=auditor, generator_fallbacks=(
        Role("backup", "other", "google", "OTHER_KEY"),))
    ok, why = heterogeneity(cfg)
    assert ok is False
    assert "overlap" in why and "google" in why


def test_project_controls_persist_recovery_and_budget_policy(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY", raising=False)
    created = projects.create_project(tmp_path, {
        "name": "resilient", "description": "Produce accurate user-facing work.",
        "max_rounds": 3, "auditor_vendor": "openai",
        "auditor_model": "gpt-5.6-sol", "generator_vendor": "anthropic",
        "generator_model": "claude-sonnet-4-6", "github": False,
    }, lambda *_: None)
    cfg = load(Path(created["root"]) / "crossaudit.yml")
    result = projects.update_runtime(cfg, {
        "generator_model": cfg.generator_model,
        "auditor_model": cfg.auditor.model,
        "generator_reasoning_effort": "", "auditor_reasoning_effort": "",
        "max_rounds": 3, "max_attempts": 4, "initial_backoff_seconds": 2,
        "max_backoff_seconds": 30, "retry_after_cap_seconds": 180,
        "circuit_breaker_failures": 2, "circuit_breaker_cooldown_seconds": 90,
        "daily_token_warning": "1000", "daily_token_limit": "2000",
        "monthly_cost_warning_usd": "5", "monthly_cost_limit_usd": "10",
        "generator_fallbacks": [{"vendor": "google", "model": "gemini-2.5-pro"}],
        "auditor_fallbacks": [{"vendor": "xai", "model": "grok-4"}],
    })
    updated = load(cfg.path)
    assert updated.resilience.max_attempts == result["resilience"]["max_attempts"] == 4
    assert updated.budgets.daily_token_limit == 2000
    assert updated.generator_fallbacks[0].vendor == "google"
    assert updated.auditor.fallbacks[0].vendor == "xai"
    assert heterogeneity(updated)[0] is True


def test_invalid_recovery_numbers_are_rejected_by_config(science):
    path = science / "crossaudit.yml"
    path.write_text(path.read_text() + "\nresilience:\n  max_attempts: 0\n")
    with pytest.raises(ConfigDenial, match="max_attempts"):
        load(path)


def test_http_retry_after_is_machine_readable():
    denial = _http_denial(429, '{"error":{"message":"slow down"}}',
                           "https://provider.invalid", {"Retry-After": "7"})
    assert denial.detail["retry_after_seconds"] == 7
