"""The parametric field must never claim an independence it cannot back.

CrossAudit's whole value is the receipt's cross-vendor independence evidence.
Two vendor *names* being disjoint is necessary but not sufficient: if either
role actually ran on an aggregator, a self-hosted gateway, or a custom
OpenAI-compatible endpoint, CrossAudit cannot prove the two "vendors" are not
reselling one underlying model, so it must record ``parametric: False`` rather
than lie (North Star §31: required independence cannot be silently disabled).

These tests are hostile. Each one asks: can a non-attestable pairing still walk
away with ``parametric: True``? The answer must be no, and a first-party pair
must never be caught in the net.
"""
from __future__ import annotations

import dataclasses

import pytest

from crossaudit.config import Role
from crossaudit.errors import IntegrityDenial
from crossaudit.providers.specs import (SPECS, official_origins,
                                         source_independent)
from crossaudit.receipt import digest, verify
from crossaudit.receipt.build import (PARAMETRIC_UNATTESTABLE,
                                       isolation_evidence)
from crossaudit.receipt.schema import isolation_shortfall, validate
from crossaudit.receipt.verify import admit

from .conftest import GOOD_RESULTS, PASS_REPLY, write_increment
from .test_loop_integrity import _audit, _receipt_for

CUSTOM = "https://openrouter.example/api/v1"          # a non-built-in origin
AGGREGATOR = "https://api.together.example/v1"


@pytest.fixture()
def evidential(monkeypatch):
    """Treat the replay provider as evidential so admission can be exercised.

    Mirrors the fixture in test_loop_integrity; fixtures do not cross modules.
    """
    monkeypatch.setattr("crossaudit.auditor.run.NON_EVIDENTIAL", frozenset())


def _replace(cfg, **kw):
    return dataclasses.replace(cfg, **kw)


def _custom_auditor(cfg, base_url=CUSTOM):
    return _replace(cfg, auditor=dataclasses.replace(cfg.auditor, base_url=base_url))


# ----------------------------------------------------- source_independent unit
def test_every_first_party_preset_is_source_independent():
    assert SPECS and all(spec.source_independence for spec in SPECS.values())
    for vendor in SPECS:
        assert source_independent(vendor) is True          # no base_url = built-in


def test_official_regional_endpoints_stay_independent():
    # A vendor's own declared regional origins are still first-party.
    assert source_independent("minimax", "https://api.minimax.io/v1") is True
    assert source_independent(
        "qwen", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1") is True
    assert source_independent("openai", "https://api.openai.com/v1") is True


def test_custom_or_aggregator_origin_is_not_independent():
    # Same vendor name, but the request leaves for an origin we cannot vouch for.
    assert source_independent("openai", CUSTOM) is False
    assert source_independent("anthropic", AGGREGATOR) is False


def test_unknown_vendor_cannot_assert_independence():
    assert source_independent("openrouter") is False
    assert source_independent("") is False
    assert official_origins("openrouter") == frozenset()


def test_human_generator_is_independent_of_any_model():
    # A person is categorically outside the "two models reselling each other"
    # failure mode, so a human generator is not demoted.
    assert source_independent("human") is True


# ------------------------------------------------- isolation_evidence, per role
def _evidence(cfg, exchange):
    return isolation_evidence(cfg, mode="local", provisioner="cli",
                              admission="local-controller", exchange=exchange)


def test_first_party_cross_vendor_stays_parametric(cfg):
    # anthropic auditor + openai generator, both built-in: the invariant we must
    # not regress. Byte-identical to before: no note is attached.
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "claude-fable-5",
                         "provider": "replay", "base_url": None})
    assert ev["parametric"] is True
    assert "parametric_note" not in ev


def test_custom_auditor_endpoint_is_not_parametric(cfg):
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "m",
                         "provider": "openai_compat", "base_url": CUSTOM})
    assert ev["parametric"] is False
    assert ev["parametric_note"] == PARAMETRIC_UNATTESTABLE


def test_custom_generator_endpoint_is_not_parametric(cfg):
    # Auditor is a clean first-party origin; the generator config points at a
    # custom endpoint, so the pair still cannot claim independence.
    cfg = _replace(cfg, generator_base_url=CUSTOM)
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "m",
                         "provider": "replay", "base_url": None})
    assert ev["parametric"] is False
    assert ev["parametric_note"] == PARAMETRIC_UNATTESTABLE


def test_generator_base_url_env_override_is_honoured(cfg, monkeypatch):
    # An operator can point generation at a custom origin purely via env, leaving
    # the config first-party. The receipt must still refuse the independence
    # claim — the env override resolves exactly as the generator role does.
    assert cfg.generator_base_url is None
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_BASE_URL", CUSTOM)
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "m",
                         "provider": "replay", "base_url": None})
    assert ev["parametric"] is False
    assert ev["parametric_note"] == PARAMETRIC_UNATTESTABLE


def test_both_roles_custom_is_not_parametric(cfg):
    cfg = _replace(cfg, generator_base_url=AGGREGATOR)
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "m",
                         "provider": "openai_compat", "base_url": CUSTOM})
    assert ev["parametric"] is False


def test_runtime_fallback_to_custom_overrides_a_first_party_declaration(cfg):
    # The config declares a first-party auditor, but a fallback actually answered
    # from a custom origin. The receipt must reflect what *ran*, not what was
    # declared: this is the exact silent-downgrade the hardening closes.
    assert cfg.auditor.base_url is None                     # declared first-party
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "m",
                         "provider": "openai_compat", "base_url": CUSTOM,
                         "fallback": True})
    assert ev["parametric"] is False
    assert ev["parametric_note"] == PARAMETRIC_UNATTESTABLE


def test_a_generator_fallback_route_to_custom_is_caught(cfg):
    # Primary generator is first-party, but a fallback route could have produced
    # the increment on a custom origin; we cannot observe which one ran, so any
    # non-attestable route in the pool withholds the claim.
    cfg = _replace(cfg, generator_fallbacks=(
        Role("openai_compat", "m", "openai", "CROSSAUDIT_GENERATOR_KEY",
             base_url=CUSTOM),))
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "m",
                         "provider": "replay", "base_url": None})
    assert ev["parametric"] is False


def test_unknown_vendor_pairing_is_not_parametric(cfg):
    # An unknown auditor vendor is disjoint from the generator's, so heterogeneity
    # by names alone would have passed — but the source cannot be attested.
    ev = _evidence(cfg, {"vendor": "openrouter", "model": "m",
                         "provider": "openai_compat", "base_url": CUSTOM})
    assert ev["parametric"] is False


def test_same_vendor_pair_fails_for_heterogeneity_not_source(cfg):
    # A same-vendor pair is already False for I1's own recorded reason; the
    # source note must not be attached (both origins here are attestable).
    cfg = _replace(cfg, generator_vendor="anthropic")
    ev = _evidence(cfg, {"vendor": "anthropic", "model": "claude-fable-5",
                         "provider": "replay", "base_url": None})
    assert ev["parametric"] is False
    assert "parametric_note" not in ev


def test_no_exchange_falls_back_to_the_declared_auditor_pool(cfg):
    # Verification/inspection paths that build evidence without a live exchange
    # judge the auditor from its configured routes. A custom declared auditor is
    # still caught.
    ev = _evidence(_custom_auditor(cfg), exchange=None)
    assert ev["parametric"] is False


# --------------------------------------------- schema stays additive / valid
def test_parametric_note_is_schema_valid_and_hashes_stably(cfg):
    ev = _evidence(_custom_auditor(cfg), exchange=None)
    iso = {"receipt_schema": 2, **_MINIMAL_RECEIPT, "isolation": ev}
    validate(iso)                                           # additive field: fine
    # Deterministic: same inputs, same evidence, same digest.
    again = _evidence(_custom_auditor(cfg), exchange=None)
    assert ev == again


# ------------------------------------- end-to-end fail-closed admission chain
def test_custom_source_receipt_is_refused_admission_when_parametric_required(
        science, cfg, transcripts, evidential, monkeypatch):
    """The whole point: a non-attestable source cannot admit where independence
    is required. Local default already sets isolation.minimum.parametric=true."""
    assert cfg.isolation_minimum["parametric"] is True     # the local default
    cfg = _replace(cfg, generator_base_url=CUSTOM)          # generator via aggregator
    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, cycle, store = _audit(cfg, sha, transcripts, PASS_REPLY)
    assert outcome.verdict == "PASS"
    receipt, _ledger = _receipt_for(cfg, sha, cycle, outcome)

    assert receipt["isolation"]["parametric"] is False
    assert receipt["isolation"]["parametric_note"] == PARAMETRIC_UNATTESTABLE
    assert isolation_shortfall(receipt, cfg.isolation_minimum) == ["parametric"]

    evidence = verify(receipt, science_root=science, audit_root=science,
                      expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert evidence["verified"] is True                    # bindings still hold
    assert evidence["admission_ready"] is False
    with pytest.raises(IntegrityDenial, match="isolation evidence is weaker"):
        admit(receipt, store, evidence, cfg=cfg)


def test_first_party_receipt_admits_under_the_local_default(
        science, cfg, transcripts, evidential, monkeypatch):
    """The net must not catch a normal local first-party user: anthropic auditor
    + openai generator admits cleanly under isolation.minimum.parametric=true."""
    from crossaudit import _selfid

    sha = write_increment(science, GOOD_RESULTS, "Fine.", "clean")
    outcome, cycle, store = _audit(cfg, sha, transcripts, PASS_REPLY)
    receipt, _ledger = _receipt_for(cfg, sha, cycle, outcome)
    assert receipt["isolation"]["parametric"] is True
    assert "parametric_note" not in receipt["isolation"]

    store.record_verdict(cycle["cycle_id"], sha, "PASS", digest(receipt),
                         cfg.max_rounds)
    evidence = verify(receipt, science_root=science, audit_root=science,
                      expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
    assert evidence["admission_ready"] is True
    monkeypatch.setattr(_selfid, "ADMISSIBLE_MODES",
                        frozenset({_selfid.install_mode()}))
    assert admit(receipt, store, evidence, cfg=cfg)["admitted"] is True


# A minimal receipt skeleton so the schema validator has the blocks it requires
# when we assert the isolation field is additive-compatible.
_MINIMAL_RECEIPT = {
    "subject": {"science_repo": "r", "sha": "a" * 40, "tree": "t", "scope": ""},
    "cycle": {"cycle_id": "c", "root_sha": "r", "active_sha": "a",
              "parent_receipt": "", "round": 1},
    "inputs": {"manifest": {}, "constitution_sha256": "x",
               "constitution_commit": "y", "dcl_source_sha256": "z",
               "prompt_sha256": "p", "checks": [], "skills": {}},
    "audit": {"verdict": "PASS", "provider": "replay", "model": "m",
              "vendor": "anthropic", "audit_integrity": "OK", "exchange": {},
              "retention": "sealed"},
    "ledger": {"audit_repo": "local", "report_commit": "", "cycle_path": "c",
               "report_sha256": "s"},
    "verifier": {"project": "crossaudit", "version": "0", "code_digest_sha256": "d",
                 "install_mode": "test"},
}
