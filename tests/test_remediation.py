"""Typed remediation: one vocabulary for what a refusal lets a person do.

Slice three of the North Star route. A denial and a stalled cycle used to
describe their exits as loose ``issue``/``action``/``url`` strings, and the
Console decided which provider remedies to show by asking whether the prose
contained "provider failure". These tests pin the replacement: a typed
``RemediationAction`` set (errors.py, North Star §14/§15), an ordered
``remediations`` list on every ``Denial``, a structured ``escalation_kind`` on
the cycle record, and a Console that renders the remedies from that list.
"""
from __future__ import annotations

import json
from pathlib import Path

from crossaudit.controller import StateStore
from crossaudit.console import overview
from crossaudit.console.page import PAGE
from crossaudit.errors import (
    ConfigDenial, ProviderDenial, RemediationAction, classify_escalation_kind,
    escalation_remediations, provider_remediations)
from crossaudit.providers.base import _http_denial


# ------------------------------------------------------------- the vocabulary
def test_remediation_values_are_the_stable_wire_strings():
    # A typed action and the legacy bare ``action=`` string are one value, so
    # no consumer has to know which minted it.
    assert RemediationAction.RETRY == "retry"
    assert RemediationAction.VALIDATE_CREDENTIAL == "validate_credential"
    assert RemediationAction.SELECT_MODEL == "select_model"
    assert RemediationAction.CONNECT_GITHUB == "connect_github"
    assert RemediationAction.AUTHORIZE_DELETE == "authorize_delete"
    # North Star §15's remediation list is present, spelled the same way.
    for name in ("retry", "validate_credential", "replace_key", "select_model",
                 "use_fallback", "reduce_context", "open_billing",
                 "continue_later", "stop"):
        assert RemediationAction(name).value == name


def test_provider_category_maps_to_ordered_remedies_primary_first():
    assert provider_remediations("authentication") == [
        "validate_credential", "replace_key", "use_fallback", "stop"]
    assert provider_remediations("rate_limit") == [
        "retry", "continue_later", "use_fallback", "stop"]
    assert provider_remediations("model") == ["select_model", "use_fallback", "stop"]
    # An unclassified category still names something a person can do.
    assert provider_remediations("something new") == ["retry", "use_fallback", "stop"]


def test_escalation_kind_maps_to_the_a40_remedy_sets():
    # The provider set is the A40 contract: retry / review connection /
    # change model or fallback / stop.
    assert escalation_remediations("provider") == [
        "retry", "validate_credential", "select_model", "stop"]
    assert escalation_remediations("audit") == ["revise", "stop"]


# --------------------------------------------------------- the Denial carrier
def test_provider_denial_carries_typed_remediations_and_round_trips():
    denial = _http_denial(401, json.dumps({"error": {"message": "bad key"}}),
                          "https://api.example/v1/chat", {})
    assert denial.remediations == provider_remediations("authentication")
    payload = denial.as_dict()
    # The remedies travel on the wire beside the historical, still-present keys.
    assert payload["remediations"] == [
        "validate_credential", "replace_key", "use_fallback", "stop"]
    assert payload["category"] == "authentication"
    assert payload["retryable"] is False
    assert payload["kind"] == "provider" and payload["denied"] is True


def test_a_denial_without_remedies_keeps_the_historical_as_dict_shape():
    # Additive contract: a refusal that names no remedy must not grow the key,
    # so callers asserting the old key set keep working.
    payload = ConfigDenial("nothing to do here", issue="x", action="retry").as_dict()
    assert "remediations" not in payload
    assert payload["issue"] == "x" and payload["action"] == "retry"


def test_remediation_members_are_unwrapped_to_their_value_not_repr():
    # The mixed-in-Enum trap: a member must serialise as "retry", never as
    # "RemediationAction.RETRY".
    denial = ProviderDenial("boom", remediations=[RemediationAction.RETRY,
                                                  RemediationAction.STOP])
    assert denial.remediations == ["retry", "stop"]
    assert json.loads(json.dumps(denial.as_dict()))["remediations"] == ["retry", "stop"]


# ------------------------------------------- the escalation, read structurally
def _store(cfg) -> StateStore:
    return StateStore(cfg.root / cfg.state_dir / "state.json")


def test_structured_provider_kind_needs_no_marker_in_the_reason(cfg):
    # The coupling this slice removes: a provider escalation whose prose does
    # NOT contain "provider failure" is still routed to the provider remedies,
    # because the kind is a stored field, not something re-parsed from prose.
    store = _store(cfg)
    stopped = store.record_build_escalation(
        cfg.science_repo, "a" * 40,
        "the model connection was refused before any audit ran", 1,
        "history", "Create one accurate review", kind="provider")

    row = next(item for item in overview.escalations(cfg)
               if item["cycle_id"] == stopped["cycle_id"])
    assert row["kind"] == "provider"
    assert row["remediations"] == [
        "retry", "validate_credential", "select_model", "stop"]
    assert "provider failure" not in row["stop_reason"]


def test_the_stored_kind_beats_a_misleading_reason(cfg):
    # The inverse guard: a content stop whose prose happens to contain the old
    # marker must stay a content escalation. Structure wins over the substring.
    store = _store(cfg)
    sha = "b" * 40
    cycle = store.open_or_advance(cfg.science_repo, sha, None)
    store.escalate(cycle["cycle_id"],
                   "a rule mentions provider failure but this is a content stop",
                   kind="audit")

    row = next(item for item in overview.escalations(cfg)
               if item["cycle_id"] == cycle["cycle_id"])
    assert row["kind"] == "audit"
    assert row["remediations"] == ["revise", "stop"]


def test_a_legacy_record_missing_the_kind_falls_back_to_the_reason(cfg):
    # Records written before escalation_kind existed carry only the reason.
    # classify_escalation_kind is the one surviving read of the marker, used
    # only for those. Simulate one by stripping the field the store now writes.
    store = _store(cfg)
    stopped = store.record_build_escalation(
        cfg.science_repo, "c" * 40,
        "generator provider failure in round 1: connection unavailable", 1,
        "history", "Create one accurate review")
    path = Path(cfg.root) / cfg.state_dir / "state.json"
    state = json.loads(path.read_text())
    del state["cycles"][stopped["cycle_id"]]["escalation_kind"]
    path.write_text(json.dumps(state))

    row = next(item for item in overview.escalations(cfg)
               if item["cycle_id"] == stopped["cycle_id"])
    assert row["kind"] == "provider"
    assert classify_escalation_kind("blockers remain") == "audit"


# ------------------------------------------------------ the Console renders it
def test_the_page_renders_provider_remedies_from_the_typed_list():
    # The buttons are driven by the remediations list, not a hardcoded kind
    # branch, and the A40 labels are bound to the typed actions in one place.
    assert "const REMEDIATION=" in PAGE
    assert "function hasRemediation(" in PAGE
    assert "validate_credential:{label:'Review provider connection'" in PAGE
    assert "select_model:{label:'Change model or fallback'" in PAGE
    # Visibility of the two provider affordances is gated on the typed list.
    assert "hidden=!hasRemediation(row,'select_model')" in PAGE
    assert "hidden=!hasRemediation(row,'validate_credential')" in PAGE
    # The A40 contract strings survive.
    for label in ("Retry provider now", "Review provider connection",
                  "Change model or fallback", "Stop this task"):
        assert label in PAGE
