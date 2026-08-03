from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from crossaudit import usage
from crossaudit.providers.base import Reply
from crossaudit.providers.codex_subscription import _Collector


def _reply(raw: dict, text: str = "private model output") -> Reply:
    return Reply(text=text, request_id="provider-private-id",
                 request_sha256="a" * 64, response_sha256="b" * 64, raw=raw)


def test_openai_counts_remove_cached_input_from_billable_input():
    counts = usage.normalise_usage({"usage": {
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "prompt_tokens_details": {"cached_tokens": 20},
    }})

    assert counts == {"input": 80, "output": 40, "cache_write": 0,
                      "cache_read": 20, "total": 140, "method": "reported"}


def test_anthropic_counts_preserve_both_cache_classes():
    counts = usage.normalise_usage({"usage": {
        "input_tokens": 100, "output_tokens": 30,
        "cache_creation_input_tokens": 10, "cache_read_input_tokens": 20,
    }})

    assert counts == {"input": 100, "output": 30, "cache_write": 10,
                      "cache_read": 20, "total": 160, "method": "reported"}


def test_codex_runtime_usage_is_provider_reported_and_not_guessed():
    counts = usage.normalise_usage({"usage": {
        "inputTokens": 250, "cachedInputTokens": 50,
        "cacheWriteInputTokens": 12, "outputTokens": 25,
        "reasoningOutputTokens": 8, "totalTokens": 275,
    }})

    assert counts == {"input": 188, "output": 25, "cache_write": 12,
                      "cache_read": 50, "total": 275, "method": "reported"}


def test_collector_captures_the_current_turn_token_notification():
    collector = _Collector("thread-1")
    collector.accept({"method": "thread/tokenUsage/updated", "params": {
        "threadId": "thread-1", "turnId": "turn-1", "tokenUsage": {
            "last": {"inputTokens": 70, "cachedInputTokens": 10,
                     "outputTokens": 20, "totalTokens": 90},
            "total": {"inputTokens": 700, "outputTokens": 200},
        }}})

    assert collector.usage == {"inputTokens": 70, "cachedInputTokens": 10,
                               "outputTokens": 20, "totalTokens": 90}


def test_local_ledger_never_contains_prompts_replies_or_provider_ids(cfg):
    event = usage.record_reply(
        root=cfg.root, state_dir=cfg.state_dir, role="auditor", phase="audit",
        vendor="anthropic", provider="anthropic", model="claude-sonnet-4-6",
        reply=_reply({"usage": {"input_tokens": 100, "output_tokens": 30,
                                "cache_creation_input_tokens": 10,
                                "cache_read_input_tokens": 20}}),
        system="private system instructions", prompt="private user prompt")
    text = (cfg.root / cfg.state_dir / usage.LEDGER_NAME).read_text()

    assert event["method"] == "reported"
    assert event["api_value_usd"] == pytest.approx(0.0007935)
    for secret in ("private system instructions", "private user prompt",
                   "private model output", "provider-private-id", "a" * 64):
        assert secret not in text
    ledger = cfg.root / cfg.state_dir / usage.LEDGER_NAME
    if os.name != "nt":
        assert (ledger.stat().st_mode & 0o777) == 0o600
    else:
        # Windows access is represented by the inherited directory ACL rather
        # than POSIX permission bits; st_mode cannot prove a 0600 equivalent.
        assert ledger.is_file()


def test_unknown_or_custom_models_keep_counts_but_are_unpriced(cfg):
    event = usage.record_reply(
        root=cfg.root, state_dir=cfg.state_dir, role="generator", phase="generation",
        vendor="other", provider="openai_compat", model="private-model",
        base_url="https://models.example.test", reply=_reply({"usage": {
            "prompt_tokens": 10, "completion_tokens": 5}}),
        system="system", prompt="prompt")

    assert event["total"] == 15
    assert event["api_value_usd"] is None
    assert event["billing_kind"] == "unpriced"


def test_summary_groups_roles_models_days_and_recent_calls(cfg):
    for role, provider, vendor, model, raw in (
        ("generator", "openai_compat", "openai", "gpt-5.6-luna",
         {"usage": {"prompt_tokens": 100, "completion_tokens": 40,
                    "prompt_tokens_details": {"cached_tokens": 20}}}),
        ("auditor", "anthropic", "anthropic", "claude-sonnet-4-6",
         {"usage": {"input_tokens": 80, "output_tokens": 20}}),
    ):
        usage.record_reply(root=cfg.root, state_dir=cfg.state_dir, role=role,
                           phase="audit" if role == "auditor" else "generation",
                           vendor=vendor, provider=provider, model=model,
                           reply=_reply(raw), system="s", prompt="p")

    result = usage.summary(cfg)

    assert result["today"]["calls"] == 2
    assert result["month"]["tokens"] == 240
    assert result["month"]["cache_read"] == 20
    assert {row["role"] for row in result["roles"]} == {"auditor", "generator"}
    assert {row["model"] for row in result["models"]} == {
        "gpt-5.6-luna", "claude-sonnet-4-6"}
    assert len(result["days"]) == 7 and len(result["recent"]) == 2
    assert result["cost_label"] == "API-value estimate"


def test_missing_provider_usage_is_visibly_estimated():
    counts = usage.normalise_usage({}, system="1234", prompt="5678",
                                   response="abcdefgh")
    assert counts == {"input": 2, "output": 2, "cache_write": 0,
                      "cache_read": 0, "total": 4, "method": "estimated"}


def test_writes_wake_live_views_after_the_event_is_durable(cfg):
    seen = []
    usage.subscribe(lambda: seen.append(usage.summary(cfg)["all"]["calls"]))

    usage.record_reply(
        root=cfg.root, state_dir=cfg.state_dir, role="auditor", phase="audit",
        vendor="anthropic", provider="anthropic", model="claude-sonnet-4-6",
        reply=_reply({"usage": {"input_tokens": 1, "output_tokens": 1}}),
        system="s", prompt="p")

    assert seen[-1] == 1


def test_windows_locking_fallback(monkeypatch, tmp_path):
    calls = []

    class FakeMsvcrt:
        LK_LOCK = 1
        LK_UNLCK = 2

        @staticmethod
        def locking(fd, mode, length):
            calls.append((fd, mode, length))

    path = tmp_path / "ledger"
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        monkeypatch.setattr(usage, "_fcntl", None)
        monkeypatch.setattr(usage, "_msvcrt", FakeMsvcrt)
        assert usage._lock_file(fd) is True
        usage._unlock_file(fd)
    finally:
        os.close(fd)
    assert [(mode, length) for _fd, mode, length in calls] == [(1, 1), (2, 1)]


def test_malformed_lines_do_not_break_the_usage_page(cfg):
    path = cfg.root / cfg.state_dir / usage.LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json\n" + json.dumps({"t": 0}) + "\n")

    result = usage.summary(cfg)

    assert result["malformed_lines"] == 1
    assert result["all"]["calls"] == 1
