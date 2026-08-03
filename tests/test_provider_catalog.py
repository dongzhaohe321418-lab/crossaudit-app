"""Provider discovery and actionable failure classification."""
from __future__ import annotations

import pytest

from crossaudit.providers import catalog
from crossaudit.providers.base import _http_denial
from crossaudit.providers.registry import get_provider
from crossaudit.providers.specs import SPECS, endpoint, endpoints


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


@pytest.mark.parametrize("vendor", list(SPECS))
def test_every_first_party_provider_has_one_key_and_model_contract(vendor):
    spec = SPECS[vendor]
    assert spec.key_env == f"CROSSAUDIT_{vendor.upper()}_KEY"
    assert spec.api_base.startswith("https://")
    assert spec.models_url.startswith("https://")
    assert spec.default_model in {model for model, _ in spec.models}
    assert spec.console_url.startswith("https://")
    assert spec.api_docs_url.startswith("https://")
    assert all(row[2].startswith("https://") and row[3].startswith("https://")
               for row in endpoints(vendor))


def test_region_bound_catalogue_uses_the_selected_official_origin(monkeypatch):
    seen = {}
    monkeypatch.setenv("REGION_KEY", "test")
    monkeypatch.setattr(catalog, "get_json", lambda url, *a, **kw:
                        (seen.setdefault("url", url) and {"data": [{"id": "MiniMax-M2.7"}]}, None))
    assert catalog.list_models("minimax", "REGION_KEY", endpoint_id="global") == [
        "MiniMax-M2.7"]
    assert seen["url"] == endpoint("minimax", "global")[3]


def test_unknown_region_is_denied_before_any_network_call(monkeypatch):
    monkeypatch.setenv("REGION_KEY", "test")
    monkeypatch.setattr(catalog, "get_json", lambda *a, **kw: pytest.fail("network call"))
    with pytest.raises(ValueError, match="unsupported qwen endpoint"):
        catalog.list_models("qwen", "REGION_KEY", endpoint_id="nowhere")


@pytest.mark.parametrize("vendor", [
    name for name in SPECS if name not in {"openai", "anthropic"}
])
def test_compatible_provider_is_bound_to_its_own_first_party_origin(
        vendor, monkeypatch):
    spec = SPECS[vendor]
    seen = {}
    monkeypatch.setenv(spec.key_env, "provider-test-key")

    def request(url, payload, headers, *, timeout):
        seen.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {"id": "safe", "choices": [{"message": {"content": "OK"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1}}, "rid"

    monkeypatch.setattr("crossaudit.providers.openai_compat.request_json", request)
    reply = get_provider(spec.provider)(
        model=spec.default_model, system="audit", prompt="answer exactly",
        key_env=spec.key_env, max_tokens=9)

    assert reply.text == "OK"
    assert seen["url"] == spec.api_base + "/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer provider-test-key"
    assert ("x-goog-api-client" in seen["headers"]) == (vendor == "google")
    assert seen["payload"].get("temperature") == (1.0 if vendor == "minimax" else 0)


def test_compatible_provider_accepts_only_a_declared_regional_origin(
        monkeypatch):
    item = SPECS["minimax"]
    monkeypatch.setenv(item.key_env, "provider-test-key")
    seen = {}
    monkeypatch.setattr(
        "crossaudit.providers.openai_compat.request_json",
        lambda url, payload, headers, *, timeout:
        (seen.setdefault("url", url) and
         {"choices": [{"message": {"content": "OK"}}]}, "rid"))
    base = endpoint("minimax", "global")[2]
    reply = get_provider(item.provider)(
        model=item.default_model, system="audit", prompt="answer",
        key_env=item.key_env, base_url=base)
    assert reply.text == "OK"
    assert seen["url"] == base + "/chat/completions"


def test_model_discovery_filters_non_chat_and_inactive_rows(monkeypatch):
    monkeypatch.setenv("MISTRAL_TEST_KEY", "test")
    rows = {"data": [
        {"id": "mistral-medium-3-5", "capabilities": {"completion_chat": True}},
        {"id": "mistral-ocr", "capabilities": {"completion_chat": False}},
        {"id": "mistral-old", "capabilities": {"completion_chat": True},
         "archived": True},
    ]}
    monkeypatch.setattr(catalog, "get_json", lambda *args, **kwargs: (rows, None))
    assert catalog.list_models("mistral", "MISTRAL_TEST_KEY") == [
        "mistral-medium-3-5"]
