"""Opt-in real-provider compatibility checks for scheduled CI and release QA."""
from __future__ import annotations

import os

import pytest

from crossaudit.providers import anthropic, openai_compat


pytestmark = pytest.mark.skipif(
    os.environ.get("CROSSAUDIT_LIVE_E2E") != "1",
    reason="set CROSSAUDIT_LIVE_E2E=1 to spend real provider credits")


def test_openai_completion_contract_is_live():
    reply = openai_compat.complete(
        model=os.environ.get("CROSSAUDIT_LIVE_OPENAI_MODEL") or "gpt-5.6-luna",
        system="This is a provider compatibility check.",
        prompt="Reply with the single word READY.",
        key_env="CROSSAUDIT_AUDITOR_KEY", max_tokens=32)
    assert reply.text.strip() and len(reply.request_sha256) == 64


def test_anthropic_completion_contract_is_live():
    reply = anthropic.complete(
        model=os.environ.get("CROSSAUDIT_LIVE_ANTHROPIC_MODEL") or
        "claude-sonnet-4-6",
        system="This is a provider compatibility check.",
        prompt="Reply with the single word READY.",
        key_env="CROSSAUDIT_GENERATOR_KEY", max_tokens=32)
    assert reply.text.strip() and len(reply.request_sha256) == 64
