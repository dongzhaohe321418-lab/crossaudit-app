"""The CapabilityCard is the one source of provider capability knowledge.

These tests pin the convergence: effort menus, adapter parameter choice, and
usage pricing all read one record, and North Star §31 — unsupported controls are
never sent to a provider — holds for every recognised built-in model.
"""
from __future__ import annotations

import pytest

from crossaudit import usage
from crossaudit.errors import ProviderDenial
from crossaudit.providers import anthropic, openai_compat
from crossaudit.providers.registry import get_provider
from crossaudit.providers.specs import capability_card, reasoning_efforts


def _openai_payload(monkeypatch, model, **kwargs):
    seen = {}

    def request(url, payload, headers, *, timeout):
        seen["payload"] = payload
        return ({"choices": [{"message": {"content": "OK"}}]}, "rid")

    monkeypatch.setattr(openai_compat, "request_json", request)
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "k")
    openai_compat.complete(model=model, system="s", prompt="p",
                           key_env="CROSSAUDIT_OPENAI_KEY", max_tokens=9, **kwargs)
    return seen["payload"]


def _anthropic_payload(monkeypatch, model, **kwargs):
    seen = {}

    def request(url, payload, headers, *, timeout):
        seen["payload"] = payload
        return ({"content": [{"type": "text", "text": "OK"}]}, "rid")

    monkeypatch.setattr(anthropic, "request_json", request)
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "k")
    anthropic.complete(model=model, system="s", prompt="p",
                       key_env="CROSSAUDIT_ANTHROPIC_KEY", max_tokens=9, **kwargs)
    return seen["payload"]


# ── §31: a recognised built-in model never sends a control it does not support ─

def test_modern_openai_model_omits_temperature_and_uses_completion_tokens(monkeypatch):
    payload = _openai_payload(monkeypatch, "gpt-5.6-sol")
    assert "temperature" not in payload
    assert payload["max_completion_tokens"] == 9
    assert "max_tokens" not in payload


def test_legacy_openai_model_still_sends_a_deterministic_temperature(monkeypatch):
    # An unrecognised OpenAI model on the built-in origin keeps the historical
    # fail-safe shape: a temperature is sent and the built-in origin uses the
    # modern token field.
    payload = _openai_payload(monkeypatch, "gpt-4o-mini")
    assert payload["temperature"] == 0
    assert payload["max_completion_tokens"] == 9


def test_opus_4_8_omits_temperature_while_sonnet_4_6_sends_zero(monkeypatch):
    assert "temperature" not in _anthropic_payload(monkeypatch, "claude-opus-4-8")
    assert _anthropic_payload(monkeypatch, "claude-sonnet-4-6")["temperature"] == 0


def test_recognised_builtin_model_never_gambles_a_retry(monkeypatch):
    calls = []

    def request(url, payload, headers, *, timeout):
        calls.append(payload)
        raise ProviderDenial(
            "temperature is not supported with this model; only the default",
            status=400, category="request")

    monkeypatch.setattr(openai_compat, "request_json", request)
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "k")
    with pytest.raises(ProviderDenial):
        openai_compat.complete(model="gpt-5.6-sol", system="s", prompt="p",
                               key_env="CROSSAUDIT_OPENAI_KEY", max_tokens=9)
    assert len(calls) == 1  # no send-reject-swap for a recognised built-in model


def test_custom_endpoint_keeps_the_send_reject_swap_safety_net(monkeypatch):
    calls = []

    def request(url, payload, headers, *, timeout):
        calls.append(dict(payload))
        if len(calls) == 1:
            raise ProviderDenial(
                "temperature is unsupported for this deployment",
                status=400, category="request")
        return ({"choices": [{"message": {"content": "OK"}}]}, "rid")

    monkeypatch.setattr(openai_compat, "request_json", request)
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "k")
    reply = openai_compat.complete(
        model="local-model", system="s", prompt="p",
        key_env="CROSSAUDIT_OPENAI_KEY", max_tokens=9,
        base_url="https://proxy.example.com/v1", allow_custom=True)
    assert reply.text == "OK"
    assert len(calls) == 2
    assert "temperature" in calls[0] and "temperature" not in calls[1]


# ── Single source of truth: every surface reads the same card ─────────────────

@pytest.mark.parametrize("vendor,model", [
    ("openai", "gpt-5.6-luna"), ("anthropic", "claude-sonnet-4-6"),
    ("anthropic", "claude-haiku-4-5-20251001"), ("openai", "gpt-5.6-terra"),
    ("google", "gemini-3.6-flash"), ("openai", "private-unknown-model"),
])
def test_usage_price_is_the_card_price(vendor, model):
    assert usage._rates(vendor, model) == capability_card(vendor, model).price


@pytest.mark.parametrize("vendor,model", [
    ("openai", "gpt-5.6-sol"), ("anthropic", "claude-opus-4-8"),
    ("google", "gemini-2.5-pro"), ("xai", "grok-4.5"),
    ("deepseek", "deepseek-v4-flash"), ("openai", "brand-new-model"),
])
def test_effort_menu_is_the_card_efforts(vendor, model):
    card = capability_card(vendor, model)
    assert reasoning_efforts(vendor, model) == (card.reasoning_efforts or ())


def test_config_effort_whitelist_derives_from_the_one_effort_catalogue():
    # The YAML effort whitelist is no longer a second hand-maintained copy: it
    # derives from specs.EFFORT_HINTS, the single vocabulary of effort levels.
    # This pins that convergence and guards the drift the derivation prevents —
    # every effort a shipping CapabilityCard emits must be an accepted value,
    # and the catalogue may stay wider (e.g. the reserved "ultra") on purpose.
    from crossaudit.config import _EFFORT_VALUES
    from crossaudit.providers.specs import EFFORT_HINTS, _CAPABILITIES

    assert _EFFORT_VALUES == frozenset(EFFORT_HINTS)
    card_efforts = {effort
                    for cards in _CAPABILITIES.values()
                    for _prefix, card in cards
                    for effort in (card.reasoning_efforts or ())}
    assert card_efforts <= _EFFORT_VALUES
    # The catalogue documents at least one reserved level no card emits yet, so
    # validation is deliberately a superset, never narrower than the cards.
    assert "ultra" in _EFFORT_VALUES and "ultra" not in card_efforts


def test_usage_no_longer_keeps_a_parallel_price_table():
    # The price data moved into the capability cards; a second table here would
    # be exactly the duplication this slice removed.
    assert not hasattr(usage, "_PRICES")


@pytest.mark.parametrize("vendor,model,rate_tuple", [
    ("openai", "gpt-5.6-sol", (5.0, 30.0, 6.25, 0.50)),
    ("openai", "gpt-5.6-luna", (1.0, 6.0, 1.25, 0.10)),
    ("anthropic", "claude-opus-4-8", (5.0, 25.0, 6.25, 0.50)),
    ("anthropic", "claude-sonnet-4-6", (3.0, 15.0, 3.75, 0.30)),
    ("anthropic", "claude-haiku-4-5-20251001", (1.0, 5.0, 1.25, 0.10)),
    ("anthropic", "claude-fable-5", (10.0, 50.0, 12.50, 1.00)),
])
def test_pricing_survived_the_migration_unchanged(vendor, model, rate_tuple):
    price = capability_card(vendor, model).price
    assert price is not None
    assert (price.input, price.output, price.cache_write, price.cache_read) == rate_tuple


# ── Conservative defaults for the models we cannot vouch for ──────────────────

def test_unknown_model_returns_a_conservative_card():
    card = capability_card("openai", "totally-unknown-2099", official=True)
    assert card.known is False
    assert card.reasoning_efforts is None
    assert card.price is None
    assert card.compat_retry is True
    # The §4 selector fields stay honestly blank for a model we cannot vouch
    # for: no fabricated context window, vision, or structured-output claim.
    assert card.context_window is None
    assert card.vision is False
    assert card.structured_output is False


def test_recognised_model_disables_the_retry_only_on_a_builtin_origin():
    builtin = capability_card("openai", "gpt-5.6-sol", official=True)
    proxied = capability_card("openai", "gpt-5.6-sol", official=False)
    assert builtin.known and builtin.compat_retry is False
    assert proxied.known and proxied.compat_retry is True


def test_compatible_vendor_default_model_still_sends_its_temperature(monkeypatch):
    # The per-vendor HTTP shape asserted elsewhere must survive card resolution:
    # a MiniMax call keeps its mandated temperature=1.0 through the card path.
    seen = {}
    monkeypatch.setenv("CROSSAUDIT_MINIMAX_KEY", "k")
    monkeypatch.setattr(
        openai_compat, "request_json",
        lambda url, payload, headers, *, timeout:
        (seen.setdefault("payload", payload) and
         {"choices": [{"message": {"content": "OK"}}]}, "rid"))
    get_provider("minimax")(model="MiniMax-M2.7", system="s", prompt="p",
                            key_env="CROSSAUDIT_MINIMAX_KEY", max_tokens=9)
    assert seen["payload"]["temperature"] == 1.0


# ── §4 model-selector capability fields ───────────────────────────────────────
#
# context_window / vision / structured_output are the North Star §4 selector
# fields.  Slice 2 declared them but left every card conservative (None/False)
# rather than invent a value.  They are now populated for the curated first-party
# families whose capabilities were verified against current official provider
# documentation.  They are display-only: no adapter, price, or request-shaping
# path reads them, so filling them changes no run behaviour.

@pytest.mark.parametrize("vendor,model,context_window", [
    ("openai", "gpt-5.6-sol", 1_050_000),
    ("openai", "gpt-5.6-terra", 1_050_000),
    ("openai", "gpt-5.6-luna", 1_050_000),
    ("anthropic", "claude-opus-4-8", 1_000_000),
    ("anthropic", "claude-sonnet-4-6", 1_000_000),
    ("anthropic", "claude-haiku-4-5-20251001", 200_000),
    ("google", "gemini-3.6-flash", 1_000_000),
    ("google", "gemini-3.5-pro", 1_000_000),
    ("google", "gemini-3.5-flash", 1_000_000),
    ("xai", "grok-4.5", 500_000),
])
def test_curated_selector_fields_are_populated_from_documentation(
        vendor, model, context_window):
    # Each verified curated family accepts image input and can return a
    # schema-guaranteed response, and reports its documented context window.
    card = capability_card(vendor, model)
    assert card.vision is True
    assert card.structured_output is True
    assert card.context_window == context_window


def test_every_declared_context_window_is_a_positive_int_or_none():
    # A populated context window is a real, positive token count; an unverified
    # one stays None.  Neither 0 nor a negative sentinel is ever stored, so the
    # selector never renders a nonsensical size.
    from crossaudit.providers.specs import _CAPABILITIES

    for cards in _CAPABILITIES.values():
        for _prefix, card in cards:
            cw = card.context_window
            assert cw is None or (isinstance(cw, int) and cw > 0), _prefix


@pytest.mark.parametrize("vendor,model", [
    ("deepseek", "deepseek-v4-flash"),
    ("zhipu", "glm-5.2"),
    ("moonshot", "kimi-k2.6"),
    ("minimax", "MiniMax-M2.7"),
    ("qwen", "qwen3.7-plus"),
    ("mistral", "mistral-medium-3-5"),
])
def test_uncarded_first_party_models_keep_honest_blank_selector_fields(vendor, model):
    # These first-party vendors have no capability card yet, so their selector
    # fields stay None/False rather than assert an unverified capability.
    # Populating them means adding a recognised-model card, which flips
    # compat_retry — deliberately out of scope for this data-only slice.
    card = capability_card(vendor, model)
    assert card.context_window is None
    assert card.vision is False
    assert card.structured_output is False


def test_custom_endpoint_model_advertises_no_selector_capability():
    # A custom OpenAI-compatible endpoint is unvouchable; its card must not
    # claim vision, structured output, or any context window.
    card = capability_card("openai", "local-model", official=False)
    assert card.context_window is None
    assert card.vision is False
    assert card.structured_output is False
