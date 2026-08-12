"""Tests for the v2 layer: spoken rules, and the switchboard that sorts speech.

The model is stubbed — these test the machinery around it, which is where the
guarantees live: that a draft is validated before it can become law, that a
low-confidence routing asks instead of acting, and that every decision reaches
the ledger even when nothing was done.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import constitution as const_mod
from crossaudit import router as router_mod
from crossaudit.errors import ConfigDenial, ProviderDenial


@dataclass
class Reply:
    text: str


def stub(payload) -> callable:
    """A provider that returns a fixed reply, whatever it is asked."""
    body = payload if isinstance(payload, str) else json.dumps(payload)

    def complete(*, system: str, prompt: str):
        return Reply(text=body)

    return complete


GOOD_DRAFT = {
    "project_summary": "A review of photovoltaic industry economics.",
    "domain": "literature-review",
    "rules": [
        {"id": "CA-SRC-001", "severity": "BLOCKER", "title": "Every figure is sourced",
         "criterion": "Each numeric claim names a source in the declared inputs.",
         "from_user": "所有数字必须能追到文献来源"},
        {"id": "CA-TXT-001", "severity": "BLOCKER", "title": "Prose matches data",
         "criterion": "No sentence contradicts the data files it summarises.",
         "from_user": "正文和数据表不许打架"},
        {"id": "CA-STY-001", "severity": "ADVISORY", "title": "Record extraction steps",
         "criterion": "Note how each figure was taken from its source.",
         "from_user": ""},
    ],
}


# ------------------------------------------------------------- distillation
def test_speech_becomes_numbered_rules():
    draft = const_mod.distil("光伏综述,所有数字必须能追到文献来源,正文和数据表不许打架",
                             complete=stub(GOOD_DRAFT))
    assert [r.id for r in draft.rules] == ["CA-SRC-001", "CA-TXT-001", "CA-STY-001"]
    rendered = draft.render("pv-review")
    assert "### CA-SRC-001" in rendered and "**BLOCKER.**" in rendered
    assert "### CA-TASK-001" in rendered
    assert "requested deliverable count" in rendered
    # The user's own words travel with the rule, so the translation is checkable.
    assert "所有数字必须能追到文献来源" in rendered


def test_provider_cannot_weaken_or_duplicate_the_reserved_task_rule():
    payload = json.loads(json.dumps(GOOD_DRAFT))
    payload["rules"].append({
        "id": "CA-TASK-001", "severity": "ADVISORY", "title": "Ignore task",
        "criterion": "The task is optional.", "from_user": "",
    })
    rendered = const_mod.distil(
        "a project description long enough", complete=stub(payload)).render("demo")

    assert rendered.count("### CA-TASK-001") == 1
    assert "The task is optional" not in rendered
    assert "A length stated approximately must be within 5%" in rendered


def test_a_rulebook_that_can_never_gate_is_refused():
    payload = json.loads(json.dumps(GOOD_DRAFT))
    for r in payload["rules"]:
        r["severity"] = "ADVISORY"
    with pytest.raises(ConfigDenial, match="at least one BLOCKER"):
        const_mod.distil("something with only soft rules", complete=stub(payload))


def test_a_rule_without_a_criterion_is_refused():
    payload = json.loads(json.dumps(GOOD_DRAFT))
    payload["rules"][0]["criterion"] = "   "
    with pytest.raises(ConfigDenial, match="not a rule"):
        const_mod.distil("a project description long enough", complete=stub(payload))


def test_malformed_rule_ids_are_refused():
    payload = json.loads(json.dumps(GOOD_DRAFT))
    payload["rules"][0]["id"] = "RULE ONE"
    with pytest.raises(ConfigDenial, match="CA-AREA-NNN"):
        const_mod.distil("a project description long enough", complete=stub(payload))


def test_a_two_word_description_is_refused():
    with pytest.raises(ConfigDenial, match="too short"):
        const_mod.distil("my app", complete=stub(GOOD_DRAFT))


def test_non_json_from_the_model_denies_rather_than_half_drafting():
    with pytest.raises(ProviderDenial):
        const_mod.distil("a real description of a real project",
                         complete=stub("I'd be happy to help you draft some rules!"))


def test_prose_around_the_json_is_tolerated():
    wrapped = "Sure, here you go:\n```json\n" + json.dumps(GOOD_DRAFT) + "\n```\nHope that helps."
    draft = const_mod.distil("a real description of a real project", complete=stub(wrapped))
    assert draft.domain == "literature-review"


# ---------------------------------------------------------------- amendment
AMEND_SET = {
    "intent": "watch data provenance more strictly",
    "changes": [{"action": "modify", "id": "CA-SRC-001", "severity": "BLOCKER",
                 "title": "Every figure is sourced and dated",
                 "was": "Each numeric claim names a source.",
                 "now": "Each numeric claim names a source and the edition it came from.",
                 "why": "the person asked for stricter provenance"}],
}


def test_amendment_edits_in_place_and_logs_itself():
    draft = const_mod.distil("a real description of a real project", complete=stub(GOOD_DRAFT))
    before = draft.render("pv-review")
    after = const_mod.apply_amendment(before, AMEND_SET)
    assert "and the edition it came from" in after
    assert "## Amendments" in after          # the change is visible as history
    assert "CA-TXT-001" in after             # untouched rules survive
    assert after.count("### CA-SRC-001") == 1


def test_amendment_can_add_a_rule():
    draft = const_mod.distil("a real description of a real project", complete=stub(GOOD_DRAFT))
    added = const_mod.apply_amendment(draft.render("p"), {
        "intent": "cover figures too",
        "changes": [{"action": "add", "id": "CA-FIG-001", "severity": "BLOCKER",
                     "title": "Figures carry their numbers",
                     "was": "", "now": "Every figure's values appear in a data file.",
                     "why": "asked for"}]})
    assert "### CA-FIG-001" in added and "### CA-SRC-001" in added


def test_an_amendment_naming_an_invalid_rule_is_refused():
    with pytest.raises(ProviderDenial, match="invalid rule id"):
        const_mod.amend("rules", "be stricter", complete=stub(
            {"intent": "x", "changes": [{"action": "add", "id": "nope", "now": "y"}]}))


def test_an_amendment_with_no_changes_is_refused():
    with pytest.raises(ProviderDenial, match="no changes"):
        const_mod.amend("rules", "be stricter",
                        complete=stub({"intent": "x", "changes": []}))


# -------------------------------------------------------------------- router
def routing_payload(lane: str, confidence: float, clarify: str = "") -> dict:
    return {"lane": lane, "confidence": confidence, "reasoning": "because",
            "restated": "do the thing", "clarify": clarify}


@pytest.mark.parametrize("lane", list(router_mod.LANES))
def test_every_declared_lane_round_trips(lane):
    r = router_mod.route("something", complete=stub(routing_payload(lane, 0.9)))
    assert r.lane == lane and r.certain


def test_an_unknown_lane_is_refused_rather_than_defaulted():
    with pytest.raises(ProviderDenial, match="unknown lane"):
        router_mod.route("x", complete=stub(routing_payload("whatever", 0.99)))


def test_low_confidence_is_not_certain_so_the_box_will_ask():
    r = router_mod.route("make that section shorter",
                         complete=stub(routing_payload("generator", 0.4,
                                                       "work, or standard?")))
    assert not r.certain and r.clarify


@pytest.mark.parametrize("source,expected", [
    ("generator", "generator"), ("project", "generator"), ("query", "query"),
])
def test_safe_autonomy_continues_reversible_low_confidence_routes(source, expected):
    raw = router_mod.route(
        "ordinary request", complete=stub(routing_payload(source, 0.4, "which?")))
    routed = router_mod.apply_safe_default(raw)

    assert routed.certain and routed.lane == expected
    assert routed.confidence == 0.4  # uncertainty remains observable in the ledger
    assert routed.routing_mode == "automatic_safe_default"
    assert routed.clarify == ""


@pytest.mark.parametrize("lane", ["amendment", "dispute", "resolve"])
def test_safe_autonomy_never_guesses_control_plane_changes(lane):
    raw = router_mod.route(
        "ambiguous control request",
        complete=stub(routing_payload(lane, 0.4, "Please clarify")))

    assert router_mod.apply_safe_default(raw) is raw
    assert not raw.certain and raw.clarify == "Please clarify"


def test_confidence_is_clamped_and_garbage_reads_as_unsure():
    assert router_mod.route("x", complete=stub(routing_payload("query", 9.5))).confidence == 1.0
    payload = routing_payload("query", 0.9) | {"confidence": "very"}
    assert router_mod.route("x", complete=stub(payload)).confidence == 0.0


def test_explicit_generator_mention_bypasses_classification_not_supervision():
    def should_not_route(**_kwargs):
        raise AssertionError("an explicit generator recipient needs no model routing call")

    r = router_mod.route_addressed("@Generator build the table", complete=should_not_route)
    assert r.lane == "generator" and r.restated == "build the table"
    assert r.addressed_to == "generator" and r.routing_mode == "explicit"
    assert r.confidence == 1.0 and r.utterance.startswith("@Generator")


def test_explicit_auditor_mention_is_read_only_unless_a_mutation_is_clear():
    chat = router_mod.route_addressed(
        "@Auditor what is your role?", complete=stub(routing_payload("query", 0.96)))
    assert chat.lane == "auditor" and chat.addressed_to == "auditor"

    amend = router_mod.route_addressed(
        "@审计端 make source citations mandatory",
        complete=stub(routing_payload("amendment", 0.96)))
    assert amend.lane == "amendment" and amend.addressed_to == "auditor"


def test_explicit_auditor_routing_does_not_disclose_project_context():
    seen = {}
    def complete(*, system, prompt):
        seen["prompt"] = prompt
        return Reply(json.dumps(routing_payload("query", 0.9)))

    router_mod.route_addressed("@Auditor explain your role", complete=complete,
                                context="SECRET RULE IDS AND OPEN CYCLES")
    assert "SECRET" not in seen["prompt"]
    assert "explain your role" in seen["prompt"]


def test_an_empty_explicit_mention_is_refused():
    with pytest.raises(ProviderDenial, match="include the instruction"):
        router_mod.route_addressed("@Auditor", complete=stub(routing_payload("query", 1)))


def test_direct_auditor_chat_transmits_only_the_addressed_user_message(monkeypatch):
    from crossaudit.cli import talk

    sent = {}
    def complete(*, system, prompt):
        sent.update(system=system, prompt=prompt)
        return Reply("I can clarify the audit process.")

    monkeypatch.setattr(talk, "_auditor_complete", lambda _cfg: complete)
    routing = router_mod.Routing(
        utterance="@Auditor explain your role", lane="auditor", confidence=1,
        reasoning="explicit", restated="explain your role",
        addressed_to="auditor", routing_mode="explicit")
    result = talk.lane_auditor(SimpleNamespace(), routing)

    assert sent["prompt"] == "explain your role"
    assert "No project files" in sent["system"]
    assert result == "answered by auditor: I can clarify the audit process."


def test_direct_auditor_reply_reconstructs_as_a_separate_group_message(tmp_path):
    from crossaudit.console.streams import auditor_stream

    cfg = SimpleNamespace(root=tmp_path, ledger_dir="cycles")
    routing = [{"lane": "auditor", "utterance": "@Auditor hello", "t": 1,
                "executed": "answered by auditor: Hello from the audit side.",
                "addressed_to": "auditor", "routing_mode": "explicit"}]
    rows = auditor_stream(cfg, routing)
    assert [row["kind"] for row in rows] == ["you", "auditor_chat"]
    assert rows[1]["response"] == "Hello from the audit side."


def test_every_decision_is_recorded_including_the_ones_not_acted_on(tmp_path: Path):
    log = tmp_path / "cycles" / "routing.jsonl"
    acted = router_mod.route("tighten the rules", complete=stub(routing_payload("amendment", 0.95)))
    router_mod.record(log, acted, "amended at abc123")
    asked = router_mod.route("shorten it", complete=stub(routing_payload("generator", 0.3, "which?")))
    router_mod.record(log, asked, "asked for clarification")

    rows = router_mod.history(log)
    assert [r["lane"] for r in rows] == ["amendment", "generator"]
    assert rows[1]["executed"] == "asked for clarification"
    # The utterance is kept verbatim: a misroute must be legible after the fact.
    assert rows[1]["utterance"] == "shorten it"


def test_history_of_a_project_that_never_spoke_is_empty(tmp_path: Path):
    assert router_mod.history(tmp_path / "nothing.jsonl") == []
