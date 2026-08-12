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
    escalation_remediations, park_escalation_kind, provider_remediations)
from crossaudit.runtime.runs import waiting_kind
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


def test_budget_escalation_axis_offers_billing_not_content_remedies():
    # The cross-slice contract: a budget (usage-guardrail) pause is its own
    # escalation kind. Its remedies are billing, identical to the provider
    # denial's budget set — not the content ("audit") fallback the missing key
    # used to collapse to (revise cannot fix a spending cap).
    assert escalation_remediations("budget") == [
        "open_billing", "continue_later", "stop"]
    assert escalation_remediations("budget") == provider_remediations("budget")
    assert escalation_remediations("budget") != escalation_remediations("audit")


def test_park_escalation_kind_mirrors_the_run_side_waiting_kind():
    # The single source is runs.waiting_kind; the cycle side mirrors it so one
    # park names one kind on both slices. Budget stays budget; every other
    # provider wait — and any missing/legacy value — is the provider default,
    # never the content 'audit' remedies.
    assert park_escalation_kind(waiting_kind("budget")) == "budget"
    assert park_escalation_kind(waiting_kind("routes_exhausted")) == "provider"
    assert park_escalation_kind(waiting_kind("circuit_open")) == "provider"
    assert park_escalation_kind(None) == "provider"
    assert park_escalation_kind("") == "provider"
    assert park_escalation_kind("nonsense") == "provider"


def test_legacy_shim_separates_a_budget_pause_from_a_connection_failure():
    # The one surviving prose read, for records written before escalation_kind.
    # A budget pause carries the "provider failure" marker too (it stops a
    # provider call), so its guardrail marker must win — otherwise a spending
    # cap falls through to the connection remedies.
    budget_reason = ("provider failure left this task waiting for a person: "
                     "Local usage guardrail paused provider calls. Daily cost "
                     "limit reached.")
    assert classify_escalation_kind(budget_reason) == "budget"
    assert classify_escalation_kind(
        "generator provider failure in round 1: connection refused") == "provider"
    assert classify_escalation_kind("blockers remain") == "audit"


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


def test_a_structured_budget_kind_routes_to_billing_remedies(cfg):
    # A budget park's cycle decision object carries kind='budget'. The overview
    # reads the structured field and offers billing remedies with no reason
    # parsing — the run-side denial and this cycle surface now agree.
    store = _store(cfg)
    stopped = store.record_build_escalation(
        cfg.science_repo, "d" * 40,
        "provider failure left this task waiting for a person: Local usage "
        "guardrail paused provider calls. Daily cost limit reached.", 1,
        "history", "Create one accurate review", kind="budget")

    row = next(item for item in overview.escalations(cfg)
               if item["cycle_id"] == stopped["cycle_id"])
    assert row["kind"] == "budget"
    assert row["remediations"] == ["open_billing", "continue_later", "stop"]


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
    # The runtime affordance now also carries the budget billing action, so the
    # select_model gate is one term of that visibility expression.
    assert "hasRemediation(row,'select_model')" in PAGE
    assert "hidden=!hasRemediation(row,'validate_credential')" in PAGE
    # The A40 contract strings survive.
    for label in ("Retry provider now", "Review provider connection",
                  "Change model or fallback", "Stop this task"):
        assert label in PAGE


def test_the_page_routes_a_budget_pause_to_billing_copy_and_labels():
    # The decision modal branches on the structured kind. A budget pause must
    # read as a usage-limit stop with billing remedies, never a connection
    # review, and the typed billing labels must be bound in one place (en + zh).
    assert "const budget=row.kind==='budget';" in PAGE
    assert "open_billing:{label:'Adjust usage limits'" in PAGE
    assert "continue_later:{label:'Continue later'}" in PAGE
    # The runtime affordance is gated on the typed billing action too, not a
    # hardcoded kind branch.
    assert "hasRemediation(row,'open_billing')" in PAGE
    # Budget-specific copy is present with its Chinese translation, so the pause
    # never surfaces the wrong "review the connection" guidance in either locale.
    for label in ("Usage limit reached", "Raise the limit & retry",
                  "Adjust usage limits", "Continue later"):
        assert label in PAGE
    assert '"Adjust usage limits":"调整用量上限"' in PAGE
    assert '"Usage limit reached":"已达用量上限"' in PAGE
