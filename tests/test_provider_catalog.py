"""Provider discovery and actionable failure classification."""
from __future__ import annotations

import pytest

from crossaudit.providers import catalog
from crossaudit.providers.base import _http_denial


@pytest.mark.parametrize("vendor,key_env,rows,expected", [
    ("openai", "AUDIT_KEY", {"data": [{"id": "gpt-z"}, {"id": "gpt-a"}]},
     ["gpt-a", "gpt-z"]),
    ("anthropic", "GEN_KEY", {"data": [{"id": "claude-next"}]},
     ["claude-next"]),
    ("google", "GEN_KEY", {"data": [{"id": "models/gemini-next"}]},
     ["gemini-next"]),
    ("deepseek", "GEN_KEY", {"data": [{"id": "deepseek-next"}]},
     ["deepseek-next"]),
])
def test_live_catalogues_parse_the_models_visible_to_the_exact_key(
        vendor, key_env, rows, expected, monkeypatch):
    seen = {}
    monkeypatch.setattr(catalog, "read_key", lambda name: seen.setdefault("env", name) or "k")
    monkeypatch.setattr(catalog, "egress_check", lambda url, **kw: seen.setdefault("url", url))
    monkeypatch.setattr(catalog, "get_json",
                        lambda url, headers, timeout: (seen.setdefault("call", (url, headers)) and rows, "r"))
    assert catalog.list_models(vendor, key_env) == expected
    assert seen["env"] == key_env and seen["url"].startswith("https://")
    header = seen["call"][1]
    assert ("x-api-key" in header) == (vendor == "anthropic")


@pytest.mark.parametrize("status,body,category,retryable", [
    (400, '{"error":{"message":"model: missing"}}', "model", False),
    (400, '{"error":{"message":"bad input"}}', "request", False),
    (401, "bad key", "authentication", False),
    (403, "forbidden", "permission", False),
    (404, "gone", "endpoint", False),
    (429, "slow down", "rate_limit", True),
    (500, "vendor down", "provider", True),
])
def test_http_failures_have_stable_machine_readable_categories(
        status, body, category, retryable):
    denial = _http_denial(status, body, "https://provider.invalid/v1")
    assert denial.detail["category"] == category
    assert denial.detail["retryable"] is retryable
